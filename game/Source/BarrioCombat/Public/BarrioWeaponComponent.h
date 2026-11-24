#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "BarrioWeaponComponent.generated.h"

/**
 * Pistola de disparo instantáneo (hitscan), única arma del MVP 0.
 *
 * El cliente envía desde dónde mira; el servidor valida cadencia, munición, que el punto de vista
 * esté cerca del personaje y que la dirección coincida con hacia dónde apunta, y recién ahí
 * calcula el impacto y aplica el daño. El cliente nunca informa a quién le pegó.
 *
 * Pendiente para el MVP completo: compensación de latencia (rebobinar posiciones al momento
 * del disparo). Sin ella, con mucho ping hay que apuntar un poco por delante del blanco.
 */
UCLASS(ClassGroup = (Barrio), meta = (BlueprintSpawnableComponent))
class BARRIOCOMBAT_API UBarrioWeaponComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UBarrioWeaponComponent();

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	/** Llamar en el cliente dueño. */
	void RequestFire();
	void RequestReload();

	UFUNCTION(BlueprintPure, Category = "Barrio|Weapon") int32 GetAmmo() const { return Ammo; }
	UFUNCTION(BlueprintPure, Category = "Barrio|Weapon") bool IsReloading() const { return bReloading; }

	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Weapon") float Damage = 25.f;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Weapon") float Range = 5000.f;          // 50 m
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Weapon") float FireInterval = 0.3f;     // segundos
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Weapon") int32 MagazineSize = 12;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Weapon") float ReloadTime = 1.5f;

	/** Distancia máxima aceptada entre el punto de vista enviado y el personaje (cámara en tercera persona). */
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Weapon") float MaxViewDistance = 800.f;

protected:
	virtual void BeginPlay() override;

private:
	UFUNCTION(Server, Reliable, WithValidation)
	void ServerFire(FVector_NetQuantize ViewStart, FVector_NetQuantizeNormal ViewDirection);

	UFUNCTION(Server, Reliable, WithValidation)
	void ServerReload();

	UFUNCTION(NetMulticast, Unreliable)
	void MulticastShotEffect(FVector_NetQuantize Start, FVector_NetQuantize End);

	void FinishReload();
	bool IsOwnerDead() const;
	bool CanOwnerUseWeapon() const;

	UPROPERTY(Replicated)
	int32 Ammo = 0;

	UPROPERTY(Replicated)
	bool bReloading = false;

	float LastFireTime = -1000.f;
	FTimerHandle ReloadTimer;
};
