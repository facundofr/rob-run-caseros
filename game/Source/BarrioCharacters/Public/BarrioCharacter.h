#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "Interactable.h"
#include "BarrioCharacter.generated.h"

class UCameraComponent;
class USpringArmComponent;
class UInputAction;
class UInputMappingContext;
class UBarrioCharacterMovementComponent;
class UBarrioHealthComponent;
class UBarrioWeaponComponent;
class ABarrioPlayerState;
struct FInputActionValue;

/**
 * Personaje jugable en tercera persona.
 *
 * Controles por defecto: WASD moverse, mouse mirar, Espacio saltar, Shift correr, C agacharse,
 * E interactuar, clic izquierdo disparar, R recargar.
 *
 * El personaje también es interactuable: un policía que mira de cerca a un sospechoso buscado
 * ve "Arrestar". El arresto lo resuelve el GameMode en el servidor.
 *
 * Si no se asignan assets de input en el Blueprint, los controles se crean en tiempo de ejecución.
 */
UCLASS()
class BARRIOCHARACTERS_API ABarrioCharacter : public ACharacter, public IInteractable
{
	GENERATED_BODY()

public:
	explicit ABarrioCharacter(const FObjectInitializer& ObjectInitializer);

	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
	virtual void PawnClientRestart() override;
	virtual float TakeDamage(float DamageAmount, const FDamageEvent& DamageEvent, AController* EventInstigator, AActor* DamageCauser) override;

	// IInteractable: arresto
	virtual FText GetInteractionText_Implementation(const AActor* InstigatorActor) const override;
	virtual bool CanInteract_Implementation(const AActor* InstigatorActor) const override;
	virtual void Interact_Implementation(AActor* InstigatorActor) override;

	UFUNCTION(BlueprintPure, Category = "Barrio|Movement")
	UBarrioCharacterMovementComponent* GetBarrioMovement() const;

	UFUNCTION(BlueprintPure, Category = "Barrio|Combat")
	UBarrioHealthComponent* GetHealth() const { return Health; }

	UFUNCTION(BlueprintPure, Category = "Barrio|Combat")
	UBarrioWeaponComponent* GetWeapon() const { return Weapon; }

	UFUNCTION(BlueprintPure, Category = "Barrio|Combat")
	bool IsDead() const;

	/** Verdadero si está corriendo y efectivamente en movimiento. */
	UFUNCTION(BlueprintPure, Category = "Barrio|Movement")
	bool IsSprinting() const;

	/** Objeto interactuable que el jugador local está mirando (solo en el cliente que controla). */
	UFUNCTION(BlueprintPure, Category = "Barrio|Interaction")
	AActor* GetFocusedInteractable() const { return FocusedInteractable.Get(); }

	/** Texto del aviso de interacción, vacío si no mira nada interactuable. */
	UFUNCTION(BlueprintPure, Category = "Barrio|Interaction")
	FText GetFocusedInteractionText() const;

	/** Distancia máxima, en cm, entre el personaje y el objeto. La valida el servidor. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Barrio|Interaction", meta = (ClampMin = "50"))
	float InteractionDistance = 250.f;

	/** Tiempo mínimo entre dos interacciones aceptadas por el servidor, en segundos. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Barrio|Interaction", meta = (ClampMin = "0"))
	float InteractionCooldown = 0.25f;

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Barrio|Camera")
	TObjectPtr<USpringArmComponent> CameraBoom;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Barrio|Camera")
	TObjectPtr<UCameraComponent> FollowCamera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Barrio|Combat")
	TObjectPtr<UBarrioHealthComponent> Health;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Barrio|Combat")
	TObjectPtr<UBarrioWeaponComponent> Weapon;

	// Input opcional. Si DefaultMappingContext queda vacío, se crean los controles por defecto.
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Input") TObjectPtr<UInputMappingContext> DefaultMappingContext;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Input") TObjectPtr<UInputAction> MoveAction;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Input") TObjectPtr<UInputAction> LookAction;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Input") TObjectPtr<UInputAction> JumpAction;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Input") TObjectPtr<UInputAction> SprintAction;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Input") TObjectPtr<UInputAction> CrouchAction;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Input") TObjectPtr<UInputAction> InteractAction;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Input") TObjectPtr<UInputAction> FireAction;
	UPROPERTY(EditDefaultsOnly, Category = "Barrio|Input") TObjectPtr<UInputAction> ReloadAction;

	virtual void BeginPlay() override;

private:
	void CreateDefaultInputIfNeeded();

	void Move(const FInputActionValue& Value);
	void Look(const FInputActionValue& Value);
	void StartSprint();
	void StopSprint();
	void ToggleCrouch();
	void RequestInteract();
	void RequestFire();
	void RequestReload();

	void HandleDeath();

	void UpdateInteractionFocus();
	bool IsWithinInteractionRange(const AActor* Target) const;
	ABarrioPlayerState* GetBarrioPlayerState() const;

	UFUNCTION(Server, Reliable, WithValidation)
	void ServerInteract(AActor* Target);

	TWeakObjectPtr<AActor> FocusedInteractable;
	float LastAcceptedInteractionTime = -1000.f;
};
