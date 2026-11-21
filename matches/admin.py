from django.contrib import admin, messages

from .models import League, Match, Prediction, Reaction, SyncState, Team


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "country", "order")
    list_editable = ("order",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "tla", "venue")
    search_fields = ("name", "short_name", "tla")


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("__str__", "league", "kickoff", "status", "home_score", "away_score", "evaluated")
    list_filter = ("league", "status", "evaluated")
    search_fields = ("home_team__name", "away_team__name")
    date_hierarchy = "kickoff"
    autocomplete_fields = ("home_team", "away_team")
    actions = ["evaluate_tips"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.status == Match.FINISHED and obj.has_result:
            n = obj.evaluate()
            self.message_user(request, f"Evaluated {n} tips for {obj}.")

    @admin.action(description="Evaluate tips of selected finished matches")
    def evaluate_tips(self, request, queryset):
        total = sum(m.evaluate() for m in queryset)
        self.message_user(request, f"Evaluated {total} tips.", messages.SUCCESS)


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ("user", "match", "score", "points", "updated_at")
    list_filter = ("match__league",)
    search_fields = ("user__email", "user__nickname")


admin.site.register(Reaction)
admin.site.register(SyncState)
