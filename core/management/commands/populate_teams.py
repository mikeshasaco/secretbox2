#!/usr/bin/env python3
"""
Populate Team model from NFL data
"""
from django.core.management.base import BaseCommand
from core.models import Team
import nflreadpy as nfl


class Command(BaseCommand):
    help = 'Populate Team model from NFL data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--season',
            type=int,
            default=2025,
            help='NFL season to process (default: 2025)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating records',
        )

    def handle(self, *args, **options):
        season = options['season']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write("DRY RUN - No data will be created")
        
        # Load NFL teams data
        try:
            teams = nfl.load_teams()
            self.stdout.write(f"Loaded {len(teams)} teams from NFL data")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error loading NFL teams data: {e}"))
            return
        
        # Convert to pandas if it's polars
        if hasattr(teams, 'to_pandas'):
            teams = teams.to_pandas()
        
        created_count = 0
        
        for _, team_data in teams.iterrows():
            if team_data['season'] != season:
                continue
                
            if not dry_run:
                # Create or update team
                team, created = Team.objects.get_or_create(
                    team_abbr=team_data['team'],
                    defaults={
                        'team_name': team_data['full'],
                        'team_city': team_data['location'],
                        'team_color_primary': team_data.get('color_primary', '#000000'),
                        'team_color_secondary': team_data.get('color_secondary', '#FFFFFF'),
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(f"Created {team_data['team']}: {team_data['full']}")
            else:
                created_count += 1
                self.stdout.write(f"Would create {team_data['team']}: {team_data['full']}")
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Would create {created_count} teams")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully created {created_count} teams")
            )
