#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Interactable.h"
#include "BarrioStations.generated.h"

class UStaticMeshComponent;

/** Bloque gris de color fijo, base de los puntos fijos del mapa. */
UCLASS(Abstract)
class BARRIOWORLD_API ABarrioColoredBlock : public AActor
{
	GENERATED_BODY()

public:
	ABarrioColoredBlock();

protected:
	virtual void BeginPlay() override;

	UPROPERTY(VisibleAnywhere, Category = "Barrio")
	TObjectPtr<UStaticMeshComponent> Mesh;

	UPROPERTY(EditAnywhere, Category = "Barrio")
	FLinearColor Color = FLinearColor::White;
};

/**
 * Reducidor: convierte el botín que el jugador lleva encima en dinero.
 * No compra a quien está buscado: primero hay que perder a la policía.
 */
UCLASS()
class BARRIOWORLD_API AFenceStation : public ABarrioColoredBlock, public IInteractable
{
	GENERATED_BODY()

public:
	AFenceStation();

	virtual FText GetInteractionText_Implementation(const AActor* InstigatorActor) const override;
	virtual bool CanInteract_Implementation(const AActor* InstigatorActor) const override;
	virtual void Interact_Implementation(AActor* InstigatorActor) override;
};

/** Mostrador de la comisaría: unirse a la policía o dejarla. El GameMode controla el cupo. */
UCLASS()
class BARRIOWORLD_API APoliceStation : public ABarrioColoredBlock, public IInteractable
{
	GENERATED_BODY()

public:
	APoliceStation();

	virtual FText GetInteractionText_Implementation(const AActor* InstigatorActor) const override;
	virtual bool CanInteract_Implementation(const AActor* InstigatorActor) const override;
	virtual void Interact_Implementation(AActor* InstigatorActor) override;
};

/**
 * Celda de la cárcel: piso, cuatro paredes y techo, sin salida.
 * Los presos aparecen en el centro, a la altura del actor. Ubicarla fuera del barrio.
 */
UCLASS()
class BARRIOWORLD_API AJailCell : public AActor
{
	GENERATED_BODY()

public:
	AJailCell();
};
