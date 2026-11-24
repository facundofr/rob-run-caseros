#include "BarrioAuthSubsystem.h"

#include "BarrioHttp.h"
#include "BarrioLog.h"
#include "BarrioOnlineSettings.h"
#include "Dom/JsonObject.h"
#include "Engine/GameInstance.h"
#include "GameFramework/PlayerController.h"

FString UBarrioAuthSubsystem::ApiUrl(const TCHAR* Path) const
{
	FString Base = GetDefault<UBarrioOnlineSettings>()->BackendUrl;
	Base.RemoveFromEnd(TEXT("/"));
	return Base + Path;
}

void UBarrioAuthSubsystem::Login(const FString& Username, const FString& Password, FDone Done)
{
	const TSharedPtr<FJsonObject> Body = MakeShared<FJsonObject>();
	Body->SetStringField(TEXT("username"), Username);
	Body->SetStringField(TEXT("password"), Password);

	TWeakObjectPtr<UBarrioAuthSubsystem> WeakThis(this);
	BarrioHttp::Send(TEXT("POST"), ApiUrl(TEXT("/v1/auth/login")), Body, FString(),
		[WeakThis, Done = MoveTemp(Done)](const BarrioHttp::FResponse& Response) mutable
		{
			if (UBarrioAuthSubsystem* Self = WeakThis.Get())
			{
				Self->HandleSession(Response, MoveTemp(Done));
			}
		});
}

void UBarrioAuthSubsystem::Register(const FString& Username, const FString& Password, const FString& Email, FDone Done)
{
	const TSharedPtr<FJsonObject> Body = MakeShared<FJsonObject>();
	Body->SetStringField(TEXT("username"), Username);
	Body->SetStringField(TEXT("password"), Password);
	if (!Email.IsEmpty())
	{
		Body->SetStringField(TEXT("email"), Email);
	}

	TWeakObjectPtr<UBarrioAuthSubsystem> WeakThis(this);
	BarrioHttp::Send(TEXT("POST"), ApiUrl(TEXT("/v1/auth/register")), Body, FString(),
		[WeakThis, Done = MoveTemp(Done)](const BarrioHttp::FResponse& Response) mutable
		{
			if (UBarrioAuthSubsystem* Self = WeakThis.Get())
			{
				Self->HandleSession(Response, MoveTemp(Done));
			}
		});
}

void UBarrioAuthSubsystem::HandleSession(const BarrioHttp::FResponse& Response, FDone Done)
{
	FString NewToken;
	if (!Response.IsOk() || !Response.Json.IsValid() || !Response.Json->TryGetStringField(TEXT("token"), NewToken))
	{
		Done(false, Response.Message.IsEmpty() ? TEXT("No se pudo iniciar sesión.") : Response.Message);
		return;
	}

	Token = NewToken;
	Response.Json->TryGetStringField(TEXT("name"), PlayerName);
	UE_LOG(LogBarrio, Log, TEXT("Sesión iniciada como %s."), *PlayerName);
	Done(true, FString());
}

void UBarrioAuthSubsystem::FindServer(FServerFound Done)
{
	const FString Fallback = GetDefault<UBarrioOnlineSettings>()->DefaultGameServer;

	BarrioHttp::Send(TEXT("GET"), ApiUrl(TEXT("/v1/servers")), nullptr, FString(),
		[Fallback, Done = MoveTemp(Done)](const BarrioHttp::FResponse& Response)
		{
			const TSharedPtr<FJsonObject>* Recommended = nullptr;
			if (Response.IsOk() && Response.Json.IsValid() && Response.Json->TryGetObjectField(TEXT("recommended"), Recommended) && Recommended)
			{
				FString Address;
				int32 Port = 0;
				if ((*Recommended)->TryGetStringField(TEXT("address"), Address) && (*Recommended)->TryGetNumberField(TEXT("port"), Port))
				{
					Done(FString::Printf(TEXT("%s:%d"), *Address, Port));
					return;
				}
			}
			Done(Fallback);
		});
}

void UBarrioAuthSubsystem::ConnectTo(const FString& Address)
{
	APlayerController* Controller = GetGameInstance() ? GetGameInstance()->GetFirstLocalPlayerController() : nullptr;
	if (!Controller || Token.IsEmpty())
	{
		UE_LOG(LogBarrio, Warning, TEXT("No se puede conectar: falta el jugador local o la sesión."));
		return;
	}

	// El token viaja como opción de la URL; el servidor de juego lo verifica con el backend.
	Controller->ClientTravel(FString::Printf(TEXT("%s?token=%s"), *Address, *Token), TRAVEL_Absolute);
}
