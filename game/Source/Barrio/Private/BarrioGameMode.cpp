#include "BarrioGameMode.h"

#include "BarrioCharacter.h"
#include "BarrioGameEvents.h"
#include "BarrioHUD.h"
#include "BarrioLog.h"
#include "BarrioPlayerController.h"
#include "BarrioPlayerState.h"
#include "BarrioServerBackend.h"
#include "BarrioStations.h"

#include "EngineUtils.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/GameSession.h"
#include "GameFramework/GameStateBase.h"
#include "GameFramework/PlayerStart.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

namespace
{
	ABarrioPlayerState* StateOf(const AController* Controller)
	{
		return Controller ? Controller->GetPlayerState<ABarrioPlayerState>() : nullptr;
	}
}

ABarrioGameMode::ABarrioGameMode()
{
	DefaultPawnClass = ABarrioCharacter::StaticClass();
	HUDClass = ABarrioHUD::StaticClass();
	PlayerControllerClass = ABarrioPlayerController::StaticClass();
	PlayerStateClass = ABarrioPlayerState::StaticClass();
}

float ABarrioGameMode::Now() const
{
	return GetWorld()->GetTimeSeconds();
}

void ABarrioGameMode::BeginPlay()
{
	Super::BeginPlay();

	if (UBarrioGameEvents* Events = UBarrioGameEvents::Get(this))
	{
		EventHandles.Add(Events->OnAlarm.AddUObject(this, &ABarrioGameMode::HandleAlarm));
		EventHandles.Add(Events->OnDamage.AddUObject(this, &ABarrioGameMode::HandleDamage));
		EventHandles.Add(Events->OnKill.AddUObject(this, &ABarrioGameMode::HandleKill));
		EventHandles.Add(Events->OnArrestRequested.AddUObject(this, &ABarrioGameMode::HandleArrest));
		EventHandles.Add(Events->OnRoleRequested.AddUObject(this, &ABarrioGameMode::HandleRoleRequest));
		EventHandles.Add(Events->OnSellLootRequested.AddUObject(this, &ABarrioGameMode::HandleSellLoot));
	}

	GetWorldTimerManager().SetTimer(RulesTimer, this, &ABarrioGameMode::TickRules, 1.f, true);

	if (IsBackendEnabled() && GetNetMode() == NM_DedicatedServer)
	{
		const int32 MaxPlayers = GameSession ? GameSession->MaxPlayers : 16;
		TWeakObjectPtr<ABarrioGameMode> WeakThis(this);
		GetBackend()->StartRegistration(GetWorld()->URL.Port, MaxPlayers, [WeakThis]()
		{
			return WeakThis.IsValid() ? WeakThis->GetNumPlayers() : 0;
		});
	}
}

// ---------------------------------------------------------------------------------------------
// Cuentas y sesiones
// ---------------------------------------------------------------------------------------------

UBarrioServerBackend* ABarrioGameMode::GetBackend() const
{
	const UGameInstance* GameInstance = GetGameInstance();
	return GameInstance ? GameInstance->GetSubsystem<UBarrioServerBackend>() : nullptr;
}

bool ABarrioGameMode::IsBackendEnabled() const
{
	const UBarrioServerBackend* Backend = GetBackend();
	return Backend && Backend->IsEnabled();
}

void ABarrioGameMode::PreLogin(const FString& Options, const FString& Address, const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage)
{
	Super::PreLogin(Options, Address, UniqueId, ErrorMessage);

	if (ErrorMessage.IsEmpty() && IsBackendEnabled() && UGameplayStatics::ParseOption(Options, TEXT("token")).IsEmpty())
	{
		ErrorMessage = TEXT("Iniciá sesión antes de entrar.");
	}
}

APlayerController* ABarrioGameMode::Login(UPlayer* NewPlayer, ENetRole InRemoteRole, const FString& Portal, const FString& Options,
	const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage)
{
	APlayerController* Controller = Super::Login(NewPlayer, InRemoteRole, Portal, Options, UniqueId, ErrorMessage);
	if (Controller && IsBackendEnabled())
	{
		PendingTokens.Add(Controller, UGameplayStatics::ParseOption(Options, TEXT("token")));
	}
	return Controller;
}

void ABarrioGameMode::HandleStartingNewPlayer_Implementation(APlayerController* NewPlayer)
{
	// Sin backend (editor, pruebas locales) o jugador ya verificado: entra directo.
	if (!IsBackendEnabled() || !NewPlayer || NewPlayer->IsLocalController() || VerifiedPlayers.Contains(NewPlayer))
	{
		Super::HandleStartingNewPlayer_Implementation(NewPlayer);
		return;
	}

	// Con backend: el personaje no aparece hasta que el backend confirma la sesión.
	FString Token;
	PendingTokens.RemoveAndCopyValue(NewPlayer, Token);

	TWeakObjectPtr<ABarrioGameMode> WeakThis(this);
	TWeakObjectPtr<APlayerController> WeakPlayer(NewPlayer);
	GetBackend()->VerifySession(Token, [WeakThis, WeakPlayer](bool bSuccess, const FBarrioProfile& Profile, const FString& Error)
	{
		if (ABarrioGameMode* Self = WeakThis.Get())
		{
			Self->OnSessionVerified(WeakPlayer, bSuccess, Profile, Error);
		}
	});
}

void ABarrioGameMode::OnSessionVerified(TWeakObjectPtr<APlayerController> Player, bool bSuccess, const FBarrioProfile& Profile, const FString& Error)
{
	APlayerController* Controller = Player.Get();
	ABarrioPlayerState* State = StateOf(Controller);
	if (!Controller || !State)
	{
		return; // se desconectó mientras se verificaba
	}

	if (!bSuccess)
	{
		UE_LOG(LogBarrio, Warning, TEXT("Sesión rechazada: %s"), *Error);
		GameSession->KickPlayer(Controller, FText::FromString(Error));
		return;
	}

	// Una cuenta, una conexión.
	for (APlayerState* Other : GameState->PlayerArray)
	{
		const ABarrioPlayerState* OtherState = Cast<ABarrioPlayerState>(Other);
		if (OtherState && OtherState != State && OtherState->AccountId == Profile.AccountId)
		{
			GameSession->KickPlayer(Controller, FText::FromString(TEXT("Esa cuenta ya está conectada.")));
			return;
		}
	}

	State->AccountId = Profile.AccountId;
	State->CharacterId = Profile.CharacterId;
	State->SetCash(Profile.Cash);
	ChangeName(Controller, Profile.Name, false);
	VerifiedPlayers.Add(Controller);
	UE_LOG(LogBarrio, Log, TEXT("%s entró (cuenta %d, $%d)."), *Profile.Name, Profile.AccountId, Profile.Cash);

	HandleStartingNewPlayer_Implementation(Controller); // ahora sí aparece
}

void ABarrioGameMode::Logout(AController* Exiting)
{
	if (APlayerController* Controller = Cast<APlayerController>(Exiting))
	{
		PendingTokens.Remove(Controller);
		VerifiedPlayers.Remove(Controller);
	}
	Super::Logout(Exiting);
}

// ---------------------------------------------------------------------------------------------
// Dinero
// ---------------------------------------------------------------------------------------------

void ABarrioGameMode::GrantCash(ABarrioPlayerState* State, int32 Amount, const FString& Reason, const FString& SuccessMessage)
{
	if (!State || Amount <= 0)
	{
		return;
	}

	AController* Controller = Cast<AController>(State->GetOwner());
	if (!IsBackendEnabled() || State->CharacterId <= 0)
	{
		State->AddCash(Amount);
		ShowMessage(Controller, SuccessMessage);
		return;
	}

	TWeakObjectPtr<ABarrioGameMode> WeakThis(this);
	TWeakObjectPtr<ABarrioPlayerState> WeakState(State);
	GetBackend()->ApplyTransaction(State->CharacterId, Amount, Reason, [WeakThis, WeakState, SuccessMessage](bool bSuccess, int32 Balance, const FString& Error)
	{
		ABarrioGameMode* Self = WeakThis.Get();
		ABarrioPlayerState* PlayerState = WeakState.Get();
		if (!Self || !PlayerState)
		{
			return;
		}
		AController* OwnerController = Cast<AController>(PlayerState->GetOwner());
		if (bSuccess)
		{
			PlayerState->SetCash(Balance);
			Self->ShowMessage(OwnerController, SuccessMessage);
		}
		else
		{
			Self->ShowMessage(OwnerController, FString::Printf(TEXT("No se pudo guardar el dinero: %s"), *Error));
		}
	});
}

void ABarrioGameMode::HandleSellLoot(AController* Seller)
{
	ABarrioPlayerState* State = StateOf(Seller);
	if (!State || State->IsPolice() || State->IsWanted() || State->IsJailed() || State->GetCarriedLoot() <= 0)
	{
		return;
	}

	const int32 Loot = State->TakeCarriedLoot();
	if (!IsBackendEnabled() || State->CharacterId <= 0)
	{
		State->AddCash(Loot);
		ShowMessage(Seller, FString::Printf(TEXT("Vendiste el botín por $%d."), Loot));
		return;
	}

	// Con backend: si la venta falla, el botín vuelve al jugador.
	TWeakObjectPtr<ABarrioGameMode> WeakThis(this);
	TWeakObjectPtr<ABarrioPlayerState> WeakState(State);
	GetBackend()->ApplyTransaction(State->CharacterId, Loot, TEXT("sell_loot"), [WeakThis, WeakState, Loot](bool bSuccess, int32 Balance, const FString& Error)
	{
		ABarrioGameMode* Self = WeakThis.Get();
		ABarrioPlayerState* PlayerState = WeakState.Get();
		if (!Self || !PlayerState)
		{
			return;
		}
		AController* OwnerController = Cast<AController>(PlayerState->GetOwner());
		if (bSuccess)
		{
			PlayerState->SetCash(Balance);
			Self->ShowMessage(OwnerController, FString::Printf(TEXT("Vendiste el botín por $%d."), Loot));
		}
		else
		{
			PlayerState->AddCarriedLoot(Loot);
			Self->ShowMessage(OwnerController, FString::Printf(TEXT("El reducidor no pudo pagarte: %s"), *Error));
		}
	});
}

void ABarrioGameMode::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UBarrioGameEvents* Events = UBarrioGameEvents::Get(this))
	{
		for (const FDelegateHandle& Handle : EventHandles)
		{
			Events->OnAlarm.Remove(Handle);
			Events->OnDamage.Remove(Handle);
			Events->OnKill.Remove(Handle);
			Events->OnArrestRequested.Remove(Handle);
			Events->OnRoleRequested.Remove(Handle);
			Events->OnSellLootRequested.Remove(Handle);
		}
	}
	EventHandles.Reset();
	Super::EndPlay(EndPlayReason);
}

// ---------------------------------------------------------------------------------------------
// Aparición
// ---------------------------------------------------------------------------------------------

bool ABarrioGameMode::ShouldSpawnAtStartSpot_Implementation(AController* Player)
{
	return false; // siempre elegir según el rol y la cárcel
}

AActor* ABarrioGameMode::ChoosePlayerStart_Implementation(AController* Player)
{
	const ABarrioPlayerState* State = StateOf(Player);

	if (State && State->IsJailed())
	{
		for (TActorIterator<AJailCell> It(GetWorld()); It; ++It)
		{
			return *It;
		}
		UE_LOG(LogBarrio, Error, TEXT("No hay ninguna JailCell en el mapa: el preso aparece en un punto normal."));
	}

	const bool bPolice = State && State->IsPolice();
	TArray<APlayerStart*> Candidates;
	for (TActorIterator<APlayerStart> It(GetWorld()); It; ++It)
	{
		const bool bIsPoliceStart = It->PlayerStartTag == PoliceStartTag;
		if (bIsPoliceStart == bPolice)
		{
			Candidates.Add(*It);
		}
	}

	if (Candidates.Num() > 0)
	{
		return Candidates[FMath::RandRange(0, Candidates.Num() - 1)];
	}
	return Super::ChoosePlayerStart_Implementation(Player);
}

void ABarrioGameMode::RespawnNow(AController* Player)
{
	if (!Player)
	{
		return;
	}
	if (APawn* OldPawn = Player->GetPawn())
	{
		Player->UnPossess();
		OldPawn->Destroy();
	}
	RestartPlayer(Player);
}

void ABarrioGameMode::RespawnLater(TWeakObjectPtr<AController> Player)
{
	if (AController* Controller = Player.Get())
	{
		if (!Controller->GetPawn())
		{
			RestartPlayer(Controller);
		}
	}
}

// ---------------------------------------------------------------------------------------------
// Eventos
// ---------------------------------------------------------------------------------------------

void ABarrioGameMode::HandleAlarm(const FVector& Location, AController* Suspect)
{
	if (ABarrioPlayerState* SuspectState = StateOf(Suspect))
	{
		if (!SuspectState->IsPolice())
		{
			SuspectState->AddWanted(1, Now());
			ShowMessage(Suspect, TEXT("¡Sonó la alarma! Estás buscado."));
		}
	}

	// Avisar a los policías cercanos; si no hay ninguno cerca, a todos.
	TArray<ABarrioPlayerController*> Nearby;
	TArray<ABarrioPlayerController*> AllPolice;
	for (APlayerState* PlayerState : GameState->PlayerArray)
	{
		const ABarrioPlayerState* State = Cast<ABarrioPlayerState>(PlayerState);
		ABarrioPlayerController* Controller = State ? Cast<ABarrioPlayerController>(State->GetOwner()) : nullptr;
		if (!State || !Controller || !State->IsPolice())
		{
			continue;
		}

		AllPolice.Add(Controller);
		const APawn* Pawn = Controller->GetPawn();
		if (Pawn && FVector::DistSquared(Pawn->GetActorLocation(), Location) <= FMath::Square(AlarmAlertRadius))
		{
			Nearby.Add(Controller);
		}
	}

	for (ABarrioPlayerController* Controller : (Nearby.Num() > 0 ? Nearby : AllPolice))
	{
		Controller->ClientNotifyAlarm(Location);
	}
}

void ABarrioGameMode::HandleDamage(AController* Victim, AController* DamageInstigator, float Damage)
{
	ABarrioPlayerState* VictimState = StateOf(Victim);
	ABarrioPlayerState* ShooterState = StateOf(DamageInstigator);
	if (!VictimState || !ShooterState || Victim == DamageInstigator || ShooterState->IsPolice())
	{
		return;
	}

	// Un civil que le dispara a un policía o a un inocente pasa a estar buscado.
	if (VictimState->IsPolice() || !VictimState->IsWanted())
	{
		if (ShooterState->IsWanted())
		{
			ShooterState->LastCrimeTime = Now(); // no baja el nivel mientras siga disparando
		}
		else
		{
			ShooterState->AddWanted(1, Now());
		}
	}
}

void ABarrioGameMode::HandleKill(AController* Victim, AController* Killer)
{
	ABarrioPlayerState* VictimState = StateOf(Victim);
	ABarrioPlayerState* KillerState = StateOf(Killer);

	if (VictimState && KillerState && Victim != Killer)
	{
		if (KillerState->IsPolice())
		{
			if (VictimState->IsWanted())
			{
				RewardPolice(KillerState, VictimState->GetWantedLevel());
				Jail(VictimState); // reaparece en la cárcel
				ShowMessage(Victim, TEXT("Te abatió la policía. Vas a la cárcel."));
			}
			else
			{
				UE_LOG(LogBarrio, Warning, TEXT("Un policía mató a un civil no buscado (%s)."), *GetNameSafe(VictimState));
			}
		}
		else
		{
			KillerState->AddWanted(VictimState->IsPolice() ? 3 : (VictimState->IsWanted() ? 0 : 2), Now());
		}
	}

	if (VictimState)
	{
		VictimState->TakeCarriedLoot(); // el botín se pierde al morir
		VictimState->ClearRobbery();
	}

	// El cuerpo queda unos segundos; el jugador reaparece después.
	if (Victim)
	{
		if (APawn* Body = Victim->GetPawn())
		{
			Victim->UnPossess();
			Body->SetLifeSpan(15.f);
		}

		FTimerHandle Handle;
		GetWorldTimerManager().SetTimer(Handle,
			FTimerDelegate::CreateUObject(this, &ABarrioGameMode::RespawnLater, TWeakObjectPtr<AController>(Victim)),
			RespawnDelay, false);
	}
}

void ABarrioGameMode::HandleArrest(AController* Police, AController* Suspect)
{
	ABarrioPlayerState* PoliceState = StateOf(Police);
	ABarrioPlayerState* SuspectState = StateOf(Suspect);
	if (!PoliceState || !SuspectState || !PoliceState->IsPolice() || !SuspectState->IsWanted() || SuspectState->IsJailed())
	{
		return;
	}

	RewardPolice(PoliceState, SuspectState->GetWantedLevel());
	Jail(SuspectState);
	ShowMessage(Suspect, TEXT("Te arrestaron."));
	RespawnNow(Suspect);
}

void ABarrioGameMode::HandleRoleRequest(AController* Player, EBarrioRole RequestedRole)
{
	ABarrioPlayerState* State = StateOf(Player);
	if (!State || State->IsJailed() || State->GetBarrioRole() == RequestedRole)
	{
		return;
	}

	if (RequestedRole == EBarrioRole::Police)
	{
		if (State->IsWanted() || State->GetCarriedLoot() > 0)
		{
			ShowMessage(Player, TEXT("No podés unirte a la policía estando buscado o con botín encima."));
			return;
		}
		if (CountPolice() >= GetPoliceQuota())
		{
			ShowMessage(Player, FString::Printf(TEXT("Cupo de policía completo (%d)."), GetPoliceQuota()));
			return;
		}
	}

	State->SetBarrioRole(RequestedRole);
	ShowMessage(Player, RequestedRole == EBarrioRole::Police ? TEXT("Ahora sos policía.") : TEXT("Dejaste la policía."));
	RespawnNow(Player);
}

// ---------------------------------------------------------------------------------------------
// Reglas periódicas
// ---------------------------------------------------------------------------------------------

void ABarrioGameMode::TickRules()
{
	const float Time = Now();

	for (APlayerState* PlayerState : GameState->PlayerArray)
	{
		ABarrioPlayerState* State = Cast<ABarrioPlayerState>(PlayerState);
		if (!State)
		{
			continue;
		}

		if (State->IsJailed() && Time >= State->GetJailReleaseTime())
		{
			State->SetJailed(false, 0.f);
			AController* Controller = Cast<AController>(State->GetOwner());
			ShowMessage(Controller, TEXT("Cumpliste la condena. Estás libre."));
			RespawnNow(Controller);
		}

		if (State->IsWanted() && Time - State->LastCrimeTime >= WantedDecayInterval)
		{
			State->SetWantedLevel(State->GetWantedLevel() - 1);
			State->LastCrimeTime = Time;
		}
	}
}

void ABarrioGameMode::Jail(ABarrioPlayerState* Suspect)
{
	const float Sentence = JailBaseTime + JailTimePerWantedLevel * Suspect->GetWantedLevel();
	Suspect->SetJailed(true, Now() + Sentence);
	Suspect->SetWantedLevel(0);
	Suspect->TakeCarriedLoot();
	Suspect->ClearRobbery();
	UE_LOG(LogBarrio, Log, TEXT("%s va preso por %.0f s."), *Suspect->GetPlayerName(), Sentence);
}

void ABarrioGameMode::RewardPolice(ABarrioPlayerState* Police, int32 WantedLevel)
{
	const int32 Reward = ArrestRewardPerWantedLevel * FMath::Max(1, WantedLevel);
	GrantCash(Police, Reward, TEXT("arrest_reward"), FString::Printf(TEXT("Captura: +$%d"), Reward));
}

void ABarrioGameMode::ShowMessage(AController* Player, const FString& Message) const
{
	if (ABarrioPlayerController* Controller = Cast<ABarrioPlayerController>(Player))
	{
		Controller->ClientShowMessage(Message);
	}
}

int32 ABarrioGameMode::CountPolice() const
{
	int32 Count = 0;
	for (const APlayerState* PlayerState : GameState->PlayerArray)
	{
		const ABarrioPlayerState* State = Cast<ABarrioPlayerState>(PlayerState);
		Count += (State && State->IsPolice()) ? 1 : 0;
	}
	return Count;
}

int32 ABarrioGameMode::GetPoliceQuota() const
{
	return FMath::Clamp(GetNumPlayers() / FMath::Max(1, PlayersPerPolice), 1, MaxPolice);
}
