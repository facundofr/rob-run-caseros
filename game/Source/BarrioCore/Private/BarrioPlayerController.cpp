#include "BarrioPlayerController.h"

#include "Engine/World.h"

void ABarrioPlayerController::ClientNotifyAlarm_Implementation(FVector_NetQuantize Location)
{
	const float Now = GetWorld()->GetTimeSeconds();
	Alarms.RemoveAll([Now](const FBarrioAlarmMarker& Marker) { return Marker.ExpireTime <= Now; });

	FBarrioAlarmMarker& Marker = Alarms.AddDefaulted_GetRef();
	Marker.Location = Location;
	Marker.ExpireTime = Now + AlarmMarkerDuration;
}

void ABarrioPlayerController::ClientShowMessage_Implementation(const FString& NewMessage)
{
	Message = NewMessage;
	MessageExpireTime = GetWorld()->GetTimeSeconds() + 5.f;
}

FString ABarrioPlayerController::GetCurrentMessage() const
{
	return GetWorld()->GetTimeSeconds() < MessageExpireTime ? Message : FString();
}

TArray<FBarrioAlarmMarker> ABarrioPlayerController::GetActiveAlarms() const
{
	const float Now = GetWorld()->GetTimeSeconds();
	return Alarms.FilterByPredicate([Now](const FBarrioAlarmMarker& Marker) { return Marker.ExpireTime > Now; });
}
