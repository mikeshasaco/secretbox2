#!/usr/bin/env python3
"""
Calculate Closing Line Value (CLV) for prop lines
"""
from django.core.management.base import BaseCommand
from core.models import PropLineHistory
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    help = 'Calculate Closing Line Value (CLV) for prop lines'

    def add_arguments(self, parser):
        parser.add_argument(
            '--game-id',
            type=str,
            help='Calculate CLV for specific game (e.g., 2025_03_ATL_CAR)',
        )
        parser.add_argument(
            '--market',
            type=str,
            help='Calculate CLV for specific market (e.g., player_pass_yds)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be calculated without actually updating',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        game_id = options.get('game_id')
        market = options.get('market')
        
        if dry_run:
            self.stdout.write("DRY RUN - No CLV will be calculated")
        
        # Build the CLV calculation query
        query = """
        WITH line_movements AS (
          SELECT 
            plh.game_id,
            plh.player_name,
            plh.market_key,
            plh.line_value,
            plh.captured_at,
            plh.id,
            -- Find opening line (earliest)
            FIRST_VALUE(plh.line_value) OVER (
              PARTITION BY plh.game_id, plh.player_name, plh.market_key 
              ORDER BY plh.captured_at ASC
            ) AS opening_line,
            -- Find closing line (latest before kickoff)
            LAST_VALUE(plh.line_value) OVER (
              PARTITION BY plh.game_id, plh.player_name, plh.market_key 
              ORDER BY plh.captured_at ASC
              ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ) AS closing_line,
            -- Mark our capture time (you can adjust this logic)
            CASE 
              WHEN plh.captured_at = (
                SELECT MAX(plh2.captured_at) 
                FROM core_proplinehistory plh2 
                WHERE plh2.game_id = plh.game_id 
                  AND plh2.player_name = plh.player_name 
                  AND plh2.market_key = plh.market_key
                  AND plh2.captured_at <= NOW() - INTERVAL '1 hour'
              ) THEN TRUE 
              ELSE FALSE 
            END AS is_our_capture,
            -- Mark opening line
            plh.captured_at = (
              SELECT MIN(plh3.captured_at) 
              FROM core_proplinehistory plh3 
              WHERE plh3.game_id = plh.game_id 
                AND plh3.player_name = plh.player_name 
                AND plh3.market_key = plh.market_key
            ) AS is_opening,
            -- Mark closing line
            plh.captured_at = (
              SELECT MAX(plh4.captured_at) 
              FROM core_proplinehistory plh4 
              WHERE plh4.game_id = plh.game_id 
                AND plh4.player_name = plh.player_name 
                AND plh4.market_key = plh.market_key
            ) AS is_closing
          FROM core_proplinehistory plh
        )
        SELECT 
          lm.game_id,
          lm.player_name,
          lm.market_key,
          lm.line_value,
          lm.captured_at,
          lm.id,
          lm.opening_line,
          lm.closing_line,
          lm.is_our_capture,
          lm.is_opening,
          lm.is_closing,
          -- Calculate CLV
          lm.line_value - lm.opening_line AS clv_vs_opening,
          lm.line_value - lm.closing_line AS clv_vs_closing
        FROM line_movements lm
        """
        
        params = []
        if game_id:
            query += " WHERE lm.game_id = %s"
            params.append(game_id)
        
        if market:
            if game_id:
                query += " AND lm.market_key = %s"
            else:
                query += " WHERE lm.market_key = %s"
            params.append(market)
        
        query += " ORDER BY lm.game_id, lm.player_name, lm.market_key, lm.captured_at"
        
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()
        
        self.stdout.write(f"Found {len(results)} prop lines to calculate CLV for")
        
        updated_count = 0
        
        for row in results:
            (game_id, player_name, market_key, line_value, captured_at, 
             plh_id, opening_line, closing_line, is_our_capture, 
             is_opening, is_closing, clv_vs_opening, clv_vs_closing) = row
            
            if not dry_run:
                try:
                    plh = PropLineHistory.objects.get(id=plh_id)
                    plh.is_opening_line = is_opening
                    plh.is_closing_line = is_closing
                    plh.is_our_capture = is_our_capture
                    plh.clv_vs_opening = clv_vs_opening
                    plh.clv_vs_closing = clv_vs_closing
                    plh.save()
                    updated_count += 1
                except PropLineHistory.DoesNotExist:
                    self.stdout.write(f"Warning: PropLineHistory {plh_id} not found")
                    continue
            else:
                updated_count += 1
            
            self.stdout.write(
                f"{player_name} {market_key}: Line={line_value}, "
                f"Opening={opening_line}, Closing={closing_line}, "
                f"CLV vs Opening={clv_vs_opening:.1f}, CLV vs Closing={clv_vs_closing:.1f}"
            )
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Would calculate CLV for {updated_count} prop lines")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully calculated CLV for {updated_count} prop lines")
            )
