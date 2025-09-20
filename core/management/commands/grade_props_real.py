#!/usr/bin/env python3
"""
Grade prop lines against real PlayerStats data
"""
from django.core.management.base import BaseCommand
from core.models import PropLineHistory, PropGrade, PlayerStats, PlayerMapping, Game, Player
from django.utils import timezone
from django.db.models import Q


class Command(BaseCommand):
    help = 'Grade prop lines against real PlayerStats data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--game-id',
            type=str,
            help='Grade props for specific game (e.g., 2025_03_ATL_CAR)',
        )
        parser.add_argument(
            '--market',
            type=str,
            help='Grade props for specific market (e.g., player_pass_yds)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be graded without actually creating grades',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        game_id = options.get('game_id')
        market = options.get('market')
        
        if dry_run:
            self.stdout.write("DRY RUN - No grades will be created")
        
        # Get props to grade
        props_query = PropLineHistory.objects.all()
        
        if game_id:
            props_query = props_query.filter(game_id=game_id)
        
        if market:
            props_query = props_query.filter(market_key=market)
        
        props = props_query.order_by('game_id', 'player_name', 'market_key')
        
        self.stdout.write(f"Found {props.count()} prop lines to grade")
        
        graded_count = 0
        skipped_count = 0
        
        for prop in props:
            try:
                # Find the actual result from PlayerStats
                actual_result = self.get_actual_result(prop)
                
                if actual_result is None:
                    self.stdout.write(f"Skipping {prop.player_name} - {prop.market_key}: No stats found")
                    skipped_count += 1
                    continue
                
                # Determine outcome
                outcome = self.determine_outcome(actual_result, prop.line_value)
                
                if dry_run:
                    self.stdout.write(f"Would grade: {prop.player_name} - {prop.market_key}: {actual_result} vs {prop.line_value} = {outcome}")
                else:
                    # Create or update grade
                    grade, created = PropGrade.objects.update_or_create(
                        proplinehistory=prop,
                        defaults={
                            'label_value': actual_result,
                            'outcome': outcome,
                        }
                    )
                    
                    if created:
                        graded_count += 1
                        if graded_count % 10 == 0:
                            self.stdout.write(f"Graded {graded_count} props...")
                
            except Exception as e:
                self.stdout.write(f"Error grading {prop.player_name} - {prop.market_key}: {e}")
                skipped_count += 1
                continue
        
        if dry_run:
            self.stdout.write(f"DRY RUN - Would grade {graded_count} props, skip {skipped_count}")
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully graded {graded_count} props, skipped {skipped_count}"))
    
    def get_actual_result(self, prop):
        """Get actual result from PlayerStats for a given prop"""
        try:
            # Parse game_id to get season, week, teams
            # Format: "2025_03_ATL_CAR" or "2024_18_ATL_CAR"
            parts = prop.game_id.split('_')
            if len(parts) < 4:
                return None
            
            season = int(parts[0])
            week = int(parts[1])
            
            # Find the game
            game = Game.objects.filter(season=season, week=week).first()
            if not game:
                return None
            
            # Find player using mapping
            player = None
            try:
                mapping = PlayerMapping.objects.get(prizepicks_name=prop.player_name, is_active=True)
                player = Player.objects.get(player_id=mapping.player_id)
            except (PlayerMapping.DoesNotExist, Player.DoesNotExist):
                # Try direct name match
                player = Player.objects.filter(player_name=prop.player_name).first()
            
            if not player:
                return None
            
            # Get player stats for this game
            stats = PlayerStats.objects.filter(
                player=player,
                game=game,
                season=season,
                week=week
            ).first()
            
            if not stats:
                return None
            
            # Map market_key to actual stat field
            market_mapping = {
                'player_pass_yds': stats.passing_yards,
                'player_rush_yds': stats.rushing_yards,
                'player_reception_yds': stats.receiving_yards,
                'player_pass_attempts': stats.passing_attempts,
                'player_rush_attempts': stats.rushing_attempts,
                'player_receptions': stats.receiving_receptions,
            }
            
            return market_mapping.get(prop.market_key)
            
        except Exception as e:
            self.stdout.write(f"Error getting actual result for {prop.player_name}: {e}")
            return None
    
    def determine_outcome(self, actual_result, line_value):
        """Determine if the result is over, under, or push"""
        if actual_result is None:
            return 'void'
        
        if actual_result > line_value:
            return 'over'
        elif actual_result < line_value:
            return 'under'
        else:
            return 'push'
