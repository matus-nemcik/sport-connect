from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models import Count, Q, Sum


class UserManager(BaseUserManager):
    """Users sign in with their e-mail address instead of a username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("E-mail is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("nickname", "admin")
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    username = None
    email = models.EmailField("e-mail", unique=True)
    nickname = models.CharField(max_length=40)
    location = models.CharField(max_length=80, blank=True)
    favorite_league = models.ForeignKey(
        "matches.League", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    favorite_team = models.ForeignKey(
        "matches.Team", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ["nickname"]

    def __str__(self):
        return self.nickname or self.email

    @property
    def initial(self):
        return (self.nickname or self.email)[:1].upper()

    def stats(self):
        return stats_for(User.objects.filter(pk=self.pk)).get(self.pk, empty_stats())


def empty_stats():
    return {"tips": 0, "evaluated": 0, "exact": 0, "correct": 0, "points": 0, "success_rate": 0}


def stats_for(users):
    """Tipping statistics (FR7) for a queryset of users, keyed by user id.

    success_rate is the share of evaluated tips that earned any points.
    """
    rows = users.annotate(
        s_tips=Count("predictions", distinct=True),
        s_evaluated=Count("predictions", filter=Q(predictions__points__isnull=False), distinct=True),
        s_exact=Count("predictions", filter=Q(predictions__points=3), distinct=True),
        s_correct=Count("predictions", filter=Q(predictions__points__gt=0), distinct=True),
        s_points=Sum("predictions__points"),
    ).values("pk", "s_tips", "s_evaluated", "s_exact", "s_correct", "s_points")
    out = {}
    for r in rows:
        evaluated = r["s_evaluated"]
        out[r["pk"]] = {
            "tips": r["s_tips"],
            "evaluated": evaluated,
            "exact": r["s_exact"],
            "correct": r["s_correct"],
            "points": r["s_points"] or 0,
            "success_rate": round(100 * r["s_correct"] / evaluated) if evaluated else 0,
        }
    return out
