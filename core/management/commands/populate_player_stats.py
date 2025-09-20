#!/usr/bin/env python3
"""
Populate PlayerStats from NFL data for grading props
"""
from django.core.management.base import BaseCommand
from core.models import PlayerStats, Player, Game, Team
import nflreadpy as nfl
from django.utils import timezone
import pandas as pd


class Command(BaseCommand):
    help = 'Populate PlayerStats from NFL data for grading props'

    def add_arguments(self, parser):
        parser.add_argument(
            '--season',
            type=int,
            default=2025,
            help='NFL season to process (default: 2025)',
        )
        parser.add_argument(
            '--week',
            type=int,
            help='Specific week to process (if not provided, processes all weeks)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating records',
        )

    def handle(self, *args, **options):
        season = options['season']
        week = options.get('week')
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write("DRY RUN - No data will be created")
        
        # Load NFL player stats data
        try:
            player_stats = nfl.load_player_stats(season)
            self.stdout.write(f"Loaded player stats for season {season}")
            
            # Load Next Gen Stats data
            passing_ngs = nfl.load_nextgen_stats(seasons=[season], stat_type='passing')
            receiving_ngs = nfl.load_nextgen_stats(seasons=[season], stat_type='receiving')
            rushing_ngs = nfl.load_nextgen_stats(seasons=[season], stat_type='rushing')
            self.stdout.write(f"Loaded Next Gen Stats for season {season}")
            
            # Filter by week if specified
            if week:
                player_stats = player_stats.filter(player_stats['week'] == week)
                passing_ngs = passing_ngs.filter(passing_ngs['week'] == week)
                receiving_ngs = receiving_ngs.filter(receiving_ngs['week'] == week)
                rushing_ngs = rushing_ngs.filter(rushing_ngs['week'] == week)
                self.stdout.write(f"Filtered to week {week}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error loading NFL player stats: {e}"))
            return
        
        created_count = 0
        updated_count = 0
        
        # Convert to pandas if it's polars
        if hasattr(player_stats, 'to_pandas'):
            player_stats = player_stats.to_pandas()
        if hasattr(passing_ngs, 'to_pandas'):
            passing_ngs = passing_ngs.to_pandas()
        if hasattr(receiving_ngs, 'to_pandas'):
            receiving_ngs = receiving_ngs.to_pandas()
        if hasattr(rushing_ngs, 'to_pandas'):
            rushing_ngs = rushing_ngs.to_pandas()
        
        # Merge Next Gen Stats with player stats
        # Create merge keys using position and team since names don't match between datasets
        player_stats['merge_key'] = player_stats['position'].astype(str) + '_' + player_stats['team'].astype(str) + '_' + player_stats['week'].astype(str)
        passing_ngs['merge_key'] = passing_ngs['player_position'].astype(str) + '_' + passing_ngs['team_abbr'].astype(str) + '_' + passing_ngs['week'].astype(str)
        receiving_ngs['merge_key'] = receiving_ngs['player_position'].astype(str) + '_' + receiving_ngs['team_abbr'].astype(str) + '_' + receiving_ngs['week'].astype(str)
        rushing_ngs['merge_key'] = rushing_ngs['player_position'].astype(str) + '_' + rushing_ngs['team_abbr'].astype(str) + '_' + rushing_ngs['week'].astype(str)
        
        # Merge passing Next Gen Stats
        passing_cols = ['merge_key', 'avg_time_to_throw', 'avg_completed_air_yards', 'avg_intended_air_yards', 
                       'avg_air_yards_differential', 'aggressiveness', 'completion_percentage_above_expectation']
        player_stats = player_stats.merge(passing_ngs[passing_cols], on='merge_key', how='left')
        
        # Merge receiving Next Gen Stats
        receiving_cols = ['merge_key', 'avg_cushion', 'avg_separation', 'avg_expected_yac', 'avg_yac_above_expectation']
        player_stats = player_stats.merge(receiving_ngs[receiving_cols], on='merge_key', how='left')
        
        # Merge rushing Next Gen Stats
        rushing_cols = ['merge_key', 'efficiency', 'avg_time_to_los', 'expected_rush_yards', 
                       'rush_yards_over_expected', 'rush_yards_over_expected_per_att']
        player_stats = player_stats.merge(rushing_ngs[rushing_cols], on='merge_key', how='left')
        
        self.stdout.write(f"Merged Next Gen Stats with player stats")
        
        for _, stats in player_stats.iterrows():
            # Create game_id from NFL data - try both formats
            game_id = f"{season}_{stats['week']:02d}_{stats['team']}_{stats['opponent_team']}"
            alt_game_id = f"{season}_{stats['week']:02d}_{stats['opponent_team']}_{stats['team']}"
            
            # Try to find our Game model
            try:
                game = Game.objects.get(game_id=game_id)
            except Game.DoesNotExist:
                try:
                    game = Game.objects.get(game_id=alt_game_id)
                except Game.DoesNotExist:
                    self.stdout.write(f"Game {game_id} or {alt_game_id} not found in our database, skipping")
                    continue
            
            # Try to find our Player model
            try:
                # Get the team instance
                team_abbr = stats.get('team', 'UNK')
                try:
                    team = Team.objects.get(team_abbr=team_abbr)
                except Team.DoesNotExist:
                    self.stdout.write(f"Team {team_abbr} not found, skipping player {stats['player_name']}")
                    continue
                
                # Create player_id from player_name
                player_id = stats['player_name'].lower().replace(' ', '_').replace('.', '').replace("'", '')
                
                player, _ = Player.objects.get_or_create(
                    player_id=player_id,
                    defaults={
                        'player_name': stats['player_name'],
                        'position': stats.get('position', 'UNK'),
                        'team': team,
                    }
                )
            except Exception as e:
                self.stdout.write(f"Could not get or create player {stats['player_name']}: {e}, skipping stats.")
                continue

            # Map NFL stats to our PlayerStats model
            stats_data = {
                'season': season,
                'week': stats['week'],
                
                # Passing stats
                'passing_attempts': stats.get('attempts', 0) or 0,
                'passing_completions': stats.get('completions', 0) or 0,
                'passing_yards': stats.get('passing_yards', 0) or 0,
                'passing_tds': stats.get('passing_tds', 0) or 0,
                'passing_ints': stats.get('passing_interceptions', 0) or 0,
                'passing_rating': stats.get('passer_rating', None),
                
                # Rushing stats
                'rushing_attempts': stats.get('carries', 0) or 0,
                'rushing_yards': stats.get('rushing_yards', 0) or 0,
                'rushing_tds': stats.get('rushing_tds', 0) or 0,
                
                # Receiving stats
                'receiving_targets': stats.get('targets', 0) or 0,
                'receiving_receptions': stats.get('receptions', 0) or 0,
                'receiving_yards': stats.get('receiving_yards', 0) or 0,
                'receiving_tds': stats.get('receiving_tds', 0) or 0,
                
                # Advanced stats
                'air_yards': stats.get('passing_air_yards', 0) or 0,
                'yac': stats.get('receiving_yac', 0) or 0,
                'adot': stats.get('avg_depth_of_target', None),
                'target_share': stats.get('target_share', None),
                'snap_share': stats.get('offense_snap_perc', None),
                
                # Next Gen Stats - Passing
                'avg_time_to_throw': stats.get('avg_time_to_throw', None) if pd.notna(stats.get('avg_time_to_throw', None)) else None,
                'avg_completed_air_yards': stats.get('avg_completed_air_yards', None) if pd.notna(stats.get('avg_completed_air_yards', None)) else None,
                'avg_intended_air_yards': stats.get('avg_intended_air_yards', None) if pd.notna(stats.get('avg_intended_air_yards', None)) else None,
                'avg_air_yards_differential': stats.get('avg_air_yards_differential', None) if pd.notna(stats.get('avg_air_yards_differential', None)) else None,
                'aggressiveness': stats.get('aggressiveness', None) if pd.notna(stats.get('aggressiveness', None)) else None,
                'completion_percentage_above_expectation': stats.get('completion_percentage_above_expectation', None) if pd.notna(stats.get('completion_percentage_above_expectation', None)) else None,
                
                # Next Gen Stats - Receiving
                'avg_cushion': stats.get('avg_cushion', None) if pd.notna(stats.get('avg_cushion', None)) else None,
                'avg_separation': stats.get('avg_separation', None) if pd.notna(stats.get('avg_separation', None)) else None,
                'avg_expected_yac': stats.get('avg_expected_yac', None) if pd.notna(stats.get('avg_expected_yac', None)) else None,
                'avg_yac_above_expectation': stats.get('avg_yac_above_expectation', None) if pd.notna(stats.get('avg_yac_above_expectation', None)) else None,
                
                # Next Gen Stats - Rushing
                'efficiency': stats.get('efficiency', None) if pd.notna(stats.get('efficiency', None)) else None,
                'avg_time_to_los': stats.get('avg_time_to_los', None) if pd.notna(stats.get('avg_time_to_los', None)) else None,
                'expected_rush_yards': stats.get('expected_rush_yards', None) if pd.notna(stats.get('expected_rush_yards', None)) else None,
                'rush_yards_over_expected': stats.get('rush_yards_over_expected', None) if pd.notna(stats.get('rush_yards_over_expected', None)) else None,
                'rush_yards_over_expected_per_att': stats.get('rush_yards_over_expected_per_att', None) if pd.notna(stats.get('rush_yards_over_expected_per_att', None)) else None,
            }
            
            if not dry_run:
                # Create or update PlayerStats
                player_stats_obj, created = PlayerStats.objects.update_or_create(
                    player=player,
                    game=game,
                    defaults=stats_data
                )
                
                if not created:
                    # Update existing record
                    for key, value in stats_data.items():
                        if key != 'game':
                            setattr(player_stats_obj, key, value)
                    player_stats_obj.save()
                    updated_count += 1
                else:
                    created_count += 1
            else:
                created_count += 1
            
            if (created_count + updated_count) % 100 == 0:
                self.stdout.write(f"Processed {created_count + updated_count} player stats...")
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Would create/update {created_count} player stats records")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully created {created_count} new and updated {updated_count} existing player stats records")
            )
