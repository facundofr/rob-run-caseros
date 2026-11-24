#pragma once

#include "CoreMinimal.h"
#include "BarrioTypes.generated.h"

/**
 * Rol del jugador dentro del barrio (ver docs/GAME_DESIGN_DOCUMENT.md, sección 3).
 * - Vecino: por defecto, no usa armas ni roba, no pierde nada al morir.
 * - Ladrón: se pone el pasamontañas; solo deja de serlo cruzando una salida del barrio.
 * - Policía: turno en la comisaría, cupo limitado, solo puede dañar ladrones.
 */
UENUM(BlueprintType)
enum class EBarrioRole : uint8
{
	Civilian UMETA(DisplayName = "Vecino"),
	Criminal UMETA(DisplayName = "Ladrón"),
	Police   UMETA(DisplayName = "Policía")
};

/** Estado de captura de un ladrón (sección 5 del documento de diseño). */
UENUM(BlueprintType)
enum class EBarrioCaptureState : uint8
{
	Free        UMETA(DisplayName = "Libre"),
	Surrendered UMETA(DisplayName = "Rendido")
};

/** Acción con duración en curso, para la barra de progreso del HUD. */
UENUM(BlueprintType)
enum class EBarrioActionKind : uint8
{
	None,
	Robbery    UMETA(DisplayName = "Robando"),
	PuttingMask UMETA(DisplayName = "Poniéndose el pasamontañas"),
	Cuffing    UMETA(DisplayName = "Esposando")
};
