#pragma once

#include "CoreMinimal.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "BarrioCharacterMovementComponent.generated.h"

/**
 * Movimiento del personaje con sprint predicho en red.
 *
 * El sprint viaja dentro de cada movimiento que el cliente envía al servidor (flag comprimido).
 * Así el cliente corre al instante sin esperar al servidor, y el servidor reproduce el mismo
 * movimiento y corrige si no coincide. Un cliente no puede inventar una velocidad mayor:
 * el servidor calcula la velocidad máxima con sus propios valores.
 */
UCLASS()
class BARRIOCHARACTERS_API UBarrioCharacterMovementComponent : public UCharacterMovementComponent
{
	GENERATED_BODY()

public:
	UBarrioCharacterMovementComponent();

	/** Velocidad al correr, en cm/s (600 = 21,6 km/h). */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Barrio|Movement", meta = (ClampMin = "0"))
	float SprintSpeed = 600.f;

	/** Velocidad máxima de un ladrón rendido, en cm/s. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Barrio|Movement", meta = (ClampMin = "0"))
	float SurrenderedSpeed = 100.f;

	void SetSprinting(bool bNewSprinting) { bWantsToSprint = bNewSprinting; }
	bool WantsToSprint() const { return bWantsToSprint; }

	virtual float GetMaxSpeed() const override;
	virtual void UpdateFromCompressedFlags(uint8 Flags) override;
	virtual FNetworkPredictionData_Client* GetPredictionData_Client() const override;

	uint8 bWantsToSprint : 1;
};
