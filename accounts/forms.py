from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from matches.models import League, Team

from .models import User


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}))

    def clean_username(self):
        return self.cleaned_data["username"].lower()


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("nickname", "email")
        labels = {"nickname": "Nickname"}
        help_texts = {"nickname": "Shown to your friends in communities and rankings."}

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("nickname", "location", "favorite_league", "favorite_team")
        labels = {"favorite_league": "Favourite league", "favorite_team": "Favourite team"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["favorite_league"].queryset = League.objects.all()
        self.fields["favorite_team"].queryset = Team.objects.all()
        self.fields["favorite_league"].empty_label = "None"
        self.fields["favorite_team"].empty_label = "None"
