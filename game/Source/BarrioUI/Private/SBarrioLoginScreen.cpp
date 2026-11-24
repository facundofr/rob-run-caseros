#include "SBarrioLoginScreen.h"

#include "BarrioAuthSubsystem.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

namespace
{
	TSharedRef<SWidget> Label(const FText& Text)
	{
		return SNew(STextBlock).Text(Text).ColorAndOpacity(FLinearColor(0.8f, 0.8f, 0.8f));
	}
}

void SBarrioLoginScreen::Construct(const FArguments& InArgs)
{
	Auth = InArgs._Auth;

	ChildSlot
	[
		SNew(SBorder)
		.BorderImage(FCoreStyle::Get().GetBrush("BlackBrush"))
		.HAlign(HAlign_Center)
		.VAlign(VAlign_Center)
		[
			SNew(SBox)
			.WidthOverride(420.f)
			[
				SNew(SVerticalBox)

				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 4.f)
				[
					SNew(STextBlock).Text(INVTEXT("BARRIO")).Font(FCoreStyle::GetDefaultFontStyle("Bold", 36))
				]
				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 24.f)
				[
					SNew(STextBlock).Text(INVTEXT("Caseros, Zona Oeste")).ColorAndOpacity(FLinearColor(0.6f, 0.6f, 0.6f))
				]

				+ SVerticalBox::Slot().AutoHeight()[ Label(INVTEXT("Usuario")) ]
				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 12.f)
				[
					SAssignNew(UsernameBox, SEditableTextBox)
				]

				+ SVerticalBox::Slot().AutoHeight()[ Label(INVTEXT("Contraseña")) ]
				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 12.f)
				[
					SAssignNew(PasswordBox, SEditableTextBox).IsPassword(true)
				]

				+ SVerticalBox::Slot().AutoHeight()[ Label(INVTEXT("Email (opcional, solo para crear cuenta)")) ]
				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 20.f)
				[
					SAssignNew(EmailBox, SEditableTextBox)
				]

				+ SVerticalBox::Slot().AutoHeight()
				[
					SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().FillWidth(1.f).Padding(0.f, 0.f, 8.f, 0.f)
					[
						SNew(SButton)
						.HAlign(HAlign_Center)
						.Text(INVTEXT("Entrar"))
						.IsEnabled_Lambda([this]() { return !bBusy; })
						.OnClicked(this, &SBarrioLoginScreen::OnLoginClicked)
					]
					+ SHorizontalBox::Slot().FillWidth(1.f)
					[
						SNew(SButton)
						.HAlign(HAlign_Center)
						.Text(INVTEXT("Crear cuenta"))
						.IsEnabled_Lambda([this]() { return !bBusy; })
						.OnClicked(this, &SBarrioLoginScreen::OnRegisterClicked)
					]
				]

				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 16.f, 0.f, 0.f)
				[
					SAssignNew(StatusText, STextBlock).AutoWrapText(true)
				]
			]
		]
	];
}

TSharedPtr<SWidget> SBarrioLoginScreen::GetInitialFocus() const
{
	return UsernameBox;
}

bool SBarrioLoginScreen::ReadFields(FString& OutUsername, FString& OutPassword)
{
	OutUsername = UsernameBox->GetText().ToString().TrimStartAndEnd();
	OutPassword = PasswordBox->GetText().ToString();
	if (OutUsername.IsEmpty() || OutPassword.IsEmpty())
	{
		SetStatus(TEXT("Completá usuario y contraseña."), true);
		return false;
	}
	if (!Auth.IsValid())
	{
		SetStatus(TEXT("Error interno: no hay sesión disponible."), true);
		return false;
	}
	return true;
}

FReply SBarrioLoginScreen::OnLoginClicked()
{
	FString Username, Password;
	if (bBusy || !ReadFields(Username, Password))
	{
		return FReply::Handled();
	}

	bBusy = true;
	SetStatus(TEXT("Iniciando sesión..."), false);

	TWeakPtr<SBarrioLoginScreen> WeakThis = StaticCastSharedRef<SBarrioLoginScreen>(AsShared());
	Auth->Login(Username, Password, [WeakThis](bool bSuccess, const FString& Message)
	{
		if (TSharedPtr<SBarrioLoginScreen> Self = WeakThis.Pin())
		{
			if (bSuccess)
			{
				Self->OnAuthenticated();
			}
			else
			{
				Self->bBusy = false;
				Self->SetStatus(Message, true);
			}
		}
	});
	return FReply::Handled();
}

FReply SBarrioLoginScreen::OnRegisterClicked()
{
	FString Username, Password;
	if (bBusy || !ReadFields(Username, Password))
	{
		return FReply::Handled();
	}

	bBusy = true;
	SetStatus(TEXT("Creando cuenta..."), false);

	TWeakPtr<SBarrioLoginScreen> WeakThis = StaticCastSharedRef<SBarrioLoginScreen>(AsShared());
	Auth->Register(Username, Password, EmailBox->GetText().ToString().TrimStartAndEnd(), [WeakThis](bool bSuccess, const FString& Message)
	{
		if (TSharedPtr<SBarrioLoginScreen> Self = WeakThis.Pin())
		{
			if (bSuccess)
			{
				Self->OnAuthenticated();
			}
			else
			{
				Self->bBusy = false;
				Self->SetStatus(Message, true);
			}
		}
	});
	return FReply::Handled();
}

void SBarrioLoginScreen::OnAuthenticated()
{
	SetStatus(TEXT("Buscando servidor..."), false);

	TWeakPtr<SBarrioLoginScreen> WeakThis = StaticCastSharedRef<SBarrioLoginScreen>(AsShared());
	TWeakObjectPtr<UBarrioAuthSubsystem> WeakAuth = Auth;
	Auth->FindServer([WeakThis, WeakAuth](const FString& Address)
	{
		if (TSharedPtr<SBarrioLoginScreen> Self = WeakThis.Pin())
		{
			Self->SetStatus(FString::Printf(TEXT("Entrando a %s..."), *Address), false);
		}
		if (UBarrioAuthSubsystem* AuthSubsystem = WeakAuth.Get())
		{
			AuthSubsystem->ConnectTo(Address);
		}
	});
}

void SBarrioLoginScreen::SetStatus(const FString& Message, bool bIsError)
{
	StatusText->SetText(FText::FromString(Message));
	StatusText->SetColorAndOpacity(bIsError ? FLinearColor(1.f, 0.35f, 0.3f) : FLinearColor(0.85f, 0.85f, 0.85f));
}
