from django.core.management.base import BaseCommand
from core.models import Team, TeamDefense, Game
import nflreadpy as nfl
import pandas as pd
from django.db.models import Avg


class Command(BaseCommand):
    help = 'Populate team defensive statistics from nflreadpy'

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
        
        self.stdout.write(f"Populating team defensive stats for seasons: {seasons}")
        
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
                            self.stdout.write(f"  Would create defense stats for {team_abbr} Week {week}")
                            continue
                        
                        # Create or update TeamDefense record
                        defense_stats, created = TeamDefense.objects.update_or_create(
                            team=team,
                            season=season,
                            week=week,
                            defaults={
                                # Passing Defense (what the team allows)
                                'passing_attempts_allowed': week_data.get('attempts', 0),
                                'passing_yards_allowed': week_data.get('passing_yards', 0),
                                'passing_tds_allowed': week_data.get('passing_tds', 0),
                                'passing_interceptions_forced': week_data.get('passing_interceptions', 0),
                                'sacks_made': week_data.get('sacks_suffered', 0),  # This is sacks made by defense
                                'passing_epa_allowed': week_data.get('passing_epa', 0),
                                
                                # Rushing Defense
                                'rushing_yards_allowed': week_data.get('rushing_yards', 0),
                                'rushing_tds_allowed': week_data.get('rushing_tds', 0),
                                'tackles_for_loss': week_data.get('def_tackles_for_loss', 0),
                                'rushing_epa_allowed': week_data.get('rushing_epa', 0),
                                
                                # Receiving Defense
                                'receiving_yards_allowed': week_data.get('receiving_yards', 0),
                                'receiving_tds_allowed': week_data.get('receiving_tds', 0),
                                'targets_allowed': week_data.get('targets', 0),
                                'receiving_epa_allowed': week_data.get('receiving_epa', 0),
                            }
                        )
                        
                        if created:
                            self.stdout.write(f"  Created defense stats for {team_abbr} Week {week}")
                        else:
                            self.stdout.write(f"  Updated defense stats for {team_abbr} Week {week}")
                    
                    teams_processed += 1
                
                self.stdout.write(f"Processed {teams_processed} teams for {season}")
                
                # Calculate season-to-date averages and rankings
                if not dry_run:
                    self.calculate_season_averages(season)
                    self.calculate_defensive_rankings(season)
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing {season}: {str(e)}"))
                continue
        
        self.stdout.write(self.style.SUCCESS("Team defense population completed!"))

    def calculate_season_averages(self, season):
        """Calculate season-to-date averages for each team"""
        self.stdout.write(f"Calculating season averages for {season}...")
        
        teams = Team.objects.all()
        for team in teams:
            # Get all defense stats for this team this season
            defense_stats = TeamDefense.objects.filter(team=team, season=season).order_by('week')
            
            for defense_stat in defense_stats:
                # Calculate averages up to this week
                previous_stats = defense_stats.filter(week__lte=defense_stat.week)
                
                if previous_stats.exists():
                    avg_stats = previous_stats.aggregate(
                        avg_passing_yards=Avg('passing_yards_allowed'),
                        avg_rushing_yards=Avg('rushing_yards_allowed'),
                        avg_receiving_yards=Avg('receiving_yards_allowed'),
                    )
                    
                    defense_stat.avg_passing_yards_allowed = avg_stats['avg_passing_yards'] or 0
                    defense_stat.avg_rushing_yards_allowed = avg_stats['avg_rushing_yards'] or 0
                    defense_stat.avg_receiving_yards_allowed = avg_stats['avg_receiving_yards'] or 0
                    defense_stat.save()

    def calculate_defensive_rankings(self, season):
        """Calculate defensive rankings for each week"""
        self.stdout.write(f"Calculating defensive rankings for {season}...")
        
        # Get all weeks in this season
        weeks = TeamDefense.objects.filter(season=season).values_list('week', flat=True).distinct().order_by('week')
        
        for week in weeks:
            # Calculate rankings for this week
            week_stats = TeamDefense.objects.filter(season=season, week=week)
            
            if not week_stats.exists():
                continue
            
            # Convert to pandas for ranking
            data = []
            for stat in week_stats:
                data.append({
                    'team': stat.team.team_abbr,
                    'passing_yards': stat.passing_yards_allowed,
                    'rushing_yards': stat.rushing_yards_allowed,
                    'receiving_yards': stat.receiving_yards_allowed,
                    'defense_stat': stat
                })
            
            df = pd.DataFrame(data)
            
            # Rank by yards allowed (lower is better for defense)
            df['passing_rank'] = df['passing_yards'].rank(method='min', ascending=True)
            df['rushing_rank'] = df['rushing_yards'].rank(method='min', ascending=True)
            df['receiving_rank'] = df['receiving_yards'].rank(method='min', ascending=True)
            
            # Overall rank (average of the three)
            df['overall_rank'] = (df['passing_rank'] + df['rushing_rank'] + df['receiving_rank']) / 3
            df['overall_rank'] = df['overall_rank'].rank(method='min', ascending=True)
            
            # Update the database
            for _, row in df.iterrows():
                defense_stat = row['defense_stat']
                defense_stat.passing_defense_rank = int(row['passing_rank'])
                defense_stat.rushing_defense_rank = int(row['rushing_rank'])
                defense_stat.receiving_defense_rank = int(row['receiving_rank'])
                defense_stat.overall_defense_rank = int(row['overall_rank'])
                defense_stat.save()
        
        self.stdout.write(f"Updated defensive rankings for {len(weeks)} weeks in {season}")
