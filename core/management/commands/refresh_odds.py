"""
Management command to refresh odds data from the API.
Calls real HTTP endpoints only; no mock data.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from services.nfl import get_current_week, get_current_week_games
from services.odds_provider import fetch_prizepicks_props_for_games


class Command(BaseCommand):
    help = 'Refresh odds data from the API for current week games'

    def handle(self, *args, **options):
        season = int(settings.NFL_SEASON)
        week = get_current_week(season)
        
        self.stdout.write(f"Refreshing odds for season {season}, week {week}")
        
        games = get_current_week_games(season, week)
        game_ids = games["game_id_sb"].tolist()
        
        self.stdout.write(f"Found {len(game_ids)} games for week {week}")
        
        # Fetch props from API
        props = fetch_prizepicks_props_for_games(season, week, game_ids)
        
        if not props:
            self.stdout.write(
                self.style.WARNING("No props returned from API - check API configuration")
            )
        else:
            self.stdout.write(f"Successfully fetched {len(props)} props")
            
        self.stdout.write(
            self.style.SUCCESS("Odds refresh completed")
        )
