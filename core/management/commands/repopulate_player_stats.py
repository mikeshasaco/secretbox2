#!/usr/bin/env python3
"""
Re-populate player stats using nflreadpy API with proper mapping system
"""
from django.core.management.base import BaseCommand
from core.models import Player, PlayerStats, Game, PlayerMapping, Team
import nflreadpy as nfl
from datetime import datetime
import math


class Command(BaseCommand):
    help = 'Re-populate player stats using nflreadpy API with mapping system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--seasons',
            nargs='+',
            type=int,
            default=[2024, 2025],
            help='Seasons to populate (default: 2024 2025)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually doing it',
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing PlayerStats before populating',
        )

    def handle(self, *args, **options):
        seasons = options['seasons']
        dry_run = options['dry_run']
        clear_existing = options['clear_existing']
        
        self.stdout.write(f"Loading nflreadpy player stats for seasons: {seasons}")
        
        # Get nflreadpy stats data
        stats_data = nfl.load_player_stats(seasons=seasons)
        
        # Convert to pandas for easier processing
        if hasattr(stats_data, 'to_pandas'):
            stats_data = stats_data.to_pandas()
        
        self.stdout.write(f"Found {len(stats_data)} stat records from nflreadpy")
        
        if clear_existing and not dry_run:
            self.stdout.write("Clearing existing PlayerStats...")
            PlayerStats.objects.all().delete()
            self.stdout.write("Existing PlayerStats cleared")
        
        # Get all active mappings
        mappings = {m.nflreadpy_name: m for m in PlayerMapping.objects.filter(is_active=True)}
        self.stdout.write(f"Found {len(mappings)} active player mappings")
        
        # Get all games for the seasons
        games = {}
        for game in Game.objects.filter(season__in=seasons):
            key = f"{game.season}_{game.week}_{game.home_team.team_abbr}_{game.away_team.team_abbr}"
            games[key] = game
        
        self.stdout.write(f"Found {len(games)} games in database")
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        # Process each stat record
        for _, stat_row in stats_data.iterrows():
            try:
                nflreadpy_name = stat_row['player_display_name']
                season = int(stat_row['season'])
                week = int(stat_row['week'])
                team_abbr = stat_row['team']
                
                # Skip if not a regular season game
                if stat_row.get('season_type', 'REG') != 'REG':
                    continue
                
                # Find the player using mapping
                player = None
                if nflreadpy_name in mappings:
                    mapping = mappings[nflreadpy_name]
                    try:
                        player = Player.objects.get(player_id=mapping.player_id)
                    except Player.DoesNotExist:
                        # Create player if it doesn't exist
                        team, _ = Team.objects.get_or_create(
                            team_abbr=mapping.current_team,
                            defaults={'team_name': mapping.current_team, 'team_city': mapping.current_team}
                        )
                        player = Player.objects.create(
                            player_id=mapping.player_id,
                            player_name=mapping.prizepicks_name,
                            position=mapping.position,
                            team=team,
                        )
                else:
                    # Try to find player by name (fallback)
                    try:
                        player = Player.objects.get(player_name=nflreadpy_name)
                    except Player.DoesNotExist:
                        # Create player with unknown team
                        team, _ = Team.objects.get_or_create(
                            team_abbr='UNK',
                            defaults={'team_name': 'Unknown', 'team_city': 'Unknown'}
                        )
                        player_id = nflreadpy_name.lower().replace(' ', '_').replace('.', '').replace("'", '')
                        player = Player.objects.create(
                            player_id=player_id,
                            player_name=nflreadpy_name,
                            position=stat_row.get('position', 'UNK'),
                            team=team,
                        )
                
                if not player:
                    skipped_count += 1
                    continue
                
                # Find the game
                game = None
                for game_key, game_obj in games.items():
                    if (game_obj.season == season and 
                        game_obj.week == week and 
                        (game_obj.home_team.team_abbr == team_abbr or game_obj.away_team.team_abbr == team_abbr)):
                        game = game_obj
                        break
                
                if not game:
                    skipped_count += 1
                    continue
                
                # Extract stats data
                stats_dict = {
                    'player': player,
                    'player_name': player.player_name,  # Add player name for easy reference
                    'game': game,
                    'season': season,
                    'week': week,
                    
                    # Passing stats
                    'passing_attempts': int(stat_row.get('attempts', 0) or 0),
                    'passing_completions': int(stat_row.get('completions', 0) or 0),
                    'passing_yards': int(stat_row.get('passing_yards', 0) or 0),
                    'passing_tds': int(stat_row.get('passing_tds', 0) or 0),
                    'passing_ints': int(stat_row.get('passing_interceptions', 0) or 0),
                    'passing_rating': self._safe_float(stat_row.get('passing_rating')),
                    
                    # Rushing stats
                    'rushing_attempts': int(stat_row.get('carries', 0) or 0),
                    'rushing_yards': int(stat_row.get('rushing_yards', 0) or 0),
                    'rushing_tds': int(stat_row.get('rushing_tds', 0) or 0),
                    
                    # Receiving stats
                    'receiving_targets': int(stat_row.get('targets', 0) or 0),
                    'receiving_receptions': int(stat_row.get('receptions', 0) or 0),
                    'receiving_yards': int(stat_row.get('receiving_yards', 0) or 0),
                    'receiving_tds': int(stat_row.get('receiving_tds', 0) or 0),
                    
                    # Advanced stats
                    'air_yards': int(stat_row.get('passing_air_yards', 0) or 0),
                    'yac': int(stat_row.get('passing_yards_after_catch', 0) or 0),
                    'adot': self._safe_float(stat_row.get('adot')),
                    'target_share': self._safe_float(stat_row.get('target_share')),
                    'snap_share': self._safe_float(stat_row.get('snap_share')),
                }
                
                if dry_run:
                    self.stdout.write(f"Would create/update: {player.player_name} - Week {week} {season}")
                else:
                    # Create or update PlayerStats
                    player_stat, created = PlayerStats.objects.update_or_create(
                        player=player,
                        game=game,
                        defaults=stats_dict
                    )
                    
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                    
                    if (created_count + updated_count) % 100 == 0:
                        self.stdout.write(f"Processed {created_count + updated_count} stat records...")
                
            except Exception as e:
                self.stdout.write(f"Error processing stat record: {e}")
                skipped_count += 1
                continue
        
        if dry_run:
            self.stdout.write(f"DRY RUN - Would create/update {created_count + updated_count} stat records, skip {skipped_count}")
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Successfully processed {created_count + updated_count} stat records "
                f"(Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count})"
            ))
    
    def _safe_float(self, value):
        """Safely convert value to float, returning None if invalid"""
        if value is None or str(value) == 'nan' or str(value) == 'None':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
