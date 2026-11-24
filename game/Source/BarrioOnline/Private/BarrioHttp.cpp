#include "BarrioHttp.h"

#include "Dom/JsonObject.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

void BarrioHttp::Send(const FString& Verb, const FString& Url, const TSharedPtr<FJsonObject>& Body, const FString& ServerKey, FCallback Callback)
{
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
	Request->SetURL(Url);
	Request->SetVerb(Verb);
	Request->SetHeader(TEXT("Accept"), TEXT("application/json"));
	Request->SetTimeout(10.f);

	if (!ServerKey.IsEmpty())
	{
		Request->SetHeader(TEXT("x-server-key"), ServerKey);
	}

	if (Body.IsValid())
	{
		FString Payload;
		const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Payload);
		FJsonSerializer::Serialize(Body.ToSharedRef(), Writer);
		Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
		Request->SetContentAsString(Payload);
	}

	Request->OnProcessRequestComplete().BindLambda(
		[Callback = MoveTemp(Callback)](FHttpRequestPtr /*Request*/, FHttpResponsePtr Response, bool bSucceeded)
		{
			FResponse Result;
			Result.bConnected = bSucceeded && Response.IsValid();

			if (Result.bConnected)
			{
				Result.Status = Response->GetResponseCode();
				TSharedPtr<FJsonObject> Json;
				const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Response->GetContentAsString());
				if (FJsonSerializer::Deserialize(Reader, Json) && Json.IsValid())
				{
					Result.Json = Json;
					Json->TryGetStringField(TEXT("error"), Result.ErrorCode);
					Json->TryGetStringField(TEXT("message"), Result.Message);
				}
				if (!Result.IsOk() && Result.Message.IsEmpty())
				{
					Result.Message = FString::Printf(TEXT("Error del servidor de cuentas (%d)."), Result.Status);
				}
			}
			else
			{
				Result.Message = TEXT("No se pudo conectar con el servidor de cuentas.");
			}

			Callback(Result);
		});

	Request->ProcessRequest();
}
