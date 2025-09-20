#!/usr/bin/env python3
"""
Fix player team assignments using PlayerMapping and nflreadpy data
"""
from django.core.management.base import BaseCommand
from core.models import Player, Team, PlayerMapping
from django.db import transaction


class Command(BaseCommand):
    help = 'Fix player team assignments using PlayerMapping and nflreadpy data'

    def add_arguments(self,parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write("Fixing player team assignments...")
        
        updated_count = 0
        created_teams = 0
        
        # Get all active mappings
        mappings = PlayerMapping.objects.filter(is_active=True)
        
        for mapping in mappings:
            try:
                # Find the player by PrizePicks name
                player = Player.objects.filter(player_name=mapping.prizepicks_name).first()
                
                if not player:
                    self.stdout.write(f"Player not found: {mapping.prizepicks_name}")
                    continue
                
                # Get or create the correct team
                team, team_created = Team.objects.get_or_create(
                    team_abbr=mapping.current_team,
                    defaults={
                        'team_name': mapping.current_team,
                        'team_city': mapping.current_team
                    }
                )
                
                if team_created:
                    created_teams += 1
                    self.stdout.write(f"Created team: {mapping.current_team}")
                
                # Update player's team and position
                old_team = player.team.team_abbr if player.team else "None"
                old_position = player.position
                
                if dry_run:
                    self.stdout.write(f"Would update {player.player_name}: {old_team} → {mapping.current_team}, {old_position} → {mapping.position}")
                else:
                    player.team = team
                    player.position = mapping.position
                    player.save()
                    
                    updated_count += 1
                    if updated_count % 10 == 0:
                        self.stdout.write(f"Updated {updated_count} players...")
                
            except Exception as e:
                self.stdout.write(f"Error updating {mapping.prizepicks_name}: {e}")
                continue
        
        if dry_run:
            self.stdout.write(f"DRY RUN - Would update {updated_count} players and create {created_teams} teams")
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully updated {updated_count} players and created {created_teams} teams"))
