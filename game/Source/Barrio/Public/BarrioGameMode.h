#pragma once

#include "CoreMinimal.h"
#include "BarrioTypes.h"
#include "GameFramework/GameModeBase.h"
#include "BarrioGameMode.generated.h"

class ABarrioPlayerState;

/**
 * Reglas de la partida. Existe solo en el servidor. Implementa docs/DISENO_JUEGO.md.
 *
 * Escucha los eventos de UBarrioGameEvents y decide:
 * - Roles: vecino por defecto; ladrón al ponerse el pasamontañas (2 s, fuera de zona segura) hasta
 *   cruzar una salida del barrio; policía en la comisaría si es vecino, sin botín y hay cupo
 *   (1 cada 3 jugadores, hasta 4).
 * - Captura: el ladrón se rinde con Q; el policía esposa (2,5 s) a un ladrón rendido o reducido;
 *   arresto = cárcel (60 s + 15 s por nivel de búsqueda) y botín confiscado.
 * - Policía: arresto $1.500 + 10 % del botín (+20 % con orden de rendición reciente), abatir $300,
 *   matar a un rendido $0. Se cobra al terminar el turno.
 * - Nivel de búsqueda: +1 por cada vecino que mata un ladrón; baja 1 por minuto sin delitos.
 * - Al morir: el botín se pierde; el ladrón vuelve a ser vecino; el policía reaparece con protección.
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
	virtual bool ShouldSpawnAtStartSpot(AController* Player) override;

	// Cuentas: con backend activo, nadie entra sin una sesión válida.
	virtual void PreLogin(const FString& Options, const FString& Address, const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage) override;
	virtual APlayerController* Login(UPlayer* NewPlayer, ENetRole InRemoteRole, const FString& Portal, const FString& Options,
		const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage) override;
	virtual void HandleStartingNewPlayer_Implementation(APlayerController* NewPlayer) override;
	virtual void Logout(AController* Exiting) override;

	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Roles") int32 MaxPolice = 4;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Roles") int32 PlayersPerPolice = 3;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Rules") float RespawnDelay = 5.f;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Rules") float JailBaseTime = 60.f;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Rules") float JailTimePerWantedLevel = 15.f;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Rules") float WantedDecayInterval = 60.f;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Rules") float AlarmAlertRadius = 15000.f; // 150 m

	// Roles y captura (documento de diseño, secciones 3, 5 y 7). Valores propios, se ajustan en la alpha.
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Capture") float MaskDuration = 2.f;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Capture") float CuffDuration = 2.5f;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Capture") float CuffMaxDistance = 300.f;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Capture") float SurrenderOrderRadius = 2500.f; // 25 m
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Police") int32 ArrestBaseReward = 1500;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Police") float ArrestLootShare = 0.10f;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Police") int32 KillCriminalReward = 300;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Police") float SurrenderOrderBonus = 0.20f;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Police") float SurrenderOrderWindow = 20.f;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Police") float PoliceSpawnProtection = 10.f;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Police") int32 ShiftSalaryCap = 50000;

	/** Tag del Player Start donde aparecen los policías. Los demás Player Start son de civiles. */
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Roles") FName PoliceStartTag = TEXT("Police");

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	void HandleAlarm(const FVector& Location, AController* Suspect);
	void HandleDamage(AController* Victim, AController* DamageInstigator, float Damage);
	void HandleKill(AController* Victim, AController* Killer);
	void HandleCuffRequested(AController* Police, AController* Suspect);
	void HandleRoleRequest(AController* Player, EBarrioRole RequestedRole);
	void HandleSellLoot(AController* Seller);
	void HandleMaskRequested(AController* Player);
	void HandleSurrenderToggled(AController* Player);
	void HandleSurrenderOrder(AController* Police);
	void HandleLeftNeighborhood(AController* Player);
	void TickRules();

	void FinishMask(TWeakObjectPtr<AController> Player);
	void FinishCuffing(TWeakObjectPtr<AController> Police, TWeakObjectPtr<AController> Suspect);
	void Arrest(AController* Police, AController* Suspect);
	void PayShift(ABarrioPlayerState* Police, const FString& Message);
	TSet<TWeakObjectPtr<AController>> SuspectsBeingCuffed;

	/** Suma dinero: con backend, lo guarda en la cuenta y usa el saldo confirmado; sin backend, solo en memoria. */
	void GrantCash(ABarrioPlayerState* State, int32 Amount, const FString& Reason, const FString& SuccessMessage);
	class UBarrioServerBackend* GetBackend() const;
	bool IsBackendEnabled() const;
	void OnSessionVerified(TWeakObjectPtr<APlayerController> Player, bool bSuccess, const struct FBarrioProfile& Profile, const FString& Error);

	TMap<TWeakObjectPtr<APlayerController>, FString> PendingTokens;
	TSet<TWeakObjectPtr<APlayerController>> VerifiedPlayers;

	void Jail(ABarrioPlayerState* Suspect);
	void RespawnNow(AController* Player);
	void RespawnLater(TWeakObjectPtr<AController> Player);
	void ShowMessage(AController* Player, const FString& Message) const;

	int32 CountPolice() const;
	int32 GetPoliceQuota() const;
	float Now() const;

	FTimerHandle RulesTimer;
	TArray<FDelegateHandle> EventHandles;
};
