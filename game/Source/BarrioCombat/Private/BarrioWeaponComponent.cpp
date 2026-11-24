#include "BarrioWeaponComponent.h"

#include "BarrioHealthComponent.h"
#include "BarrioLog.h"
#include "BarrioPlayerState.h"
#include "CollisionQueryParams.h"
#include "DrawDebugHelpers.h"
#include "Engine/World.h"
#include "GameFramework/Controller.h"
#include "GameFramework/DamageType.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Net/UnrealNetwork.h"
#include "TimerManager.h"

namespace
{
	FCollisionObjectQueryParams ShotObjectTypes()
	{
		FCollisionObjectQueryParams Types;
		Types.AddObjectTypesToQuery(ECC_WorldStatic);
		Types.AddObjectTypesToQuery(ECC_WorldDynamic);
		Types.AddObjectTypesToQuery(ECC_Pawn);
		Types.AddObjectTypesToQuery(ECC_PhysicsBody);
		return Types;
	}
}

UBarrioWeaponComponent::UBarrioWeaponComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
	SetIsReplicatedByDefault(true);
}

void UBarrioWeaponComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME_CONDITION(UBarrioWeaponComponent, Ammo, COND_OwnerOnly);
	DOREPLIFETIME_CONDITION(UBarrioWeaponComponent, bReloading, COND_OwnerOnly);
}

void UBarrioWeaponComponent::BeginPlay()
{
	Super::BeginPlay();
	if (GetOwner() && GetOwner()->HasAuthority())
	{
		Ammo = MagazineSize;
	}
}

bool UBarrioWeaponComponent::IsOwnerDead() const
{
	const UBarrioHealthComponent* Health = GetOwner() ? GetOwner()->FindComponentByClass<UBarrioHealthComponent>() : nullptr;
	return Health && Health->IsDead();
}

bool UBarrioWeaponComponent::CanOwnerUseWeapon() const
{
	// Los vecinos no usan armas y un ladrón rendido tampoco (documento de diseño, secciones 3 y 5).
	const APawn* Pawn = Cast<APawn>(GetOwner());
	const ABarrioPlayerState* State = Pawn ? Pawn->GetPlayerState<ABarrioPlayerState>() : nullptr;
	return State && !State->IsCivilian() && !State->IsSurrendered() && !State->IsJailed() && !IsOwnerDead();
}

void UBarrioWeaponComponent::RequestFire()
{
	const APawn* Pawn = Cast<APawn>(GetOwner());
	AController* Controller = Pawn ? Pawn->GetController() : nullptr;
	if (!Controller || bReloading || !CanOwnerUseWeapon())
	{
		return;
	}

	if (Ammo <= 0)
	{
		RequestReload();
		return;
	}

	FVector ViewLocation;
	FRotator ViewRotation;
	Controller->GetPlayerViewPoint(ViewLocation, ViewRotation);
	ServerFire(ViewLocation, ViewRotation.Vector());
}

void UBarrioWeaponComponent::RequestReload()
{
	if (!bReloading && Ammo < MagazineSize && !IsOwnerDead())
	{
		ServerReload();
	}
}

bool UBarrioWeaponComponent::ServerFire_Validate(FVector_NetQuantize ViewStart, FVector_NetQuantizeNormal ViewDirection)
{
	return true; // Los disparos inválidos se descartan sin desconectar al jugador.
}

void UBarrioWeaponComponent::ServerFire_Implementation(FVector_NetQuantize ViewStart, FVector_NetQuantizeNormal ViewDirection)
{
	APawn* Pawn = Cast<APawn>(GetOwner());
	UWorld* World = GetWorld();
	if (!Pawn || !World || bReloading || Ammo <= 0 || !CanOwnerUseWeapon())
	{
		return;
	}

	const float Now = World->GetTimeSeconds();
	if (Now - LastFireTime < FireInterval * 0.9f) // pequeño margen por variación de red
	{
		return;
	}

	// El punto de vista tiene que estar cerca del personaje y apuntar hacia donde mira.
	const FVector Direction = FVector(ViewDirection).GetSafeNormal();
	const FVector AimDirection = Pawn->GetControlRotation().Vector();
	if (FVector::Dist(ViewStart, Pawn->GetActorLocation()) > MaxViewDistance
		|| FVector::DotProduct(Direction, AimDirection) < 0.9f)
	{
		UE_LOG(LogBarrio, Warning, TEXT("Disparo rechazado de %s: punto de vista o dirección inválidos."), *GetNameSafe(Pawn));
		return;
	}

	LastFireTime = Now;
	--Ammo;

	FCollisionQueryParams Params(SCENE_QUERY_STAT(BarrioShot), true, Pawn);

	// 1) Desde la cámara: a qué apunta la mira.
	const FVector ViewEnd = FVector(ViewStart) + Direction * Range;
	FHitResult ViewHit;
	const bool bViewHit = World->LineTraceSingleByObjectType(ViewHit, ViewStart, ViewEnd, ShotObjectTypes(), Params);
	const FVector AimPoint = bViewHit ? ViewHit.ImpactPoint : ViewEnd;

	// 2) Desde el personaje hasta ese punto: evita disparar a través de paredes que están entre
	//    la cámara y el personaje.
	const FVector Muzzle = Pawn->GetActorLocation() + FVector(0.f, 0.f, 50.f);
	const FVector ShotDirection = (AimPoint - Muzzle).GetSafeNormal();
	FHitResult Hit;
	const bool bHit = World->LineTraceSingleByObjectType(Hit, Muzzle, AimPoint + ShotDirection * 10.f, ShotObjectTypes(), Params);
	const FVector ImpactPoint = bHit ? Hit.ImpactPoint : AimPoint;

	if (bHit && Hit.GetActor())
	{
		UGameplayStatics::ApplyPointDamage(Hit.GetActor(), Damage, ShotDirection, Hit, Pawn->GetController(), Pawn, UDamageType::StaticClass());
	}

	MulticastShotEffect(Muzzle, ImpactPoint);
}

bool UBarrioWeaponComponent::ServerReload_Validate()
{
	return true;
}

void UBarrioWeaponComponent::ServerReload_Implementation()
{
	if (bReloading || Ammo >= MagazineSize || IsOwnerDead())
	{
		return;
	}

	bReloading = true;
	GetWorld()->GetTimerManager().SetTimer(ReloadTimer, this, &UBarrioWeaponComponent::FinishReload, ReloadTime, false);
}

void UBarrioWeaponComponent::FinishReload()
{
	Ammo = MagazineSize;
	bReloading = false;
}

void UBarrioWeaponComponent::MulticastShotEffect_Implementation(FVector_NetQuantize Start, FVector_NetQuantize End)
{
	// Trazo provisorio para el mapa gris: se reemplaza por efectos y sonido reales.
	// Las líneas de debug no existen en builds Shipping.
#if ENABLE_DRAW_DEBUG
	if (GetNetMode() != NM_DedicatedServer)
	{
		DrawDebugLine(GetWorld(), Start, End, FColor::Yellow, false, 0.08f, 0, 1.5f);
	}
#endif
}
