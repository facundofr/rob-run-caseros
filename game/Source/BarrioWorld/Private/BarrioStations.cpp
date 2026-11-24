#include "BarrioStations.h"

#include "BarrioGameEvents.h"
#include "BarrioLog.h"
#include "BarrioPlayerState.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Controller.h"
#include "GameFramework/Pawn.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	ABarrioPlayerState* GetState(const AActor* Actor)
	{
		const APawn* Pawn = Cast<APawn>(Actor);
		return Pawn ? Pawn->GetPlayerState<ABarrioPlayerState>() : nullptr;
	}

	UStaticMesh* FindCube()
	{
		static ConstructorHelpers::FObjectFinder<UStaticMesh> Finder(TEXT("/Engine/BasicShapes/Cube.Cube"));
		return Finder.Object;
	}

	UMaterialInterface* FindBasicMaterial()
	{
		static ConstructorHelpers::FObjectFinder<UMaterialInterface> Finder(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
		return Finder.Object;
	}
}

// ---------------------------------------------------------------------------------------------
// Bloque de color
// ---------------------------------------------------------------------------------------------

ABarrioColoredBlock::ABarrioColoredBlock()
{
	PrimaryActorTick.bCanEverTick = false;
	bReplicates = true; // para que los clientes puedan pedir interactuar con este actor

	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	RootComponent = Mesh;
	Mesh->SetStaticMesh(FindCube());
	Mesh->SetMaterial(0, FindBasicMaterial());
	Mesh->SetCollisionProfileName(UCollisionProfile::BlockAll_ProfileName);
	Mesh->SetRelativeScale3D(FVector(1.5f, 0.8f, 1.1f)); // mostrador de 1,5 x 0,8 x 1,1 m
}

void ABarrioColoredBlock::BeginPlay()
{
	Super::BeginPlay();
	if (UMaterialInstanceDynamic* Material = Mesh->CreateDynamicMaterialInstance(0))
	{
		Material->SetVectorParameterValue(TEXT("Color"), Color);
	}
}

// ---------------------------------------------------------------------------------------------
// Reducidor
// ---------------------------------------------------------------------------------------------

AFenceStation::AFenceStation()
{
	Color = FLinearColor(0.1f, 0.6f, 0.2f);
}

bool AFenceStation::CanInteract_Implementation(const AActor* InstigatorActor) const
{
	const ABarrioPlayerState* State = GetState(InstigatorActor);
	return State && !State->IsPolice() && !State->IsJailed() && State->GetCarriedLoot() > 0;
}

FText AFenceStation::GetInteractionText_Implementation(const AActor* InstigatorActor) const
{
	const ABarrioPlayerState* State = GetState(InstigatorActor);
	if (State && State->IsWanted())
	{
		return INVTEXT("Estás buscado: el reducidor no te compra");
	}
	const int32 Loot = State ? State->GetCarriedLoot() : 0;
	return FText::Format(INVTEXT("Vender botín (${0})"), FText::AsNumber(Loot));
}

void AFenceStation::Interact_Implementation(AActor* InstigatorActor)
{
	const APawn* Pawn = Cast<APawn>(InstigatorActor);
	const ABarrioPlayerState* State = GetState(InstigatorActor);
	UBarrioGameEvents* Events = UBarrioGameEvents::Get(this);
	if (!HasAuthority() || !Pawn || !State || !Events || State->IsWanted() || State->GetCarriedLoot() <= 0)
	{
		return;
	}

	// La venta la resuelve el GameMode: con backend, el dinero se guarda en la cuenta.
	Events->OnSellLootRequested.Broadcast(Pawn->GetController());
}

// ---------------------------------------------------------------------------------------------
// Comisaría
// ---------------------------------------------------------------------------------------------

APoliceStation::APoliceStation()
{
	Color = FLinearColor(0.1f, 0.2f, 0.8f);
}

bool APoliceStation::CanInteract_Implementation(const AActor* InstigatorActor) const
{
	const ABarrioPlayerState* State = GetState(InstigatorActor);
	return State && !State->IsJailed();
}

FText APoliceStation::GetInteractionText_Implementation(const AActor* InstigatorActor) const
{
	const ABarrioPlayerState* State = GetState(InstigatorActor);
	return (State && State->IsPolice()) ? INVTEXT("Dejar la policía") : INVTEXT("Unirse a la policía");
}

void APoliceStation::Interact_Implementation(AActor* InstigatorActor)
{
	const APawn* Pawn = Cast<APawn>(InstigatorActor);
	const ABarrioPlayerState* State = GetState(InstigatorActor);
	UBarrioGameEvents* Events = UBarrioGameEvents::Get(this);
	if (HasAuthority() && Pawn && State && Events)
	{
		const EBarrioRole Requested = State->IsPolice() ? EBarrioRole::Civilian : EBarrioRole::Police;
		Events->OnRoleRequested.Broadcast(Pawn->GetController(), Requested);
	}
}

// ---------------------------------------------------------------------------------------------
// Celda
// ---------------------------------------------------------------------------------------------

AJailCell::AJailCell()
{
	PrimaryActorTick.bCanEverTick = false;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

	// Interior de 6 x 6 x 3,2 m. El piso queda 1 m por debajo del actor para que el
	// personaje aparezca parado sobre él.
	constexpr float Inner = 600.f;
	constexpr float Height = 320.f;
	constexpr float Thickness = 30.f;
	constexpr float FloorTop = -100.f;

	struct FPiece { const TCHAR* Name; FVector Center; FVector Size; };
	const FPiece Pieces[] =
	{
		{ TEXT("Floor"), FVector(0.f, 0.f, FloorTop - Thickness * 0.5f), FVector(Inner + 2 * Thickness, Inner + 2 * Thickness, Thickness) },
		{ TEXT("Roof"),  FVector(0.f, 0.f, FloorTop + Height + Thickness * 0.5f), FVector(Inner + 2 * Thickness, Inner + 2 * Thickness, Thickness) },
		{ TEXT("WallN"), FVector(0.f,  (Inner + Thickness) * 0.5f, FloorTop + Height * 0.5f), FVector(Inner + 2 * Thickness, Thickness, Height) },
		{ TEXT("WallS"), FVector(0.f, -(Inner + Thickness) * 0.5f, FloorTop + Height * 0.5f), FVector(Inner + 2 * Thickness, Thickness, Height) },
		{ TEXT("WallE"), FVector( (Inner + Thickness) * 0.5f, 0.f, FloorTop + Height * 0.5f), FVector(Thickness, Inner, Height) },
		{ TEXT("WallW"), FVector(-(Inner + Thickness) * 0.5f, 0.f, FloorTop + Height * 0.5f), FVector(Thickness, Inner, Height) },
	};

	UStaticMesh* Cube = FindCube();
	UMaterialInterface* Material = FindBasicMaterial();
	for (const FPiece& Piece : Pieces)
	{
		UStaticMeshComponent* Part = CreateDefaultSubobject<UStaticMeshComponent>(Piece.Name);
		Part->SetupAttachment(RootComponent);
		Part->SetStaticMesh(Cube);
		Part->SetMaterial(0, Material);
		Part->SetRelativeLocation(Piece.Center);
		Part->SetRelativeScale3D(Piece.Size / 100.f);
		Part->SetCollisionProfileName(UCollisionProfile::BlockAll_ProfileName);
	}
}
