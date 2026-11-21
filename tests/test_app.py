from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from communities.models import Community, Invitation, Membership
from communities.ranking import community_ranking
from matches.football_data import import_payload
from matches.models import League, Match, Prediction, Team
from matches.scoring import points_for


def make_match(days=1, **kw):
    league, _ = League.objects.get_or_create(code="PD", defaults={"name": "La Liga"})
    home, _ = Team.objects.get_or_create(name="FC Barcelona")
    away, _ = Team.objects.get_or_create(name="Real Madrid")
    return Match.objects.create(league=league, home_team=home, away_team=away,
                                kickoff=timezone.now() + timedelta(days=days), **kw)


class ScoringTests(TestCase):
    def test_rules(self):
        self.assertEqual(points_for(3, 1, 3, 1), 3)   # exact
        self.assertEqual(points_for(2, 0, 3, 1), 1)   # right winner
        self.assertEqual(points_for(1, 1, 2, 2), 1)   # right draw
        self.assertEqual(points_for(0, 2, 3, 1), 0)   # wrong

    def test_evaluate_match_awards_points_once(self):
        m = make_match(days=-1)
        u = User.objects.create_user("a@x.sk", "pw", nickname="A")
        Prediction.objects.create(user=u, match=m, home_score=3, away_score=1)
        m.status, m.home_score, m.away_score = Match.FINISHED, 3, 1
        m.save()
        m.evaluate(); m.evaluate()
        self.assertEqual(u.stats()["points"], 3)
        self.assertTrue(Match.objects.get(pk=m.pk).evaluated)


class AccountTests(TestCase):
    def test_register_login_joins_global_and_invited_community(self):
        owner = User.objects.create_user("tondo@x.sk", "pw", nickname="Tondo")
        c = Community.objects.create(name="Experti", owner=owner)
        Invitation.objects.create(community=c, email="pavol@x.sk", invited_by=owner)
        r = self.client.post(reverse("register"), {
            "nickname": "Pavol", "email": "Pavol@x.sk", "password1": "Tipujem-2026!", "password2": "Tipujem-2026!"})
        self.assertRedirects(r, reverse("matches:list"))
        pavol = User.objects.get(email="pavol@x.sk")
        self.assertTrue(Community.get_global().has_member(pavol))
        self.assertTrue(c.has_member(pavol))
        self.assertFalse(Invitation.objects.exists())

    def test_login_with_email(self):
        User.objects.create_user("pavol@x.sk", "secret-pw-1", nickname="Pavol")
        r = self.client.post(reverse("login"), {"username": "pavol@x.sk", "password": "secret-pw-1"})
        self.assertRedirects(r, reverse("matches:list"))

    def test_pages_require_login(self):
        r = self.client.get(reverse("matches:list"))
        self.assertEqual(r.status_code, 302)


class TippingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("pavol@x.sk", "pw", nickname="Pavol")
        self.client.force_login(self.user)

    def test_save_and_update_tip(self):
        m = make_match()
        url = reverse("matches:detail", args=[m.pk])
        self.client.post(url, {"home_score": 3, "away_score": 1})
        self.client.post(url, {"home_score": 2, "away_score": 2})
        p = Prediction.objects.get(user=self.user, match=m)
        self.assertEqual(p.score, "2:2")

    def test_no_tip_after_kickoff(self):
        m = make_match(days=-1)
        self.client.post(reverse("matches:detail", args=[m.pk]), {"home_score": 1, "away_score": 0})
        self.assertFalse(Prediction.objects.exists())

    def test_list_search_and_league_filter(self):
        make_match()
        r = self.client.get(reverse("matches:list"), {"q": "barc"})
        self.assertContains(r, "FC Barcelona")
        r = self.client.get(reverse("matches:list"), {"league": "PL"})
        self.assertNotContains(r, "Real Madrid")


class CommunityTests(TestCase):
    def setUp(self):
        self.tondo = User.objects.create_user("tondo@x.sk", "pw", nickname="Tondo")
        self.pavol = User.objects.create_user("pavol@x.sk", "pw", nickname="Pavol")
        self.client.force_login(self.tondo)

    def test_create_private_with_invite(self):
        r = self.client.post(reverse("communities:create"), {
            "name": "Futbaloví experti", "privacy": "private", "invite_emails": "pavol@x.sk, new@x.sk"})
        c = Community.objects.get(name="Futbaloví experti")
        self.assertRedirects(r, reverse("communities:detail", args=[c.pk]))
        self.assertTrue(c.is_private)
        self.assertTrue(c.has_member(self.pavol))
        self.assertTrue(Invitation.objects.filter(community=c, email="new@x.sk").exists())

    def test_private_community_hidden_from_non_members(self):
        c = Community.objects.create(name="Secret", owner=self.tondo)
        Membership.objects.create(community=c, user=self.tondo)
        self.client.force_login(self.pavol)
        self.assertEqual(self.client.get(reverse("communities:detail", args=[c.pk])).status_code, 404)
        self.client.post(reverse("communities:join", args=[c.pk]))
        self.assertFalse(c.has_member(self.pavol))

    def test_owner_removes_member_and_ranking(self):
        c = Community.objects.create(name="F", owner=self.tondo)
        for u in (self.tondo, self.pavol):
            Membership.objects.create(community=c, user=u)
        m = make_match(days=-1, status=Match.FINISHED, home_score=2, away_score=0)
        Prediction.objects.create(user=self.pavol, match=m, home_score=2, away_score=0)
        Prediction.objects.create(user=self.tondo, match=m, home_score=1, away_score=0)
        m.evaluate()
        rows = community_ranking(c)
        self.assertEqual([r["user"] for r in rows], [self.pavol, self.tondo])
        self.client.post(reverse("communities:remove_member", args=[c.pk, self.pavol.pk]))
        self.assertFalse(c.has_member(self.pavol))


class ImportTests(TestCase):
    PAYLOAD = {
        "competition": {"id": 2014, "name": "Primera Division", "code": "PD", "emblem": ""},
        "matches": [
            {"id": 1, "utcDate": "2026-11-20T20:00:00Z", "status": "FINISHED", "matchday": 13,
             "homeTeam": {"id": 81, "name": "FC Barcelona", "shortName": "Barça", "tla": "FCB", "crest": ""},
             "awayTeam": {"id": 86, "name": "Real Madrid CF", "shortName": "Real Madrid", "tla": "RMA", "crest": ""},
             "score": {"fullTime": {"home": 3, "away": 1}}},
            {"id": 2, "utcDate": "2030-01-01T20:00:00Z", "status": "TIMED",
             "homeTeam": {"id": 86, "name": "Real Madrid CF"}, "awayTeam": {"id": 81, "name": "FC Barcelona"},
             "score": {"fullTime": {"home": None, "away": None}}},
            {"id": 3, "utcDate": "2030-01-02T20:00:00Z", "status": "TIMED",
             "homeTeam": {"id": None}, "awayTeam": {"id": None}, "score": {}},
        ],
    }

    def test_import_and_evaluate(self):
        user = User.objects.create_user("p@x.sk", "pw", nickname="P")
        import_payload({**self.PAYLOAD, "matches": self.PAYLOAD["matches"][1:]})
        future = Match.objects.get(external_id=2)
        self.assertEqual(future.status, Match.SCHEDULED)
        saved, evaluated = import_payload(self.PAYLOAD)
        self.assertEqual((saved, evaluated), (2, 1))
        finished = Match.objects.get(external_id=1)
        Prediction.objects.create(user=user, match=finished, home_score=3, away_score=1)
        finished.evaluated = False
        finished.save()
        import_payload(self.PAYLOAD)
        self.assertEqual(user.stats()["points"], 3)
        self.assertEqual(League.objects.get(code="PD").name, "Primera Division")
