#pragma once

#include "CoreMinimal.h"
#include "Engine/EngineTypes.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "BarrioServerBackend.generated.h"

struct FBarrioProfile
{
	int32 AccountId = 0;
	int32 CharacterId = 0;
	FString Name;
	int32 Cash = 0;
};

/**
 * Backend visto desde el servidor de juego: registro y heartbeat de la instancia, verificación de la
 * sesión de cada jugador que entra y movimientos de dinero.
 *
 * Se activa solo si existe la variable de entorno BARRIO_SERVER_KEY (la genera setup-vps.sh en
 * /etc/barrio/gameserver.env). Sin ella, por ejemplo al probar en el editor, el juego funciona
 * sin cuentas y el dinero no se guarda.
 *
 * Variables de entorno: BARRIO_BACKEND_URL, BARRIO_SERVER_KEY, BARRIO_SERVER_NAME,
 * BARRIO_PUBLIC_ADDRESS, BARRIO_REGION.
 */
UCLASS()
class BARRIOONLINE_API UBarrioServerBackend : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	using FVerified = TFunction<void(bool bSuccess, const FBarrioProfile& Profile, const FString& Error)>;
	using FTransactionDone = TFunction<void(bool bSuccess, int32 Balance, const FString& Error)>;

	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	bool IsEnabled() const { return !ServerKey.IsEmpty(); }

	/** Registra la instancia y empieza a enviar heartbeats. PlayerCount informa cuántos jugadores hay. */
	void StartRegistration(int32 Port, int32 MaxPlayers, TFunction<int32()> PlayerCount);

	void VerifySession(const FString& Token, FVerified Done);

	/**
	 * Cobra (Amount > 0) o paga (Amount < 0). Genera una clave de idempotencia única y, si la red falla,
	 * reintenta una vez con la misma clave: el backend garantiza que no se aplica dos veces.
	 */
	void ApplyTransaction(int32 CharacterId, int32 Amount, const FString& Reason, FTransactionDone Done);

private:
	void Register();
	void SendHeartbeat();
	void SendTransaction(TSharedPtr<class FJsonObject> Body, FTransactionDone Done, bool bIsRetry);
	FString ApiUrl(const FString& Path) const;

	FString BackendUrl;
	FString ServerKey;
	FString ServerName;
	FString PublicAddress;
	FString Region;
	FString ServerId;

	int32 Port = 7777;
	int32 MaxPlayers = 16;
	TFunction<int32()> PlayerCountProvider;

	FTimerHandle HeartbeatTimer;
	FTimerHandle RegisterRetryTimer;
};
