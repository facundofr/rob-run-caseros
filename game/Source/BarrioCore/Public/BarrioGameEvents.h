#pragma once

#include "CoreMinimal.h"
#include "BarrioTypes.h"
#include "Subsystems/WorldSubsystem.h"
#include "BarrioGameEvents.generated.h"

class AController;
class ABarrioPlayerState;

/**
 * Canal de eventos del juego. Los sistemas informan lo que pasa (sonó una alarma, un ladrón salió
 * del barrio, un policía quiere esposar) y las reglas, que viven en el GameMode, deciden qué hacer.
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
	DECLARE_MULTICAST_DELEGATE_TwoParams(FPairEvent, AController* /*Police*/, AController* /*Suspect*/);
	DECLARE_MULTICAST_DELEGATE_TwoParams(FRoleEvent, AController* /*Player*/, EBarrioRole /*RequestedRole*/);
	DECLARE_MULTICAST_DELEGATE_OneParam(FPlayerEvent, AController* /*Player*/);

	FAlarmEvent OnAlarm;
	FDamageEvent OnDamage;
	FKillEvent OnKill;
	/** Un policía empezó a esposar a un sospechoso (el GameMode controla los 2,5 s). */
	FPairEvent OnCuffRequested;
	/** Pedido en el mostrador de la comisaría: entrar de servicio (Police) o terminar el turno (Civilian). */
	FRoleEvent OnRoleRequested;
	/** Un vecino pidió ponerse el pasamontañas. */
	FPlayerEvent OnMaskRequested;
	/** Un ladrón se rindió o dejó de estar rendido (tecla Q). */
	FPlayerEvent OnSurrenderToggled;
	/** Un policía dio la orden de rendición (tecla Q). */
	FPlayerEvent OnSurrenderOrder;
	/** Un jugador cruzó una salida del barrio. */
	FPlayerEvent OnLeftNeighborhood;
	/** Un jugador pidió vender su botín al reducidor. */
	FPlayerEvent OnSellLootRequested;

	static UBarrioGameEvents* Get(const UObject* WorldContext);

	// --- Zonas seguras -----------------------------------------------------------------------

	void RegisterSafeZone(const FBox& Bounds) { SafeZones.Add(Bounds); }
	void UnregisterSafeZone(const FBox& Bounds) { SafeZones.Remove(Bounds); }
	bool IsInSafeZone(const FVector& Location) const;

	// --- Reglas de daño ------------------------------------------------------------------------

	/**
	 * Regla central de quién puede dañar a quién (sección 3 del documento de diseño):
	 * - Nadie recibe daño en una zona segura ni con protección de reaparición.
	 * - Un vecino no usa armas.
	 * - Un policía solo daña ladrones.
	 * - Un ladrón puede dañar a cualquiera (dañar vecinos tiene consecuencias en el GameMode).
	 * Devuelve false si el daño no debe ocurrir.
	 */
	bool CanDamage(const ABarrioPlayerState* Attacker, const ABarrioPlayerState* Victim, const FVector& VictimLocation, float ServerTime) const;

private:
	TArray<FBox> SafeZones;
};
