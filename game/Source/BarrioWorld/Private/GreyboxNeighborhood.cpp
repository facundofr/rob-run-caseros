#include "GreyboxNeighborhood.h"

#include "BarrioLog.h"
#include "Engine/World.h"
#include "LootPoint.h"

#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Math/RandomStream.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// El cubo básico del motor mide 100 cm de lado, con el pivote en el centro.
	constexpr float CubeSize = 100.f;
	constexpr float GroundThickness = 20.f;
	constexpr float CurbHeight = 15.f;
	constexpr float WallHeight = 250.f;
	constexpr float WallThickness = 20.f;
	constexpr float DoorOffset = 12.f;
	constexpr float DoorHalfHeight = 110.f;
}

AGreyboxNeighborhood::AGreyboxNeighborhood()
{
	PrimaryActorTick.bCanEverTick = false;
	bReplicates = false;

	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeFinder(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> MaterialFinder(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	CubeMesh = CubeFinder.Object;
	BaseMaterial = MaterialFinder.Object;

	auto MakeInstances = [this](const TCHAR* Name)
	{
		UInstancedStaticMeshComponent* Instances = CreateDefaultSubobject<UInstancedStaticMeshComponent>(Name);
		Instances->SetupAttachment(RootComponent);
		Instances->SetStaticMesh(CubeMesh);
		Instances->SetCollisionProfileName(UCollisionProfile::BlockAll_ProfileName);
		Instances->SetMobility(EComponentMobility::Static);
		return Instances;
	};

	GroundInstances = MakeInstances(TEXT("Ground"));
	SidewalkInstances = MakeInstances(TEXT("Sidewalks"));
	HouseInstances = MakeInstances(TEXT("Houses"));
}

void AGreyboxNeighborhood::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	TArray<FTransform> HouseFronts;
	Rebuild(true, HouseFronts);
}

void AGreyboxNeighborhood::AddBox(UInstancedStaticMeshComponent* Instances, const FVector& Center, const FVector& Size)
{
	Instances->AddInstance(FTransform(FRotator::ZeroRotator, Center, Size / CubeSize));
}

void AGreyboxNeighborhood::ApplyColor(UInstancedStaticMeshComponent* Instances, const FLinearColor& Color) const
{
	if (!BaseMaterial)
	{
		return;
	}
	if (UMaterialInstanceDynamic* Material = Instances->CreateDynamicMaterialInstance(0, BaseMaterial))
	{
		Material->SetVectorParameterValue(TEXT("Color"), Color);
	}
}

void AGreyboxNeighborhood::BeginPlay()
{
	Super::BeginPlay();

	if (!HasAuthority() || !bSpawnLootPoints)
	{
		return;
	}

	UClass* SpawnClass = LootPointClass ? LootPointClass.Get() : ALootPoint::StaticClass();
	TArray<FTransform> HouseFronts;
	Rebuild(false, HouseFronts);

	FActorSpawnParameters SpawnParams;
	SpawnParams.Owner = this;
	SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	for (const FTransform& Front : HouseFronts)
	{
		GetWorld()->SpawnActor<AActor>(SpawnClass, Front * GetActorTransform(), SpawnParams);
	}
	UE_LOG(LogBarrio, Log, TEXT("Barrio gris: %d puntos de robo creados."), HouseFronts.Num());
}

void AGreyboxNeighborhood::Rebuild(bool bAddInstances, TArray<FTransform>& OutHouseFronts)
{
	OutHouseFronts.Reset();

	if (bAddInstances)
	{
		GroundInstances->ClearInstances();
		SidewalkInstances->ClearInstances();
		HouseInstances->ClearInstances();

		ApplyColor(GroundInstances, FLinearColor(0.08f, 0.08f, 0.09f));   // asfalto
		ApplyColor(SidewalkInstances, FLinearColor(0.45f, 0.45f, 0.43f)); // vereda
		ApplyColor(HouseInstances, FLinearColor(0.70f, 0.66f, 0.60f));    // construcciones
	}

	auto Box = [bAddInstances](UInstancedStaticMeshComponent* Instances, const FVector& Center, const FVector& Size)
	{
		if (bAddInstances)
		{
			AddBox(Instances, Center, Size);
		}
	};

	const float MinDepth = FMath::Min(MinHouseDepth, MaxHouseDepth);
	const float MaxDepth = FMath::Max(MinHouseDepth, MaxHouseDepth);
	const float MinHeight = FMath::Min(MinHouseHeight, MaxHouseHeight);
	const float MaxHeight = FMath::Max(MinHouseHeight, MaxHouseHeight);

	FRandomStream Random(Seed);

	const float TotalX = BlocksX * BlockSize + (BlocksX + 1) * StreetWidth;
	const float TotalY = BlocksY * BlockSize + (BlocksY + 1) * StreetWidth;

	// Calzada: una losa que cubre el barrio y la franja de "Afuera" a su alrededor, con la cara superior en Z = 0.
	Box(GroundInstances, FVector(TotalX * 0.5f, TotalY * 0.5f, -GroundThickness * 0.5f),
		FVector(TotalX + 2.f * OutsideMargin, TotalY + 2.f * OutsideMargin, GroundThickness));

	const float BuildableLength = BlockSize - 2.f * SidewalkWidth;
	const float LotWidth = BuildableLength / LotsPerSide;

	for (int32 BlockX = 0; BlockX < BlocksX; ++BlockX)
	{
		for (int32 BlockY = 0; BlockY < BlocksY; ++BlockY)
		{
			const float X0 = StreetWidth + BlockX * (BlockSize + StreetWidth);
			const float Y0 = StreetWidth + BlockY * (BlockSize + StreetWidth);

			// Manzana elevada como vereda (cordón de 15 cm).
			Box(SidewalkInstances,
				FVector(X0 + BlockSize * 0.5f, Y0 + BlockSize * 0.5f, CurbHeight * 0.5f),
				FVector(BlockSize, BlockSize, CurbHeight));

			// Casas en los dos frentes que dan a calles en Y.
			for (int32 Side = 0; Side < 2; ++Side)
			{
				for (int32 Lot = 0; Lot < LotsPerSide; ++Lot)
				{
					const float Width = FMath::Max(LotWidth - Random.FRandRange(50.f, 200.f), 200.f);
					const float Depth = Random.FRandRange(MinDepth, MaxDepth);
					const float Height = Random.FRandRange(MinHeight, MaxHeight);
					const float Setback = Random.FRandRange(0.f, MaxFrontSetback);

					const float CenterX = X0 + SidewalkWidth + LotWidth * (Lot + 0.5f);
					const float CenterY = (Side == 0)
						? Y0 + SidewalkWidth + Setback + Depth * 0.5f
						: Y0 + BlockSize - SidewalkWidth - Setback - Depth * 0.5f;

					Box(HouseInstances, FVector(CenterX, CenterY, CurbHeight + Height * 0.5f), FVector(Width, Depth, Height));

					// Puerta de entrada en el centro del frente, apenas hacia afuera de la fachada.
					const float FacadeY = (Side == 0) ? CenterY - Depth * 0.5f - DoorOffset : CenterY + Depth * 0.5f + DoorOffset;
					OutHouseFronts.Add(FTransform(FRotator::ZeroRotator, FVector(CenterX, FacadeY, CurbHeight + DoorHalfHeight)));
				}
			}

			// Medianeras en los frentes en X, para cerrar los fondos de los lotes.
			for (int32 Side = 0; Side < 2; ++Side)
			{
				const float WallX = (Side == 0)
					? X0 + SidewalkWidth + WallThickness * 0.5f
					: X0 + BlockSize - SidewalkWidth - WallThickness * 0.5f;

				Box(HouseInstances,
					FVector(WallX, Y0 + BlockSize * 0.5f, CurbHeight + WallHeight * 0.5f),
					FVector(WallThickness, BuildableLength, WallHeight));
			}
		}
	}
}
