from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import User


class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput,
        label="Contraseña"
    )

    class Meta:
        model = User

        fields = [
            "full_name",
            "professional_role",
            "email",
        ]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Ya existe una cuenta con este correo electrónico."
            )

        return email

    def clean_password(self):
        password = self.cleaned_data["password"]

        user = User(
            email=self.cleaned_data.get("email", ""),
            full_name=self.cleaned_data.get("full_name", "")
        )

        try:
            validate_password(password, user)
        except ValidationError as error:
            raise forms.ValidationError(error.messages)

        return password

    def save(self, commit=True):
        user = super().save(commit=False)

        user.email = user.email.lower()
        user.set_password(self.cleaned_data["password"])

        if commit:
            user.save()

        return user


class LoginForm(forms.Form):
    email = forms.EmailField(
        label="Correo Electrónico"
    )

    password = forms.CharField(
        widget=forms.PasswordInput,
        label="Contraseña"
    )

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.request = request
        self.user = None

    def clean(self):
        cleaned_data = super().clean()

        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if email and password:
            self.user = authenticate(
                request=self.request,
                username=email.lower(),
                password=password
            )

            if self.user is None:
                raise forms.ValidationError(
                    "El correo electrónico o la contraseña son incorrectos."
                )

        return cleaned_data

    def get_user(self):
        return self.user