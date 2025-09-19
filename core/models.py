from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
import json


class Team(models.Model):
    """NFL Teams"""
    team_abbr = models.CharField(max_length=3, unique=True)
    team_name = models.CharField(max_length=50)
    team_city = models.CharField(max_length=50)
    team_color_primary = models.CharField(max_length=7, default='#000000')
    team_color_secondary = models.CharField(max_length=7, default='#FFFFFF')
    
    def __str__(self):
        return f"{self.team_city} {self.team_name}"
    
    class Meta:
        ordering = ['team_abbr']


class Player(models.Model):
    """NFL Players"""
    player_id = models.CharField(max_length=20, unique=True)
    player_name = models.CharField(max_length=100)
    position = models.CharField(max_length=5)  # QB, RB, WR, TE, etc.
    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True)
    jersey_number = models.IntegerField(null=True, blank=True)
    height = models.CharField(max_length=10, blank=True)
    weight = models.IntegerField(null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.player_name} ({self.position})"
    
    class Meta:
        ordering = ['player_name']


class Game(models.Model):
    """NFL Games"""
    game_id = models.CharField(max_length=20, unique=True)
    season = models.IntegerField(validators=[MinValueValidator(2025), MaxValueValidator(2025)])
    week = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(18)])
    game_type = models.CharField(max_length=10, default='REG')  # REG, WC, DIV, CONF, SB
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_games')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_games')
    game_date = models.DateTimeField()
    game_time_et = models.CharField(max_length=10, blank=True)
    week_name = models.CharField(max_length=20, blank=True)
    season_type = models.CharField(max_length=10, default='REG')
    completed = models.BooleanField(default=False)
    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        return f"Week {self.week}: {self.away_team} @ {self.home_team}"
    
    class Meta:
        ordering = ['-game_date']
        unique_together = ['season', 'week', 'home_team', 'away_team']


class PlayerStats(models.Model):
    """Weekly player statistics"""
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    season = models.IntegerField(validators=[MinValueValidator(2025), MaxValueValidator(2025)])
    week = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(18)])
    
    # Passing stats
    passing_attempts = models.IntegerField(default=0)
    passing_completions = models.IntegerField(default=0)
    passing_yards = models.IntegerField(default=0)
    passing_tds = models.IntegerField(default=0)
    passing_ints = models.IntegerField(default=0)
    passing_rating = models.FloatField(null=True, blank=True)
    
    # Rushing stats
    rushing_attempts = models.IntegerField(default=0)
    rushing_yards = models.IntegerField(default=0)
    rushing_tds = models.IntegerField(default=0)
    
    # Receiving stats
    receiving_targets = models.IntegerField(default=0)
    receiving_receptions = models.IntegerField(default=0)
    receiving_yards = models.IntegerField(default=0)
    receiving_tds = models.IntegerField(default=0)
    
    # Advanced stats
    air_yards = models.IntegerField(default=0)
    yac = models.IntegerField(default=0)  # Yards after catch
    adot = models.FloatField(null=True, blank=True)  # Average depth of target
    target_share = models.FloatField(null=True, blank=True)
    snap_share = models.FloatField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.player} - Week {self.week} {self.season}"
    
    class Meta:
        unique_together = ['player', 'game']
        ordering = ['-week', 'player']


class TeamStats(models.Model):
    """Weekly team statistics"""
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    season = models.IntegerField(validators=[MinValueValidator(2025), MaxValueValidator(2025)])
    week = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(18)])
    is_home = models.BooleanField(default=False)
    
    # Offensive stats
    total_plays = models.IntegerField(default=0)
    pass_attempts = models.IntegerField(default=0)
    rush_attempts = models.IntegerField(default=0)
    total_yards = models.IntegerField(default=0)
    passing_yards = models.IntegerField(default=0)
    rushing_yards = models.IntegerField(default=0)
    points_scored = models.IntegerField(default=0)
    
    # Defensive stats
    sacks = models.IntegerField(default=0)
    interceptions = models.IntegerField(default=0)
    fumbles_recovered = models.IntegerField(default=0)
    points_allowed = models.IntegerField(default=0)
    
    # Advanced team stats
    epa_per_play = models.FloatField(null=True, blank=True)
    success_rate = models.FloatField(null=True, blank=True)
    pace = models.FloatField(null=True, blank=True)  # Plays per game
    
    def __str__(self):
        return f"{self.team} - Week {self.week} {self.season}"
    
    class Meta:
        unique_together = ['team', 'game']
        ordering = ['-week', 'team']


class Prediction(models.Model):
    """ML Model predictions for props"""
    player = models.ForeignKey(Player, on_delete=models.CASCADE, null=True, blank=True)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    prop_type = models.CharField(max_length=20)  # passing_yards, rushing_yards, etc.
    predicted_value = models.FloatField()
    confidence_band_lower = models.FloatField()
    confidence_band_upper = models.FloatField()
    over_probability = models.FloatField()
    under_probability = models.FloatField()
    model_line = models.FloatField()
    user_line = models.FloatField(null=True, blank=True)
    edge = models.FloatField(null=True, blank=True)  # predicted - line
    rationale = models.TextField(blank=True)
    model_version = models.CharField(max_length=20, default='1.0')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.player} {self.prop_type} - {self.predicted_value}"
    
    class Meta:
        ordering = ['-created_at']


class GamePrediction(models.Model):
    """Game win probability predictions"""
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    home_win_probability = models.FloatField()
    away_win_probability = models.FloatField()
    model_version = models.CharField(max_length=20, default='1.0')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.game} - Home: {self.home_win_probability:.1%}"
    
    class Meta:
        ordering = ['-created_at']


class CachedData(models.Model):
    """Cache for nflreadpy data to avoid repeated API calls"""
    data_type = models.CharField(max_length=50)  # schedule, weekly_stats, pbp
    season = models.IntegerField()
    week = models.IntegerField(null=True, blank=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    def __str__(self):
        return f"{self.data_type} - {self.season} Week {self.week}"
    
    class Meta:
        unique_together = ['data_type', 'season', 'week']
        ordering = ['-created_at']


class PropLine(models.Model):
    """PrizePicks prop lines for current week games"""
    season = models.IntegerField(validators=[MinValueValidator(2025), MaxValueValidator(2025)])
    week = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(18)])
    game_id = models.CharField(max_length=20)
    player_id = models.CharField(max_length=20)
    player_name = models.CharField(max_length=100)
    team = models.CharField(max_length=10)
    opp = models.CharField(max_length=10)  # opponent team
    prop_type = models.CharField(max_length=30)  # passing_yards, rushing_yards, etc.
    line_value = models.FloatField()
    book = models.CharField(max_length=20, default='PrizePicks')
    board_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.player_name} {self.prop_type} {self.line_value} vs {self.opp}"
    
    class Meta:
        ordering = ['-board_time', 'player_name']
        indexes = [
            models.Index(fields=['season', 'week', 'prop_type', 'team', 'opp']),
            models.Index(fields=['game_id', 'player_id']),
        ]


class OddsEventMap(models.Model):
    """Mapping from our internal game_id -> The Odds API event id.
    Used to avoid repeated resolution on each request.
    """
    game_id = models.CharField(max_length=32, unique=True)
    odds_event_id = models.CharField(max_length=64)
    last_checked_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.game_id} → {self.odds_event_id}"

    class Meta:
        ordering = ['-last_checked_at']


class OddsEvent(models.Model):
    """Stores Odds API event data for games with player props"""
    event_id = models.CharField(max_length=64, unique=True)
    game_id = models.CharField(max_length=32)  # Our internal game ID
    home_team = models.CharField(max_length=50)
    away_team = models.CharField(max_length=50)
    commence_time = models.DateTimeField()
    last_updated = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.away_team} @ {self.home_team} ({self.event_id})"
    
    class Meta:
        ordering = ['-commence_time']


class PlayerProp(models.Model):
    """Individual player prop lines from PrizePicks"""
    event = models.ForeignKey(OddsEvent, on_delete=models.CASCADE, related_name='props')
    player_name = models.CharField(max_length=100)
    market_key = models.CharField(max_length=50)  # e.g., 'player_pass_yds'
    market_display = models.CharField(max_length=100)  # e.g., 'Pass Yards'
    
    # Over/Under lines
    over_odds = models.IntegerField(null=True, blank=True)  # American odds format
    over_point = models.FloatField(null=True, blank=True)
    under_odds = models.IntegerField(null=True, blank=True)
    under_point = models.FloatField(null=True, blank=True)
    
    # Metadata
    last_updated = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.player_name} {self.market_display} O{self.over_point}/U{self.under_point}"
    
    class Meta:
        ordering = ['market_key', 'player_name']
        unique_together = ['event', 'player_name', 'market_key']


class PropLineHistory(models.Model):
    """Tracks line changes over time for analysis"""
    prop = models.ForeignKey(PlayerProp, on_delete=models.CASCADE, related_name='line_history')
    over_odds = models.IntegerField(null=True, blank=True)
    over_point = models.FloatField(null=True, blank=True)
    under_odds = models.IntegerField(null=True, blank=True)
    under_point = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.prop.player_name} {self.timestamp.strftime('%m/%d %H:%M')}"
    
    class Meta:
        ordering = ['-timestamp']


class DataRefreshLog(models.Model):
    """Logs when we refresh data from the API"""
    event = models.ForeignKey(OddsEvent, on_delete=models.CASCADE, related_name='refresh_logs')
    markets_requested = models.TextField()  # Comma-separated list
    markets_found = models.IntegerField(default=0)
    total_lines = models.IntegerField(default=0)
    api_status = models.CharField(max_length=20)  # 'success', 'partial', 'failed'
    error_message = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.event} - {self.timestamp.strftime('%m/%d %H:%M')} ({self.api_status})"
    
    class Meta:
        ordering = ['-timestamp']


class PropProjection(models.Model):
    """ML model projections for props"""
    prop_line = models.ForeignKey(PropLine, on_delete=models.CASCADE, related_name='projections')
    season = models.IntegerField(validators=[MinValueValidator(2025), MaxValueValidator(2025)])
    week = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(18)])
    game_id = models.CharField(max_length=20)
    player_id = models.CharField(max_length=20)
    prop_type = models.CharField(max_length=30)
    
    # Projection statistics
    mean = models.FloatField()  # Expected value
    p10 = models.FloatField()   # 10th percentile
    p50 = models.FloatField()   # 50th percentile (median)
    p90 = models.FloatField()   # 90th percentile
    
    # Betting probabilities
    win_prob_over = models.FloatField()  # Probability of going over the line
    edge_pct = models.FloatField()       # Edge percentage (positive = good bet)
    
    # Model metadata
    model_version = models.CharField(max_length=20, default='v1')
    features_json = models.JSONField(default=dict)  # Features used for prediction
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.prop_line.player_name} {self.prop_type} - Mean: {self.mean:.1f}"
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['prop_line', 'model_version']