#include "BarrioPlayerState.h"

#include "Net/UnrealNetwork.h"

void ABarrioPlayerState::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);

	// Lo que ven todos: rol, captura, búsqueda, notoriedad y cárcel.
	DOREPLIFETIME(ABarrioPlayerState, BarrioRole);
	DOREPLIFETIME(ABarrioPlayerState, CaptureState);
	DOREPLIFETIME(ABarrioPlayerState, WantedLevel);
	DOREPLIFETIME(ABarrioPlayerState, Notoriety);
	DOREPLIFETIME(ABarrioPlayerState, bJailed);

	// Lo que ve solo el dueño.
	DOREPLIFETIME_CONDITION(ABarrioPlayerState, Cash, COND_OwnerOnly);
	DOREPLIFETIME_CONDITION(ABarrioPlayerState, CarriedLoot, COND_OwnerOnly);
	DOREPLIFETIME_CONDITION(ABarrioPlayerState, ShiftEarnings, COND_OwnerOnly);
	DOREPLIFETIME_CONDITION(ABarrioPlayerState, JailReleaseTime, COND_OwnerOnly);
	DOREPLIFETIME_CONDITION(ABarrioPlayerState, ActionKind, COND_OwnerOnly);
	DOREPLIFETIME_CONDITION(ABarrioPlayerState, ActionEndTime, COND_OwnerOnly);
	DOREPLIFETIME_CONDITION(ABarrioPlayerState, ActionDuration, COND_OwnerOnly);
}

void ABarrioPlayerState::SetBarrioRole(EBarrioRole NewRole)
{
	if (HasAuthority())
	{
		BarrioRole = NewRole;
	}
}

void ABarrioPlayerState::SetCaptureState(EBarrioCaptureState NewState)
{
	if (HasAuthority())
	{
		CaptureState = NewState;
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

void ABarrioPlayerState::AddNotoriety(int32 Amount)
{
	if (HasAuthority())
	{
		Notoriety = FMath::Clamp(Notoriety + Amount, 0, MaxNotoriety);
	}
}

void ABarrioPlayerState::ResetCriminalState()
{
	if (HasAuthority())
	{
		BarrioRole = EBarrioRole::Civilian;
		CaptureState = EBarrioCaptureState::Free;
		WantedLevel = 0;
		Notoriety = 0;
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

void ABarrioPlayerState::AddShiftEarnings(int32 Amount)
{
	if (HasAuthority() && Amount > 0)
	{
		ShiftEarnings += Amount;
	}
}

int32 ABarrioPlayerState::TakeShiftEarnings()
{
	if (!HasAuthority())
	{
		return 0;
	}
	const int32 Earned = ShiftEarnings;
	ShiftEarnings = 0;
	return Earned;
}

void ABarrioPlayerState::SetJailed(bool bNewJailed, float ReleaseTime)
{
	if (HasAuthority())
	{
		bJailed = bNewJailed;
		JailReleaseTime = bNewJailed ? ReleaseTime : 0.f;
	}
}

void ABarrioPlayerState::SetAction(EBarrioActionKind Kind, float EndTime, float Duration)
{
	if (HasAuthority())
	{
		ActionKind = Kind;
		ActionEndTime = EndTime;
		ActionDuration = Duration;
	}
}

void ABarrioPlayerState::ClearAction()
{
	SetAction(EBarrioActionKind::None, 0.f, 0.f);
}
