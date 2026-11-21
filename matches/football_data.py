"""Import of leagues, teams, fixtures and results from football-data.org (API v4).

The free tier allows 10 requests per minute; one sync makes one request per
competition listed in settings.FOOTBALL_COMPETITIONS.
"""
import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import League, Match, SyncState, Team

log = logging.getLogger(__name__)

API_URL = "https://api.football-data.org/v4"

# football-data.org status -> our status
STATUS_MAP = {
    "SCHEDULED": Match.SCHEDULED,
    "TIMED": Match.SCHEDULED,
    "IN_PLAY": Match.LIVE,
    "PAUSED": Match.LIVE,
    "LIVE": Match.LIVE,
    "FINISHED": Match.FINISHED,
    "AWARDED": Match.FINISHED,
    "POSTPONED": Match.POSTPONED,
    "SUSPENDED": Match.POSTPONED,
    "CANCELLED": Match.CANCELLED,
}

LEAGUE_ORDER = {"PL": 1, "PD": 2, "SA": 3, "BL1": 4, "FL1": 5, "CL": 6}


class FootballDataError(Exception):
    pass


def fetch_competition_matches(code, date_from, date_to, token=None, timeout=10):
    token = token or settings.FOOTBALL_DATA_TOKEN
    if not token:
        raise FootballDataError("FOOTBALL_DATA_TOKEN is not set")
    resp = requests.get(
        f"{API_URL}/competitions/{code}/matches",
        params={"dateFrom": date_from.isoformat(), "dateTo": date_to.isoformat()},
        headers={"X-Auth-Token": token},
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise FootballDataError(f"{code}: HTTP {resp.status_code} {resp.text[:200]}")
    return resp.json()


def _team(data):
    team, _ = Team.objects.update_or_create(
        external_id=data["id"],
        defaults={
            "name": data.get("name") or data.get("shortName") or "Unknown",
            "short_name": data.get("shortName") or "",
            "tla": data.get("tla") or "",
            "crest_url": data.get("crest") or "",
        },
    )
    return team


@transaction.atomic
def import_payload(payload):
    """Store one /competitions/{code}/matches response. Returns (saved, evaluated)."""
    comp = payload.get("competition") or {}
    area = (payload.get("area") or {}) or (comp.get("area") or {})
    league = None
    saved = evaluated = 0
    for m in payload.get("matches", []):
        home, away = m.get("homeTeam") or {}, m.get("awayTeam") or {}
        if not home.get("id") or not away.get("id"):
            continue  # knockout fixtures with teams not decided yet
        c = m.get("competition") or comp
        if league is None or league.external_id != c.get("id"):
            league, _ = League.objects.update_or_create(
                code=c.get("code"),
                defaults={
                    "external_id": c.get("id"),
                    "name": c.get("name", c.get("code")),
                    "emblem_url": c.get("emblem") or "",
                    "country": (m.get("area") or area).get("name", ""),
                    "order": LEAGUE_ORDER.get(c.get("code"), 50),
                },
            )
        full = (m.get("score") or {}).get("fullTime") or {}
        status = STATUS_MAP.get(m.get("status"), Match.SCHEDULED)
        match, _ = Match.objects.update_or_create(
            external_id=m["id"],
            defaults={
                "league": league,
                "home_team": _team(home),
                "away_team": _team(away),
                "kickoff": parse_datetime(m["utcDate"]),
                "venue": m.get("venue") or "",
                "matchday": m.get("matchday"),
                "status": status,
                "home_score": full.get("home"),
                "away_score": full.get("away"),
            },
        )
        saved += 1
        if status == Match.FINISHED and match.has_result and not match.evaluated:
            match.evaluate()
            evaluated += 1
    return saved, evaluated


def sync(days_back=3, days_ahead=14, competitions=None):
    """Fetch recent results and upcoming fixtures for all configured competitions."""
    today = timezone.localdate()
    date_from, date_to = today - timedelta(days=days_back), today + timedelta(days=days_ahead)
    total_saved = total_eval = 0
    errors = []
    for code in competitions or settings.FOOTBALL_COMPETITIONS:
        try:
            saved, ev = import_payload(fetch_competition_matches(code, date_from, date_to))
            total_saved += saved
            total_eval += ev
        except (FootballDataError, requests.RequestException, KeyError, ValueError) as exc:
            log.warning("football-data sync failed for %s: %s", code, exc)
            errors.append(str(exc))
    # Safety net: evaluate finished matches entered by hand in the admin.
    for match in Match.objects.filter(status=Match.FINISHED, evaluated=False):
        if match.has_result:
            match.evaluate()
            total_eval += 1
    SyncState.objects.update_or_create(
        key="football-data", defaults={"last_run": timezone.now(), "last_error": "\n".join(errors)}
    )
    return total_saved, total_eval, errors


def sync_if_stale():
    """Called from the match list; refreshes data at most every FOOTBALL_SYNC_MINUTES."""
    if not (settings.FOOTBALL_SYNC_ON_REQUEST and settings.FOOTBALL_DATA_TOKEN):
        return
    state, _ = SyncState.objects.get_or_create(key="football-data")
    limit = timezone.now() - timedelta(minutes=settings.FOOTBALL_SYNC_MINUTES)
    # Claim the slot first so parallel requests don't all hit the API.
    stale = Q(last_run__isnull=True) | Q(last_run__lt=limit)
    claimed = SyncState.objects.filter(pk=state.pk).filter(stale).update(last_run=timezone.now())
    if claimed:
        sync()

