#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "BarrioAuthSubsystem.generated.h"

namespace BarrioHttp { struct FResponse; }

/**
 * Sesión del jugador en el cliente: login, registro y conexión al servidor de juego.
 *
 * El token de sesión dura 15 minutos y solo sirve para entrar a un servidor: el servidor de juego
 * lo verifica con el backend antes de aceptar al jugador.
 */
UCLASS()
class BARRIOONLINE_API UBarrioAuthSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	using FDone = TFunction<void(bool bSuccess, const FString& Message)>;
	using FServerFound = TFunction<void(const FString& Address)>;

	void Login(const FString& Username, const FString& Password, FDone Done);
	void Register(const FString& Username, const FString& Password, const FString& Email, FDone Done);

	/** Pide al backend el servidor recomendado. Si no hay ninguno, usa el de la configuración. */
	void FindServer(FServerFound Done);

	/** Viaja al servidor de juego llevando el token de sesión. */
	void ConnectTo(const FString& Address);

	bool IsLoggedIn() const { return !Token.IsEmpty(); }
	const FString& GetPlayerName() const { return PlayerName; }

private:
	void HandleSession(const BarrioHttp::FResponse& Response, FDone Done);
	FString ApiUrl(const TCHAR* Path) const;

	FString Token;
	FString PlayerName;
};
