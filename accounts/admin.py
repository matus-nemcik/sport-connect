from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "nickname", "location", "is_staff")
    search_fields = ("email", "nickname")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("nickname", "location", "favorite_league", "favorite_team")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "nickname", "password1", "password2")}),)
