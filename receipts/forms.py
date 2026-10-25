from allauth.account.forms import SignupForm
from django import forms


class LegalSignupForm(SignupForm):
    terms_accepted = forms.BooleanField(
        required=True,
        label="Acepto los Términos de Servicio y la Política de Privacidad",
        error_messages={
            "required": "Debes aceptar los Términos de Servicio y la Política de Privacidad para crear una cuenta."
        },
    )

    def save(self, request):
        user = super().save(request)
        return user
