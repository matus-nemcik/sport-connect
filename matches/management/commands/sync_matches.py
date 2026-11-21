from django.core.management.base import BaseCommand, CommandError

from matches.football_data import sync


class Command(BaseCommand):
    help = "Import fixtures and results from football-data.org and evaluate finished matches."

    def add_arguments(self, parser):
        parser.add_argument("--days-back", type=int, default=3)
        parser.add_argument("--days-ahead", type=int, default=14)
        parser.add_argument("--competitions", help="Comma-separated codes, e.g. PL,PD")

    def handle(self, *args, **opts):
        comps = opts["competitions"].split(",") if opts["competitions"] else None
        saved, evaluated, errors = sync(opts["days_back"], opts["days_ahead"], comps)
        for e in errors:
            self.stderr.write(self.style.WARNING(e))
        self.stdout.write(self.style.SUCCESS(f"Saved {saved} matches, evaluated {evaluated}."))
        if errors and not saved:
            raise CommandError("Sync failed, check FOOTBALL_DATA_TOKEN and the competition codes.")
