from django.conf import settings
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

from .scoring import points_for


class League(models.Model):
    name = models.CharField(max_length=80)
    code = models.CharField(max_length=10, unique=True)
    country = models.CharField(max_length=60, blank=True)
    emblem_url = models.URLField(blank=True)
    external_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=40, blank=True)
    tla = models.CharField("abbreviation", max_length=5, blank=True)
    crest_url = models.URLField(blank=True)
    venue = models.CharField(max_length=100, blank=True)
    external_id = models.PositiveIntegerField(null=True, blank=True, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return self.short_name or self.name


class Match(models.Model):
    SCHEDULED = "SCHEDULED"
    LIVE = "LIVE"
    FINISHED = "FINISHED"
    POSTPONED = "POSTPONED"
    CANCELLED = "CANCELLED"
    STATUS_CHOICES = [
        (SCHEDULED, "Scheduled"),
        (LIVE, "Live"),
        (FINISHED, "Finished"),
        (POSTPONED, "Postponed"),
        (CANCELLED, "Cancelled"),
    ]

    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name="matches")
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="home_matches")
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="away_matches")
    kickoff = models.DateTimeField(db_index=True)
    venue = models.CharField(max_length=100, blank=True)
    matchday = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=SCHEDULED)
    home_score = models.PositiveSmallIntegerField(null=True, blank=True)
    away_score = models.PositiveSmallIntegerField(null=True, blank=True)
    evaluated = models.BooleanField(default=False, editable=False)
    external_id = models.PositiveIntegerField(null=True, blank=True, unique=True)

    class Meta:
        ordering = ["kickoff"]
        verbose_name_plural = "matches"

    def __str__(self):
        return f"{self.home_team} vs {self.away_team}"

    def get_absolute_url(self):
        return reverse("matches:detail", args=[self.pk])

    @property
    def venue_display(self):
        return self.venue or self.home_team.venue

    @property
    def is_open(self):
        """Tips may be placed or changed only before kickoff (FR3)."""
        return self.status == self.SCHEDULED and self.kickoff > timezone.now()

    @property
    def has_result(self):
        return self.home_score is not None and self.away_score is not None

    def evaluate(self):
        """Award points for every tip on a finished match (FR4). Idempotent."""
        if self.status != self.FINISHED or not self.has_result:
            return 0
        with transaction.atomic():
            preds = list(self.predictions.select_for_update())
            for p in preds:
                p.points = points_for(p.home_score, p.away_score, self.home_score, self.away_score)
            Prediction.objects.bulk_update(preds, ["points"])
            if not self.evaluated:
                self.evaluated = True
                Match.objects.filter(pk=self.pk).update(evaluated=True)
        return len(preds)


class Prediction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="predictions")
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="predictions")
    home_score = models.PositiveSmallIntegerField()
    away_score = models.PositiveSmallIntegerField()
    comment = models.CharField(max_length=140, blank=True)
    points = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "match"], name="one_tip_per_match")]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user}: {self.match} {self.score}"

    @property
    def score(self):
        return f"{self.home_score}:{self.away_score}"


class Reaction(models.Model):
    LIKE = 1
    DISLIKE = -1
    prediction = models.ForeignKey(Prediction, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reactions")
    value = models.SmallIntegerField(choices=[(LIKE, "Like"), (DISLIKE, "Dislike")])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["prediction", "user"], name="one_reaction_per_user")]


class SyncState(models.Model):
    """Remembers when matches were last fetched from the external API."""

    key = models.CharField(max_length=40, unique=True)
    last_run = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
