#pragma once

#include "CoreMinimal.h"
#include "BarrioTypes.h"
#include "GameFramework/PlayerState.h"
#include "BarrioPlayerState.generated.h"

/**
 * Estado de un jugador en la partida: rol, nivel de buscado, dinero, botín encima y cárcel.
 *
 * Los valores se leen en cualquier lado, pero solo el servidor los cambia (los métodos Set/Add
 * no hacen nada en un cliente). En el MVP 0 no hay backend: todo se pierde al salir.
 */
UCLASS()
class BARRIOCORE_API ABarrioPlayerState : public APlayerState
{
	GENERATED_BODY()

public:
	static constexpr int32 MaxWantedLevel = 5;

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	UFUNCTION(BlueprintPure, Category = "Barrio") EBarrioRole GetBarrioRole() const { return BarrioRole; }
	UFUNCTION(BlueprintPure, Category = "Barrio") bool IsPolice() const { return BarrioRole == EBarrioRole::Police; }
	UFUNCTION(BlueprintPure, Category = "Barrio") int32 GetWantedLevel() const { return WantedLevel; }
	UFUNCTION(BlueprintPure, Category = "Barrio") bool IsWanted() const { return WantedLevel > 0; }
	UFUNCTION(BlueprintPure, Category = "Barrio") int32 GetCash() const { return Cash; }
	UFUNCTION(BlueprintPure, Category = "Barrio") int32 GetCarriedLoot() const { return CarriedLoot; }
	UFUNCTION(BlueprintPure, Category = "Barrio") bool IsJailed() const { return bJailed; }
	UFUNCTION(BlueprintPure, Category = "Barrio") float GetJailReleaseTime() const { return JailReleaseTime; }
	UFUNCTION(BlueprintPure, Category = "Barrio") float GetRobberyEndTime() const { return RobberyEndTime; }
	UFUNCTION(BlueprintPure, Category = "Barrio") float GetRobberyDuration() const { return RobberyDuration; }

	// Solo servidor
	void SetBarrioRole(EBarrioRole NewRole);
	void AddWanted(int32 Amount, float ServerTime);
	void SetWantedLevel(int32 NewLevel);
	void AddCash(int32 Amount);
	/** Saldo confirmado por el backend. */
	void SetCash(int32 NewCash);
	void AddCarriedLoot(int32 Amount);
	int32 TakeCarriedLoot();
	void SetJailed(bool bNewJailed, float ReleaseTime);
	void SetRobbery(float EndTime, float Duration);
	void ClearRobbery();

	/** Momento del último delito, en tiempo del servidor. Solo existe en el servidor. */
	float LastCrimeTime = 0.f;

	/** Cuenta y personaje en el backend (0 = sin backend). Solo existen en el servidor. */
	int32 AccountId = 0;
	int32 CharacterId = 0;

private:
	UPROPERTY(Replicated)
	EBarrioRole BarrioRole = EBarrioRole::Civilian;

	UPROPERTY(Replicated)
	int32 WantedLevel = 0;

	UPROPERTY(Replicated)
	int32 Cash = 0;

	UPROPERTY(Replicated)
	int32 CarriedLoot = 0;

	UPROPERTY(Replicated)
	bool bJailed = false;

	UPROPERTY(Replicated)
	float JailReleaseTime = 0.f;

	UPROPERTY(Replicated)
	float RobberyEndTime = 0.f;

	UPROPERTY(Replicated)
	float RobberyDuration = 0.f;
};
