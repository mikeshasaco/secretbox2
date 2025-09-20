from django.core.management.base import BaseCommand
from core.models import PropLineHistory, Prediction, Player, Game
from django.utils import timezone
import random

class Command(BaseCommand):
    help = 'Creates mock ML predictions for existing prop lines'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Do not save predictions to the database.',
        )

    def handle(self, *args, **options):
        self.stdout.write("Creating mock ML predictions...")
        dry_run = options['dry_run']

        # Get all prop lines
        prop_lines = PropLineHistory.objects.all()
        self.stdout.write(f"Found {prop_lines.count()} prop lines")

        predictions_created = 0

        for prop in prop_lines:
            # Create mock predictions based on player name patterns
            player_name = prop.player_name.lower()
            
            # Mock logic: different players get different probabilities
            if 'young' in player_name:
                over_prob = 0.35  # 35% chance of going over
                under_prob = 0.65  # 65% chance of going under
                predicted_value = prop.line_value - 15.0  # Predict under
            elif 'mahomes' in player_name:
                over_prob = 0.72  # 72% chance of going over
                under_prob = 0.28  # 28% chance of going under
                predicted_value = prop.line_value + 25.0  # Predict over
            elif 'allen' in player_name:
                over_prob = 0.68  # 68% chance of going over
                under_prob = 0.32  # 32% chance of going under
                predicted_value = prop.line_value + 18.0  # Predict over
            elif 'burrow' in player_name:
                over_prob = 0.58  # 58% chance of going over
                under_prob = 0.42  # 42% chance of going under
                predicted_value = prop.line_value + 8.0  # Predict over
            else:
                # Random probabilities for other players
                over_prob = random.uniform(0.3, 0.7)
                under_prob = 1.0 - over_prob
                predicted_value = prop.line_value + random.uniform(-20, 20)

            # Get or create player
            try:
                player, _ = Player.objects.get_or_create(
                    player_name=prop.player_name,
                    defaults={
                        'position': 'QB',  # Default position
                        'team': 'UNK',
                    }
                )
            except Exception as e:
                self.stdout.write(f"Could not create player {prop.player_name}: {e}")
                continue

            # Get or create game
            try:
                game, _ = Game.objects.get_or_create(
                    game_id=prop.game_id,
                    defaults={
                        'season': 2025,
                        'week': 3,
                        'game_date': timezone.now(),
                        'home_team_id': 1,  # Default team
                        'away_team_id': 2,  # Default team
                    }
                )
            except Exception as e:
                self.stdout.write(f"Could not create game {prop.game_id}: {e}")
                continue

            if not dry_run:
                # Create prediction
                prediction, created = Prediction.objects.update_or_create(
                    player=player,
                    game=game,
                    prop_type=prop.market_key,
                    defaults={
                        'predicted_value': predicted_value,
                        'confidence_band_lower': predicted_value * 0.8,
                        'confidence_band_upper': predicted_value * 1.2,
                        'over_probability': over_prob,
                        'under_probability': under_prob,
                        'model_line': predicted_value,
                        'user_line': prop.line_value,
                        'edge': predicted_value - prop.line_value,
                        'rationale': f"Mock ML prediction for {prop.player_name}",
                        'model_version': '1.0',
                    }
                )
                if created:
                    predictions_created += 1
                    self.stdout.write(f"Created prediction for {prop.player_name} {prop.market_key}: Over {over_prob:.1%}, Under {under_prob:.1%}")
            else:
                self.stdout.write(f"Would create prediction for {prop.player_name} {prop.market_key}: Over {over_prob:.1%}, Under {under_prob:.1%}")

        if dry_run:
            self.stdout.write(f"DRY RUN - Would create {predictions_created} predictions")
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully created {predictions_created} mock predictions"))
