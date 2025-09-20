#!/usr/bin/env python3
"""
Populate PropLineHistory from existing PlayerProp data
This creates historical snapshots of all current prop lines
"""
from django.core.management.base import BaseCommand
from core.models import PlayerProp, PropLineHistory, OddsEvent
from django.utils import timezone


class Command(BaseCommand):
    help = 'Populate PropLineHistory from existing PlayerProp data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating records',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write("DRY RUN - No data will be created")
        
        created_count = 0
        
        # Get all current player props
        props = PlayerProp.objects.filter(is_active=True).select_related('event')
        
        self.stdout.write(f"Found {props.count()} active player props")
        
        for prop in props:
            # Create historical snapshot
            if not dry_run:
                PropLineHistory.objects.create(
                    game_id=prop.event.game_id,
                    player_name=prop.player_name,
                    market_key=prop.market_key,
                    line_value=prop.over_point or 0,  # Use over_point as the line
                    over_odds=prop.over_odds,
                    under_odds=prop.under_odds,
                    source='prizepicks',
                    captured_at=timezone.now()
                )
            
            created_count += 1
            
            if created_count % 50 == 0:
                self.stdout.write(f"Processed {created_count} props...")
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Would create {created_count} PropLineHistory records")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully created {created_count} PropLineHistory records")
            )
