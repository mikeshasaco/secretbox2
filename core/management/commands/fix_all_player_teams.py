#!/usr/bin/env python3
"""
Fix all player team assignments based on nflreadpy data
"""
import nflreadpy as nfl
from django.core.management.base import BaseCommand
from core.models import Player, Team, PlayerMapping
from django.db import transaction
import polars as pl

class Command(BaseCommand):
    help = 'Fixes all player team assignments based on nflreadpy data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        self.stdout.write("Loading nflreadpy player data...")
        
        try:
            nfl_players_df = nfl.load_players()
            self.stdout.write(f"Loaded {len(nfl_players_df)} players from nflreadpy")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error loading nflreadpy players: {e}"))
            return

        self.stdout.write("Fixing player team assignments...")
        
        updated_count = 0
        created_teams_count = 0
        errors_count = 0
        not_found_count = 0

        # Get all players that have props (active players)
        from core.models import PlayerProp
        active_player_names = set(PlayerProp.objects.values_list('player_name', flat=True).distinct())
        
        self.stdout.write(f"Found {len(active_player_names)} players with props")

        for player_name in active_player_names:
            try:
                # Find the player in our database
                player = Player.objects.filter(player_name=player_name).first()
                if not player:
                    self.stdout.write(self.style.WARNING(f"  Player '{player_name}' not found in Player table. Skipping."))
                    not_found_count += 1
                    continue

                # Find the corresponding player in nflreadpy data
                nfl_player_data = nfl_players_df.filter(
                    pl.col('display_name') == player_name
                )

                if nfl_player_data.height == 0:
                    # Try alternative name matching
                    nfl_player_data = nfl_players_df.filter(
                        pl.col('display_name').str.contains(player_name.split()[-1], literal=True)
                    )
                    
                    if nfl_player_data.height == 0:
                        self.stdout.write(self.style.WARNING(f"  NFLReadPy player '{player_name}' not found. Skipping."))
                        not_found_count += 1
                        continue

                nfl_data = nfl_player_data.row(0, named=True)
                latest_team_abbr = nfl_data['latest_team']
                latest_position = nfl_data['position']

                # Get or create team
                team_obj, team_created = Team.objects.get_or_create(
                    team_abbr=latest_team_abbr,
                    defaults={'team_name': latest_team_abbr, 'team_city': latest_team_abbr}
                )
                if team_created:
                    created_teams_count += 1

                # Check if player needs update
                needs_update = False
                old_team_abbr = player.team.team_abbr if player.team else "None"
                old_position = player.position

                if player.team != team_obj:
                    needs_update = True
                if player.position != latest_position:
                    needs_update = True

                if needs_update:
                    if dry_run:
                        self.stdout.write(f"Would update {player_name}:")
                        if player.team != team_obj:
                            self.stdout.write(f"  Team: {old_team_abbr} → {latest_team_abbr}")
                        if player.position != latest_position:
                            self.stdout.write(f"  Position: {old_position} → {latest_position}")
                    else:
                        with transaction.atomic():
                            player.team = team_obj
                            player.position = latest_position
                            player.save()
                            updated_count += 1
                            self.stdout.write(f"Updated {player_name}: {old_team_abbr} → {latest_team_abbr}, {old_position} → {latest_position}")
                else:
                    # Player is already correct
                    pass

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing {player_name}: {e}"))
                errors_count += 1
                continue

        if dry_run:
            self.stdout.write(self.style.WARNING(f"DRY RUN - Would update {updated_count} players, create {created_teams_count} teams, {not_found_count} not found, {errors_count} errors"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully updated {updated_count} players, created {created_teams_count} teams, {not_found_count} not found, {errors_count} errors"))
