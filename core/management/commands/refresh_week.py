from django.core.management.base import BaseCommand, CommandParser

from services.nfl import refresh_week_cache


class Command(BaseCommand):
    help = 'Fetch and cache nflreadpy data for a given 2025 week.'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--season', type=int, default=2025)
        parser.add_argument('--week', type=int, required=True)

    def handle(self, *args, **options):
        season = options['season']
        week = options['week']
        if season != 2025:
            self.stderr.write('Only season 2025 is supported.')
            return
        self.stdout.write(f'Refreshing caches for season={season} week={week}...')
        refresh_week_cache(week)
        self.stdout.write(self.style.SUCCESS('Done.'))


