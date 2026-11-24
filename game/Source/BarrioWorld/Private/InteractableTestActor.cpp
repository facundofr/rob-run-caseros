#include "InteractableTestActor.h"

#include "BarrioLog.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Net/UnrealNetwork.h"
#include "UObject/ConstructorHelpers.h"

AInteractableTestActor::AInteractableTestActor()
{
	PrimaryActorTick.bCanEverTick = false;
	bReplicates = true;

	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	RootComponent = Mesh;
	Mesh->SetRelativeScale3D(FVector(0.5f, 0.5f, 1.2f));
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

void AInteractableTestActor::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(AInteractableTestActor, bIsOn);
}

void AInteractableTestActor::BeginPlay()
{
	Super::BeginPlay();
	DynamicMaterial = Mesh->CreateDynamicMaterialInstance(0);
	UpdateVisuals();
}

FText AInteractableTestActor::GetInteractionText_Implementation(const AActor* InstigatorActor) const
{
	return bIsOn ? INVTEXT("Apagar interruptor de prueba") : INVTEXT("Encender interruptor de prueba");
}

void AInteractableTestActor::Interact_Implementation(AActor* InstigatorActor)
{
	if (!HasAuthority())
	{
		return; // Solo el servidor cambia el estado.
	}

	bIsOn = !bIsOn;
	UpdateVisuals(); // En el servidor OnRep no se llama solo.
	UE_LOG(LogBarrio, Log, TEXT("%s %s el interruptor %s."), *GetNameSafe(InstigatorActor), bIsOn ? TEXT("encendió") : TEXT("apagó"), *GetName());
}

void AInteractableTestActor::OnRep_IsOn()
{
	UpdateVisuals();
}

void AInteractableTestActor::UpdateVisuals()
{
	if (DynamicMaterial)
	{
		DynamicMaterial->SetVectorParameterValue(TEXT("Color"), bIsOn ? OnColor : OffColor);
	}
}
