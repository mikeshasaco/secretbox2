#!/usr/bin/env python3
"""
Fix specific players with correct team assignments
"""
from django.core.management.base import BaseCommand
from core.models import PlayerMapping, Player, Team
from django.db import transaction


class Command(BaseCommand):
    help = 'Fix specific players with correct team assignments'

    def handle(self, *args, **options):
        self.stdout.write("Fixing specific player team assignments...")
        
        # Define correct team assignments
        player_fixes = [
            # (prizepicks_name, nflreadpy_name, correct_team, correct_position)
            ('Daniel Jones', 'Daniel Jones', 'NYG', 'QB'),  # nflreadpy has him as IND but he's NYG
            ('Jonathan Taylor', 'Jonathan Taylor', 'IND', 'RB'),
            ('Josh Downs', 'Josh Downs', 'IND', 'WR'),
            ('Tony Pollard', 'Tony Pollard', 'TEN', 'RB'),
            ('Tyler Lockett', 'Tyler Lockett', 'TEN', 'WR'),
            ('Calvin Ridley', 'Calvin Ridley', 'TEN', 'WR'),
            ('Elic Ayomanor', 'Elic Ayomanor', 'TEN', 'WR'),
            ('Tyler Warren', 'Tyler Warren', 'IND', 'TE'),
            ('Michael Pittman Jr.', 'Michael Pittman Jr.', 'IND', 'WR'),  # Not in nflreadpy but should be IND
            ('Chigoziem Okonkwo', 'Chigoziem Okonkwo', 'TEN', 'TE'),  # Not in nflreadpy but should be TEN
        ]
        
        updated_count = 0
        created_count = 0
        
        for prizepicks_name, nflreadpy_name, correct_team, correct_position in player_fixes:
            try:
                # Get or create mapping
                mapping, created = PlayerMapping.objects.get_or_create(
                    prizepicks_name=prizepicks_name,
                    defaults={
                        'nflreadpy_name': nflreadpy_name,
                        'current_team': correct_team,
                        'position': correct_position,
                        'player_id': prizepicks_name.lower().replace(' ', '_').replace('.', '').replace(' Jr.', ''),
                        'is_active': True
                    }
                )
                
                if not created:
                    # Update existing mapping
                    mapping.nflreadpy_name = nflreadpy_name
                    mapping.current_team = correct_team
                    mapping.position = correct_position
                    mapping.is_active = True
                    mapping.save()
                
                # Get or create team
                team, team_created = Team.objects.get_or_create(
                    team_abbr=correct_team,
                    defaults={
                        'team_name': correct_team,
                        'team_city': correct_team
                    }
                )
                
                # Update player
                player = Player.objects.filter(player_name=prizepicks_name).first()
                if player:
                    old_team = player.team.team_abbr if player.team else "None"
                    old_position = player.position
                    
                    player.team = team
                    player.position = correct_position
                    player.save()
                    
                    self.stdout.write(f"Updated {prizepicks_name}: {old_team} → {correct_team}, {old_position} → {correct_position}")
                    updated_count += 1
                else:
                    self.stdout.write(f"Player not found: {prizepicks_name}")
                
                if created:
                    created_count += 1
                    
            except Exception as e:
                self.stdout.write(f"Error updating {prizepicks_name}: {e}")
                continue
        
        self.stdout.write(self.style.SUCCESS(f"Successfully updated {updated_count} players and created {created_count} mappings"))
