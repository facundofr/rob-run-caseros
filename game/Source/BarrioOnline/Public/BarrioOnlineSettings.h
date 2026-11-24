#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "BarrioOnlineSettings.generated.h"

/**
 * Configuración de la conexión con el backend. Se edita en Project Settings → Game → Barrio Online
 * y queda en Config/DefaultGame.ini.
 *
 * La clave de servidor NUNCA va acá (este archivo viaja con el cliente): el servidor de juego la lee
 * de la variable de entorno BARRIO_SERVER_KEY.
 */
UCLASS(Config = Game, DefaultConfig, meta = (DisplayName = "Barrio Online"))
class BARRIOONLINE_API UBarrioOnlineSettings : public UDeveloperSettings
{
	GENERATED_BODY()

public:
	/** URL pública del backend, usada por el cliente para login. */
	UPROPERTY(Config, EditAnywhere, Category = "Backend")
	FString BackendUrl = TEXT("https://caseros-api.facundofr.com");

	/** Servidor al que se conecta el cliente si el backend no recomienda ninguno. */
	UPROPERTY(Config, EditAnywhere, Category = "Backend")
	FString DefaultGameServer = TEXT("caseros.facundofr.com:7777");

	/** Mostrar la pantalla de login al abrir el juego. */
	UPROPERTY(Config, EditAnywhere, Category = "Login")
	bool bRequireLogin = true;

	/** Mostrar la pantalla de login también al probar en el editor (por defecto no, para probar rápido). */
	UPROPERTY(Config, EditAnywhere, Category = "Login")
	bool bShowLoginInEditor = false;

	/** Segundos entre heartbeats del servidor de juego. */
	UPROPERTY(Config, EditAnywhere, Category = "Server", meta = (ClampMin = "5"))
	float HeartbeatInterval = 15.f;

	virtual FName GetCategoryName() const override { return TEXT("Game"); }
};
