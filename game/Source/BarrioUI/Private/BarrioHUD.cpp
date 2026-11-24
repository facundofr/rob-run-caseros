#include "BarrioHUD.h"

#include "BarrioAuthSubsystem.h"
#include "BarrioCharacter.h"
#include "BarrioHealthComponent.h"
#include "BarrioOnlineSettings.h"
#include "BarrioPlayerController.h"
#include "BarrioPlayerState.h"
#include "BarrioWeaponComponent.h"
#include "SBarrioLoginScreen.h"

#include "Camera/PlayerCameraManager.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/GameInstance.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/GameStateBase.h"

namespace
{
	const FLinearColor PoliceColor(0.3f, 0.55f, 1.f);
	const FLinearColor WantedColor(1.f, 0.25f, 0.2f);
	const FLinearColor AlarmColor(1.f, 0.1f, 0.1f);

	const TCHAR* DescribeNetMode(ENetMode Mode)
	{
		switch (Mode)
		{
		case NM_Client:          return TEXT("Cliente");
		case NM_ListenServer:    return TEXT("Servidor (host)");
		case NM_DedicatedServer: return TEXT("Servidor dedicado");
		default:                 return TEXT("Local");
		}
	}

	FString Stars(int32 Level)
	{
		FString Result;
		for (int32 Index = 0; Index < ABarrioPlayerState::MaxWantedLevel; ++Index)
		{
			Result += Index < Level ? TEXT("*") : TEXT("-");
		}
		return Result;
	}
}

// ---------------------------------------------------------------------------------------------
// Pantalla de login
// ---------------------------------------------------------------------------------------------

bool ABarrioHUD::ShouldShowLogin() const
{
	const UBarrioOnlineSettings* Settings = GetDefault<UBarrioOnlineSettings>();
	const UGameInstance* GameInstance = GetGameInstance();
	const UBarrioAuthSubsystem* Auth = GameInstance ? GameInstance->GetSubsystem<UBarrioAuthSubsystem>() : nullptr;

	// Solo en el juego abierto sin conexión (no en una partida en red) y sin sesión iniciada.
	return Settings->bRequireLogin
		&& (!GIsEditor || Settings->bShowLoginInEditor)
		&& GetNetMode() == NM_Standalone
		&& PlayerOwner && PlayerOwner->IsLocalController()
		&& Auth && !Auth->IsLoggedIn();
}

void ABarrioHUD::BeginPlay()
{
	Super::BeginPlay();
	if (ShouldShowLogin())
	{
		ShowLogin();
	}
}

void ABarrioHUD::ShowLogin()
{
	UGameViewportClient* Viewport = GEngine ? GEngine->GameViewport : nullptr;
	UBarrioAuthSubsystem* Auth = GetGameInstance()->GetSubsystem<UBarrioAuthSubsystem>();
	if (!Viewport || !Auth)
	{
		return;
	}

	// El viewport guarda una referencia fuerte a la pantalla hasta que se quita en EndPlay.
	TSharedRef<SBarrioLoginScreen> Screen = SNew(SBarrioLoginScreen).Auth(Auth);
	LoginOverlay = Screen;
	Viewport->AddViewportWidgetContent(Screen, 100);

	FInputModeUIOnly InputMode;
	InputMode.SetWidgetToFocus(Screen->GetInitialFocus());
	PlayerOwner->SetInputMode(InputMode);
	PlayerOwner->SetShowMouseCursor(true);
}

void ABarrioHUD::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (LoginOverlay.IsValid() && GEngine && GEngine->GameViewport)
	{
		GEngine->GameViewport->RemoveViewportWidgetContent(LoginOverlay.ToSharedRef());
	}
	LoginOverlay.Reset();
	Super::EndPlay(EndPlayReason);
}

// ---------------------------------------------------------------------------------------------
// HUD de juego
// ---------------------------------------------------------------------------------------------

void ABarrioHUD::DrawHUD()
{
	Super::DrawHUD();

	if (!Canvas || !PlayerOwner || LoginOverlay.IsValid())
	{
		return; // con la pantalla de login abierta no se dibuja el HUD de juego
	}

	UFont* Font = GEngine ? GEngine->GetMediumFont() : nullptr;
	UFont* BigFont = GEngine ? GEngine->GetLargeFont() : Font;
	const float CenterX = Canvas->ClipX * 0.5f;
	const float CenterY = Canvas->ClipY * 0.5f;
	const AGameStateBase* GameStateBase = GetWorld()->GetGameState();
	const float ServerTime = GameStateBase ? GameStateBase->GetServerWorldTimeSeconds() : GetWorld()->GetTimeSeconds();

	const ABarrioPlayerState* MyState = PlayerOwner->GetPlayerState<ABarrioPlayerState>();
	const ABarrioCharacter* Character = Cast<ABarrioCharacter>(GetOwningPawn());
	const ABarrioPlayerController* Controller = Cast<ABarrioPlayerController>(PlayerOwner);

	auto DrawCentered = [this](const FString& Text, const FLinearColor& Color, float Y, UFont* InFont)
	{
		float Width = 0.f;
		float Height = 0.f;
		GetTextSize(Text, Width, Height, InFont);
		DrawText(Text, Color, Canvas->ClipX * 0.5f - Width * 0.5f, Y, InFont);
	};

	// --- Cárcel ---------------------------------------------------------------------------
	if (MyState && MyState->IsJailed())
	{
		const int32 Remaining = FMath::Max(0, FMath::CeilToInt(MyState->GetJailReleaseTime() - ServerTime));
		DrawCentered(FString::Printf(TEXT("EN LA CÁRCEL: %d s"), Remaining), WantedColor, 80.f, BigFont);
	}

	// --- Mira y aviso de interacción ------------------------------------------------------
	if (Character && !Character->IsDead())
	{
		DrawLine(CenterX - 6.f, CenterY, CenterX + 6.f, CenterY, FLinearColor::White, 1.5f);
		DrawLine(CenterX, CenterY - 6.f, CenterX, CenterY + 6.f, FLinearColor::White, 1.5f);

		const FText Prompt = Character->GetFocusedInteractionText();
		if (!Prompt.IsEmpty())
		{
			DrawCentered(FString::Printf(TEXT("[E] %s"), *Prompt.ToString()), FLinearColor::Yellow, CenterY + 40.f, Font);
		}
	}
	else if (!MyState || !MyState->IsJailed())
	{
		DrawCentered(TEXT("Reapareciendo en unos segundos..."), WantedColor, CenterY - 20.f, BigFont);
	}

	// --- Barra de la acción en curso (robo, pasamontañas, esposas) ------------------------
	if (MyState && MyState->GetActionKind() != EBarrioActionKind::None && MyState->GetActionDuration() > 0.f)
	{
		const float Remaining = MyState->GetActionEndTime() - ServerTime;
		const float Progress = FMath::Clamp(1.f - Remaining / MyState->GetActionDuration(), 0.f, 1.f);
		const float BarWidth = 300.f;
		const float BarY = CenterY + 80.f;
		DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.6f), CenterX - BarWidth * 0.5f, BarY, BarWidth, 14.f);
		DrawRect(FLinearColor(0.9f, 0.75f, 0.1f), CenterX - BarWidth * 0.5f, BarY, BarWidth * Progress, 14.f);

		const TCHAR* Label = TEXT("");
		switch (MyState->GetActionKind())
		{
		case EBarrioActionKind::Robbery:     Label = TEXT("Robando... (no te alejes)"); break;
		case EBarrioActionKind::PuttingMask: Label = TEXT("Poniéndote el pasamontañas..."); break;
		case EBarrioActionKind::Cuffing:     Label = TEXT("Esposando... (quedate cerca)"); break;
		default: break;
		}
		DrawCentered(Label, FLinearColor::White, BarY + 18.f, Font);
	}

	// --- Panel del jugador (arriba a la izquierda) ----------------------------------------
	float PanelY = 20.f;
	auto PanelLine = [this, &PanelY, Font](const FString& Text, const FLinearColor& Color)
	{
		DrawText(Text, Color, 20.f, PanelY, Font);
		PanelY += 22.f;
	};

	if (MyState)
	{
		switch (MyState->GetBarrioRole())
		{
		case EBarrioRole::Police:
			PanelLine(TEXT("POLICÍA (de servicio)"), PoliceColor);
			PanelLine(FString::Printf(TEXT("Ganancias del turno: $%d"), MyState->GetShiftEarnings()), FLinearColor::Green);
			PanelLine(TEXT("Q: orden de rendición  |  E: esposar"), FLinearColor::Gray);
			break;
		case EBarrioRole::Criminal:
			PanelLine(MyState->IsSurrendered() ? TEXT("LADRÓN (RENDIDO)") : TEXT("LADRÓN"), WantedColor);
			PanelLine(FString::Printf(TEXT("Botín encima: $%d"), MyState->GetCarriedLoot()), FLinearColor::Yellow);
			PanelLine(FString::Printf(TEXT("Notoriedad: %d (botín +%d %%)"), MyState->GetNotoriety(), MyState->GetNotoriety() * 10), FLinearColor::Yellow);
			PanelLine(FString::Printf(TEXT("Búsqueda: %s"), *Stars(MyState->GetWantedLevel())), MyState->GetWantedLevel() > 0 ? WantedColor : FLinearColor::Gray);
			PanelLine(TEXT("Escapá por una salida del barrio  |  Q: rendirse"), FLinearColor::Gray);
			break;
		default:
			PanelLine(TEXT("VECINO"), FLinearColor::White);
			if (MyState->GetCarriedLoot() > 0)
			{
				PanelLine(FString::Printf(TEXT("Botín para vender: $%d"), MyState->GetCarriedLoot()), FLinearColor::Yellow);
			}
			PanelLine(TEXT("G: ponerse el pasamontañas"), FLinearColor::Gray);
			break;
		}
		PanelLine(FString::Printf(TEXT("Banco: $%d"), MyState->GetCash()), FLinearColor::Green);
	}

	if (Character)
	{
		if (const UBarrioHealthComponent* Health = Character->GetHealth())
		{
			PanelLine(FString::Printf(TEXT("Vida: %.0f"), Health->GetHealth()), FLinearColor::White);
		}
		if (const UBarrioWeaponComponent* Weapon = Character->GetWeapon())
		{
			PanelLine(Weapon->IsReloading()
				? FString(TEXT("Recargando..."))
				: FString::Printf(TEXT("Balas: %d / %d"), Weapon->GetAmmo(), Weapon->MagazineSize), FLinearColor::White);
		}
	}

	// --- Mensaje del servidor -------------------------------------------------------------
	if (Controller)
	{
		const FString Message = Controller->GetCurrentMessage();
		if (!Message.IsEmpty())
		{
			DrawCentered(Message, FLinearColor::White, 130.f, Font);
		}
	}

	// --- Marcas sobre otros jugadores y alarmas -------------------------------------------
	const APlayerCameraManager* Camera = PlayerOwner->PlayerCameraManager;
	if (Camera && GameStateBase)
	{
		const FVector CameraLocation = Camera->GetCameraLocation();
		const FVector CameraForward = Camera->GetCameraRotation().Vector();
		auto IsInFront = [&](const FVector& Location) { return FVector::DotProduct(Location - CameraLocation, CameraForward) > 0.f; };

		for (const APlayerState* PlayerState : GameStateBase->PlayerArray)
		{
			const ABarrioPlayerState* Other = Cast<ABarrioPlayerState>(PlayerState);
			const APawn* OtherPawn = Other ? Other->GetPawn() : nullptr;
			if (!OtherPawn || Other == MyState)
			{
				continue;
			}

			const FVector Head = OtherPawn->GetActorLocation() + FVector(0.f, 0.f, 120.f);
			const float Distance = FVector::Dist(Head, CameraLocation);
			// Los "más buscados" (nivel 3) se ven desde cualquier distancia: toda la ciudad sabe dónde están.
			const bool bVisibleFromAfar = Other->IsMostWanted();
			if ((!bVisibleFromAfar && Distance > 4000.f) || !IsInFront(Head))
			{
				continue;
			}

			FString Label;
			FLinearColor Color = FLinearColor::White;
			if (Other->IsPolice())
			{
				Label = TEXT("POLICÍA");
				Color = PoliceColor;
			}
			else if (Other->IsCriminal())
			{
				Label = Other->IsSurrendered() ? TEXT("LADRÓN (RENDIDO)") : TEXT("LADRÓN");
				if (Other->GetWantedLevel() > 0)
				{
					Label += FString::Printf(TEXT(" %s"), *Stars(Other->GetWantedLevel()));
				}
				if (bVisibleFromAfar)
				{
					Label += FString::Printf(TEXT(" - MÁS BUSCADO (%d m)"), FMath::RoundToInt(Distance / 100.f));
				}
				Color = WantedColor;
			}
			else
			{
				continue; // los vecinos no llevan marca
			}

			const FVector Screen = Project(Head);
			float Width = 0.f;
			float Height = 0.f;
			GetTextSize(Label, Width, Height, Font);
			DrawText(Label, Color, Screen.X - Width * 0.5f, Screen.Y, Font);
		}

		if (Controller)
		{
			for (const FBarrioAlarmMarker& Alarm : Controller->GetActiveAlarms())
			{
				const int32 Meters = FMath::RoundToInt(FVector::Dist(Alarm.Location, CameraLocation) / 100.f);
				if (IsInFront(Alarm.Location))
				{
					const FVector Screen = Project(Alarm.Location + FVector(0.f, 0.f, 300.f));
					DrawText(FString::Printf(TEXT("ALARMA %d m"), Meters), AlarmColor, Screen.X - 40.f, Screen.Y, Font);
				}
				else
				{
					PanelLine(FString::Printf(TEXT("ALARMA a %d m (detrás tuyo)"), Meters), AlarmColor);
				}
			}
		}
	}

	// --- Línea de estado (abajo) ----------------------------------------------------------
	if (Character)
	{
		const UCharacterMovementComponent* Movement = Character->GetCharacterMovement();
		const TCHAR* MoveState = TEXT("Quieto");
		if (Movement && Movement->IsFalling())          { MoveState = TEXT("En el aire"); }
		else if (Character->bIsCrouched)                { MoveState = TEXT("Agachado"); }
		else if (Character->IsSprinting())              { MoveState = TEXT("Corriendo"); }
		else if (Character->GetVelocity().Size2D() > 10.f) { MoveState = TEXT("Caminando"); }

		const float SpeedKmh = Character->GetVelocity().Size2D() * 0.036f; // cm/s a km/h
		DrawText(FString::Printf(TEXT("%s  |  %.1f km/h  |  %s"), DescribeNetMode(GetNetMode()), SpeedKmh, MoveState),
			FLinearColor::White, 20.f, Canvas->ClipY - 40.f, Font);
	}
}
