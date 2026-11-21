from django.contrib import admin

from .models import Community, Invitation, Membership


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ("name", "is_private", "is_global", "owner", "created_at")
    inlines = [MembershipInline]


admin.site.register(Invitation)
