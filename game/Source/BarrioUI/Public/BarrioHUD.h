#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "BarrioHUD.generated.h"

/**
 * HUD mínimo de la Fase 1, dibujado sin assets: mira, aviso de interacción y una línea de estado
 * (rol de red, velocidad y estado de movimiento) que sirve para las pruebas de la Fase 2.
 * Se reemplaza por widgets de UMG cuando el diseñador arme la interfaz.
 */
UCLASS()
class BARRIOUI_API ABarrioHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;
};
