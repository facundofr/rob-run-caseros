#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "BarrioHealthComponent.generated.h"

/**
 * Vida del personaje. Solo el servidor aplica daño; la vida y la muerte se replican.
 * OnDied se dispara una vez en el servidor y una vez en cada cliente.
 *
 * MVP 0: daño simple del motor. El Gameplay Ability System del informe entra cuando
 * haya armaduras, efectos y más de un arma.
 */
UCLASS(ClassGroup = (Barrio), meta = (BlueprintSpawnableComponent))
class BARRIOCOMBAT_API UBarrioHealthComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UBarrioHealthComponent();

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	/** Solo servidor. Devuelve el daño efectivamente aplicado. */
	float ApplyDamage(float Amount);

	UFUNCTION(BlueprintPure, Category = "Barrio|Health") float GetHealth() const { return Health; }
	UFUNCTION(BlueprintPure, Category = "Barrio|Health") float GetMaxHealth() const { return MaxHealth; }
	UFUNCTION(BlueprintPure, Category = "Barrio|Health") bool IsDead() const { return bDead; }

	FSimpleMulticastDelegate OnDied;

	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Health", meta = (ClampMin = "1"))
	float MaxHealth = 100.f;

private:
	UFUNCTION()
	void OnRep_Dead();

	UPROPERTY(Replicated)
	float Health = 100.f;

	UPROPERTY(ReplicatedUsing = OnRep_Dead)
	bool bDead = false;
};
