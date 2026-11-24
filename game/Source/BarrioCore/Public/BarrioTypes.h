#pragma once

#include "CoreMinimal.h"
#include "BarrioTypes.generated.h"

/** Rol del jugador. "Ladrón" no es un rol: es un civil con nivel de buscado mayor a cero. */
UENUM(BlueprintType)
enum class EBarrioRole : uint8
{
	Civilian UMETA(DisplayName = "Civil"),
	Police   UMETA(DisplayName = "Policía")
};
