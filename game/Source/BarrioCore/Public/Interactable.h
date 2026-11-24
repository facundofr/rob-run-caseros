#pragma once

#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "Interactable.generated.h"

UINTERFACE(MinimalAPI, BlueprintType)
class UInteractable : public UInterface
{
	GENERATED_BODY()
};

/**
 * Todo lo que el jugador puede usar con la tecla de interacción: puertas, ventanas, cajones, cajas fuertes.
 *
 * Reglas de red:
 * - GetInteractionText y CanInteract se llaman en el cliente para mostrar el aviso en el HUD,
 *   y en el servidor para validar.
 * - Interact se ejecuta SOLO en el servidor, después de que el personaje validó la distancia.
 *   El resultado llega a los clientes por replicación, nunca porque el cliente lo decida.
 */
class BARRIOCORE_API IInteractable
{
	GENERATED_BODY()

public:
	/** Texto del aviso. Recibe a quien mira, porque el texto puede depender de su rol. */
	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Barrio|Interaction")
	FText GetInteractionText(const AActor* InstigatorActor) const;

	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Barrio|Interaction")
	bool CanInteract(const AActor* InstigatorActor) const;

	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Barrio|Interaction")
	void Interact(AActor* InstigatorActor);

	virtual FText GetInteractionText_Implementation(const AActor* InstigatorActor) const { return FText::GetEmpty(); }
	virtual bool CanInteract_Implementation(const AActor* InstigatorActor) const { return true; }
	virtual void Interact_Implementation(AActor* InstigatorActor) {}
};
