#!/usr/bin/env python3
"""
Add missing players manually with correct 2025 team assignments
"""
from django.core.management.base import BaseCommand
from core.models import Player, Team
from django.db import transaction

class Command(BaseCommand):
    help = 'Adds missing players with correct 2025 team assignments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        self.stdout.write("Adding missing players with correct 2025 team assignments...")
        
        # Manually curated list of missing players with their correct 2025 teams
        missing_players = {
            'AJ Brown': {'team_abbr': 'PHI', 'position': 'WR'},
            'Cameron Ward': {'team_abbr': 'TEN', 'position': 'QB'},  # Rookie QB
            'Michael Pittman Jr.': {'team_abbr': 'IND', 'position': 'WR'},
            'Travis Etienne Jr.': {'team_abbr': 'JAX', 'position': 'RB'},
            'Chigoziem Okonkwo': {'team_abbr': 'TEN', 'position': 'TE'},
            'Brian Thomas Jr': {'team_abbr': 'JAX', 'position': 'WR'},  # Rookie WR
        }
        
        updated_count = 0
        created_teams_count = 0
        errors_count = 0

        for player_name, data in missing_players.items():
            team_abbr = data['team_abbr']
            position = data['position']
            
            try:
                with transaction.atomic():
                    # Get or create team
                    team_obj, team_created = Team.objects.get_or_create(
                        team_abbr=team_abbr,
                        defaults={'team_name': team_abbr, 'team_city': team_abbr}
                    )
                    if team_created:
                        created_teams_count += 1

                    # Get or create player
                    player, player_created = Player.objects.get_or_create(
                        player_name=player_name,
                        defaults={
                            'player_id': player_name.lower().replace(' ', '_').replace('.', '').replace(' Jr', ''),
                            'position': position,
                            'team': team_obj
                        }
                    )
                    
                    if not player_created:
                        # Player exists, update team and position
                        old_team_abbr = player.team.team_abbr if player.team else "None"
                        old_position = player.position
                        
                        if player.team != team_obj or player.position != position:
                            if dry_run:
                                self.stdout.write(f"Would update {player_name}:")
                                if player.team != team_obj:
                                    self.stdout.write(f"  Team: {old_team_abbr} → {team_abbr}")
                                if player.position != position:
                                    self.stdout.write(f"  Position: {old_position} → {position}")
                            else:
                                player.team = team_obj
                                player.position = position
                                player.save()
                                updated_count += 1
                                self.stdout.write(f"Updated {player_name}: {old_team_abbr} → {team_abbr}, {old_position} → {position}")
                        else:
                            self.stdout.write(f"{player_name} already correct: {team_abbr} {position}")
                    else:
                        if dry_run:
                            self.stdout.write(f"Would create {player_name}: {team_abbr} {position}")
                        else:
                            self.stdout.write(f"Created {player_name}: {team_abbr} {position}")
                            updated_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing {player_name}: {e}"))
                errors_count += 1
                continue

        if dry_run:
            self.stdout.write(self.style.WARNING(f"DRY RUN - Would update/create {updated_count} players, create {created_teams_count} teams, {errors_count} errors"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully updated/created {updated_count} players, created {created_teams_count} teams, {errors_count} errors"))
