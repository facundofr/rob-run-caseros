#include "BarrioCharacter.h"

#include "BarrioCharacterMovementComponent.h"
#include "BarrioGameEvents.h"
#include "BarrioHealthComponent.h"
#include "BarrioLog.h"
#include "BarrioPlayerState.h"
#include "BarrioWeaponComponent.h"

#include "Camera/CameraComponent.h"
#include "CollisionQueryParams.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/DamageEvents.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "InputMappingContext.h"
#include "InputModifiers.h"

ABarrioCharacter::ABarrioCharacter(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer.SetDefaultSubobjectClass<UBarrioCharacterMovementComponent>(ACharacter::CharacterMovementComponentName))
{
	PrimaryActorTick.bCanEverTick = true;

	GetCapsuleComponent()->InitCapsuleSize(42.f, 96.f);

	// La cámara gira con el mouse; el cuerpo gira hacia donde se mueve.
	bUseControllerRotationPitch = false;
	bUseControllerRotationYaw = false;
	bUseControllerRotationRoll = false;

	UCharacterMovementComponent* Movement = GetCharacterMovement();
	Movement->bOrientRotationToMovement = true;
	Movement->RotationRate = FRotator(0.f, 500.f, 0.f);
	Movement->JumpZVelocity = 500.f;
	Movement->AirControl = 0.35f;
	Movement->MaxWalkSpeed = 350.f;          // caminar: 12,6 km/h
	Movement->MaxWalkSpeedCrouched = 180.f;
	Movement->BrakingDecelerationWalking = 2000.f;
	Movement->GetNavAgentPropertiesRef().bCanCrouch = true;

	// Posición estándar del maniquí de Unreal dentro de la cápsula.
	GetMesh()->SetRelativeLocationAndRotation(FVector(0.f, 0.f, -96.f), FRotator(0.f, -90.f, 0.f));

	CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
	CameraBoom->SetupAttachment(RootComponent);
	CameraBoom->TargetArmLength = 400.f;
	CameraBoom->SocketOffset = FVector(0.f, 50.f, 60.f);
	CameraBoom->bUsePawnControlRotation = true;

	FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
	FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
	FollowCamera->bUsePawnControlRotation = false;

	Health = CreateDefaultSubobject<UBarrioHealthComponent>(TEXT("Health"));
	Weapon = CreateDefaultSubobject<UBarrioWeaponComponent>(TEXT("Weapon"));
}

void ABarrioCharacter::BeginPlay()
{
	Super::BeginPlay();
	Health->OnDied.AddUObject(this, &ABarrioCharacter::HandleDeath);
}

UBarrioCharacterMovementComponent* ABarrioCharacter::GetBarrioMovement() const
{
	return Cast<UBarrioCharacterMovementComponent>(GetCharacterMovement());
}

ABarrioPlayerState* ABarrioCharacter::GetBarrioPlayerState() const
{
	return GetPlayerState<ABarrioPlayerState>();
}

bool ABarrioCharacter::IsDead() const
{
	return Health && Health->IsDead();
}

bool ABarrioCharacter::IsSprinting() const
{
	const UBarrioCharacterMovementComponent* Movement = GetBarrioMovement();
	return Movement && Movement->WantsToSprint() && !bIsCrouched && GetVelocity().Size2D() > 10.f;
}

void ABarrioCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (IsLocallyControlled())
	{
		UpdateInteractionFocus();
	}
}

// ---------------------------------------------------------------------------------------------
// Input
// ---------------------------------------------------------------------------------------------

void ABarrioCharacter::CreateDefaultInputIfNeeded()
{
	if (DefaultMappingContext)
	{
		return; // El Blueprint trae sus propios assets de input.
	}

	auto MakeAction = [this](const TCHAR* Name, EInputActionValueType Type)
	{
		UInputAction* Action = NewObject<UInputAction>(this, Name);
		Action->ValueType = Type;
		return Action;
	};

	MoveAction = MakeAction(TEXT("IA_Move_Default"), EInputActionValueType::Axis2D);
	LookAction = MakeAction(TEXT("IA_Look_Default"), EInputActionValueType::Axis2D);
	JumpAction = MakeAction(TEXT("IA_Jump_Default"), EInputActionValueType::Boolean);
	SprintAction = MakeAction(TEXT("IA_Sprint_Default"), EInputActionValueType::Boolean);
	CrouchAction = MakeAction(TEXT("IA_Crouch_Default"), EInputActionValueType::Boolean);
	InteractAction = MakeAction(TEXT("IA_Interact_Default"), EInputActionValueType::Boolean);
	FireAction = MakeAction(TEXT("IA_Fire_Default"), EInputActionValueType::Boolean);
	ReloadAction = MakeAction(TEXT("IA_Reload_Default"), EInputActionValueType::Boolean);
	MaskAction = MakeAction(TEXT("IA_Mask_Default"), EInputActionValueType::Boolean);
	SurrenderAction = MakeAction(TEXT("IA_Surrender_Default"), EInputActionValueType::Boolean);

	UInputMappingContext* Context = NewObject<UInputMappingContext>(this, TEXT("IMC_Default"));

	// WASD sobre un eje 2D: X = derecha/izquierda, Y = adelante/atrás.
	Context->MapKey(MoveAction, EKeys::W).Modifiers.Add(NewObject<UInputModifierSwizzleAxis>(Context));
	{
		FEnhancedActionKeyMapping& Back = Context->MapKey(MoveAction, EKeys::S);
		Back.Modifiers.Add(NewObject<UInputModifierSwizzleAxis>(Context));
		Back.Modifiers.Add(NewObject<UInputModifierNegate>(Context));
	}
	Context->MapKey(MoveAction, EKeys::A).Modifiers.Add(NewObject<UInputModifierNegate>(Context));
	Context->MapKey(MoveAction, EKeys::D);

	{
		FEnhancedActionKeyMapping& Mouse = Context->MapKey(LookAction, EKeys::Mouse2D);
		UInputModifierNegate* InvertY = NewObject<UInputModifierNegate>(Context);
		InvertY->bX = false;
		InvertY->bY = true;
		InvertY->bZ = false;
		Mouse.Modifiers.Add(InvertY);
	}

	Context->MapKey(JumpAction, EKeys::SpaceBar);
	Context->MapKey(SprintAction, EKeys::LeftShift);
	Context->MapKey(CrouchAction, EKeys::C);
	Context->MapKey(InteractAction, EKeys::E);
	Context->MapKey(FireAction, EKeys::LeftMouseButton);
	Context->MapKey(ReloadAction, EKeys::R);
	Context->MapKey(MaskAction, EKeys::G);
	Context->MapKey(SurrenderAction, EKeys::Q);

	DefaultMappingContext = Context;
}

void ABarrioCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	CreateDefaultInputIfNeeded();

	UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(PlayerInputComponent);
	if (!Input)
	{
		UE_LOG(LogBarrio, Error, TEXT("El proyecto no usa Enhanced Input. Revisar Config/DefaultInput.ini."));
		return;
	}

	if (MoveAction)     { Input->BindAction(MoveAction, ETriggerEvent::Triggered, this, &ABarrioCharacter::Move); }
	if (LookAction)     { Input->BindAction(LookAction, ETriggerEvent::Triggered, this, &ABarrioCharacter::Look); }
	if (JumpAction)
	{
		Input->BindAction(JumpAction, ETriggerEvent::Started, this, &ACharacter::Jump);
		Input->BindAction(JumpAction, ETriggerEvent::Completed, this, &ACharacter::StopJumping);
	}
	if (SprintAction)
	{
		Input->BindAction(SprintAction, ETriggerEvent::Started, this, &ABarrioCharacter::StartSprint);
		Input->BindAction(SprintAction, ETriggerEvent::Completed, this, &ABarrioCharacter::StopSprint);
	}
	if (CrouchAction)   { Input->BindAction(CrouchAction, ETriggerEvent::Started, this, &ABarrioCharacter::ToggleCrouch); }
	if (InteractAction) { Input->BindAction(InteractAction, ETriggerEvent::Started, this, &ABarrioCharacter::RequestInteract); }
	if (FireAction)     { Input->BindAction(FireAction, ETriggerEvent::Started, this, &ABarrioCharacter::RequestFire); }
	if (ReloadAction)   { Input->BindAction(ReloadAction, ETriggerEvent::Started, this, &ABarrioCharacter::RequestReload); }
	if (MaskAction)     { Input->BindAction(MaskAction, ETriggerEvent::Started, this, &ABarrioCharacter::RequestMask); }
	if (SurrenderAction) { Input->BindAction(SurrenderAction, ETriggerEvent::Started, this, &ABarrioCharacter::PressSurrenderKey); }
}

void ABarrioCharacter::PawnClientRestart()
{
	Super::PawnClientRestart(); // Crea el InputComponent y llama a SetupPlayerInputComponent.

	const APlayerController* PlayerController = Cast<APlayerController>(GetController());
	const ULocalPlayer* LocalPlayer = PlayerController ? PlayerController->GetLocalPlayer() : nullptr;
	UEnhancedInputLocalPlayerSubsystem* Subsystem = LocalPlayer ? LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>() : nullptr;
	if (Subsystem && DefaultMappingContext)
	{
		Subsystem->ClearAllMappings();
		Subsystem->AddMappingContext(DefaultMappingContext, 0);
	}
}

void ABarrioCharacter::Move(const FInputActionValue& Value)
{
	const FVector2D Axis = Value.Get<FVector2D>();
	if (!Controller || IsDead())
	{
		return;
	}

	const FRotator YawRotation(0.f, Controller->GetControlRotation().Yaw, 0.f);
	const FRotationMatrix Rotation(YawRotation);
	AddMovementInput(Rotation.GetUnitAxis(EAxis::X), Axis.Y);
	AddMovementInput(Rotation.GetUnitAxis(EAxis::Y), Axis.X);
}

void ABarrioCharacter::Look(const FInputActionValue& Value)
{
	const FVector2D Axis = Value.Get<FVector2D>();
	AddControllerYawInput(Axis.X);
	AddControllerPitchInput(Axis.Y);
}

void ABarrioCharacter::StartSprint()
{
	if (UBarrioCharacterMovementComponent* Movement = GetBarrioMovement())
	{
		Movement->SetSprinting(true);
	}
}

void ABarrioCharacter::StopSprint()
{
	if (UBarrioCharacterMovementComponent* Movement = GetBarrioMovement())
	{
		Movement->SetSprinting(false);
	}
}

void ABarrioCharacter::ToggleCrouch()
{
	if (IsDead())
	{
		return;
	}

	// Crouch/UnCrouch ya están replicados y predichos por el motor.
	if (bIsCrouched)
	{
		UnCrouch();
	}
	else
	{
		Crouch();
	}
}

void ABarrioCharacter::RequestFire()
{
	if (Weapon && !IsDead())
	{
		Weapon->RequestFire();
	}
}

void ABarrioCharacter::RequestReload()
{
	if (Weapon && !IsDead())
	{
		Weapon->RequestReload();
	}
}

void ABarrioCharacter::RequestMask()
{
	const ABarrioPlayerState* State = GetBarrioPlayerState();
	if (!IsDead() && State && State->IsCivilian())
	{
		ServerRequestMask();
	}
}

void ABarrioCharacter::PressSurrenderKey()
{
	if (!IsDead())
	{
		ServerPressSurrenderKey();
	}
}

bool ABarrioCharacter::ServerRequestMask_Validate()
{
	return true;
}

void ABarrioCharacter::ServerRequestMask_Implementation()
{
	// El GameMode valida (vecino, fuera de zona segura) y controla los 2 s de la animación.
	if (UBarrioGameEvents* Events = UBarrioGameEvents::Get(this))
	{
		Events->OnMaskRequested.Broadcast(GetController());
	}
}

bool ABarrioCharacter::ServerPressSurrenderKey_Validate()
{
	return true;
}

void ABarrioCharacter::ServerPressSurrenderKey_Implementation()
{
	const ABarrioPlayerState* State = GetBarrioPlayerState();
	UBarrioGameEvents* Events = UBarrioGameEvents::Get(this);
	if (!State || !Events || IsDead())
	{
		return;
	}

	if (State->IsCriminal())
	{
		Events->OnSurrenderToggled.Broadcast(GetController());
	}
	else if (State->IsPolice())
	{
		Events->OnSurrenderOrder.Broadcast(GetController());
	}
}

// ---------------------------------------------------------------------------------------------
// Daño y muerte
// ---------------------------------------------------------------------------------------------

float ABarrioCharacter::TakeDamage(float DamageAmount, const FDamageEvent& DamageEvent, AController* EventInstigator, AActor* DamageCauser)
{
	if (!HasAuthority() || IsDead())
	{
		return 0.f;
	}

	// Regla central de daño: zona segura, protección de reaparición, vecinos sin armas,
	// la policía solo daña ladrones.
	UBarrioGameEvents* RulesEvents = UBarrioGameEvents::Get(this);
	const ABarrioPlayerState* AttackerState = EventInstigator ? EventInstigator->GetPlayerState<ABarrioPlayerState>() : nullptr;
	if (RulesEvents && !RulesEvents->CanDamage(AttackerState, GetBarrioPlayerState(), GetActorLocation(), GetWorld()->GetTimeSeconds()))
	{
		return 0.f;
	}

	const float Applied = Health->ApplyDamage(Super::TakeDamage(DamageAmount, DamageEvent, EventInstigator, DamageCauser));
	if (Applied <= 0.f)
	{
		return 0.f;
	}

	if (UBarrioGameEvents* Events = UBarrioGameEvents::Get(this))
	{
		Events->OnDamage.Broadcast(GetController(), EventInstigator, Applied);
		if (Health->IsDead())
		{
			Events->OnKill.Broadcast(GetController(), EventInstigator);
		}
	}
	return Applied;
}

void ABarrioCharacter::HandleDeath()
{
	// Corre en el servidor y en cada cliente. Después el GameMode le quita el control y lo reaparece.
	GetCharacterMovement()->DisableMovement();
	GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	GetMesh()->SetCollisionProfileName(TEXT("Ragdoll"));
	GetMesh()->SetSimulatePhysics(true);
}

// ---------------------------------------------------------------------------------------------
// Interacción
// ---------------------------------------------------------------------------------------------

FText ABarrioCharacter::GetFocusedInteractionText() const
{
	AActor* Target = FocusedInteractable.Get();
	if (!Target)
	{
		return FText::GetEmpty();
	}
	return IInteractable::Execute_GetInteractionText(Target, this);
}

bool ABarrioCharacter::IsWithinInteractionRange(const AActor* Target) const
{
	if (!Target)
	{
		return false;
	}

	// Distancia a la caja que envuelve al objeto, no a su centro: una puerta ancha
	// se puede usar desde cualquiera de sus bordes.
	const FBox Bounds = Target->GetComponentsBoundingBox();
	if (!Bounds.IsValid)
	{
		return FVector::DistSquared(GetActorLocation(), Target->GetActorLocation()) <= FMath::Square(InteractionDistance);
	}
	return Bounds.ComputeSquaredDistanceToPoint(GetActorLocation()) <= FMath::Square(InteractionDistance);
}

void ABarrioCharacter::UpdateInteractionFocus()
{
	FocusedInteractable.Reset();

	if (!FollowCamera || IsDead())
	{
		return;
	}

	// Rayo desde la cámara hacia el centro de la pantalla. Se suma el largo del brazo
	// de la cámara para que el alcance se sienta igual que en primera persona.
	const FVector Start = FollowCamera->GetComponentLocation();
	const FVector End = Start + FollowCamera->GetForwardVector() * (CameraBoom->TargetArmLength + InteractionDistance);

	// Por tipo de objeto para detectar también a otros personajes (arresto).
	FCollisionObjectQueryParams ObjectTypes;
	ObjectTypes.AddObjectTypesToQuery(ECC_WorldStatic);
	ObjectTypes.AddObjectTypesToQuery(ECC_WorldDynamic);
	ObjectTypes.AddObjectTypesToQuery(ECC_Pawn);

	FCollisionQueryParams Params(SCENE_QUERY_STAT(BarrioInteractionTrace), false, this);
	FHitResult Hit;
	if (!GetWorld()->LineTraceSingleByObjectType(Hit, Start, End, ObjectTypes, Params))
	{
		return;
	}

	AActor* HitActor = Hit.GetActor();
	if (HitActor
		&& HitActor->Implements<UInteractable>()
		&& IsWithinInteractionRange(HitActor)
		&& IInteractable::Execute_CanInteract(HitActor, this))
	{
		FocusedInteractable = HitActor;
	}
}

void ABarrioCharacter::RequestInteract()
{
	if (AActor* Target = FocusedInteractable.Get())
	{
		ServerInteract(Target);
	}
}

bool ABarrioCharacter::ServerInteract_Validate(AActor* Target)
{
	// No se desconecta al jugador por un pedido inválido: se rechaza en _Implementation.
	return true;
}

void ABarrioCharacter::ServerInteract_Implementation(AActor* Target)
{
	const float Now = GetWorld()->GetTimeSeconds();
	if (IsDead() || Now - LastAcceptedInteractionTime < InteractionCooldown)
	{
		return; // Límite de frecuencia.
	}

	if (!IsValid(Target) || Target == this || !Target->Implements<UInteractable>())
	{
		UE_LOG(LogBarrio, Warning, TEXT("Interacción rechazada: objetivo inválido (%s)."), *GetNameSafe(this));
		return;
	}

	if (!IsWithinInteractionRange(Target))
	{
		UE_LOG(LogBarrio, Warning, TEXT("Interacción rechazada: %s está fuera de alcance de %s."), *GetNameSafe(Target), *GetNameSafe(this));
		return;
	}

	if (!IInteractable::Execute_CanInteract(Target, this))
	{
		return;
	}

	LastAcceptedInteractionTime = Now;
	IInteractable::Execute_Interact(Target, this);
}

// ---------------------------------------------------------------------------------------------
// Captura (este personaje como objetivo)
// ---------------------------------------------------------------------------------------------

bool ABarrioCharacter::CanInteract_Implementation(const AActor* InstigatorActor) const
{
	const APawn* OtherPawn = Cast<APawn>(InstigatorActor);
	const ABarrioPlayerState* OtherState = OtherPawn ? OtherPawn->GetPlayerState<ABarrioPlayerState>() : nullptr;
	const ABarrioPlayerState* MyState = GetBarrioPlayerState();
	if (!OtherState || !MyState || !OtherState->IsPolice() || !MyState->IsCriminal() || MyState->IsJailed() || IsDead())
	{
		return false;
	}

	// Se puede esposar a un ladrón rendido o reducido (poca vida).
	const bool bSubdued = Health && Health->GetHealth() <= Health->GetMaxHealth() * SubduedHealthFraction;
	return MyState->IsSurrendered() || bSubdued;
}

FText ABarrioCharacter::GetInteractionText_Implementation(const AActor* InstigatorActor) const
{
	const ABarrioPlayerState* MyState = GetBarrioPlayerState();
	return (MyState && MyState->IsSurrendered()) ? INVTEXT("Esposar (se rindió)") : INVTEXT("Esposar (reducido)");
}

void ABarrioCharacter::Interact_Implementation(AActor* InstigatorActor)
{
	const APawn* PolicePawn = Cast<APawn>(InstigatorActor);
	UBarrioGameEvents* Events = UBarrioGameEvents::Get(this);
	if (PolicePawn && Events && HasAuthority())
	{
		Events->OnCuffRequested.Broadcast(PolicePawn->GetController(), GetController());
	}
}
