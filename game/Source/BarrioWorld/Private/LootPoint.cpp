#include "LootPoint.h"

#include "BarrioGameEvents.h"
#include "BarrioLog.h"
#include "BarrioPlayerState.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/Controller.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Net/UnrealNetwork.h"
#include "TimerManager.h"
#include "UObject/ConstructorHelpers.h"

ALootPoint::ALootPoint()
{
	PrimaryActorTick.bCanEverTick = false;
	bReplicates = true;

	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Door"));
	RootComponent = Mesh;
	Mesh->SetRelativeScale3D(FVector(1.2f, 0.2f, 2.2f)); // puerta de 1,2 x 2,2 m
	Mesh->SetCollisionProfileName(UCollisionProfile::BlockAll_ProfileName);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeFinder(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> MaterialFinder(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	if (CubeFinder.Succeeded())
	{
		Mesh->SetStaticMesh(CubeFinder.Object);
	}
	if (MaterialFinder.Succeeded())
	{
		Mesh->SetMaterial(0, MaterialFinder.Object);
	}
}

void ALootPoint::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(ALootPoint, Tier);
	DOREPLIFETIME(ALootPoint, bLooted);
	DOREPLIFETIME(ALootPoint, bAlarmRinging);
	DOREPLIFETIME(ALootPoint, Robber);
}

void ALootPoint::BeginPlay()
{
	Super::BeginPlay();

	if (HasAuthority() && bRandomizeTier)
	{
		const float Roll = FMath::FRand();
		Tier = Roll < 0.6f ? ELootTier::Low : (Roll < 0.9f ? ELootTier::Medium : ELootTier::High);
	}

	DynamicMaterial = Mesh->CreateDynamicMaterialInstance(0);
	UpdateVisuals();
}

float ALootPoint::GetAlarmChance() const
{
	switch (Tier)
	{
	case ELootTier::High:   return 0.9f;
	case ELootTier::Medium: return 0.7f;
	default:                return 0.4f;
	}
}

FIntPoint ALootPoint::GetLootRange() const
{
	switch (Tier)
	{
	case ELootTier::High:   return FIntPoint(400, 1000);
	case ELootTier::Medium: return FIntPoint(150, 400);
	default:                return FIntPoint(50, 150);
	}
}

// ---------------------------------------------------------------------------------------------
// Interacción
// ---------------------------------------------------------------------------------------------

bool ALootPoint::CanInteract_Implementation(const AActor* InstigatorActor) const
{
	// Vecinos y ladrones ven la puerta; solo el ladrón (libre) puede robarla. El vecino recibe la pista.
	const APawn* Pawn = Cast<APawn>(InstigatorActor);
	const ABarrioPlayerState* State = Pawn ? Pawn->GetPlayerState<ABarrioPlayerState>() : nullptr;
	return State && !State->IsPolice() && !State->IsJailed() && !State->IsSurrendered() && !bLooted && Robber == nullptr;
}

FText ALootPoint::GetInteractionText_Implementation(const AActor* InstigatorActor) const
{
	const APawn* Pawn = Cast<APawn>(InstigatorActor);
	const ABarrioPlayerState* State = Pawn ? Pawn->GetPlayerState<ABarrioPlayerState>() : nullptr;
	if (State && State->IsCivilian())
	{
		return INVTEXT("Para robar, ponete el pasamontañas (G)");
	}

	const FText TierText = Tier == ELootTier::High ? INVTEXT("alto") : (Tier == ELootTier::Medium ? INVTEXT("medio") : INVTEXT("bajo"));
	return FText::Format(INVTEXT("Robar casa (botín {0}). Agachado: más lento y con menos riesgo de alarma"), TierText);
}

void ALootPoint::Interact_Implementation(AActor* InstigatorActor)
{
	APawn* Pawn = Cast<APawn>(InstigatorActor);
	ABarrioPlayerState* State = Pawn ? Pawn->GetPlayerState<ABarrioPlayerState>() : nullptr;
	if (!HasAuthority() || !State || !State->IsCriminal() || !CanInteract_Implementation(InstigatorActor))
	{
		return;
	}

	const ACharacter* Character = Cast<ACharacter>(Pawn);
	const bool bStealth = Character && Character->bIsCrouched;
	const float Duration = bStealth ? StealthRobDuration : RobDuration;
	const float Now = GetWorld()->GetTimeSeconds();

	Robber = Pawn;
	RobberyEndTime = Now + Duration;
	State->SetAction(EBarrioActionKind::Robbery, RobberyEndTime, Duration);

	FTimerManager& Timers = GetWorld()->GetTimerManager();
	Timers.SetTimer(RobberyTimer, this, &ALootPoint::CheckRobbery, 0.2f, true);

	const float AlarmChance = GetAlarmChance() * (bStealth ? 0.5f : 1.f);
	if (!bAlarmRinging && FMath::FRand() < AlarmChance)
	{
		AlarmSuspect = Pawn->GetController();
		Timers.SetTimer(AlarmTimer, this, &ALootPoint::TriggerAlarm, AlarmDelay, false);
	}

	UE_LOG(LogBarrio, Log, TEXT("%s empezó a robar %s (%s)."), *GetNameSafe(Pawn), *GetName(), bStealth ? TEXT("sigilo") : TEXT("normal"));
}

// ---------------------------------------------------------------------------------------------
// Robo (solo servidor)
// ---------------------------------------------------------------------------------------------

void ALootPoint::CheckRobbery()
{
	if (!IsValid(Robber) || !Robber->GetController())
	{
		CancelRobbery(); // murió, lo arrestaron o se desconectó
		return;
	}

	const ABarrioPlayerState* State = Robber->GetPlayerState<ABarrioPlayerState>();
	const FBox Bounds = GetComponentsBoundingBox();
	const float DistanceSquared = Bounds.IsValid
		? Bounds.ComputeSquaredDistanceToPoint(Robber->GetActorLocation())
		: FVector::DistSquared(GetActorLocation(), Robber->GetActorLocation());

	if (!State || !State->IsCriminal() || State->IsJailed() || State->IsSurrendered() || DistanceSquared > FMath::Square(MaxRobDistance))
	{
		CancelRobbery();
		return;
	}

	if (GetWorld()->GetTimeSeconds() >= RobberyEndTime)
	{
		CompleteRobbery();
	}
}

void ALootPoint::CompleteRobbery()
{
	GetWorld()->GetTimerManager().ClearTimer(RobberyTimer);

	ABarrioPlayerState* State = Robber ? Robber->GetPlayerState<ABarrioPlayerState>() : nullptr;
	if (State)
	{
		const FIntPoint Range = GetLootRange();
		// La notoriedad (racha de robos sin salir del barrio) hace que el botín valga más.
		const int32 Value = FMath::RoundToInt(FMath::RandRange(Range.X, Range.Y) * State->GetLootMultiplier());
		State->AddCarriedLoot(Value);
		State->AddNotoriety(1);
		State->ClearAction();
		UE_LOG(LogBarrio, Log, TEXT("%s robó $%d de %s."), *GetNameSafe(Robber), Value, *GetName());
	}

	Robber = nullptr;
	bLooted = true;
	UpdateVisuals();
	GetWorld()->GetTimerManager().SetTimer(RestockTimer, this, &ALootPoint::Restock, RestockTime, false);
}

void ALootPoint::CancelRobbery()
{
	GetWorld()->GetTimerManager().ClearTimer(RobberyTimer);

	if (IsValid(Robber))
	{
		if (ABarrioPlayerState* State = Robber->GetPlayerState<ABarrioPlayerState>())
		{
			State->ClearAction();
		}
	}
	Robber = nullptr;
	// La alarma, si se disparó, sigue: la puerta ya fue forzada.
}

void ALootPoint::TriggerAlarm()
{
	bAlarmRinging = true;
	UpdateVisuals();

	if (UBarrioGameEvents* Events = UBarrioGameEvents::Get(this))
	{
		Events->OnAlarm.Broadcast(GetActorLocation(), AlarmSuspect.Get());
	}
	GetWorld()->GetTimerManager().SetTimer(AlarmStopTimer, this, &ALootPoint::StopAlarm, AlarmDuration, false);
}

void ALootPoint::StopAlarm()
{
	bAlarmRinging = false;
	AlarmSuspect.Reset();
	UpdateVisuals();
}

void ALootPoint::Restock()
{
	bLooted = false;
	UpdateVisuals();
}

// ---------------------------------------------------------------------------------------------
// Visual
// ---------------------------------------------------------------------------------------------

void ALootPoint::OnRep_State()
{
	UpdateVisuals();
}

void ALootPoint::UpdateVisuals()
{
	if (!DynamicMaterial)
	{
		return;
	}

	FLinearColor Color(0.15f, 0.35f, 0.8f); // disponible
	if (bAlarmRinging)
	{
		Color = FLinearColor(0.9f, 0.05f, 0.05f);
	}
	else if (bLooted)
	{
		Color = FLinearColor(0.25f, 0.25f, 0.25f);
	}
	DynamicMaterial->SetVectorParameterValue(TEXT("Color"), Color);
}
