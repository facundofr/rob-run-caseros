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
		EventHandles.Add(Events->OnCuffRequested.AddUObject(this, &ABarrioGameMode::HandleCuffRequested));
		EventHandles.Add(Events->OnRoleRequested.AddUObject(this, &ABarrioGameMode::HandleRoleRequest));
		EventHandles.Add(Events->OnSellLootRequested.AddUObject(this, &ABarrioGameMode::HandleSellLoot));
		EventHandles.Add(Events->OnMaskRequested.AddUObject(this, &ABarrioGameMode::HandleMaskRequested));
		EventHandles.Add(Events->OnSurrenderToggled.AddUObject(this, &ABarrioGameMode::HandleSurrenderToggled));
		EventHandles.Add(Events->OnSurrenderOrder.AddUObject(this, &ABarrioGameMode::HandleSurrenderOrder));
		EventHandles.Add(Events->OnLeftNeighborhood.AddUObject(this, &ABarrioGameMode::HandleLeftNeighborhood));
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

	if (ABarrioPlayerState* State = StateOf(Exiting))
	{
		if (State->IsPolice())
		{
			PayShift(State, FString()); // el policía cobra lo acumulado aunque se desconecte
		}
		else if (State->IsCriminal())
		{
			// Desconectarse siendo ladrón = morir: el botín no se guarda en ningún lado y se pierde.
			UE_LOG(LogBarrio, Log, TEXT("%s se desconectó siendo ladrón: pierde $%d de botín."), *State->GetPlayerName(), State->GetCarriedLoot());
		}
	}
	SuspectsBeingCuffed.Remove(Exiting);
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
	if (!State || !State->IsCivilian() || State->IsJailed() || State->GetCarriedLoot() <= 0)
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
			Events->OnCuffRequested.Remove(Handle);
			Events->OnRoleRequested.Remove(Handle);
			Events->OnSellLootRequested.Remove(Handle);
			Events->OnMaskRequested.Remove(Handle);
			Events->OnSurrenderToggled.Remove(Handle);
			Events->OnSurrenderOrder.Remove(Handle);
			Events->OnLeftNeighborhood.Remove(Handle);
		}
	}
	EventHandles.Reset();
	Super::EndPlay(EndPlayReason);
}

// ---------------------------------------------------------------------------------------------
// Aparición
// ---------------------------------------------------------------------------------------------

bool ABarrioGameMode::ShouldSpawnAtStartSpot(AController* Player)
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

		// El policía reaparece con unos segundos de protección.
		if (ABarrioPlayerState* State = StateOf(Controller))
		{
			if (State->IsPolice())
			{
				State->SpawnProtectedUntil = Now() + PoliceSpawnProtection;
			}
		}
	}
}

// ---------------------------------------------------------------------------------------------
// Eventos
// ---------------------------------------------------------------------------------------------

void ABarrioGameMode::HandleAlarm(const FVector& Location, AController* Suspect)
{
	// La alarma marca DÓNDE está pasando el robo; no identifica al ladrón ni sube su búsqueda.
	ShowMessage(Suspect, TEXT("¡Sonó la alarma! La policía va a venir."));

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
	if (!VictimState || !ShooterState || Victim == DamageInstigator)
	{
		return;
	}

	// Un ladrón que lastima vecinos no deja bajar su nivel de búsqueda mientras siga.
	if (ShooterState->IsCriminal() && VictimState->IsCivilian() && ShooterState->GetWantedLevel() > 0)
	{
		ShooterState->LastCrimeTime = Now();
	}
}

void ABarrioGameMode::HandleKill(AController* Victim, AController* Killer)
{
	ABarrioPlayerState* VictimState = StateOf(Victim);
	ABarrioPlayerState* KillerState = StateOf(Killer);

	if (VictimState && KillerState && Victim != Killer)
	{
		if (KillerState->IsPolice() && VictimState->IsCriminal())
		{
			// Matar a un rendido no paga: la regla empuja a arrestar vivo.
			if (VictimState->IsSurrendered())
			{
				ShowMessage(Killer, TEXT("Mataste a un ladrón rendido: no se paga."));
				UE_LOG(LogBarrio, Warning, TEXT("%s mató a un ladrón rendido."), *KillerState->GetPlayerName());
			}
			else
			{
				KillerState->AddShiftEarnings(KillCriminalReward);
				ShowMessage(Killer, FString::Printf(TEXT("Ladrón abatido: +$%d (arrestarlo paga mucho más)."), KillCriminalReward));
			}
		}
		else if (KillerState->IsCriminal() && VictimState->IsCivilian())
		{
			KillerState->AddWanted(1, Now()); // +1 por cada vecino muerto; en 3, toda la ciudad lo ve
		}
	}

	if (VictimState)
	{
		// Al morir se pierde el botín. El ladrón pierde además su condición: vuelve como vecino.
		VictimState->TakeCarriedLoot();
		VictimState->ClearAction();
		if (VictimState->IsCriminal())
		{
			VictimState->ResetCriminalState();
			ShowMessage(Victim, TEXT("Moriste como ladrón: perdiste todo lo que llevabas."));
		}
	}
	SuspectsBeingCuffed.Remove(Victim);

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

// --- Pasamontañas ------------------------------------------------------------------------------

void ABarrioGameMode::HandleMaskRequested(AController* Player)
{
	ABarrioPlayerState* State = StateOf(Player);
	const APawn* Pawn = Player ? Player->GetPawn() : nullptr;
	const UBarrioGameEvents* Events = UBarrioGameEvents::Get(this);
	if (!State || !Pawn || !Events || !State->IsCivilian() || State->IsJailed() || State->GetActionKind() != EBarrioActionKind::None)
	{
		return;
	}
	if (Events->IsInSafeZone(Pawn->GetActorLocation()))
	{
		ShowMessage(Player, TEXT("Acá no te podés poner el pasamontañas."));
		return;
	}

	State->SetAction(EBarrioActionKind::PuttingMask, Now() + MaskDuration, MaskDuration);
	FTimerHandle Handle;
	GetWorldTimerManager().SetTimer(Handle,
		FTimerDelegate::CreateUObject(this, &ABarrioGameMode::FinishMask, TWeakObjectPtr<AController>(Player)), MaskDuration, false);
}

void ABarrioGameMode::FinishMask(TWeakObjectPtr<AController> Player)
{
	AController* Controller = Player.Get();
	ABarrioPlayerState* State = StateOf(Controller);
	const APawn* Pawn = Controller ? Controller->GetPawn() : nullptr;
	const UBarrioGameEvents* Events = UBarrioGameEvents::Get(this);
	if (!State || State->GetActionKind() != EBarrioActionKind::PuttingMask)
	{
		return;
	}
	State->ClearAction();

	if (!Pawn || !Events || !State->IsCivilian() || Events->IsInSafeZone(Pawn->GetActorLocation()))
	{
		return;
	}

	State->SetBarrioRole(EBarrioRole::Criminal);
	ShowMessage(Controller, TEXT("Te pusiste el pasamontañas. Sos ladrón hasta que salgas del barrio."));
}

// --- Salida del barrio -------------------------------------------------------------------------

void ABarrioGameMode::HandleLeftNeighborhood(AController* Player)
{
	ABarrioPlayerState* State = StateOf(Player);
	if (!State || !State->IsCriminal() || State->IsSurrendered())
	{
		return; // un ladrón rendido no escapa caminando
	}

	State->ResetCriminalState();
	State->ClearAction();
	SuspectsBeingCuffed.Remove(Player);
	ShowMessage(Player, State->GetCarriedLoot() > 0
		? TEXT("Saliste del barrio: ya no sos ladrón. Vendé el botín al reducidor.")
		: TEXT("Saliste del barrio: ya no sos ladrón."));
}

// --- Rendición y esposas -----------------------------------------------------------------------

void ABarrioGameMode::HandleSurrenderToggled(AController* Player)
{
	ABarrioPlayerState* State = StateOf(Player);
	if (!State || !State->IsCriminal() || SuspectsBeingCuffed.Contains(Player))
	{
		return; // mientras lo esposan no puede dejar de estar rendido
	}

	const bool bSurrender = !State->IsSurrendered();
	State->SetCaptureState(bSurrender ? EBarrioCaptureState::Surrendered : EBarrioCaptureState::Free);
	ShowMessage(Player, bSurrender
		? TEXT("Te rendiste: no podés disparar ni correr. Q para dejar de estar rendido.")
		: TEXT("Ya no estás rendido."));
}

void ABarrioGameMode::HandleSurrenderOrder(AController* Police)
{
	ABarrioPlayerState* PoliceState = StateOf(Police);
	const APawn* PolicePawn = Police ? Police->GetPawn() : nullptr;
	if (!PoliceState || !PoliceState->IsPolice() || !PolicePawn)
	{
		return;
	}

	PoliceState->LastSurrenderOrderTime = Now();
	ShowMessage(Police, TEXT("Diste la orden de rendición: el próximo arresto paga +20 %."));

	for (APlayerState* PlayerState : GameState->PlayerArray)
	{
		const ABarrioPlayerState* State = Cast<ABarrioPlayerState>(PlayerState);
		const APawn* Pawn = State ? State->GetPawn() : nullptr;
		if (State && Pawn && State->IsCriminal()
			&& FVector::DistSquared(Pawn->GetActorLocation(), PolicePawn->GetActorLocation()) <= FMath::Square(SurrenderOrderRadius))
		{
			ShowMessage(Cast<AController>(State->GetOwner()), TEXT("¡POLICÍA! ¡Rendite! (Q)"));
		}
	}
}

void ABarrioGameMode::HandleCuffRequested(AController* Police, AController* Suspect)
{
	ABarrioPlayerState* PoliceState = StateOf(Police);
	ABarrioPlayerState* SuspectState = StateOf(Suspect);
	if (!PoliceState || !SuspectState || !PoliceState->IsPolice() || !SuspectState->IsCriminal()
		|| SuspectState->IsJailed() || SuspectsBeingCuffed.Contains(Suspect)
		|| PoliceState->GetActionKind() != EBarrioActionKind::None)
	{
		return;
	}

	SuspectsBeingCuffed.Add(Suspect);
	PoliceState->SetAction(EBarrioActionKind::Cuffing, Now() + CuffDuration, CuffDuration);
	ShowMessage(Suspect, TEXT("Te están esposando."));

	FTimerHandle Handle;
	GetWorldTimerManager().SetTimer(Handle,
		FTimerDelegate::CreateUObject(this, &ABarrioGameMode::FinishCuffing, TWeakObjectPtr<AController>(Police), TWeakObjectPtr<AController>(Suspect)),
		CuffDuration, false);
}

void ABarrioGameMode::FinishCuffing(TWeakObjectPtr<AController> Police, TWeakObjectPtr<AController> Suspect)
{
	AController* PoliceController = Police.Get();
	AController* SuspectController = Suspect.Get();
	SuspectsBeingCuffed.Remove(Suspect);

	ABarrioPlayerState* PoliceState = StateOf(PoliceController);
	if (PoliceState)
	{
		PoliceState->ClearAction();
	}

	APawn* PolicePawn = PoliceController ? PoliceController->GetPawn() : nullptr;
	APawn* SuspectPawn = SuspectController ? SuspectController->GetPawn() : nullptr;
	if (!PoliceState || !PolicePawn || !SuspectPawn)
	{
		return;
	}

	// Al terminar los 2,5 s tiene que seguir cerca y seguir siendo esposable (rendido o reducido).
	const bool bClose = FVector::DistSquared(PolicePawn->GetActorLocation(), SuspectPawn->GetActorLocation()) <= FMath::Square(CuffMaxDistance);
	const bool bStillValid = SuspectPawn->Implements<UInteractable>() && IInteractable::Execute_CanInteract(SuspectPawn, PolicePawn);
	if (!bClose || !bStillValid)
	{
		ShowMessage(PoliceController, TEXT("Se te escapó: no pudiste esposarlo."));
		return;
	}

	Arrest(PoliceController, SuspectController);
}

void ABarrioGameMode::Arrest(AController* Police, AController* Suspect)
{
	ABarrioPlayerState* PoliceState = StateOf(Police);
	ABarrioPlayerState* SuspectState = StateOf(Suspect);
	if (!PoliceState || !SuspectState)
	{
		return;
	}

	// Arrestar paga mucho más que abatir: base + parte del botín confiscado (+20 % con orden de rendición).
	const int32 Confiscated = SuspectState->TakeCarriedLoot();
	float Reward = ArrestBaseReward + Confiscated * ArrestLootShare;
	if (Now() - PoliceState->LastSurrenderOrderTime <= SurrenderOrderWindow)
	{
		Reward *= 1.f + SurrenderOrderBonus;
	}
	const int32 Paid = FMath::RoundToInt(Reward);
	PoliceState->AddShiftEarnings(Paid);

	ShowMessage(Police, FString::Printf(TEXT("Arresto: +$%d (se cobra al terminar el turno). Botín confiscado: $%d."), Paid, Confiscated));
	ShowMessage(Suspect, TEXT("Te arrestaron: perdiste el botín y vas a la celda."));
	Jail(SuspectState);
	RespawnNow(Suspect);
}

// --- Comisaría: entrar de servicio y terminar el turno -----------------------------------------

void ABarrioGameMode::HandleRoleRequest(AController* Player, EBarrioRole RequestedRole)
{
	ABarrioPlayerState* State = StateOf(Player);
	if (!State || State->IsJailed() || State->GetBarrioRole() == RequestedRole)
	{
		return;
	}

	if (RequestedRole == EBarrioRole::Police)
	{
		if (!State->IsCivilian() || State->GetCarriedLoot() > 0)
		{
			ShowMessage(Player, TEXT("Para entrar de servicio tenés que ser vecino y no llevar botín."));
			return;
		}
		if (CountPolice() >= GetPoliceQuota())
		{
			ShowMessage(Player, FString::Printf(TEXT("Cupo de policía completo (%d)."), GetPoliceQuota()));
			return;
		}

		State->SetBarrioRole(EBarrioRole::Police);
		ShowMessage(Player, TEXT("Entraste de servicio. Solo podés dañar ladrones; arrestar paga más que abatir."));
		RespawnNow(Player);
		return;
	}

	if (RequestedRole == EBarrioRole::Civilian && State->IsPolice())
	{
		PayShift(State, TEXT("Terminaste el turno."));
		State->SetBarrioRole(EBarrioRole::Civilian);
		RespawnNow(Player);
	}
}

void ABarrioGameMode::PayShift(ABarrioPlayerState* Police, const FString& Message)
{
	const int32 Earned = FMath::Min(Police->TakeShiftEarnings(), ShiftSalaryCap);
	AController* Controller = Cast<AController>(Police->GetOwner());
	if (Earned <= 0)
	{
		if (!Message.IsEmpty())
		{
			ShowMessage(Controller, Message + TEXT(" No hubo ganancias en este turno."));
		}
		return;
	}
	GrantCash(Police, Earned, TEXT("police_salary"), FString::Printf(TEXT("%s Cobraste $%d."), *Message, Earned));
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

		if (State->GetWantedLevel() > 0 && Time - State->LastCrimeTime >= WantedDecayInterval)
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
	Suspect->ResetCriminalState(); // sale de la celda como vecino
	Suspect->TakeCarriedLoot();
	Suspect->ClearAction();
	UE_LOG(LogBarrio, Log, TEXT("%s va preso por %.0f s."), *Suspect->GetPlayerName(), Sentence);
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
	// GetNumPlayers() del motor no es const: se cuentan los jugadores humanos a mano.
	int32 NumPlayers = 0;
	for (const APlayerState* PlayerState : GameState->PlayerArray)
	{
		NumPlayers += (PlayerState && !PlayerState->IsABot()) ? 1 : 0;
	}
	return FMath::Clamp(NumPlayers / FMath::Max(1, PlayersPerPolice), 1, MaxPolice);
}
