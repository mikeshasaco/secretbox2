#!/usr/bin/env python3
"""
Populate kickoff times for games using NFL data
"""
from django.core.management.base import BaseCommand
from core.models import Game
import nflreadpy as nfl
from django.utils import timezone
import pytz
import pandas as pd


class Command(BaseCommand):
    help = 'Populate kickoff times for games using NFL data'

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
            help='Show what would be updated without actually updating',
        )

    def handle(self, *args, **options):
        season = options['season']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write("DRY RUN - No data will be updated")
        
        # Load NFL schedule data
        try:
            schedules = nfl.load_schedules(seasons=[season])
            self.stdout.write(f"Loaded {len(schedules)} games from NFL data")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error loading NFL data: {e}"))
            return
        
        updated_count = 0
        
        # Convert to pandas if it's polars
        if hasattr(schedules, 'to_pandas'):
            schedules = schedules.to_pandas()
        
        for _, game_data in schedules.iterrows():
            game_id = game_data['game_id']
            
            # Try to find our Game model
            try:
                game = Game.objects.get(game_id=game_id)
            except Game.DoesNotExist:
                self.stdout.write(f"Game {game_id} not found in our database, skipping")
                continue
            
            # Parse kickoff time
            if 'gametime' in game_data and pd.notna(game_data['gametime']):
                try:
                    # Convert to UTC datetime
                    kickoff_utc = pd.to_datetime(f"{game_data['gameday']} {game_data['gametime']}", utc=True)
                    
                    # Convert to Eastern
                    et_tz = pytz.timezone('US/Eastern')
                    kickoff_et = kickoff_utc.astimezone(et_tz)
                    
                    if not dry_run:
                        game.kickoff_utc = kickoff_utc
                        game.kickoff_et = kickoff_et
                        game.save()
                    
                    updated_count += 1
                    self.stdout.write(f"Updated {game_id}: {kickoff_utc} UTC")
                    
                except Exception as e:
                    self.stdout.write(f"Error parsing time for {game_id}: {e}")
                    continue
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Would update {updated_count} games with kickoff times")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully updated {updated_count} games with kickoff times")
            )
