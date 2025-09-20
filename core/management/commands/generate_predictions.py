from django.core.management.base import BaseCommand
from core.models import PropLineHistory, Prediction, Player, Game, PlayerStats, Team, PlayerProp
from django.utils import timezone
from django.db.models import Avg, Q
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class Command(BaseCommand):
    help = 'Generates ML predictions for existing prop lines'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Do not save predictions to the database.',
        )

    def handle(self, *args, **options):
        self.stdout.write("Training XGBoost models with Monte Carlo simulation...")
        dry_run = options['dry_run']

        # Check if we have 2025 data to train on (current season only)
        historical_stats = PlayerStats.objects.filter(season=2025)
        if not historical_stats.exists():
            self.stdout.write(self.style.WARNING("No 2025 PlayerStats found. Cannot train ML models without current season data."))
            self.stdout.write("Please run: python manage.py repopulate_player_stats --seasons 2025")
            return

        self.stdout.write(f"Found {historical_stats.count()} 2025 player stats records for training")

        # Train XGBoost models for each prop type
        prop_types = ['player_pass_yds', 'player_rush_yds', 'player_reception_yds', 'player_pass_attempts', 'player_rush_attempts', 'player_receptions']
        trained_models = {}

        for prop_type in prop_types:
            self.stdout.write(f"Training simple model for {prop_type}...")
            model_data = self.train_simple_model(prop_type, historical_stats)
            if model_data:
                trained_models[prop_type] = model_data
                self.stdout.write(f"Successfully trained model for {prop_type}")

        if not trained_models:
            self.stdout.write(self.style.ERROR("No models could be trained. Exiting."))
            return

        # Generate predictions for current prop lines
        prop_lines = PlayerProp.objects.filter(is_active=True).values('player_name', 'market_display', 'event', 'over_point', 'under_point')
        self.stdout.write(f"Generating predictions for {len(prop_lines)} current prop lines")

        predictions_created = 0

        for prop in prop_lines:
            player_name = prop['player_name']
            market_display = prop['market_display']
            event = prop['event']
            over_line = prop['over_point']
            under_line = prop['under_point']
            
            # Convert market_display to market_key format
            market_key = market_display.lower().replace(' ', '_').replace('yards', 'yds').replace('attempts', 'attempts')
            if 'pass' in market_display.lower():
                market_key = 'player_pass_yds' if 'yards' in market_display.lower() else 'player_pass_attempts'
            elif 'rush' in market_display.lower():
                market_key = 'player_rush_yds' if 'yards' in market_display.lower() else 'player_rush_attempts'
            elif 'reception' in market_display.lower():
                market_key = 'player_reception_yds' if 'yards' in market_display.lower() else 'player_receptions'

            # Skip if we don't have a trained model for this prop type
            if market_key not in trained_models:
                continue

            # Get or create player
            try:
                player = self.get_or_create_player(player_name)
                # Use an existing game for predictions (simplified approach)
                from core.models import Game
                game = Game.objects.filter(season=2025, week=3).first()
                if not game:
                    # If no 2025 week 3 game exists, use any existing game
                    game = Game.objects.first()
                if not game:
                    self.stdout.write(f"No games found in database")
                    continue
            except Exception as e:
                self.stdout.write(f"Could not get player/game for {player_name}: {e}")
                continue

            # Generate prediction using simple model
            try:
                model_data = trained_models[market_key]
                
                # Use simple prediction method
                mean_pred, sigma = self.predict_simple(player_name, game, market_key, model_data)
                
                if mean_pred is None or sigma is None:
                    self.stdout.write(f"Could not generate prediction for {player_name} {market_key}")
                    continue
                
                # Use over_line as the line value for prediction
                line_value = over_line
                
                # Monte Carlo simulation
                over_prob, under_prob, confidence_interval = self.monte_carlo_simulation(
                    mean_pred, sigma, line_value, n_simulations=10000
                )
                
                # Calculate edge and EV
                edge = mean_pred - line_value
                ev_over = (over_prob * 0.5) - ((1 - over_prob) * 0.5)  # Assuming -110 odds
                ev_under = (under_prob * 0.5) - ((1 - under_prob) * 0.5)
                
                if not dry_run:
                    # Create prediction
                    prediction, created = Prediction.objects.update_or_create(
                        player=player,
                        game=game,
                        prop_type=market_key,
                        defaults={
                            'predicted_value': mean_pred,
                            'confidence_band_lower': confidence_interval[0],
                            'confidence_band_upper': confidence_interval[1],
                            'over_probability': over_prob,
                            'under_probability': under_prob,
                            'model_line': mean_pred,
                            'user_line': line_value,
                            'edge': edge,
                            'rationale': f"Simple Statistical + Monte Carlo: μ={mean_pred:.1f}, σ={sigma:.1f}, P(Over)={over_prob:.1%}",
                            'model_version': '4.0_simple',
                        }
                    )
                    if created:
                        predictions_created += 1
                        self.stdout.write(f"Created prediction for {player_name} {market_key}: μ={mean_pred:.1f}, σ={sigma:.1f}, P(Over)={over_prob:.1%}, Edge={edge:.1f}")
                else:
                    self.stdout.write(f"Would create prediction for {player_name} {market_key}: μ={mean_pred:.1f}, σ={sigma:.1f}, P(Over)={over_prob:.1%}")

            except Exception as e:
                self.stdout.write(f"Error generating prediction for {player_name} {market_key}: {e}")
                continue

        if dry_run:
            self.stdout.write(f"DRY RUN - Would create {predictions_created} predictions")
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully created {predictions_created} simple statistical predictions"))

    def train_simple_model(self, prop_type, historical_stats):
        """Train simple statistical model that works with limited data"""
        try:
            # Map prop type to stat field
            stat_field_map = {
                'player_pass_yds': 'passing_yards',
                'player_rush_yds': 'rushing_yards', 
                'player_reception_yds': 'receiving_yards',
                'player_pass_attempts': 'passing_attempts',
                'player_rush_attempts': 'rushing_attempts',
                'player_receptions': 'receiving_receptions'
            }
            
            if prop_type not in stat_field_map:
                return None
                
            stat_field = stat_field_map[prop_type]
            
            # Get all stats for this prop type
            stats_query = historical_stats.filter(
                **{f"{stat_field}__isnull": False}
            ).exclude(**{stat_field: 0}).order_by('season', 'week')
            
            if stats_query.count() < 2:
                self.stdout.write(f"Not enough data for {prop_type}: {stats_query.count()} samples")
                return None
            
            # Collect player data for simple statistical analysis
            player_data = {}
            for stat in stats_query:
                player_name = stat.player.player_name
                if player_name not in player_data:
                    player_data[player_name] = []
                player_data[player_name].append({
                    'value': getattr(stat, stat_field),
                    'week': stat.week,
                    'game': stat.game
                })
            
            # Calculate simple statistics for each player
            player_stats = {}
            for player_name, games in player_data.items():
                if len(games) < 1:
                    continue
                    
                values = [g['value'] for g in games]
                player_stats[player_name] = {
                    'mean': np.mean(values),
                    'std': np.std(values) if len(values) > 1 else values[0] * 0.1,  # 10% of value if only 1 game
                    'trend': self.calculate_trend(values),
                    'recent_games': games[-2:],  # Last 2 games
                    'total_games': len(games)
                }
            
            self.stdout.write(f"Simple model for {prop_type}:")
            self.stdout.write(f"  Players with data: {len(player_stats)}")
            self.stdout.write(f"  Total data points: {stats_query.count()}")
            
            return {
                'model_type': 'simple_statistical',
                'player_stats': player_stats,
                'stat_field': stat_field,
                'prop_type': prop_type
            }
            
        except Exception as e:
            self.stdout.write(f"Error training simple model for {prop_type}: {e}")
            return None

    def calculate_trend(self, values):
        """Calculate simple trend from recent values"""
        if len(values) < 2:
            return 0
        # Simple linear trend: (last - first) / (len - 1)
        return (values[-1] - values[0]) / (len(values) - 1)

    def predict_simple(self, player_name, game, prop_type, model_data):
        """Make prediction using simple statistical model"""
        try:
            player_stats = model_data['player_stats']
            
            if player_name not in player_stats:
                # If no data for this player, use league average
                all_values = []
                for stats in player_stats.values():
                    all_values.extend([g['value'] for g in stats['recent_games']])
                
                if not all_values:
                    return None, None
                
                mean_pred = np.mean(all_values)
                std_pred = np.std(all_values) if len(all_values) > 1 else mean_pred * 0.2
            else:
                stats = player_stats[player_name]
                
                # Use recent average with trend adjustment
                recent_values = [g['value'] for g in stats['recent_games']]
                mean_pred = np.mean(recent_values)
                
                # Add trend if we have multiple games
                if len(recent_values) > 1:
                    trend_adjustment = stats['trend'] * 0.5  # Conservative trend application
                    mean_pred += trend_adjustment
                
                # Use calculated std or fallback
                std_pred = stats['std'] if stats['std'] > 0 else mean_pred * 0.15
                
                # Apply opponent adjustment
                mean_pred = self.apply_opponent_adjustment(mean_pred, game, prop_type, player_name)
                
                # Apply conservative adjustment for limited data
                if stats['total_games'] < 3:  # Less than 3 games of data
                    # Blend with league average to reduce overconfidence
                    all_values = []
                    for other_stats in player_stats.values():
                        all_values.extend([g['value'] for g in other_stats['recent_games']])
                    
                    if all_values:
                        league_avg = np.mean(all_values)
                        
                        # More conservative blending for very limited data
                        if stats['total_games'] == 1:
                            # Only 1 game: 50% player, 50% league average
                            mean_pred = 0.5 * mean_pred + 0.5 * league_avg
                            std_pred = max(std_pred, mean_pred * 0.5)  # High uncertainty
                        else:
                            # 2 games: 70% player, 30% league average
                            mean_pred = 0.7 * mean_pred + 0.3 * league_avg
                            std_pred = max(std_pred, mean_pred * 0.3)
            
            # Ensure reasonable bounds
            mean_pred = max(0, mean_pred)
            std_pred = max(mean_pred * 0.05, std_pred)  # At least 5% variance
            
            # Prevent extreme probabilities by ensuring minimum variance
            # This prevents 100% over/under when prediction is far from line
            min_std = mean_pred * 0.2  # At least 20% of mean as std dev
            std_pred = max(std_pred, min_std)
            
            # Additional check: if prediction is very far from typical range, increase uncertainty
            # This handles cases where limited data might be misleading
            if mean_pred < 5 and prop_type in ['player_pass_yds', 'player_rush_yds', 'player_reception_yds']:
                # Very low predictions for major stats - increase uncertainty
                std_pred = max(std_pred, mean_pred * 0.8)
            elif mean_pred > 500 and prop_type == 'player_pass_yds':
                # Very high passing predictions - increase uncertainty
                std_pred = max(std_pred, mean_pred * 0.3)
            
            return mean_pred, std_pred
            
        except Exception as e:
            self.stdout.write(f"Error in simple prediction for {player_name}: {e}")
            return None, None

    def apply_opponent_adjustment(self, base_prediction, game, prop_type, player_name):
        """Apply simple opponent strength adjustment"""
        try:
            from core.models import TeamDefense, Player
            
            # Get player's team
            player = Player.objects.get(player_name=player_name)
            if not player.team:
                return base_prediction
            
            # Determine opponent
            if player.team == game.home_team:
                opponent_team = game.away_team
            elif player.team == game.away_team:
                opponent_team = game.home_team
            else:
                return base_prediction
            
            # Get opponent defense stats
            opponent_defense = TeamDefense.objects.filter(
                team=opponent_team,
                season=game.season,
                week__lte=game.week
            ).order_by('-week').first()
            
            if not opponent_defense:
                return base_prediction
            
            # Simple adjustment based on defensive rank (1=best defense, 32=worst)
            if 'pass' in prop_type:
                def_rank = opponent_defense.passing_defense_rank or 16
            elif 'rush' in prop_type:
                def_rank = opponent_defense.rushing_defense_rank or 16
            elif 'reception' in prop_type or 'receiving' in prop_type:
                def_rank = opponent_defense.receiving_defense_rank or 16
            else:
                def_rank = opponent_defense.overall_defense_rank or 16
            
            # Adjust prediction: better defense = lower prediction
            # More aggressive adjustments for better defense impact
            if def_rank <= 8:  # Top 8 defense
                adjustment = 0.80 + (def_rank - 1) * 0.025  # 0.80 to 0.975 (20-2.5% reduction)
            elif def_rank >= 25:  # Bottom 8 defense
                adjustment = 1.05 + (32 - def_rank) * 0.03  # 1.05 to 1.26 (5-26% increase)
            elif def_rank <= 16:  # Above average defense
                adjustment = 0.90 + (def_rank - 9) * 0.014  # 0.90 to 0.998 (10-0.2% reduction)
            else:  # Below average defense
                adjustment = 1.01 + (def_rank - 17) * 0.02  # 1.01 to 1.30 (1-30% increase)
            
            return base_prediction * adjustment
            
        except Exception as e:
            return base_prediction

    def create_advanced_feature_vector(self, stat, recent_stats, game, prop_type):
        """Create advanced feature vector with rolling averages, context, and opponent strength"""
        from core.models import TeamDefense
        
        try:
            # Current game context
            current_features = [
                stat.passing_attempts or 0,
                stat.passing_completions or 0,
                stat.passing_yards or 0,
                stat.passing_tds or 0,
                stat.rushing_attempts or 0,
                stat.rushing_yards or 0,
                stat.rushing_tds or 0,
                stat.receiving_targets or 0,
                stat.receiving_receptions or 0,
                stat.receiving_yards or 0,
                stat.receiving_tds or 0,
                stat.air_yards or 0,
                stat.yac or 0,
                stat.adot or 0,
                stat.target_share or 0,
                stat.snap_share or 0,
            ]
            
            # Rolling averages (last 5 games)
            if recent_stats.exists():
                recent_avg = recent_stats.aggregate(
                    avg_passing_attempts=Avg('passing_attempts'),
                    avg_passing_completions=Avg('passing_completions'),
                    avg_passing_yards=Avg('passing_yards'),
                    avg_passing_tds=Avg('passing_tds'),
                    avg_rushing_attempts=Avg('rushing_attempts'),
                    avg_rushing_yards=Avg('rushing_yards'),
                    avg_rushing_tds=Avg('rushing_tds'),
                    avg_receiving_targets=Avg('receiving_targets'),
                    avg_receiving_receptions=Avg('receiving_receptions'),
                    avg_receiving_yards=Avg('receiving_yards'),
                    avg_receiving_tds=Avg('receiving_tds'),
                    avg_air_yards=Avg('air_yards'),
                    avg_yac=Avg('yac'),
                    avg_adot=Avg('adot'),
                    avg_target_share=Avg('target_share'),
                    avg_snap_share=Avg('snap_share'),
                )
                
                rolling_features = [
                    recent_avg['avg_passing_attempts'] or 0,
                    recent_avg['avg_passing_completions'] or 0,
                    recent_avg['avg_passing_yards'] or 0,
                    recent_avg['avg_passing_tds'] or 0,
                    recent_avg['avg_rushing_attempts'] or 0,
                    recent_avg['avg_rushing_yards'] or 0,
                    recent_avg['avg_rushing_tds'] or 0,
                    recent_avg['avg_receiving_targets'] or 0,
                    recent_avg['avg_receiving_receptions'] or 0,
                    recent_avg['avg_receiving_yards'] or 0,
                    recent_avg['avg_receiving_tds'] or 0,
                    recent_avg['avg_air_yards'] or 0,
                    recent_avg['avg_yac'] or 0,
                    recent_avg['avg_adot'] or 0,
                    recent_avg['avg_target_share'] or 0,
                    recent_avg['avg_snap_share'] or 0,
                ]
            else:
                rolling_features = [0] * 16
            
            # Season-to-date stats
            season_stats = PlayerStats.objects.filter(
                player=stat.player,
                season=stat.season,
                week__lt=stat.week
            ).aggregate(
                season_passing_attempts=Avg('passing_attempts'),
                season_passing_yards=Avg('passing_yards'),
                season_rushing_yards=Avg('rushing_yards'),
                season_receiving_yards=Avg('receiving_yards'),
            )
            
            season_features = [
                season_stats['season_passing_attempts'] or 0,
                season_stats['season_passing_yards'] or 0,
                season_stats['season_rushing_yards'] or 0,
                season_stats['season_receiving_yards'] or 0,
            ]
            
            # Game context
            context_features = [
                stat.week,  # Week of season
                stat.season,  # Season year
                1 if stat.week <= 4 else 0,  # Early season
                1 if stat.week >= 14 else 0,  # Late season
            ]
            
            # Opponent defensive strength features
            opponent_features = self.get_opponent_defensive_features(game, prop_type, stat.player.team)
            
            # Team offensive strength features
            team_offense_features = self.get_team_offensive_features(game, prop_type, stat.player.team)
            
            # Next Gen Stats features
            nextgen_features = self.get_nextgen_features(stat, prop_type)
            
            # Combine all features
            all_features = current_features + rolling_features + season_features + context_features + opponent_features + team_offense_features + nextgen_features
            return all_features
            
        except Exception as e:
            return None

    def get_opponent_defensive_features(self, game, prop_type, player_team=None):
        """Get opponent defensive strength features based on prop type and player's team"""
        from core.models import TeamDefense
        
        try:
            # Determine which team is the opponent
            if game.home_team == game.away_team:
                # This shouldn't happen, but handle gracefully
                return [0] * 10
            
            # Determine opponent team based on player's team
            if player_team is None:
                # If no player team provided, default to away team (fallback)
                opponent_team = game.away_team
            else:
                # Find the team that's NOT the player's team
                if player_team == game.home_team:
                    opponent_team = game.away_team
                elif player_team == game.away_team:
                    opponent_team = game.home_team
                else:
                    # Player's team doesn't match either team in the game
                    # This could happen if player changed teams or data is inconsistent
                    opponent_team = game.away_team  # Default fallback
            
            # Get opponent's defensive stats for this week or most recent
            opponent_defense = TeamDefense.objects.filter(
                team=opponent_team,
                season=game.season,
                week__lte=game.week
            ).order_by('-week').first()
            
            if not opponent_defense:
                return [0] * 10
            
            # Base defensive features (normalized rankings 0-1, where 0=worst defense, 1=best defense)
            base_features = [
                (32 - (opponent_defense.passing_defense_rank or 16)) / 31,  # Normalize 1-32 to 0-1
                (32 - (opponent_defense.rushing_defense_rank or 16)) / 31,
                (32 - (opponent_defense.receiving_defense_rank or 16)) / 31,
                (32 - (opponent_defense.overall_defense_rank or 16)) / 31,
                (opponent_defense.avg_passing_yards_allowed or 0) / 500,  # Normalize yards
                (opponent_defense.avg_rushing_yards_allowed or 0) / 200,
                (opponent_defense.avg_receiving_yards_allowed or 0) / 500,
            ]
            
            # Prop-specific features (normalized)
            if 'pass' in prop_type:
                # For passing props, focus on passing defense
                prop_features = [
                    (opponent_defense.passing_yards_allowed or 0) / 500,  # Normalize yards
                    (opponent_defense.passing_tds_allowed or 0) / 10,     # Normalize TDs
                    (opponent_defense.sacks_made or 0) / 10,              # Normalize sacks
                ]
            elif 'rush' in prop_type:
                # For rushing props, focus on rushing defense
                prop_features = [
                    (opponent_defense.rushing_yards_allowed or 0) / 200,  # Normalize yards
                    (opponent_defense.rushing_tds_allowed or 0) / 5,      # Normalize TDs
                    (opponent_defense.tackles_for_loss or 0) / 20,        # Normalize TFL
                ]
            elif 'reception' in prop_type or 'receiving' in prop_type:
                # For receiving props, focus on receiving defense
                prop_features = [
                    (opponent_defense.receiving_yards_allowed or 0) / 500,  # Normalize yards
                    (opponent_defense.receiving_tds_allowed or 0) / 10,     # Normalize TDs
                    (opponent_defense.targets_allowed or 0) / 50,           # Normalize targets
                ]
            else:
                # Default features for other prop types
                prop_features = [0, 0, 0]
            
            return base_features + prop_features
            
        except Exception as e:
            return [0] * 10

    def get_team_offensive_features(self, game, prop_type, player_team=None):
        """Get team offensive strength features based on prop type and player's team"""
        from core.models import TeamOffense
        
        try:
            # Get player's team offensive stats
            if player_team is None:
                return [0] * 10
            
            # Get most recent team offense stats
            team_offense = TeamOffense.objects.filter(
                team=player_team,
                season=game.season,
                week__lte=game.week
            ).order_by('-week').first()
            
            if not team_offense:
                return [0] * 10
            
            # Select features based on prop type
            if 'pass' in prop_type:
                features = [
                    team_offense.passing_yards or 0,
                    team_offense.passing_attempts or 0,
                    team_offense.passing_tds or 0,
                    team_offense.passing_epa or 0,
                    team_offense.passing_offense_rank or 16,
                    team_offense.avg_passing_yards or 0,
                ]
            elif 'rush' in prop_type:
                features = [
                    team_offense.rushing_yards or 0,
                    team_offense.rushing_tds or 0,
                    team_offense.rushing_epa or 0,
                    team_offense.rushing_offense_rank or 16,
                    team_offense.avg_rushing_yards or 0,
                    0,  # Padding for consistent feature count
                ]
            elif 'reception' in prop_type or 'receiving' in prop_type:
                features = [
                    team_offense.receiving_yards or 0,
                    team_offense.receiving_tds or 0,
                    team_offense.targets or 0,
                    team_offense.receiving_epa or 0,
                    team_offense.receiving_offense_rank or 16,
                    team_offense.avg_receiving_yards or 0,
                ]
            else:
                # General offensive features
                features = [
                    team_offense.passing_yards or 0,
                    team_offense.rushing_yards or 0,
                    team_offense.receiving_yards or 0,
                    team_offense.overall_offense_rank or 16,
                    team_offense.avg_passing_yards or 0,
                    team_offense.avg_rushing_yards or 0,
                ]
            
            # Pad to 10 features for consistency
            while len(features) < 10:
                features.append(0)
            
            return features[:10]
        
        except Exception as e:
            return [0] * 10

    def get_nextgen_features(self, stat, prop_type):
        """Get Next Gen Stats features based on prop type"""
        try:
            # Initialize features with zeros
            features = [0] * 15  # 15 Next Gen Stats features
            
            # Passing Next Gen Stats
            if 'pass' in prop_type:
                features[0] = stat.avg_time_to_throw or 0
                features[1] = stat.avg_completed_air_yards or 0
                features[2] = stat.avg_intended_air_yards or 0
                features[3] = stat.avg_air_yards_differential or 0
                features[4] = stat.aggressiveness or 0
                features[5] = stat.completion_percentage_above_expectation or 0
            
            # Receiving Next Gen Stats
            if 'reception' in prop_type or 'receiving' in prop_type:
                features[6] = stat.avg_cushion or 0
                features[7] = stat.avg_separation or 0
                features[8] = stat.avg_expected_yac or 0
                features[9] = stat.avg_yac_above_expectation or 0
            
            # Rushing Next Gen Stats
            if 'rush' in prop_type:
                features[10] = stat.efficiency or 0
                features[11] = stat.avg_time_to_los or 0
                features[12] = stat.expected_rush_yards or 0
                features[13] = stat.rush_yards_over_expected or 0
                features[14] = stat.rush_yards_over_expected_per_att or 0
            
            return features
            
        except Exception as e:
            return [0] * 15

    def get_feature_names(self):
        """Get feature names for model interpretation"""
        current_features = [
            'passing_attempts', 'passing_completions', 'passing_yards', 'passing_tds',
            'rushing_attempts', 'rushing_yards', 'rushing_tds',
            'receiving_targets', 'receiving_receptions', 'receiving_yards', 'receiving_tds',
            'air_yards', 'yac', 'adot', 'target_share', 'snap_share'
        ]
        
        rolling_features = [f'recent_avg_{f}' for f in current_features]
        season_features = ['season_passing_attempts', 'season_passing_yards', 'season_rushing_yards', 'season_receiving_yards']
        context_features = ['week', 'season', 'early_season', 'late_season']
        opponent_features = [
            'opp_passing_def_rank', 'opp_rushing_def_rank', 'opp_receiving_def_rank', 'opp_overall_def_rank',
            'opp_avg_passing_yards_allowed', 'opp_avg_rushing_yards_allowed', 'opp_avg_receiving_yards_allowed',
            'opp_prop_specific_1', 'opp_prop_specific_2', 'opp_prop_specific_3'
        ]
        
        team_offense_features = [
            'team_passing_yards', 'team_passing_attempts', 'team_passing_tds', 'team_passing_epa',
            'team_passing_offense_rank', 'team_avg_passing_yards', 'team_rushing_yards', 'team_rushing_tds',
            'team_rushing_epa', 'team_rushing_offense_rank'
        ]
        
        nextgen_features = [
            'ngs_avg_time_to_throw', 'ngs_avg_completed_air_yards', 'ngs_avg_intended_air_yards', 
            'ngs_avg_air_yards_differential', 'ngs_aggressiveness', 'ngs_completion_pct_above_exp',
            'ngs_avg_cushion', 'ngs_avg_separation', 'ngs_avg_expected_yac', 'ngs_avg_yac_above_expectation',
            'ngs_efficiency', 'ngs_avg_time_to_los', 'ngs_expected_rush_yards', 'ngs_rush_yards_over_expected',
            'ngs_rush_yards_over_expected_per_att'
        ]
        
        return current_features + rolling_features + season_features + context_features + opponent_features + team_offense_features + nextgen_features

    def monte_carlo_simulation(self, mean, sigma, line_value, n_simulations=10000):
        """Run Monte Carlo simulation to calculate probabilities"""
        # Generate samples from normal distribution
        samples = np.random.normal(mean, sigma, n_simulations)
        
        # Calculate probabilities
        over_count = np.sum(samples > line_value)
        under_count = np.sum(samples < line_value)
        
        over_prob = over_count / n_simulations
        under_prob = under_count / n_simulations
        
        # Calculate confidence interval (5th-95th percentile)
        confidence_interval = [
            np.percentile(samples, 5),
            np.percentile(samples, 95)
        ]
        
        return over_prob, under_prob, confidence_interval

    def prepare_prediction_features(self, player, game, prop_type):
        """Prepare features for prediction using advanced feature engineering"""
        from core.models import PlayerMapping, TeamDefense
        
        # Try to find stats using the nflreadpy name if we have a mapping
        stats_player = player
        try:
            mapping = PlayerMapping.objects.get(player_id=player.player_id, is_active=True)
            # Look for stats using the nflreadpy name
            nflreadpy_player = Player.objects.filter(player_name=mapping.nflreadpy_name).first()
            if nflreadpy_player:
                stats_player = nflreadpy_player
        except PlayerMapping.DoesNotExist:
            pass
        
        # Get player's recent stats (last 5 games)
        recent_stats = PlayerStats.objects.filter(
            player=stats_player,
            season=game.season
        ).order_by('-week')[:5]
        
        if not recent_stats.exists():
            # Use default features if no recent stats
            return [0] * 50  # 50 features total (increased from 40)
        
        # Create a mock current stat for feature creation
        # We'll use the most recent stat as a proxy
        latest_stat = recent_stats.first()
        
        # Create advanced feature vector
        features = self.create_advanced_feature_vector(latest_stat, recent_stats[1:], game, prop_type)
        
        if features is None:
            return [0] * 50
        
        return features

    def get_or_create_player(self, player_name):
        """Get or create player using mapping system"""
        from core.models import PlayerMapping, Team
        
        # First, try to find a mapping for this PrizePicks name
        try:
            mapping = PlayerMapping.objects.get(prizepicks_name=player_name, is_active=True)
            # Use the mapped player_id to find the player
            try:
                return Player.objects.get(player_id=mapping.player_id)
            except Player.DoesNotExist:
                # Create player using mapping data
                team, _ = Team.objects.get_or_create(
                    team_abbr=mapping.current_team,
                    defaults={'team_name': mapping.current_team, 'team_city': mapping.current_team}
                )
                return Player.objects.create(
                    player_id=mapping.player_id,
                    player_name=player_name,  # Use PrizePicks name for display
                    position=mapping.position,
                    team=team,
                )
        except PlayerMapping.DoesNotExist:
            # Fallback to old behavior if no mapping exists
            try:
                return Player.objects.get(player_name=player_name)
            except Player.DoesNotExist:
                default_team, _ = Team.objects.get_or_create(
                    team_abbr='UNK',
                    defaults={'team_name': 'Unknown', 'team_city': 'Unknown'}
                )
                player_id = player_name.lower().replace(' ', '_').replace('.', '').replace("'", '')
                return Player.objects.create(
                    player_id=player_id,
                    player_name=player_name,
                    position='QB',
                    team=default_team,
                )

    def get_or_create_game(self, game_id):
        """Get or create game"""
        try:
            return Game.objects.get(game_id=game_id)
        except Game.DoesNotExist:
            from core.models import Team
            default_team, _ = Team.objects.get_or_create(
                team_abbr='UNK',
                defaults={'team_name': 'Unknown', 'team_city': 'Unknown'}
            )
            return Game.objects.create(
                game_id=game_id,
                season=2025,
                week=3,
                game_date=timezone.now(),
                home_team=default_team,
                away_team=default_team,
            )
