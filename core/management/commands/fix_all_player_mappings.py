#!/usr/bin/env python3
"""
Fix all player mappings with correct nflreadpy data
"""
import nflreadpy as nfl
from django.core.management.base import BaseCommand
from core.models import PlayerMapping, Player, Team
from django.db import transaction


class Command(BaseCommand):
    help = 'Fix all player mappings with correct nflreadpy data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write("Loading nflreadpy player data...")
        players = nfl.load_players()
        self.stdout.write(f"Loaded {len(players)} players from nflreadpy")
        
        self.stdout.write("Fixing player mappings...")
        
        updated_mappings = 0
        updated_players = 0
        created_teams = 0
        errors = 0
        
        # Get all active mappings
        mappings = PlayerMapping.objects.filter(is_active=True)
        
        for mapping in mappings:
            try:
                # Find the player in nflreadpy data
                nfl_player = players.filter(players['display_name'] == mapping.nflreadpy_name).to_pandas()
                
                if nfl_player.empty:
                    self.stdout.write(f"Player not found in nflreadpy: {mapping.nflreadpy_name}")
                    errors += 1
                    continue
                
                nfl_data = nfl_player.iloc[0]
                correct_team = nfl_data['latest_team']
                correct_position = nfl_data['position']
                
                # Check if mapping needs updating
                if (mapping.current_team != correct_team or 
                    mapping.position != correct_position):
                    
                    if dry_run:
                        self.stdout.write(f"Would update {mapping.prizepicks_name}:")
                        self.stdout.write(f"  Team: {mapping.current_team} → {correct_team}")
                        self.stdout.write(f"  Position: {mapping.position} → {correct_position}")
                    else:
                        # Update mapping
                        mapping.current_team = correct_team
                        mapping.position = correct_position
                        mapping.save()
                        updated_mappings += 1
                        
                        # Update player
                        player = Player.objects.filter(player_name=mapping.prizepicks_name).first()
                        if player:
                            # Get or create the correct team
                            team, team_created = Team.objects.get_or_create(
                                team_abbr=correct_team,
                                defaults={
                                    'team_name': correct_team,
                                    'team_city': correct_team
                                }
                            )
                            
                            if team_created:
                                created_teams += 1
                            
                            # Update player's team and position
                            player.team = team
                            player.position = correct_position
                            player.save()
                            updated_players += 1
                            
                            if updated_players % 10 == 0:
                                self.stdout.write(f"Updated {updated_players} players...")
                
            except Exception as e:
                self.stdout.write(f"Error updating {mapping.prizepicks_name}: {e}")
                errors += 1
                continue
        
        if dry_run:
            self.stdout.write(f"DRY RUN - Would update {updated_mappings} mappings and {updated_players} players, create {created_teams} teams")
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully updated {updated_mappings} mappings and {updated_players} players, created {created_teams} teams, {errors} errors"))
