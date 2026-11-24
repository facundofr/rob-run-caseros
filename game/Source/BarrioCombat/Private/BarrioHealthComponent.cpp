#include "BarrioHealthComponent.h"

#include "GameFramework/Actor.h"
#include "Net/UnrealNetwork.h"

UBarrioHealthComponent::UBarrioHealthComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
	SetIsReplicatedByDefault(true);
	Health = MaxHealth;
}

void UBarrioHealthComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(UBarrioHealthComponent, Health);
	DOREPLIFETIME(UBarrioHealthComponent, bDead);
}

float UBarrioHealthComponent::ApplyDamage(float Amount)
{
	const AActor* Owner = GetOwner();
	if (!Owner || !Owner->HasAuthority() || bDead || Amount <= 0.f)
	{
		return 0.f;
	}

	const float Previous = Health;
	Health = FMath::Max(0.f, Health - Amount);

	if (Health <= 0.f)
	{
		bDead = true;
		OnRep_Dead(); // En el servidor OnRep no se llama solo.
	}
	return Previous - Health;
}

void UBarrioHealthComponent::OnRep_Dead()
{
	if (bDead)
	{
		OnDied.Broadcast();
	}
}
