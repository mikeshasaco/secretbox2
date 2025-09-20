#!/usr/bin/env python3
"""
Populate team offensive statistics from nflreadpy
"""
from django.core.management.base import BaseCommand
from core.models import Team, TeamOffense
import nflreadpy as nfl
import pandas as pd
from django.db.models import Avg


class Command(BaseCommand):
    help = 'Populate team offensive statistics from nflreadpy'

    def add_arguments(self, parser):
        parser.add_argument(
            '--seasons',
            nargs='+',
            type=int,
            default=[2024, 2025],
            help='Seasons to populate (default: 2024, 2025)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be populated without saving'
        )

    def handle(self, *args, **options):
        seasons = options['seasons']
        dry_run = options['dry_run']
        
        self.stdout.write(f"Populating team offensive stats for seasons: {seasons}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No data will be saved"))
        
        for season in seasons:
            self.stdout.write(f"\n=== Processing {season} Season ===")
            
            try:
                # Load team stats from nflreadpy
                team_stats = nfl.load_team_stats(seasons=[season])
                self.stdout.write(f"Loaded {len(team_stats)} team stat records for {season}")
                
                # Convert to pandas for easier processing
                df = team_stats.to_pandas()
                
                # Process each team's weekly stats
                teams_processed = 0
                for team_abbr in df['team'].unique():
                    team_data = df[df['team'] == team_abbr].copy()
                    
                    # Get or create team
                    try:
                        team = Team.objects.get(team_abbr=team_abbr)
                    except Team.DoesNotExist:
                        self.stdout.write(f"Team {team_abbr} not found in database, skipping")
                        continue
                    
                    # Process each week
                    for _, week_data in team_data.iterrows():
                        week = week_data['week']
                        
                        if dry_run:
                            self.stdout.write(f"  Would create offense stats for {team_abbr} Week {week}")
                            continue
                        
                        # Create or update TeamOffense record
                        offense_stats, created = TeamOffense.objects.update_or_create(
                            team=team,
                            season=season,
                            week=week,
                            defaults={
                                # Passing Offense (what the team produces)
                                'passing_attempts': week_data.get('attempts', 0),
                                'passing_yards': week_data.get('passing_yards', 0),
                                'passing_tds': week_data.get('passing_tds', 0),
                                'passing_interceptions': week_data.get('passing_interceptions', 0),
                                'sacks_taken': week_data.get('sacks', 0),  # Sacks taken by offense
                                'passing_epa': week_data.get('passing_epa', 0),
                                
                                # Rushing Offense
                                'rushing_yards': week_data.get('rushing_yards', 0),
                                'rushing_tds': week_data.get('rushing_tds', 0),
                                'rushing_epa': week_data.get('rushing_epa', 0),
                                
                                # Receiving Offense
                                'receiving_yards': week_data.get('receiving_yards', 0),
                                'receiving_tds': week_data.get('receiving_tds', 0),
                                'targets': week_data.get('targets', 0),
                                'receiving_epa': week_data.get('receiving_epa', 0),
                            }
                        )
                        
                        if created:
                            self.stdout.write(f"  Created offense stats for {team_abbr} Week {week}")
                        else:
                            self.stdout.write(f"  Updated offense stats for {team_abbr} Week {week}")
                    
                    teams_processed += 1
                
                self.stdout.write(f"Processed {teams_processed} teams for {season}")
                
                # Calculate season-to-date averages and rankings
                if not dry_run:
                    self.calculate_season_averages(season)
                    self.calculate_offensive_rankings(season)
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing {season}: {str(e)}"))
                continue
        
        self.stdout.write(self.style.SUCCESS("Team offense population completed!"))

    def calculate_season_averages(self, season):
        """Calculate season-to-date averages for each team"""
        self.stdout.write(f"Calculating season averages for {season}...")
        
        teams = Team.objects.all()
        for team in teams:
            # Get all offense stats for this team this season
            offense_stats = TeamOffense.objects.filter(team=team, season=season).order_by('week')
            
            for offense_stat in offense_stats:
                # Calculate averages up to this week
                previous_stats = offense_stats.filter(week__lte=offense_stat.week)
                
                if previous_stats.exists():
                    avg_stats = previous_stats.aggregate(
                        avg_passing_yards=Avg('passing_yards'),
                        avg_rushing_yards=Avg('rushing_yards'),
                        avg_receiving_yards=Avg('receiving_yards'),
                    )
                    
                    offense_stat.avg_passing_yards = avg_stats['avg_passing_yards'] or 0
                    offense_stat.avg_rushing_yards = avg_stats['avg_rushing_yards'] or 0
                    offense_stat.avg_receiving_yards = avg_stats['avg_receiving_yards'] or 0
                    offense_stat.save()

    def calculate_offensive_rankings(self, season):
        """Calculate offensive rankings for each week"""
        self.stdout.write(f"Calculating offensive rankings for {season}...")
        
        # Get all weeks in this season
        weeks = TeamOffense.objects.filter(season=season).values_list('week', flat=True).distinct().order_by('week')
        
        for week in weeks:
            # Calculate rankings for this week
            week_stats = TeamOffense.objects.filter(season=season, week=week)
            
            if not week_stats.exists():
                continue
            
            # Passing offense rankings (more yards = better rank)
            passing_stats = week_stats.exclude(passing_yards=0).order_by('-passing_yards')
            for i, stat in enumerate(passing_stats, 1):
                stat.passing_offense_rank = i
                stat.save()
            
            # Rushing offense rankings (more yards = better rank)
            rushing_stats = week_stats.exclude(rushing_yards=0).order_by('-rushing_yards')
            for i, stat in enumerate(rushing_stats, 1):
                stat.rushing_offense_rank = i
                stat.save()
            
            # Receiving offense rankings (more yards = better rank)
            receiving_stats = week_stats.exclude(receiving_yards=0).order_by('-receiving_yards')
            for i, stat in enumerate(receiving_stats, 1):
                stat.receiving_offense_rank = i
                stat.save()
            
            # Overall offense rankings (total yards = better rank)
            overall_stats = week_stats.exclude(
                passing_yards=0, rushing_yards=0, receiving_yards=0
            ).extra(
                select={'total_yards': 'passing_yards + rushing_yards + receiving_yards'}
            ).order_by('-total_yards')
            
            for i, stat in enumerate(overall_stats, 1):
                stat.overall_offense_rank = i
                stat.save()
            
            self.stdout.write(f"  Calculated rankings for Week {week}")
