#!/usr/bin/env python3
"""
Populate player details (jersey number, height, weight, age) from nflreadpy data
"""
from django.core.management.base import BaseCommand
from core.models import Player, PlayerMapping
import nflreadpy as nfl
from datetime import datetime, date
import math


class Command(BaseCommand):
    help = 'Populate player details from nflreadpy data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write("Loading nflreadpy player data...")
        
        # Get nflreadpy players data
        nfl_players = nfl.load_players()
        nfl_players = nfl_players.filter(nfl_players['status'] == 'ACT')  # Only active players
        
        # Convert to pandas for easier processing
        if hasattr(nfl_players, 'to_pandas'):
            nfl_players = nfl_players.to_pandas()
        
        self.stdout.write(f"Found {len(nfl_players)} active NFL players")
        
        updated_count = 0
        
        # Process each player in our database
        for player in Player.objects.all():
            try:
                # Try to find the player in nflreadpy data
                nfl_player = None
                
                # First, try direct name match
                nfl_match = nfl_players[nfl_players['display_name'] == player.player_name]
                if not nfl_match.empty:
                    nfl_player = nfl_match.iloc[0]
                else:
                    # Try using PlayerMapping to find the nflreadpy name
                    try:
                        mapping = PlayerMapping.objects.get(player_id=player.player_id, is_active=True)
                        nfl_match = nfl_players[nfl_players['display_name'] == mapping.nflreadpy_name]
                        if not nfl_match.empty:
                            nfl_player = nfl_match.iloc[0]
                    except PlayerMapping.DoesNotExist:
                        pass
                
                if nfl_player is not None:
                    # Extract data from nflreadpy
                    jersey_number = nfl_player.get('jersey_number')
                    height_inches = nfl_player.get('height')
                    weight = nfl_player.get('weight')
                    birth_date_str = nfl_player.get('birth_date')
                    
                    # Convert height from inches to feet'inches" format
                    height_formatted = None
                    if height_inches is not None and str(height_inches) != 'nan' and str(height_inches) != 'None':
                        try:
                            height_val = float(height_inches)
                            if not math.isnan(height_val):
                                feet = int(height_val // 12)
                                inches = int(height_val % 12)
                                height_formatted = f"{feet}'{inches}\""
                        except (ValueError, TypeError):
                            pass
                    
                    # Calculate age from birth date
                    age = None
                    if birth_date_str and str(birth_date_str) != 'nan' and str(birth_date_str) != 'None':
                        try:
                            birth_date = datetime.strptime(str(birth_date_str), '%Y-%m-%d').date()
                            today = date.today()
                            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                        except (ValueError, TypeError):
                            pass
                    
                    # Check if we have any data to update
                    has_data = any([
                        jersey_number is not None and str(jersey_number) != 'nan' and str(jersey_number) != 'None',
                        height_formatted,
                        weight is not None and str(weight) != 'nan' and str(weight) != 'None',
                        age is not None
                    ])
                    
                    if has_data:
                        if dry_run:
                            self.stdout.write(f"Would update {player.player_name}: Jersey={jersey_number}, Height={height_formatted}, Weight={weight}, Age={age}")
                        else:
                            if jersey_number is not None and str(jersey_number) != 'nan' and str(jersey_number) != 'None':
                                try:
                                    player.jersey_number = int(jersey_number)
                                except (ValueError, TypeError):
                                    pass
                            if height_formatted:
                                player.height = height_formatted
                            if weight is not None and str(weight) != 'nan' and str(weight) != 'None':
                                try:
                                    player.weight = int(weight)
                                except (ValueError, TypeError):
                                    pass
                            if age is not None:
                                player.age = age
                            
                            player.save()
                            updated_count += 1
                            
                            if updated_count % 50 == 0:
                                self.stdout.write(f"Updated {updated_count} players...")
                
            except Exception as e:
                self.stdout.write(f"Error updating {player.player_name}: {e}")
                continue
        
        if dry_run:
            self.stdout.write(f"DRY RUN - Would update {updated_count} players")
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully updated {updated_count} players with detailed information"))
