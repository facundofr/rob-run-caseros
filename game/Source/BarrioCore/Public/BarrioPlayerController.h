#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "BarrioPlayerController.generated.h"

USTRUCT()
struct FBarrioAlarmMarker
{
	GENERATED_BODY()

	FVector Location = FVector::ZeroVector;
	float ExpireTime = 0.f; // tiempo local del cliente
};

/**
 * Controlador del jugador. En el MVP 0 recibe los avisos de alarma, que el servidor manda
 * solo a los policías que corresponde. Los ladrones nunca reciben esta información.
 */
UCLASS()
class BARRIOCORE_API ABarrioPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	UFUNCTION(Client, Reliable)
	void ClientNotifyAlarm(FVector_NetQuantize Location);

	/** Mensaje corto en pantalla para este jugador (por ejemplo, por qué se rechazó un pedido). */
	UFUNCTION(Client, Reliable)
	void ClientShowMessage(const FString& NewMessage);

	/** Alarmas vigentes para este jugador (vacío si no es policía). */
	TArray<FBarrioAlarmMarker> GetActiveAlarms() const;

	/** Mensaje vigente, vacío si ya expiró. */
	FString GetCurrentMessage() const;

	/** Cuánto dura una alarma en el mapa del policía, en segundos. */
	UPROPERTY(EditDefaultsOnly, Category = "Barrio")
	float AlarmMarkerDuration = 60.f;

private:
	TArray<FBarrioAlarmMarker> Alarms;
	FString Message;
	float MessageExpireTime = 0.f;
};
