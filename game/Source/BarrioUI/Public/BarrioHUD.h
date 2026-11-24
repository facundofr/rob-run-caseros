#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "BarrioHUD.generated.h"

class SWidget;

/**
 * HUD dibujado sin assets: mira, aviso de interacción, panel del jugador, alarmas y marcas.
 * Al abrir el juego sin estar conectado a un servidor muestra la pantalla de login.
 * Se reemplaza por widgets de UMG cuando el diseñador arme la interfaz.
 */
UCLASS()
class BARRIOUI_API ABarrioHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	bool ShouldShowLogin() const;
	void ShowLogin();

	TSharedPtr<SWidget> LoginOverlay;
};
