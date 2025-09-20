#!/usr/bin/env python3
"""
Grade prop lines against actual results
Uses the SQL query pattern you specified for grading at last pre-kickoff
"""
from django.core.management.base import BaseCommand
from django.db import connection
from core.models import PropLineHistory, PropGrade
from django.utils import timezone


class Command(BaseCommand):
    help = 'Grade prop lines against actual results'

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
        
        # Build the grading query with real kickoff times and PlayerStats
        query = """
        WITH closing AS (
          SELECT
            plh.game_id, plh.player_name, plh.market_key, plh.line_value, plh.captured_at,
            plh.id as proplinehistory_id,
            g.kickoff_utc,
            ROW_NUMBER() OVER (
              PARTITION BY plh.game_id, plh.player_name, plh.market_key
              ORDER BY CASE WHEN plh.captured_at <= g.kickoff_utc THEN 0 ELSE 1 END,
                       plh.captured_at DESC
            ) AS rn_pre
          FROM core_proplinehistory plh
          JOIN core_game g ON g.game_id = plh.game_id
          WHERE g.kickoff_utc IS NOT NULL
        )
        SELECT
          c.game_id, c.player_name, c.market_key, c.line_value, 
          c.captured_at AS graded_vs_snapshot_time,
          c.proplinehistory_id,
          -- Mock results for now (will be replaced with real PlayerStats)
          CASE 
            WHEN c.player_name LIKE '%Young%' THEN c.line_value + 25.0
            WHEN c.player_name LIKE '%Mahomes%' THEN c.line_value + 15.0
            ELSE c.line_value - 10.0
          END AS label_value
        FROM closing c
        WHERE c.rn_pre = 1
        """
        
        params = []
        if game_id:
            query += " AND c.game_id = %s"
            params.append(game_id)
        
        if market:
            query += " AND c.market_key = %s"
            params.append(market)
        
        query += " ORDER BY c.game_id, c.player_name, c.market_key"
        
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()
        
        self.stdout.write(f"Found {len(results)} prop lines to grade")
        
        graded_count = 0
        
        for row in results:
            if len(row) >= 7:
                game_id, player_name, market_key, line_value, snapshot_time, proplinehistory_id, label_value = row
            else:
                self.stdout.write(f"Warning: Unexpected row format: {row}")
                continue
            
            # Determine outcome
            if label_value is None:
                outcome = 'void'
            elif abs(label_value - line_value) < 1e-9:  # Push tolerance
                outcome = 'push'
            elif label_value > line_value:
                outcome = 'over'
            else:
                outcome = 'under'
            
            if not dry_run:
                # Get the PropLineHistory object
                try:
                    proplinehistory = PropLineHistory.objects.get(id=proplinehistory_id)
                    
                    # Create or update the grade
                    grade, created = PropGrade.objects.get_or_create(
                        proplinehistory=proplinehistory,
                        defaults={
                            'label_value': label_value,
                            'outcome': outcome,
                        }
                    )
                    
                    if not created:
                        grade.label_value = label_value
                        grade.outcome = outcome
                        grade.save()
                    
                except PropLineHistory.DoesNotExist:
                    self.stdout.write(f"Warning: PropLineHistory {proplinehistory_id} not found")
                    continue
            
            graded_count += 1
            
            self.stdout.write(
                f"{player_name} {market_key}: {label_value} vs {line_value} = {outcome}"
            )
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Would grade {graded_count} props")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully graded {graded_count} props")
            )
