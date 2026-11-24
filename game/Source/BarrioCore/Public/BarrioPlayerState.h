#pragma once

#include "CoreMinimal.h"
#include "BarrioTypes.h"
#include "GameFramework/PlayerState.h"
#include "BarrioPlayerState.generated.h"

/**
 * Estado de un jugador en la partida: rol, captura, nivel de búsqueda, notoriedad, dinero,
 * botín encima, cárcel, ganancias del turno policial y acción en curso.
 *
 * Los valores se leen en cualquier lado, pero solo el servidor los cambia (los métodos Set/Add
 * no hacen nada en un cliente).
 */
UCLASS()
class BARRIOCORE_API ABarrioPlayerState : public APlayerState
{
	GENERATED_BODY()

public:
	/** Nivel máximo de búsqueda. En este nivel toda la ciudad ve la ubicación del jugador. */
	static constexpr int32 MaxWantedLevel = 3;
	static constexpr int32 MaxNotoriety = 5;

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	UFUNCTION(BlueprintPure, Category = "Barrio") EBarrioRole GetBarrioRole() const { return BarrioRole; }
	UFUNCTION(BlueprintPure, Category = "Barrio") bool IsPolice() const { return BarrioRole == EBarrioRole::Police; }
	UFUNCTION(BlueprintPure, Category = "Barrio") bool IsCriminal() const { return BarrioRole == EBarrioRole::Criminal; }
	UFUNCTION(BlueprintPure, Category = "Barrio") bool IsCivilian() const { return BarrioRole == EBarrioRole::Civilian; }
	UFUNCTION(BlueprintPure, Category = "Barrio") EBarrioCaptureState GetCaptureState() const { return CaptureState; }
	UFUNCTION(BlueprintPure, Category = "Barrio") bool IsSurrendered() const { return CaptureState == EBarrioCaptureState::Surrendered; }
	UFUNCTION(BlueprintPure, Category = "Barrio") int32 GetWantedLevel() const { return WantedLevel; }
	UFUNCTION(BlueprintPure, Category = "Barrio") bool IsMostWanted() const { return WantedLevel >= MaxWantedLevel; }
	UFUNCTION(BlueprintPure, Category = "Barrio") int32 GetNotoriety() const { return Notoriety; }
	UFUNCTION(BlueprintPure, Category = "Barrio") int32 GetCash() const { return Cash; }
	UFUNCTION(BlueprintPure, Category = "Barrio") int32 GetCarriedLoot() const { return CarriedLoot; }
	UFUNCTION(BlueprintPure, Category = "Barrio") int32 GetShiftEarnings() const { return ShiftEarnings; }
	UFUNCTION(BlueprintPure, Category = "Barrio") bool IsJailed() const { return bJailed; }
	UFUNCTION(BlueprintPure, Category = "Barrio") float GetJailReleaseTime() const { return JailReleaseTime; }
	UFUNCTION(BlueprintPure, Category = "Barrio") EBarrioActionKind GetActionKind() const { return ActionKind; }
	UFUNCTION(BlueprintPure, Category = "Barrio") float GetActionEndTime() const { return ActionEndTime; }
	UFUNCTION(BlueprintPure, Category = "Barrio") float GetActionDuration() const { return ActionDuration; }

	/** Multiplicador de valor del botín según la notoriedad: +10 % por nivel, hasta +50 %. */
	float GetLootMultiplier() const { return 1.f + 0.1f * Notoriety; }

	// Solo servidor
	void SetBarrioRole(EBarrioRole NewRole);
	void SetCaptureState(EBarrioCaptureState NewState);
	void AddWanted(int32 Amount, float ServerTime);
	void SetWantedLevel(int32 NewLevel);
	void AddNotoriety(int32 Amount);
	void ResetCriminalState(); // vuelve a vecino: sin búsqueda, sin notoriedad, libre
	void AddCash(int32 Amount);
	/** Saldo confirmado por el backend. */
	void SetCash(int32 NewCash);
	void AddCarriedLoot(int32 Amount);
	int32 TakeCarriedLoot();
	void AddShiftEarnings(int32 Amount);
	int32 TakeShiftEarnings();
	void SetJailed(bool bNewJailed, float ReleaseTime);
	void SetAction(EBarrioActionKind Kind, float EndTime, float Duration);
	void ClearAction();

	/** Momento del último delito violento, en tiempo del servidor. Solo existe en el servidor. */
	float LastCrimeTime = 0.f;

	/** Hasta cuándo no recibe daño (policía recién reaparecido). Solo servidor. */
	float SpawnProtectedUntil = 0.f;

	/** Momento de la última orden de rendición dada por este policía. Solo servidor. */
	float LastSurrenderOrderTime = -1000.f;

	/** Cuenta y personaje en el backend (0 = sin backend). Solo existen en el servidor. */
	int32 AccountId = 0;
	int32 CharacterId = 0;

private:
	UPROPERTY(Replicated) EBarrioRole BarrioRole = EBarrioRole::Civilian;
	UPROPERTY(Replicated) EBarrioCaptureState CaptureState = EBarrioCaptureState::Free;
	UPROPERTY(Replicated) int32 WantedLevel = 0;
	UPROPERTY(Replicated) int32 Notoriety = 0;
	UPROPERTY(Replicated) bool bJailed = false;

	UPROPERTY(Replicated) int32 Cash = 0;
	UPROPERTY(Replicated) int32 CarriedLoot = 0;
	UPROPERTY(Replicated) int32 ShiftEarnings = 0;
	UPROPERTY(Replicated) float JailReleaseTime = 0.f;
	UPROPERTY(Replicated) EBarrioActionKind ActionKind = EBarrioActionKind::None;
	UPROPERTY(Replicated) float ActionEndTime = 0.f;
	UPROPERTY(Replicated) float ActionDuration = 0.f;
};
