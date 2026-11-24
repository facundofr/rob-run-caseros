#include "BarrioGameEvents.h"

#include "Engine/World.h"

UBarrioGameEvents* UBarrioGameEvents::Get(const UObject* WorldContext)
{
	const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	return World ? World->GetSubsystem<UBarrioGameEvents>() : nullptr;
}
