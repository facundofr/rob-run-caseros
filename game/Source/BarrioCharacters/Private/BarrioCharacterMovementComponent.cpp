#include "BarrioCharacterMovementComponent.h"
#include "BarrioPlayerState.h"
#include "GameFramework/Character.h"

namespace
{
	/** Movimiento guardado por el cliente: suma el estado de sprint al movimiento estándar. */
	class FSavedMove_Barrio : public FSavedMove_Character
	{
		typedef FSavedMove_Character Super;

	public:
		uint8 bSavedWantsToSprint : 1;

		virtual void Clear() override
		{
			Super::Clear();
			bSavedWantsToSprint = false;
		}

		virtual uint8 GetCompressedFlags() const override
		{
			uint8 Result = Super::GetCompressedFlags();
			if (bSavedWantsToSprint)
			{
				Result |= FLAG_Custom_0;
			}
			return Result;
		}

		virtual bool CanCombineWith(const FSavedMovePtr& NewMove, ACharacter* InCharacter, float MaxDelta) const override
		{
			const FSavedMove_Barrio* Other = static_cast<const FSavedMove_Barrio*>(NewMove.Get());
			if (bSavedWantsToSprint != Other->bSavedWantsToSprint)
			{
				return false;
			}
			return Super::CanCombineWith(NewMove, InCharacter, MaxDelta);
		}

		virtual void SetMoveFor(ACharacter* C, float InDeltaTime, FVector const& NewAccel, FNetworkPredictionData_Client_Character& ClientData) override
		{
			Super::SetMoveFor(C, InDeltaTime, NewAccel, ClientData);
			if (const UBarrioCharacterMovementComponent* Movement = Cast<UBarrioCharacterMovementComponent>(C->GetCharacterMovement()))
			{
				bSavedWantsToSprint = Movement->bWantsToSprint;
			}
		}

		virtual void PrepMoveFor(ACharacter* C) override
		{
			Super::PrepMoveFor(C);
			if (UBarrioCharacterMovementComponent* Movement = Cast<UBarrioCharacterMovementComponent>(C->GetCharacterMovement()))
			{
				Movement->bWantsToSprint = bSavedWantsToSprint;
			}
		}
	};

	class FNetworkPredictionData_Client_Barrio : public FNetworkPredictionData_Client_Character
	{
		typedef FNetworkPredictionData_Client_Character Super;

	public:
		explicit FNetworkPredictionData_Client_Barrio(const UCharacterMovementComponent& ClientMovement)
			: Super(ClientMovement)
		{
		}

		virtual FSavedMovePtr AllocateNewMove() override
		{
			return FSavedMovePtr(new FSavedMove_Barrio());
		}
	};
}

UBarrioCharacterMovementComponent::UBarrioCharacterMovementComponent()
{
	bWantsToSprint = false;
}

float UBarrioCharacterMovementComponent::GetMaxSpeed() const
{
	// Un ladrón rendido camina con las manos arriba: lento y sin correr.
	const ABarrioPlayerState* State = PawnOwner ? PawnOwner->GetPlayerState<ABarrioPlayerState>() : nullptr;
	if (State && State->IsSurrendered())
	{
		return SurrenderedSpeed;
	}

	if (MovementMode == MOVE_Walking && bWantsToSprint && !IsCrouching())
	{
		return SprintSpeed;
	}
	return Super::GetMaxSpeed();
}

void UBarrioCharacterMovementComponent::UpdateFromCompressedFlags(uint8 Flags)
{
	Super::UpdateFromCompressedFlags(Flags);
	bWantsToSprint = (Flags & FSavedMove_Character::FLAG_Custom_0) != 0;
}

FNetworkPredictionData_Client* UBarrioCharacterMovementComponent::GetPredictionData_Client() const
{
	check(PawnOwner != nullptr);

	if (!ClientPredictionData)
	{
		UBarrioCharacterMovementComponent* MutableThis = const_cast<UBarrioCharacterMovementComponent*>(this);
		MutableThis->ClientPredictionData = new FNetworkPredictionData_Client_Barrio(*this);
	}
	return ClientPredictionData;
}
