#pragma once

#include "CoreMinimal.h"
#include "BarrioTypes.h"
#include "Subsystems/WorldSubsystem.h"
#include "BarrioGameEvents.generated.h"

class AController;

/**
 * Canal de eventos del juego. Los sistemas informan lo que pasa (sonó una alarma, alguien recibió
 * daño, un policía pidió un arresto) y las reglas, que viven en el GameMode, deciden qué hacer.
 * Así ningún sistema depende de otro.
 *
 * Los eventos se emiten y se escuchan SOLO en el servidor.
 */
UCLASS()
class BARRIOCORE_API UBarrioGameEvents : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	DECLARE_MULTICAST_DELEGATE_TwoParams(FAlarmEvent, const FVector& /*Location*/, AController* /*Suspect*/);
	DECLARE_MULTICAST_DELEGATE_ThreeParams(FDamageEvent, AController* /*Victim*/, AController* /*Instigator*/, float /*Damage*/);
	DECLARE_MULTICAST_DELEGATE_TwoParams(FKillEvent, AController* /*Victim*/, AController* /*Killer*/);
	DECLARE_MULTICAST_DELEGATE_TwoParams(FArrestEvent, AController* /*Police*/, AController* /*Suspect*/);
	DECLARE_MULTICAST_DELEGATE_TwoParams(FRoleEvent, AController* /*Player*/, EBarrioRole /*RequestedRole*/);

	FAlarmEvent OnAlarm;
	FDamageEvent OnDamage;
	FKillEvent OnKill;
	FArrestEvent OnArrestRequested;
	FRoleEvent OnRoleRequested;

	static UBarrioGameEvents* Get(const UObject* WorldContext);
};
