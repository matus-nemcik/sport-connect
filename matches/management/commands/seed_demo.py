"""Demo data for local development and usability testing.

    python manage.py seed_demo              # demo users, community, matches and tips
    python manage.py seed_demo --real       # users, community and tips on real API matches
    python manage.py seed_demo --no-matches # only users and community

All demo users have the password given by --password (default: sportconnect).
"""
import random
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from communities.models import Community, Membership
from matches.models import League, Match, Prediction, Reaction, Team

LEAGUES = [
    ("PL", "Premier League", "England", 1),
    ("PD", "La Liga", "Spain", 2),
    ("SK1", "Niké liga", "Slovakia", 7),
]

TEAMS = {
    "Arsenal": ("ARS", "Emirates Stadium"),
    "Chelsea": ("CHE", "Stamford Bridge"),
    "Liverpool": ("LIV", "Anfield"),
    "Man City": ("MCI", "Etihad Stadium"),
    "Tottenham": ("TOT", "Tottenham Hotspur Stadium"),
    "Man United": ("MUN", "Old Trafford"),
    "FC Barcelona": ("FCB", "Camp Nou"),
    "Real Madrid": ("RMA", "Santiago Bernabéu"),
    "Atlético Madrid": ("ATM", "Metropolitano"),
    "Sevilla": ("SEV", "Ramón Sánchez-Pizjuán"),
    "Slovan Bratislava": ("SLO", "Tehelné pole"),
    "Spartak Trnava": ("TRN", "Štadión Antona Malatinského"),
    "DAC Dunajská Streda": ("DAC", "MOL Aréna"),
    "MŠK Žilina": ("ZIL", "Štadión pod Dubňom"),
}

# (league, home, away, days from today, hour, minute, result or None)
MATCHES = [
    ("SK1", "Slovan Bratislava", "Spartak Trnava", 0, 18, 30, None),
    ("PL", "Arsenal", "Chelsea", 1, 13, 30, None),
    ("PD", "FC Barcelona", "Real Madrid", 1, 20, 0, None),
    ("PL", "Liverpool", "Arsenal", 2, 17, 30, None),
    ("PL", "Man City", "Tottenham", 3, 21, 0, None),
    ("PD", "Atlético Madrid", "Sevilla", 3, 18, 30, None),
    ("SK1", "DAC Dunajská Streda", "MŠK Žilina", 4, 18, 0, None),
    ("PL", "Man United", "Liverpool", 6, 16, 0, None),
    ("PD", "Real Madrid", "Atlético Madrid", 7, 21, 0, None),
    ("PL", "Chelsea", "Man City", -1, 16, 0, (1, 2)),
    ("PD", "Sevilla", "FC Barcelona", -2, 21, 0, (0, 3)),
    ("SK1", "Spartak Trnava", "DAC Dunajská Streda", -3, 18, 0, (2, 2)),
    ("PL", "Tottenham", "Man United", -4, 17, 30, (3, 1)),
]

USERS = [
    ("pavol@example.com", "Pavol", "Bratislava"),
    ("tondo@example.com", "Tondo", "Šarišské Michaľany"),
    ("marek@example.com", "Marek", "Košice"),
    ("jana@example.com", "Jana", "Žilina"),
    ("peter@example.com", "Peter", "Trnava"),
]

# user -> tips for finished matches (index into MATCHES) and upcoming ones
TIPS = {
    "Tondo": {9: (1, 2), 10: (1, 2), 11: (1, 1), 12: (2, 0), 2: (1, 2), 1: (2, 1)},
    "Marek": {9: (2, 2), 10: (0, 3), 11: (0, 1), 12: (3, 1), 2: (2, 2), 3: (1, 1)},
    "Jana": {9: (0, 1), 10: (1, 1), 11: (2, 2), 2: (3, 0), 0: (2, 0)},
    "Peter": {9: (2, 1), 10: (0, 2), 12: (1, 1), 1: (0, 0)},
    "Pavol": {9: (0, 2), 10: (1, 3), 11: (1, 0), 12: (2, 1)},
}
COMMENTS = {("Tondo", 2): "Real wins this one, mark my words.", ("Marek", 2): "Draw, both teams tired."}


class Command(BaseCommand):
    help = "Create demo users, a community, matches and tips."

    def add_arguments(self, parser):
        parser.add_argument("--no-matches", action="store_true", help="Skip demo leagues, matches and tips.")
        parser.add_argument("--real", action="store_true",
                            help="No demo matches; give demo users tips on matches imported from the API.")
        parser.add_argument("--password", default="sportconnect")

    @transaction.atomic
    def handle(self, *args, **opts):
        users = {}
        for email, nick, location in USERS:
            user = User.objects.filter(email=email).first()
            if not user:
                user = User.objects.create_user(email, opts["password"], nickname=nick, location=location)
            users[nick] = user

        friends, _ = Community.objects.get_or_create(
            name="Football friends",
            defaults={"owner": users["Tondo"], "is_private": True,
                      "description": "Friday football and a beer afterwards."},
        )
        for nick in ("Tondo", "Pavol", "Marek", "Jana", "Peter"):
            Membership.objects.get_or_create(community=friends, user=users[nick])

        if opts["real"]:
            self._tips_on_real_matches(users)
        elif not opts["no_matches"]:
            self._matches(users)
        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready. Log in as pavol@example.com / {opts['password']} "
            f"(also tondo@, marek@, jana@, peter@example.com)."))

    def _tips_on_real_matches(self, users):
        """Demo tips on real (imported) matches, so rankings and community bets have data.

        Pavol gets no tips on upcoming matches, so testers can place their own.
        """
        now = timezone.now()
        real = Match.objects.filter(external_id__isnull=False)
        finished = list(real.filter(status=Match.FINISHED, home_score__isnull=False).order_by("-kickoff")[:12])
        upcoming = list(real.filter(status=Match.SCHEDULED, kickoff__gt=now).order_by("kickoff")[:8])
        if not finished and not upcoming:
            self.stdout.write(self.style.WARNING("No imported matches. Run `python manage.py sync_matches` first."))
            return
        rng = random.Random(2026)  # same tips every run
        pool = [(1, 0), (2, 1), (1, 1), (0, 0), (2, 0), (0, 1), (1, 2), (3, 1), (2, 2), (0, 2)]
        for nick, user in users.items():
            for m in finished:
                if rng.random() < 0.8:
                    # some exact hits so the ranking is interesting
                    h, a = (m.home_score, m.away_score) if rng.random() < 0.2 else rng.choice(pool)
                    Prediction.objects.update_or_create(user=user, match=m, defaults={"home_score": h, "away_score": a})
            if nick == "Pavol":
                continue
            for m in upcoming:
                if rng.random() < 0.6:
                    h, a = rng.choice(pool)
                    Prediction.objects.update_or_create(user=user, match=m, defaults={"home_score": h, "away_score": a})
        for m in finished:
            m.evaluate()
        self.stdout.write(f"Demo tips placed on {len(finished)} finished and {len(upcoming)} upcoming real matches.")

    def _matches(self, users):
        leagues = {}
        for code, name, country, order in LEAGUES:
            leagues[code], _ = League.objects.get_or_create(
                code=code, defaults={"name": name, "country": country, "order": order})
        teams = {}
        for name, (tla, venue) in TEAMS.items():
            teams[name], _ = Team.objects.get_or_create(
                name=name, external_id=None, defaults={"tla": tla, "venue": venue})

        today = timezone.localdate()
        tz = timezone.get_current_timezone()
        created = []
        for code, home, away, days, hh, mm, result in MATCHES:
            kickoff = datetime.combine(today + timedelta(days=days), time(hh, mm), tzinfo=tz)
            if result is None and kickoff <= timezone.now():
                kickoff = timezone.now() + timedelta(hours=2)
            match, _ = Match.objects.update_or_create(
                league=leagues[code], home_team=teams[home], away_team=teams[away], external_id=None,
                defaults={
                    "kickoff": kickoff,
                    "status": Match.FINISHED if result else Match.SCHEDULED,
                    "home_score": result[0] if result else None,
                    "away_score": result[1] if result else None,
                },
            )
            created.append(match)

        for nick, tips in TIPS.items():
            for idx, (h, a) in tips.items():
                Prediction.objects.update_or_create(
                    user=users[nick], match=created[idx],
                    defaults={"home_score": h, "away_score": a, "comment": COMMENTS.get((nick, idx), "")},
                )
        for m in created:
            m.evaluate()

        tondo_clasico = Prediction.objects.get(user=users["Tondo"], match=created[2])
        Reaction.objects.get_or_create(prediction=tondo_clasico, user=users["Marek"], defaults={"value": Reaction.DISLIKE})
        Reaction.objects.get_or_create(prediction=tondo_clasico, user=users["Peter"], defaults={"value": Reaction.LIKE})
