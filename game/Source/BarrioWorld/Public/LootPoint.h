#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Interactable.h"
#include "LootPoint.generated.h"

class APawn;
class AController;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;

UENUM(BlueprintType)
enum class ELootTier : uint8
{
	Low    UMETA(DisplayName = "Bajo"),
	Medium UMETA(DisplayName = "Medio"),
	High   UMETA(DisplayName = "Alto")
};

/**
 * Puerta de una casa que se puede robar.
 *
 * Flujo (todo en el servidor):
 * 1. Un civil interactúa: empieza el robo. Dura 4 s, o 7 s agachado (más sigiloso).
 * 2. Al empezar se tira la alarma según el nivel de la casa; agachado, la chance se reduce a la mitad.
 *    Si suena, a los 2 s se avisa a la policía y el ladrón pasa a estar buscado.
 * 3. Si el ladrón se aleja, muere o lo arrestan, el robo se cancela.
 * 4. Al terminar, el botín queda "encima" del jugador hasta venderlo al reducidor.
 * 5. La casa se repone a los 5 minutos.
 *
 * Colores: azul disponible, gris robada, rojo alarma sonando.
 */
UCLASS()
class BARRIOWORLD_API ALootPoint : public AActor, public IInteractable
{
	GENERATED_BODY()

public:
	ALootPoint();

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	virtual FText GetInteractionText_Implementation(const AActor* InstigatorActor) const override;
	virtual bool CanInteract_Implementation(const AActor* InstigatorActor) const override;
	virtual void Interact_Implementation(AActor* InstigatorActor) override;

	/** Si está activo, el nivel de la casa se sortea al empezar la partida (60% bajo, 30% medio, 10% alto). */
	UPROPERTY(EditAnywhere, Category = "Barrio|Loot")
	bool bRandomizeTier = true;

	UPROPERTY(EditAnywhere, Replicated, Category = "Barrio|Loot")
	ELootTier Tier = ELootTier::Low;

	UPROPERTY(EditAnywhere, Category = "Barrio|Loot") float RobDuration = 4.f;
	UPROPERTY(EditAnywhere, Category = "Barrio|Loot") float StealthRobDuration = 7.f;
	UPROPERTY(EditAnywhere, Category = "Barrio|Loot") float AlarmDelay = 2.f;
	UPROPERTY(EditAnywhere, Category = "Barrio|Loot") float AlarmDuration = 60.f;
	UPROPERTY(EditAnywhere, Category = "Barrio|Loot") float RestockTime = 300.f;

	/** Distancia máxima (cm) a la que el ladrón puede alejarse sin cancelar el robo. */
	UPROPERTY(EditAnywhere, Category = "Barrio|Loot") float MaxRobDistance = 350.f;

protected:
	virtual void BeginPlay() override;

	UPROPERTY(VisibleAnywhere, Category = "Barrio")
	TObjectPtr<UStaticMeshComponent> Mesh;

private:
	void CheckRobbery();
	void CompleteRobbery();
	void CancelRobbery();
	void TriggerAlarm();
	void StopAlarm();
	void Restock();

	float GetAlarmChance() const;
	FIntPoint GetLootRange() const;

	UFUNCTION()
	void OnRep_State();

	void UpdateVisuals();

	UPROPERTY(ReplicatedUsing = OnRep_State)
	bool bLooted = false;

	UPROPERTY(ReplicatedUsing = OnRep_State)
	bool bAlarmRinging = false;

	UPROPERTY(Replicated)
	TObjectPtr<APawn> Robber;

	TWeakObjectPtr<AController> AlarmSuspect;
	float RobberyEndTime = 0.f;

	FTimerHandle RobberyTimer;
	FTimerHandle AlarmTimer;
	FTimerHandle AlarmStopTimer;
	FTimerHandle RestockTimer;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> DynamicMaterial;
};
