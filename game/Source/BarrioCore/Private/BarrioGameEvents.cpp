#include "BarrioGameEvents.h"

#include "BarrioPlayerState.h"
#include "Engine/World.h"

UBarrioGameEvents* UBarrioGameEvents::Get(const UObject* WorldContext)
{
	const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	return World ? World->GetSubsystem<UBarrioGameEvents>() : nullptr;
}

bool UBarrioGameEvents::IsInSafeZone(const FVector& Location) const
{
	for (const FBox& Zone : SafeZones)
	{
		if (Zone.IsInsideOrOn(Location))
		{
			return true;
		}
	}
	return false;
}

bool UBarrioGameEvents::CanDamage(const ABarrioPlayerState* Attacker, const ABarrioPlayerState* Victim, const FVector& VictimLocation, float ServerTime) const
{
	if (IsInSafeZone(VictimLocation))
	{
		return false;
	}
	if (Victim && ServerTime < Victim->SpawnProtectedUntil)
	{
		return false;
	}
	if (!Attacker || !Victim || Attacker == Victim)
	{
		return true; // daño del entorno o propio: se permite
	}

	switch (Attacker->GetBarrioRole())
	{
	case EBarrioRole::Civilian:
		return false; // los vecinos no usan armas
	case EBarrioRole::Police:
		return Victim->IsCriminal(); // la policía solo daña ladrones
	case EBarrioRole::Criminal:
	default:
		return true;
	}
}
