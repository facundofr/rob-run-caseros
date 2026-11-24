#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GreyboxNeighborhood.generated.h"

class UInstancedStaticMeshComponent;
class UMaterialInterface;
class UStaticMesh;

/**
 * Barrio en gris (blockout) generado con cubos: calles, veredas, casas bajas y medianeras.
 *
 * Sirve para probar escala, recorridos y tiempos de llegada de la policía antes de tener arte.
 * Se arrastra al nivel y se ajusta desde el panel Details; cada cambio regenera el barrio.
 * Las medidas siguen una manzana típica del conurbano: unos 100 m de lado y lotes de unos 9 m de frente.
 *
 * No se replica: es geometría fija del nivel, presente igual en el servidor y en cada cliente.
 */
UCLASS()
class BARRIOWORLD_API AGreyboxNeighborhood : public AActor
{
	GENERATED_BODY()

public:
	AGreyboxNeighborhood();

	virtual void OnConstruction(const FTransform& Transform) override;

	/** Manzanas en X y en Y. 2 x 2 = 4 manzanas. */
	UPROPERTY(EditAnywhere, Category = "Greybox|Layout", meta = (ClampMin = "1", ClampMax = "10"))
	int32 BlocksX = 2;

	UPROPERTY(EditAnywhere, Category = "Greybox|Layout", meta = (ClampMin = "1", ClampMax = "10"))
	int32 BlocksY = 2;

	/** Lado de la manzana, en cm. */
	UPROPERTY(EditAnywhere, Category = "Greybox|Layout", meta = (ClampMin = "3000"))
	float BlockSize = 10000.f;

	/** Ancho de calzada, en cm. */
	UPROPERTY(EditAnywhere, Category = "Greybox|Layout", meta = (ClampMin = "500"))
	float StreetWidth = 1000.f;

	UPROPERTY(EditAnywhere, Category = "Greybox|Layout", meta = (ClampMin = "100"))
	float SidewalkWidth = 300.f;

	/** Franja de terreno alrededor del barrio ("Afuera": reducidor, sin policía), en cm. */
	UPROPERTY(EditAnywhere, Category = "Greybox|Layout", meta = (ClampMin = "0"))
	float OutsideMargin = 4000.f;

	/** Lotes por cada frente de manzana. */
	UPROPERTY(EditAnywhere, Category = "Greybox|Houses", meta = (ClampMin = "1", ClampMax = "30"))
	int32 LotsPerSide = 10;

	UPROPERTY(EditAnywhere, Category = "Greybox|Houses", meta = (ClampMin = "300"))
	float MinHouseDepth = 1000.f;

	UPROPERTY(EditAnywhere, Category = "Greybox|Houses", meta = (ClampMin = "300"))
	float MaxHouseDepth = 2200.f;

	/** Alturas entre una planta (~3,2 m) y dos plantas (~6,5 m). */
	UPROPERTY(EditAnywhere, Category = "Greybox|Houses", meta = (ClampMin = "200"))
	float MinHouseHeight = 320.f;

	UPROPERTY(EditAnywhere, Category = "Greybox|Houses", meta = (ClampMin = "200"))
	float MaxHouseHeight = 650.f;

	/** Retiro máximo desde la línea de vereda (jardín delantero), en cm. */
	UPROPERTY(EditAnywhere, Category = "Greybox|Houses", meta = (ClampMin = "0"))
	float MaxFrontSetback = 400.f;

	/** Cambiar la semilla genera otra variación de casas con el mismo trazado. */
	UPROPERTY(EditAnywhere, Category = "Greybox|Houses")
	int32 Seed = 1234;

protected:
	UPROPERTY(VisibleAnywhere, Category = "Greybox")
	TObjectPtr<UInstancedStaticMeshComponent> GroundInstances;

	UPROPERTY(VisibleAnywhere, Category = "Greybox")
	TObjectPtr<UInstancedStaticMeshComponent> SidewalkInstances;

	UPROPERTY(VisibleAnywhere, Category = "Greybox")
	TObjectPtr<UInstancedStaticMeshComponent> HouseInstances;

	/** Si está activo, el servidor crea un punto de robo (puerta) en el frente de cada casa al empezar. */
	UPROPERTY(EditAnywhere, Category = "Greybox|Gameplay")
	bool bSpawnLootPoints = true;

	/** Clase del punto de robo. Se puede reemplazar por un Blueprint hijo de ALootPoint. */
	UPROPERTY(EditAnywhere, Category = "Greybox|Gameplay", meta = (EditCondition = "bSpawnLootPoints"))
	TSubclassOf<AActor> LootPointClass;

protected:
	virtual void BeginPlay() override;

private:
	/**
	 * Calcula el barrio. Con bAddInstances agrega los cubos; siempre devuelve el frente de cada casa.
	 * Es determinístico: con la misma semilla y medidas da siempre el mismo resultado.
	 */
	void Rebuild(bool bAddInstances, TArray<FTransform>& OutHouseFronts);
	void ApplyColor(UInstancedStaticMeshComponent* Instances, const FLinearColor& Color) const;
	static void AddBox(UInstancedStaticMeshComponent* Instances, const FVector& Center, const FVector& Size);

	UPROPERTY()
	TObjectPtr<UStaticMesh> CubeMesh;

	UPROPERTY()
	TObjectPtr<UMaterialInterface> BaseMaterial;
};
