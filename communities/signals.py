from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Community, Invitation, Membership


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def join_communities_on_signup(sender, instance, created, **kwargs):
    """New users join the global community and any community they were invited to."""
    if not created:
        return
    Membership.objects.get_or_create(community=Community.get_global(), user=instance)
    invitations = Invitation.objects.filter(email__iexact=instance.email)
    for inv in invitations:
        Membership.objects.get_or_create(community=inv.community, user=instance)
    invitations.delete()
