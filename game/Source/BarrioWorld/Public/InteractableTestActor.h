#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Interactable.h"
#include "InteractableTestActor.generated.h"

class UStaticMeshComponent;
class UMaterialInstanceDynamic;

/**
 * Interruptor de prueba: un bloque que cambia de color al interactuar.
 *
 * Prueba el camino completo que van a usar puertas, ventanas y cajones:
 * el cliente pide, el servidor valida y cambia el estado, y el estado se replica a todos.
 * Se reemplaza por los objetos reales en la Fase 3.
 */
UCLASS()
class BARRIOWORLD_API AInteractableTestActor : public AActor, public IInteractable
{
	GENERATED_BODY()

public:
	AInteractableTestActor();

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	virtual FText GetInteractionText_Implementation(const AActor* InstigatorActor) const override;
	virtual void Interact_Implementation(AActor* InstigatorActor) override;

protected:
	virtual void BeginPlay() override;

	UPROPERTY(VisibleAnywhere, Category = "Barrio")
	TObjectPtr<UStaticMeshComponent> Mesh;

	UPROPERTY(EditAnywhere, Category = "Barrio")
	FLinearColor OffColor = FLinearColor(0.6f, 0.1f, 0.1f);

	UPROPERTY(EditAnywhere, Category = "Barrio")
	FLinearColor OnColor = FLinearColor(0.1f, 0.7f, 0.2f);

private:
	UFUNCTION()
	void OnRep_IsOn();

	void UpdateVisuals();

	UPROPERTY(ReplicatedUsing = OnRep_IsOn)
	bool bIsOn = false;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> DynamicMaterial;
};
