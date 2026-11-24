#pragma once

#include "CoreMinimal.h"

class FJsonObject;

/** Pedidos HTTP con JSON al backend. Las respuestas llegan en el hilo del juego. */
namespace BarrioHttp
{
	struct FResponse
	{
		/** false si no hubo respuesta (sin red, backend caído, timeout). */
		bool bConnected = false;
		int32 Status = 0;
		TSharedPtr<FJsonObject> Json;
		/** Código de error del backend, por ejemplo "invalid_credentials". */
		FString ErrorCode;
		/** Mensaje listo para mostrar al jugador. */
		FString Message;

		bool IsOk() const { return bConnected && Status >= 200 && Status < 300; }
	};

	using FCallback = TFunction<void(const FResponse&)>;

	/** Body puede ser nulo. ServerKey vacía = pedido de cliente (sin header x-server-key). */
	BARRIOONLINE_API void Send(const FString& Verb, const FString& Url, const TSharedPtr<FJsonObject>& Body, const FString& ServerKey, FCallback Callback);
}
