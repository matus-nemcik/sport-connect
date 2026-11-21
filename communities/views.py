from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from matches.models import Match, Prediction

from .models import Community, Invitation, Membership
from .ranking import community_ranking

PRIVACY_CHOICES = [("private", "Private"), ("public", "Public")]


class CommunityForm(forms.ModelForm):
    privacy = forms.ChoiceField(choices=PRIVACY_CHOICES, widget=forms.RadioSelect, initial="private")

    class Meta:
        model = Community
        fields = ("name", "description")
        labels = {"name": "Community name"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["privacy"] = "private" if self.instance.is_private else "public"

    def save(self, commit=True):
        self.instance.is_private = self.cleaned_data["privacy"] == "private"
        return super().save(commit)


class CreateCommunityForm(CommunityForm):
    invite_emails = forms.CharField(
        required=False, label="Invite friends",
        widget=forms.TextInput(attrs={"placeholder": "friend@email.com, another@email.com"}),
        help_text="Optional. You can invite more people later.",
    )

    def clean_invite_emails(self):
        raw = self.cleaned_data["invite_emails"].replace(";", ",").replace(" ", ",")
        emails = [e.strip().lower() for e in raw.split(",") if e.strip()]
        for e in emails:
            try:
                validate_email(e)
            except forms.ValidationError:
                raise forms.ValidationError(f"“{e}” is not a valid email address.")
        return emails


class InviteForm(forms.Form):
    email = forms.EmailField(label="Friend's email", widget=forms.EmailInput(attrs={"placeholder": "friend@email.com"}))


def invite(community, email, invited_by):
    """Add an existing user directly; remember the e-mail for people without an account.

    Returns (status, user) where status is 'added', 'already', 'invited' or 'self'.
    """
    email = email.lower()
    user = User.objects.filter(email__iexact=email).first()
    if user:
        if user == invited_by:
            return "self", user
        _, created = Membership.objects.get_or_create(community=community, user=user)
        return ("added" if created else "already"), user
    Invitation.objects.get_or_create(community=community, email=email, defaults={"invited_by": invited_by})
    return "invited", None


def _get_member_community(request, pk):
    community = get_object_or_404(Community, pk=pk)
    is_member = community.has_member(request.user)
    if community.is_private and not is_member:
        raise Http404
    return community, is_member


@login_required
def community_list(request):
    mine = (Community.objects.filter(pk__in=request.user.communities.values("pk"))
            .annotate(n=Count("memberships", distinct=True)))
    q = request.GET.get("q", "").strip()
    public = (Community.objects.filter(is_private=False).exclude(memberships__user=request.user)
              .annotate(n=Count("memberships", distinct=True)))
    if q:
        public = public.filter(name__icontains=q)
    return render(request, "communities/list.html", {
        "mine": mine, "public": public.order_by("-n", "name")[:20], "q": q, "nav": "groups",
    })


@login_required
def community_create(request):
    form = CreateCommunityForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            community = form.save(commit=False)
            community.owner = request.user
            community.save()
            Membership.objects.create(community=community, user=request.user)
            results = [invite(community, e, request.user)[0] for e in form.cleaned_data["invite_emails"]]
        msg = f"Community “{community.name}” created"
        if results:
            msg += f", {len([r for r in results if r != 'self'])} friend(s) invited"
        messages.success(request, msg)
        return redirect("communities:detail", pk=community.pk)
    return render(request, "communities/create.html", {"form": form, "nav": "groups"})


@login_required
def community_detail(request, pk, tab="members"):
    community, is_member = _get_member_community(request, pk)
    ctx = {"community": community, "is_member": is_member, "is_owner": community.is_owner(request.user),
           "tab": tab, "nav": "groups"}

    if tab == "members":
        ctx["memberships"] = community.memberships.select_related("user").order_by("joined_at")
        ctx["invitations"] = community.invitations.all() if ctx["is_owner"] else []
        ctx["invite_form"] = InviteForm()
        ctx["show_invite"] = request.GET.get("invite") == "1"
    elif tab == "rankings":
        ctx["rows"] = community_ranking(community)
    elif tab == "bets":
        now = timezone.now()
        member_ids = community.members.values_list("pk", flat=True)
        matches = (Match.objects.filter(predictions__user__in=member_ids).distinct()
                   .select_related("home_team", "away_team", "league").order_by("-kickoff")[:30])
        upcoming = Match.objects.filter(status=Match.SCHEDULED, kickoff__gt=now).select_related(
            "home_team", "away_team").order_by("kickoff")[:10]
        options = list({m.pk: m for m in list(upcoming) + list(matches)}.values())
        options.sort(key=lambda m: m.kickoff)
        selected = None
        if request.GET.get("match"):
            selected = next((m for m in options if str(m.pk) == request.GET["match"]), None)
        if selected is None and options:
            selected = next((m for m in options if m.kickoff > now), options[-1])
        ctx["match_options"] = options
        ctx["selected"] = selected
        ctx["bets"] = (Prediction.objects.filter(match=selected, user__in=member_ids).select_related("user")
                       .order_by("user__nickname") if selected else [])
    return render(request, "communities/detail.html", ctx)


@login_required
@require_POST
def invite_member(request, pk):
    community = get_object_or_404(Community, pk=pk)
    if not community.is_owner(request.user):
        raise Http404
    form = InviteForm(request.POST)
    if form.is_valid():
        status, user = invite(community, form.cleaned_data["email"], request.user)
        text = {
            "added": f"{user} added to the community" if user else "",
            "already": f"{user} is already a member",
            "invited": f"Invitation saved. {form.cleaned_data['email']} joins after signing up.",
            "self": "You are already a member",
        }[status]
        (messages.success if status in ("added", "invited") else messages.info)(request, text)
    else:
        messages.error(request, "Enter a valid email address.")
        return redirect(reverse("communities:detail", args=[pk]) + "?invite=1")
    return redirect("communities:detail", pk=pk)


@login_required
@require_POST
def remove_member(request, pk, user_id):
    community = get_object_or_404(Community, pk=pk)
    if not community.is_owner(request.user) or user_id == request.user.pk:
        raise Http404
    m = get_object_or_404(Membership, community=community, user_id=user_id)
    name = m.user.nickname
    m.delete()
    messages.success(request, f"{name} removed from the community")
    return redirect("communities:detail", pk=pk)


@login_required
@require_POST
def cancel_invitation(request, pk, inv_id):
    community = get_object_or_404(Community, pk=pk)
    if not community.is_owner(request.user):
        raise Http404
    Invitation.objects.filter(community=community, pk=inv_id).delete()
    messages.success(request, "Invitation cancelled")
    return redirect("communities:detail", pk=pk)


@login_required
@require_POST
def join(request, pk):
    community = get_object_or_404(Community, pk=pk, is_private=False)
    Membership.objects.get_or_create(community=community, user=request.user)
    messages.success(request, f"You joined “{community.name}”")
    return redirect("communities:detail", pk=pk)


@login_required
@require_POST
def leave(request, pk):
    community = get_object_or_404(Community, pk=pk)
    if community.is_owner(request.user):
        messages.error(request, "You own this community. Delete it in Settings instead.")
        return redirect("communities:detail", pk=pk)
    Membership.objects.filter(community=community, user=request.user).delete()
    messages.success(request, f"You left “{community.name}”")
    return redirect("communities:list")


@login_required
def community_settings(request, pk):
    community = get_object_or_404(Community, pk=pk)
    if not community.is_owner(request.user):
        raise Http404
    form = CommunityForm(request.POST or None, instance=community)
    if request.method == "POST":
        if "delete" in request.POST:
            name = community.name
            community.delete()
            messages.success(request, f"Community “{name}” deleted")
            return redirect("communities:list")
        if form.is_valid():
            form.save()
            messages.success(request, "Settings saved")
            return redirect("communities:detail", pk=pk)
    return render(request, "communities/settings.html", {"form": form, "community": community, "nav": "groups"})


@login_required
def ranking_view(request):
    communities = list(request.user.communities.all())
    community = None
    if request.GET.get("community"):
        community = next((c for c in communities if str(c.pk) == request.GET["community"]), None)
    if community is None:
        community = Community.get_global()
    return render(request, "communities/ranking.html", {
        "communities": communities, "community": community, "rows": community_ranking(community),
        "is_member": community.has_member(request.user), "nav": "ranking",
    })
