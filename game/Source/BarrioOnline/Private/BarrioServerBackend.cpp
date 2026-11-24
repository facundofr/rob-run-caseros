#include "BarrioServerBackend.h"

#include "BarrioHttp.h"
#include "BarrioLog.h"
#include "BarrioOnlineSettings.h"
#include "Dom/JsonObject.h"
#include "Engine/GameInstance.h"
#include "HAL/PlatformMisc.h"
#include "Misc/Guid.h"
#include "TimerManager.h"

namespace
{
	FString EnvOr(const TCHAR* Name, const FString& Fallback)
	{
		const FString Value = FPlatformMisc::GetEnvironmentVariable(Name);
		return Value.IsEmpty() ? Fallback : Value;
	}
}

void UBarrioServerBackend::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	ServerKey = FPlatformMisc::GetEnvironmentVariable(TEXT("BARRIO_SERVER_KEY"));
	BackendUrl = EnvOr(TEXT("BARRIO_BACKEND_URL"), GetDefault<UBarrioOnlineSettings>()->BackendUrl);
	BackendUrl.RemoveFromEnd(TEXT("/"));
	ServerName = EnvOr(TEXT("BARRIO_SERVER_NAME"), TEXT("Barrio"));
	PublicAddress = EnvOr(TEXT("BARRIO_PUBLIC_ADDRESS"), TEXT("127.0.0.1"));
	Region = EnvOr(TEXT("BARRIO_REGION"), TEXT("sa-east"));

	if (IsEnabled())
	{
		UE_LOG(LogBarrio, Log, TEXT("Backend activo: %s (servidor %s, %s)."), *BackendUrl, *ServerName, *PublicAddress);
	}
}

void UBarrioServerBackend::Deinitialize()
{
	if (UGameInstance* GameInstance = GetGameInstance())
	{
		GameInstance->GetTimerManager().ClearTimer(HeartbeatTimer);
		GameInstance->GetTimerManager().ClearTimer(RegisterRetryTimer);
	}
	Super::Deinitialize();
}

FString UBarrioServerBackend::ApiUrl(const FString& Path) const
{
	return BackendUrl + Path;
}

// ---------------------------------------------------------------------------------------------
// Registro y heartbeat
// ---------------------------------------------------------------------------------------------

void UBarrioServerBackend::StartRegistration(int32 InPort, int32 InMaxPlayers, TFunction<int32()> PlayerCount)
{
	if (!IsEnabled())
	{
		return;
	}
	Port = InPort;
	MaxPlayers = InMaxPlayers;
	PlayerCountProvider = MoveTemp(PlayerCount);
	Register();
}

void UBarrioServerBackend::Register()
{
	const TSharedPtr<FJsonObject> Body = MakeShared<FJsonObject>();
	Body->SetStringField(TEXT("name"), ServerName);
	Body->SetStringField(TEXT("address"), PublicAddress);
	Body->SetNumberField(TEXT("port"), Port);
	Body->SetStringField(TEXT("region"), Region);
	Body->SetNumberField(TEXT("maxPlayers"), MaxPlayers);

	TWeakObjectPtr<UBarrioServerBackend> WeakThis(this);
	BarrioHttp::Send(TEXT("POST"), ApiUrl(TEXT("/v1/servers/register")), Body, ServerKey,
		[WeakThis](const BarrioHttp::FResponse& Response)
		{
			UBarrioServerBackend* Self = WeakThis.Get();
			UGameInstance* GameInstance = Self ? Self->GetGameInstance() : nullptr;
			if (!GameInstance)
			{
				return;
			}

			FTimerManager& Timers = GameInstance->GetTimerManager();
			if (Response.IsOk() && Response.Json.IsValid() && Response.Json->TryGetStringField(TEXT("id"), Self->ServerId))
			{
				UE_LOG(LogBarrio, Log, TEXT("Servidor registrado en el backend (id %s)."), *Self->ServerId);
				const float Interval = GetDefault<UBarrioOnlineSettings>()->HeartbeatInterval;
				Timers.SetTimer(Self->HeartbeatTimer, FTimerDelegate::CreateUObject(Self, &UBarrioServerBackend::SendHeartbeat), Interval, true);
				return;
			}

			UE_LOG(LogBarrio, Warning, TEXT("No se pudo registrar el servidor: %s. Reintento en 10 s."), *Response.Message);
			Timers.SetTimer(Self->RegisterRetryTimer, FTimerDelegate::CreateUObject(Self, &UBarrioServerBackend::Register), 10.f, false);
		});
}

void UBarrioServerBackend::SendHeartbeat()
{
	if (ServerId.IsEmpty())
	{
		return;
	}

	const TSharedPtr<FJsonObject> Body = MakeShared<FJsonObject>();
	Body->SetNumberField(TEXT("currentPlayers"), PlayerCountProvider ? PlayerCountProvider() : 0);

	TWeakObjectPtr<UBarrioServerBackend> WeakThis(this);
	BarrioHttp::Send(TEXT("POST"), ApiUrl(FString::Printf(TEXT("/v1/servers/%s/heartbeat"), *ServerId)), Body, ServerKey,
		[WeakThis](const BarrioHttp::FResponse& Response)
		{
			UBarrioServerBackend* Self = WeakThis.Get();
			if (!Self || Response.IsOk())
			{
				return;
			}
			if (Response.Status == 404)
			{
				// El backend no conoce esta instancia (por ejemplo, se borró la base): registrarse de nuevo.
				Self->ServerId.Reset();
				if (UGameInstance* GameInstance = Self->GetGameInstance())
				{
					GameInstance->GetTimerManager().ClearTimer(Self->HeartbeatTimer);
				}
				Self->Register();
				return;
			}
			UE_LOG(LogBarrio, Warning, TEXT("Heartbeat fallido: %s"), *Response.Message);
		});
}

// ---------------------------------------------------------------------------------------------
// Sesiones
// ---------------------------------------------------------------------------------------------

void UBarrioServerBackend::VerifySession(const FString& Token, FVerified Done)
{
	if (Token.IsEmpty())
	{
		Done(false, FBarrioProfile(), TEXT("Iniciá sesión antes de entrar."));
		return;
	}

	const TSharedPtr<FJsonObject> Body = MakeShared<FJsonObject>();
	Body->SetStringField(TEXT("token"), Token);

	BarrioHttp::Send(TEXT("POST"), ApiUrl(TEXT("/v1/sessions/verify")), Body, ServerKey,
		[Done = MoveTemp(Done)](const BarrioHttp::FResponse& Response)
		{
			FBarrioProfile Profile;
			if (!Response.IsOk() || !Response.Json.IsValid()
				|| !Response.Json->TryGetNumberField(TEXT("accountId"), Profile.AccountId)
				|| !Response.Json->TryGetNumberField(TEXT("characterId"), Profile.CharacterId))
			{
				Done(false, Profile, Response.Status == 401 ? TEXT("La sesión venció. Volvé a iniciar sesión.") : Response.Message);
				return;
			}
			Response.Json->TryGetStringField(TEXT("name"), Profile.Name);
			Response.Json->TryGetNumberField(TEXT("cash"), Profile.Cash);
			Done(true, Profile, FString());
		});
}

// ---------------------------------------------------------------------------------------------
// Economía
// ---------------------------------------------------------------------------------------------

void UBarrioServerBackend::ApplyTransaction(int32 CharacterId, int32 Amount, const FString& Reason, FTransactionDone Done)
{
	const TSharedPtr<FJsonObject> Body = MakeShared<FJsonObject>();
	Body->SetNumberField(TEXT("characterId"), CharacterId);
	Body->SetNumberField(TEXT("amount"), Amount);
	Body->SetStringField(TEXT("reason"), Reason);
	Body->SetStringField(TEXT("idempotencyKey"),
		FString::Printf(TEXT("%s-%d-%s"), *Reason, CharacterId, *FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	if (!ServerId.IsEmpty())
	{
		Body->SetStringField(TEXT("serverId"), ServerId);
	}

	SendTransaction(Body, MoveTemp(Done), false);
}

void UBarrioServerBackend::SendTransaction(TSharedPtr<FJsonObject> Body, FTransactionDone Done, bool bIsRetry)
{
	TWeakObjectPtr<UBarrioServerBackend> WeakThis(this);
	BarrioHttp::Send(TEXT("POST"), ApiUrl(TEXT("/v1/economy/transactions")), Body, ServerKey,
		[WeakThis, Body, bIsRetry, Done = MoveTemp(Done)](const BarrioHttp::FResponse& Response) mutable
		{
			// Sin respuesta: reintentar una vez con la MISMA clave. Si el primer pedido sí llegó,
			// el backend devuelve el movimiento original en lugar de repetirlo.
			if (!Response.bConnected && !bIsRetry)
			{
				if (UBarrioServerBackend* Self = WeakThis.Get())
				{
					Self->SendTransaction(Body, MoveTemp(Done), true);
					return;
				}
			}

			int32 Balance = 0;
			if (Response.IsOk() && Response.Json.IsValid() && Response.Json->TryGetNumberField(TEXT("balance"), Balance))
			{
				Done(true, Balance, FString());
				return;
			}
			UE_LOG(LogBarrio, Warning, TEXT("Movimiento de dinero rechazado: %s (%s)"), *Response.Message, *Response.ErrorCode);
			Done(false, 0, Response.Message);
		});
}
