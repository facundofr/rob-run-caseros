#include "BarrioPlayerState.h"

#include "Net/UnrealNetwork.h"

void ABarrioPlayerState::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);

	// Lo que ven todos: rol y nivel de buscado (la policía necesita saber a quién perseguir).
	DOREPLIFETIME(ABarrioPlayerState, BarrioRole);
	DOREPLIFETIME(ABarrioPlayerState, WantedLevel);
	DOREPLIFETIME(ABarrioPlayerState, bJailed);

	// Lo que ve solo el dueño.
	DOREPLIFETIME_CONDITION(ABarrioPlayerState, Cash, COND_OwnerOnly);
	DOREPLIFETIME_CONDITION(ABarrioPlayerState, CarriedLoot, COND_OwnerOnly);
	DOREPLIFETIME_CONDITION(ABarrioPlayerState, JailReleaseTime, COND_OwnerOnly);
	DOREPLIFETIME_CONDITION(ABarrioPlayerState, RobberyEndTime, COND_OwnerOnly);
	DOREPLIFETIME_CONDITION(ABarrioPlayerState, RobberyDuration, COND_OwnerOnly);
}

void ABarrioPlayerState::SetBarrioRole(EBarrioRole NewRole)
{
	if (HasAuthority())
	{
		BarrioRole = NewRole;
	}
}

void ABarrioPlayerState::AddWanted(int32 Amount, float ServerTime)
{
	if (HasAuthority() && Amount > 0)
	{
		WantedLevel = FMath::Clamp(WantedLevel + Amount, 0, MaxWantedLevel);
		LastCrimeTime = ServerTime;
	}
}

void ABarrioPlayerState::SetWantedLevel(int32 NewLevel)
{
	if (HasAuthority())
	{
		WantedLevel = FMath::Clamp(NewLevel, 0, MaxWantedLevel);
	}
}

void ABarrioPlayerState::AddCash(int32 Amount)
{
	if (HasAuthority())
	{
		Cash = FMath::Max(0, Cash + Amount);
	}
}

void ABarrioPlayerState::SetCash(int32 NewCash)
{
	if (HasAuthority())
	{
		Cash = FMath::Max(0, NewCash);
	}
}

void ABarrioPlayerState::AddCarriedLoot(int32 Amount)
{
	if (HasAuthority())
	{
		CarriedLoot = FMath::Max(0, CarriedLoot + Amount);
	}
}

int32 ABarrioPlayerState::TakeCarriedLoot()
{
	if (!HasAuthority())
	{
		return 0;
	}
	const int32 Taken = CarriedLoot;
	CarriedLoot = 0;
	return Taken;
}

void ABarrioPlayerState::SetJailed(bool bNewJailed, float ReleaseTime)
{
	if (HasAuthority())
	{
		bJailed = bNewJailed;
		JailReleaseTime = bNewJailed ? ReleaseTime : 0.f;
	}
}

void ABarrioPlayerState::SetRobbery(float EndTime, float Duration)
{
	if (HasAuthority())
	{
		RobberyEndTime = EndTime;
		RobberyDuration = Duration;
	}
}

void ABarrioPlayerState::ClearRobbery()
{
	SetRobbery(0.f, 0.f);
}
