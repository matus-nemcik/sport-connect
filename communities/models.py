from django.conf import settings
from django.db import models

GLOBAL_COMMUNITY_NAME = "SportConnect"


class Community(models.Model):
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=200, blank=True)
    is_private = models.BooleanField(
        default=True, help_text="Private communities can be joined only by invitation."
    )
    is_global = models.BooleanField(
        default=False, editable=False, help_text="Everyone joins it on sign-up (global ranking)."
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_communities"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, through="Membership", related_name="communities")

    class Meta:
        ordering = ["-is_global", "name"]
        verbose_name_plural = "communities"

    def __str__(self):
        return self.name

    @classmethod
    def get_global(cls):
        community, _ = cls.objects.get_or_create(
            is_global=True,
            defaults={"name": GLOBAL_COMMUNITY_NAME, "is_private": False,
                      "description": "Everyone who uses SportConnect. Global ranking."},
        )
        return community

    def is_owner(self, user):
        return user.is_authenticated and self.owner_id == user.pk

    def has_member(self, user):
        return user.is_authenticated and self.memberships.filter(user=user).exists()


class Membership(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["community", "user"], name="unique_membership")]
        ordering = ["joined_at"]


class Invitation(models.Model):
    """An invitation for an e-mail that has no account yet.

    It turns into a membership when someone registers with that e-mail.
    """

    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["community", "email"], name="unique_invitation")]
