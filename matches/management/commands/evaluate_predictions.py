from django.core.management.base import BaseCommand

from matches.models import Match


class Command(BaseCommand):
    help = "Award points for tips on finished matches that have a result."

    def handle(self, *args, **opts):
        n = 0
        for match in Match.objects.filter(status=Match.FINISHED, evaluated=False):
            if match.has_result:
                match.evaluate()
                n += 1
        self.stdout.write(self.style.SUCCESS(f"Evaluated {n} matches."))
