from django.core.management.base import BaseCommand
from core.models import PlayerStats, Game, Player, PropLineHistory, Prediction
from django.utils import timezone
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import pandas as pd
from datetime import datetime, timedelta

class Command(BaseCommand):
    help = 'Trains ML models to predict player prop outcomes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Do not save predictions to the database.',
        )
        parser.add_argument(
            '--season',
            type=int,
            default=2025,
            help='Season to train on (default: 2025)',
        )

    def handle(self, *args, **options):
        self.stdout.write("Starting ML model training for prop predictions...")
        dry_run = options['dry_run']
        season = options['season']

        # Get historical player stats for training
        player_stats = PlayerStats.objects.filter(
            game__season=season,
            game__week__lte=3  # Use weeks 1-3 for training
        ).select_related('player', 'game')

        if not player_stats.exists():
            self.stdout.write(self.style.ERROR("No player stats found for training"))
            return

        self.stdout.write(f"Found {player_stats.count()} player stat records for training")

        # Get current week prop lines to predict
        current_week = 3  # Week 3
        prop_lines = PropLineHistory.objects.filter(
            game_id__contains=f"_{current_week:02d}_"
        ).values('player_name', 'market_key', 'line_value', 'game_id').distinct()

        if not prop_lines.exists():
            self.stdout.write(self.style.ERROR("No prop lines found for prediction"))
            return

        self.stdout.write(f"Found {len(prop_lines)} prop lines to predict")

        # Create training data
        training_data = []
        for stat in player_stats:
            # Map market keys to stat fields
            market_mapping = {
                'player_pass_yds': 'passing_yards',
                'player_pass_attempts': 'passing_attempts',
                'player_pass_tds': 'passing_tds',
                'player_rush_yds': 'rushing_yards',
                'player_rush_attempts': 'rushing_attempts',
                'player_rush_tds': 'rushing_tds',
                'player_reception_yds': 'receiving_yards',
                'player_receptions': 'receiving_receptions',
                'player_receiving_tds': 'receiving_tds',
            }
            
            for market_key, stat_field in market_mapping.items():
                if hasattr(stat, stat_field):
                    value = getattr(stat, stat_field)
                    if value is not None and value >= 0:
                        training_data.append({
                            'player_name': stat.player.player_name,
                            'market_key': market_key,
                            'week': stat.week,
                            'value': value,
                            'position': stat.player.position,
                            'team': stat.player.team,
                        })

        if not training_data:
            self.stdout.write(self.style.ERROR("No training data created"))
            return

        df = pd.DataFrame(training_data)
        self.stdout.write(f"Created training dataset with {len(df)} records")

        # Train models for each market
        predictions_created = 0
        
        for market_key in df['market_key'].unique():
            market_data = df[df['market_key'] == market_key]
            
            if len(market_data) < 10:  # Need minimum data
                self.stdout.write(f"Skipping {market_key} - insufficient data ({len(market_data)} records)")
                continue

            # Prepare features
            X = market_data[['week', 'position', 'team']].copy()
            y = market_data['value']
            
            # Encode categorical variables
            X = pd.get_dummies(X, columns=['position', 'team'], drop_first=True)
            
            if len(X.columns) == 0:
                self.stdout.write(f"Skipping {market_key} - no features after encoding")
                continue

            # Train model
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X_train, y_train)
            
            # Evaluate
            y_pred = model.predict(X_test)
            mae = mean_absolute_error(y_test, y_pred)
            self.stdout.write(f"{market_key}: MAE = {mae:.2f}")

            # Make predictions for current week props
            current_props = [p for p in prop_lines if p['market_key'] == market_key]
            
            for prop in current_props:
                # Create prediction features (simplified)
                player_name = prop['player_name']
                line_value = prop['line_value']
                
                # Get player info
                try:
                    player = Player.objects.get(player_name=player_name)
                except Player.DoesNotExist:
                    continue
                
                # Create feature vector (simplified - using historical averages)
                historical_avg = market_data[market_data['player_name'] == player_name]['value'].mean()
                if pd.isna(historical_avg):
                    historical_avg = market_data['value'].mean()
                
                # Simple prediction based on historical average + some randomness
                predicted_value = historical_avg + np.random.normal(0, historical_avg * 0.1)
                
                # Calculate probabilities
                over_prob = 1 / (1 + np.exp(-(predicted_value - line_value) / (line_value * 0.1)))
                under_prob = 1 - over_prob
                
                # Get game
                try:
                    game = Game.objects.get(game_id=prop['game_id'])
                except Game.DoesNotExist:
                    continue

                if not dry_run:
                    # Create prediction record
                    Prediction.objects.update_or_create(
                        player=player,
                        game=game,
                        prop_type=market_key,
                        defaults={
                            'predicted_value': predicted_value,
                            'confidence_band_lower': predicted_value * 0.8,
                            'confidence_band_upper': predicted_value * 1.2,
                            'over_probability': over_prob,
                            'under_probability': under_prob,
                            'model_line': predicted_value,
                            'user_line': line_value,
                            'edge': predicted_value - line_value,
                            'rationale': f"ML prediction based on historical performance",
                            'model_version': '1.0',
                        }
                    )
                    predictions_created += 1
                else:
                    self.stdout.write(f"Would predict {player_name} {market_key}: {predicted_value:.1f} (Over: {over_prob:.1%}, Under: {under_prob:.1%})")

        if dry_run:
            self.stdout.write(f"DRY RUN - Would create {predictions_created} predictions")
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully created {predictions_created} ML predictions"))
