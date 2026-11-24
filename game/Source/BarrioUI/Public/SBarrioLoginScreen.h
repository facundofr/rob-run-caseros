#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"

class SEditableTextBox;
class STextBlock;
class UBarrioAuthSubsystem;

/**
 * Pantalla de login y registro, hecha en Slate (sin assets). Al iniciar sesión busca el servidor
 * recomendado y entra. El diseñador puede reemplazarla más adelante por un widget de UMG.
 */
class BARRIOUI_API SBarrioLoginScreen : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SBarrioLoginScreen) {}
		SLATE_ARGUMENT(TWeakObjectPtr<UBarrioAuthSubsystem>, Auth)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);

	/** Widget al que se le da el foco al mostrar la pantalla. */
	TSharedPtr<SWidget> GetInitialFocus() const;

private:
	FReply OnLoginClicked();
	FReply OnRegisterClicked();
	void OnAuthenticated();
	void SetStatus(const FString& Message, bool bIsError);
	bool ReadFields(FString& OutUsername, FString& OutPassword);

	TWeakObjectPtr<UBarrioAuthSubsystem> Auth;
	TSharedPtr<SEditableTextBox> UsernameBox;
	TSharedPtr<SEditableTextBox> PasswordBox;
	TSharedPtr<SEditableTextBox> EmailBox;
	TSharedPtr<STextBlock> StatusText;
	bool bBusy = false;
};
