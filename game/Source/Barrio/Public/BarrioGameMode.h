#pragma once

#include "CoreMinimal.h"
#include "BarrioTypes.h"
#include "GameFramework/GameModeBase.h"
#include "BarrioGameMode.generated.h"

class ABarrioPlayerState;

/**
 * Reglas de la partida del MVP 0. Existe solo en el servidor.
 *
 * Escucha los eventos de UBarrioGameEvents y decide:
 * - Roles: cualquiera puede unirse a la policía en la comisaría si no está buscado, no lleva botín
 *   y hay cupo (1 policía cada 3 jugadores, hasta 4).
 * - Nivel de buscado: sube con alarmas, disparos y muertes de inocentes o policías; baja 1 nivel
 *   cada 60 s sin delitos.
 * - Arresto o muerte a manos de la policía estando buscado: cárcel (60 s + 15 s por nivel),
 *   pérdida del botín y recompensa para el policía.
 * - Reaparición a los 5 s después de morir; policías y civiles en puntos distintos.
 *
 * Para usar el personaje con malla y animaciones, crear un Blueprint hijo (BP_BarrioGameMode)
 * y asignarle como Default Pawn Class el Blueprint del personaje (ver README).
 */
UCLASS()
class BARRIO_API ABarrioGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ABarrioGameMode();

	virtual AActor* ChoosePlayerStart_Implementation(AController* Player) override;
	virtual bool ShouldSpawnAtStartSpot_Implementation(AController* Player) override;

	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Roles") int32 MaxPolice = 4;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Roles") int32 PlayersPerPolice = 3;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Rules") float RespawnDelay = 5.f;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Rules") float JailBaseTime = 60.f;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Rules") float JailTimePerWantedLevel = 15.f;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Rules") float WantedDecayInterval = 60.f;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Rules") float AlarmAlertRadius = 15000.f; // 150 m
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Rules") int32 ArrestRewardPerWantedLevel = 100;

	/** Tag del Player Start donde aparecen los policías. Los demás Player Start son de civiles. */
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Roles") FName PoliceStartTag = TEXT("Police");

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	void HandleAlarm(const FVector& Location, AController* Suspect);
	void HandleDamage(AController* Victim, AController* DamageInstigator, float Damage);
	void HandleKill(AController* Victim, AController* Killer);
	void HandleArrest(AController* Police, AController* Suspect);
	void HandleRoleRequest(AController* Player, EBarrioRole RequestedRole);
	void TickRules();

	void Jail(ABarrioPlayerState* Suspect);
	void RewardPolice(ABarrioPlayerState* Police, int32 WantedLevel);
	void RespawnNow(AController* Player);
	void RespawnLater(TWeakObjectPtr<AController> Player);
	void ShowMessage(AController* Player, const FString& Message) const;

	int32 CountPolice() const;
	int32 GetPoliceQuota() const;
	float Now() const;

	FTimerHandle RulesTimer;
	TArray<FDelegateHandle> EventHandles;
};
