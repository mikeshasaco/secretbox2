#!/usr/bin/env python3
"""
Populate Game model from NFL data
"""
from django.core.management.base import BaseCommand
from core.models import Game, Team
import nflreadpy as nfl
from django.utils import timezone
import pytz
import pandas as pd


class Command(BaseCommand):
    help = 'Populate Game model from NFL data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--season',
            type=int,
            default=2025,
            help='NFL season to process (default: 2025)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating records',
        )

    def handle(self, *args, **options):
        season = options['season']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write("DRY RUN - No data will be created")
        
        # Load NFL schedule data
        try:
            schedules = nfl.load_schedules(seasons=[season])
            self.stdout.write(f"Loaded {len(schedules)} games from NFL data")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error loading NFL data: {e}"))
            return
        
        # Convert to pandas if it's polars
        if hasattr(schedules, 'to_pandas'):
            schedules = schedules.to_pandas()
        
        created_count = 0
        
        for _, game_data in schedules.iterrows():
            # Create game_id in our format: 2025_03_ATL_CAR
            game_id = f"{season}_{game_data['week']:02d}_{game_data['away_team']}_{game_data['home_team']}"
            
            # Get or create teams
            try:
                away_team = Team.objects.get(team_abbr=game_data['away_team'])
                home_team = Team.objects.get(team_abbr=game_data['home_team'])
            except Team.DoesNotExist:
                self.stdout.write(f"Team not found for {game_id}, skipping")
                continue
            
            # Parse game date
            try:
                game_date = pd.to_datetime(f"{game_data['gameday']} {game_data['gametime']}", utc=True)
            except Exception as e:
                self.stdout.write(f"Error parsing date for {game_id}: {e}")
                continue
            
            if not dry_run:
                # Create or update game
                game, created = Game.objects.get_or_create(
                    game_id=game_id,
                    defaults={
                        'season': season,
                        'week': game_data['week'],
                        'game_type': game_data.get('game_type', 'REG'),
                        'home_team': home_team,
                        'away_team': away_team,
                        'game_date': game_date,
                        'game_time_et': game_data.get('gametime', ''),
                        'week_name': f"Week {game_data['week']}",
                        'season_type': game_data.get('game_type', 'REG'),
                        'completed': game_data.get('result', '') != '',
                        'home_score': game_data.get('home_score') if pd.notna(game_data.get('home_score')) else None,
                        'away_score': game_data.get('away_score') if pd.notna(game_data.get('away_score')) else None,
                        'kickoff_utc': game_date,
                        'kickoff_et': game_date.astimezone(pytz.timezone('US/Eastern')),
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(f"Created {game_id}: {away_team} @ {home_team}")
            else:
                created_count += 1
                self.stdout.write(f"Would create {game_id}: {game_data['away_team']} @ {game_data['home_team']}")
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Would create {created_count} games")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully created {created_count} games")
            )
