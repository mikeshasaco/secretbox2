#!/usr/bin/env python3
"""
Clean up duplicate players by merging them based on PlayerMapping
"""
from django.core.management.base import BaseCommand
from core.models import Player, PlayerMapping, PlayerStats, Prediction
from django.db import transaction


class Command(BaseCommand):
    help = 'Clean up duplicate players by merging them based on PlayerMapping'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cleaned up without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write("Analyzing duplicate players...")
        
        # Find players that have mappings
        mapped_player_ids = set(PlayerMapping.objects.values_list('player_id', flat=True))
        
        # Find duplicate players (same player_id or similar names)
        duplicates_found = 0
        merged_count = 0
        
        # Process each mapped player
        for player_id in mapped_player_ids:
            try:
                mapping = PlayerMapping.objects.get(player_id=player_id)
                
                # Find the nflreadpy player (for stats)
                nflreadpy_player = Player.objects.filter(player_name=mapping.nflreadpy_name).first()
                
                # Find the PrizePicks player (for predictions)
                prizepicks_player = Player.objects.filter(player_name=mapping.prizepicks_name).first()
                
                if nflreadpy_player and prizepicks_player and nflreadpy_player.id != prizepicks_player.id:
                    duplicates_found += 1
                    
                    if dry_run:
                        self.stdout.write(f"Would merge: {nflreadpy_player.player_name} + {prizepicks_player.player_name} → {mapping.prizepicks_name}")
                    else:
                        # Merge the players
                        with transaction.atomic():
                            # Update all PlayerStats to point to the PrizePicks player
                            PlayerStats.objects.filter(player=nflreadpy_player).update(player=prizepicks_player)
                            
                            # Update all Predictions to point to the PrizePicks player
                            Prediction.objects.filter(player=nflreadpy_player).update(player=prizepicks_player)
                            
                            # Update the PrizePicks player with better info from mapping
                            prizepicks_player.position = mapping.position
                            if mapping.current_team != 'UNK':
                                from core.models import Team
                                team, _ = Team.objects.get_or_create(
                                    team_abbr=mapping.current_team,
                                    defaults={'team_name': mapping.current_team, 'team_city': mapping.current_team}
                                )
                                prizepicks_player.team = team
                            prizepicks_player.save()
                            
                            # Delete the nflreadpy player
                            nflreadpy_player.delete()
                            
                            merged_count += 1
                            self.stdout.write(f"Merged: {nflreadpy_player.player_name} + {prizepicks_player.player_name} → {mapping.prizepicks_name}")
                
            except PlayerMapping.DoesNotExist:
                continue
            except Exception as e:
                self.stdout.write(f"Error processing {player_id}: {e}")
                continue
        
        if dry_run:
            self.stdout.write(f"DRY RUN - Found {duplicates_found} duplicate pairs that would be merged")
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully merged {merged_count} duplicate player pairs"))
