# main/forms.py
from django import forms
from .models import SonarToken


class SonarTokenForm(forms.ModelForm):
    class Meta:
        model = SonarToken
        fields = ["token"]
        widgets = {
            "sonar_token": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ingrese su token de Sonar"})
        }

