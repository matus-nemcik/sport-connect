from datetime import timedelta
from itertools import groupby

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from communities.models import Community

from .football_data import sync_if_stale
from .models import League, Match, Prediction, Reaction


class PredictionForm(forms.Form):
    home_score = forms.IntegerField(min_value=0, max_value=20)
    away_score = forms.IntegerField(min_value=0, max_value=20)
    comment = forms.CharField(max_length=140, required=False)


def _visible_matches(tab):
    now = timezone.now()
    qs = Match.objects.select_related("league", "home_team", "away_team")
    if tab == "closed":
        return qs.filter(
            Q(status__in=[Match.FINISHED, Match.LIVE]) | Q(kickoff__lte=now),
            kickoff__gte=now - timedelta(days=14),
        ).exclude(status=Match.CANCELLED).order_by("-kickoff")
    return qs.filter(status=Match.SCHEDULED, kickoff__gt=now, kickoff__lte=now + timedelta(days=21))


@login_required
def match_list(request):
    try:
        sync_if_stale()
    except Exception:  # never break the page because the external API failed
        pass
    tab = "closed" if request.GET.get("tab") == "closed" else "upcoming"
    q = request.GET.get("q", "").strip()
    league_code = request.GET.get("league", "")
    user = request.user

    matches = _visible_matches(tab)
    if q:
        matches = matches.filter(Q(home_team__name__icontains=q) | Q(away_team__name__icontains=q)
                                 | Q(home_team__short_name__icontains=q) | Q(away_team__short_name__icontains=q))
    if league_code == "fav":
        matches = matches.filter(
            Q(league_id=user.favorite_league_id) | Q(home_team_id=user.favorite_team_id) | Q(away_team_id=user.favorite_team_id)
        )
    elif league_code:
        matches = matches.filter(league__code=league_code)

    matches = list(matches)
    tips = {p.match_id: p for p in Prediction.objects.filter(user=user, match__in=matches)}
    for m in matches:
        m.my_tip = tips.get(m.pk)
        m.is_favorite = user.favorite_team_id in (m.home_team_id, m.away_team_id)

    # Group by league (favourite league first), keeping time order inside a league.
    def league_key(m):
        return (m.league_id != user.favorite_league_id, m.league.order, m.league.name)

    groups = [(league, list(items)) for league, items in
              groupby(sorted(matches, key=league_key), key=lambda m: m.league)]

    leagues = League.objects.filter(matches__in=_visible_matches(tab)).distinct()
    return render(request, "matches/list.html", {
        "groups": groups, "tab": tab, "q": q, "league_code": league_code, "leagues": leagues,
        "has_favorites": bool(user.favorite_league_id or user.favorite_team_id), "nav": "matches",
    })


@login_required
def match_detail(request, pk):
    match = get_object_or_404(Match.objects.select_related("league", "home_team", "away_team"), pk=pk)
    user = request.user
    my_tip = Prediction.objects.filter(user=user, match=match).first()
    editing = match.is_open and (my_tip is None or request.GET.get("edit") == "1")

    if request.method == "POST":
        if not match.is_open:
            messages.error(request, "Tips are closed, the match has already started.")
            return redirect("matches:detail", pk=pk)
        form = PredictionForm(request.POST)
        if form.is_valid():
            Prediction.objects.update_or_create(user=user, match=match, defaults=form.cleaned_data)
            messages.success(request, "Prediction saved" if my_tip is None else "Prediction updated")
            url = f"{match.get_absolute_url()}"
            if request.GET.get("community"):
                url += f"?community={request.GET['community']}"
            return redirect(url)
        editing = True
    else:
        initial = {"home_score": my_tip.home_score, "away_score": my_tip.away_score,
                   "comment": my_tip.comment} if my_tip else None
        form = PredictionForm(initial=initial)

    # Community bets (members' tips with reactions)
    communities = list(user.communities.all())
    community = None
    cid = request.GET.get("community")
    if cid:
        community = next((c for c in communities if str(c.pk) == cid), None)
    if community is None:
        community = next((c for c in communities if not c.is_global), communities[0] if communities else None)
    bets = []
    if community:
        bets = list(
            Prediction.objects.filter(match=match, user__in=community.members.all()).exclude(user=user)
            .select_related("user")
            .annotate(likes=Count("reactions", filter=Q(reactions__value=Reaction.LIKE)),
                      dislikes=Count("reactions", filter=Q(reactions__value=Reaction.DISLIKE)))
            .order_by("user__nickname")
        )
        mine = {r.prediction_id: r.value for r in Reaction.objects.filter(user=user, prediction__in=bets)}
        for b in bets:
            b.my_reaction = mine.get(b.pk)

    return render(request, "matches/detail.html", {
        "match": match, "my_tip": my_tip, "form": form, "editing": editing,
        "communities": communities, "community": community, "bets": bets, "nav": "matches",
    })


@login_required
@require_POST
def react(request, pk):
    prediction = get_object_or_404(Prediction.objects.select_related("match"), pk=pk)
    if prediction.user_id == request.user.pk:
        raise Http404
    shared = Community.objects.filter(memberships__user=request.user).filter(memberships__user=prediction.user_id)
    if not shared.exists():
        raise Http404
    value = Reaction.LIKE if request.POST.get("value") == "like" else Reaction.DISLIKE
    existing = Reaction.objects.filter(prediction=prediction, user=request.user).first()
    if existing and existing.value == value:
        existing.delete()  # clicking the same reaction again removes it
    else:
        Reaction.objects.update_or_create(prediction=prediction, user=request.user, defaults={"value": value})
    url = prediction.match.get_absolute_url()
    if request.POST.get("community"):
        url += f"?community={request.POST['community']}"
    return redirect(url + "#community-bets")


@login_required
def my_bets(request):
    preds = list(Prediction.objects.filter(user=request.user)
                 .select_related("match", "match__league", "match__home_team", "match__away_team")
                 .order_by("match__kickoff"))
    upcoming = [p for p in preds if p.match.is_open]
    in_play = [p for p in preds if not p.match.is_open and p.points is None]
    finished = sorted((p for p in preds if p.points is not None), key=lambda p: p.match.kickoff, reverse=True)
    return render(request, "matches/my_bets.html", {
        "upcoming": upcoming, "in_play": in_play, "finished": finished,
        "stats": request.user.stats(), "nav": "bets",
    })


@login_required
@require_POST
def toggle_favorite_league(request, code):
    league = get_object_or_404(League, code=code)
    user = request.user
    user.favorite_league = None if user.favorite_league_id == league.pk else league
    user.save(update_fields=["favorite_league"])
    return redirect(request.POST.get("next") or "matches:list")
