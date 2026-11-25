#pragma once

#include "CoreMinimal.h"
#include "Engine/HitResult.h"
#include "GameFramework/Actor.h"
#include "Interactable.h"
#include "BarrioStations.generated.h"

class UStaticMeshComponent;
class UBoxComponent;
class UPrimitiveComponent;

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

/** Caja invisible en el juego (visible en el editor y en el mapa gris) que marca una zona. */
UCLASS(Abstract)
class BARRIOWORLD_API ABarrioZone : public AActor
{
	GENERATED_BODY()

public:
	ABarrioZone();

protected:
	UPROPERTY(VisibleAnywhere, Category = "Barrio")
	TObjectPtr<UBoxComponent> Area;
};

/**
 * Salida del barrio (paso a nivel, avenida). Cruzarla es la ÚNICA forma de dejar de ser ladrón:
 * el jugador vuelve a ser vecino, con el botín encima, listo para venderlo Afuera.
 * Ubicarla en el borde del barrio; el reducidor va del otro lado.
 */
UCLASS()
class BARRIOWORLD_API AExitZone : public ABarrioZone
{
	GENERATED_BODY()

public:
	AExitZone();

protected:
	virtual void BeginPlay() override;

private:
	UFUNCTION()
	void OnAreaBeginOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp,
		int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);
};

/**
 * Zona segura (punto de llegada, interior de la comisaría): nadie recibe daño adentro
 * y no se puede poner el pasamontañas.
 */
UCLASS()
class BARRIOWORLD_API ABarrioSafeZone : public ABarrioZone
{
	GENERATED_BODY()

public:
	ABarrioSafeZone();

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	FBox RegisteredBounds;
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
