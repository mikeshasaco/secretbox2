#!/usr/bin/env python3
"""
Populate player_name field in PlayerStats table
"""
from django.core.management.base import BaseCommand
from core.models import PlayerStats


class Command(BaseCommand):
    help = 'Populate player_name field in PlayerStats table'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write("Populating player_name field in PlayerStats...")
        
        # Get all PlayerStats records that don't have player_name populated
        stats_without_name = PlayerStats.objects.filter(player_name='')
        total_count = stats_without_name.count()
        
        self.stdout.write(f"Found {total_count} PlayerStats records without player_name")
        
        updated_count = 0
        
        for stat in stats_without_name:
            try:
                player_name = stat.player.player_name
                
                if dry_run:
                    self.stdout.write(f"Would update: {stat.id} -> {player_name}")
                else:
                    stat.player_name = player_name
                    stat.save(update_fields=['player_name'])
                    updated_count += 1
                    
                    if updated_count % 1000 == 0:
                        self.stdout.write(f"Updated {updated_count} records...")
                
            except Exception as e:
                self.stdout.write(f"Error updating PlayerStats {stat.id}: {e}")
                continue
        
        if dry_run:
            self.stdout.write(f"DRY RUN - Would update {total_count} PlayerStats records")
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully updated {updated_count} PlayerStats records with player names"))
