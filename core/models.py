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


class TeamDefense(models.Model):
    """Team Defensive Statistics and Rankings"""
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='defense_stats')
    season = models.IntegerField(validators=[MinValueValidator(2024), MaxValueValidator(2025)])
    week = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(18)])
    
    # Passing Defense (what the team allows)
    passing_attempts_allowed = models.FloatField(default=0)
    passing_yards_allowed = models.FloatField(default=0)
    passing_tds_allowed = models.FloatField(default=0)
    passing_interceptions_forced = models.FloatField(default=0)
    sacks_made = models.FloatField(default=0)
    passing_epa_allowed = models.FloatField(default=0)
    
    # Rushing Defense
    rushing_yards_allowed = models.FloatField(default=0)
    rushing_tds_allowed = models.FloatField(default=0)
    tackles_for_loss = models.FloatField(default=0)
    rushing_epa_allowed = models.FloatField(default=0)
    
    # Receiving Defense
    receiving_yards_allowed = models.FloatField(default=0)
    receiving_tds_allowed = models.FloatField(default=0)
    targets_allowed = models.FloatField(default=0)
    receiving_epa_allowed = models.FloatField(default=0)
    
    # Defensive Rankings (1 = best defense, 32 = worst)
    passing_defense_rank = models.IntegerField(null=True, blank=True)
    rushing_defense_rank = models.IntegerField(null=True, blank=True)
    receiving_defense_rank = models.IntegerField(null=True, blank=True)
    overall_defense_rank = models.IntegerField(null=True, blank=True)
    
    # Season-to-date averages
    avg_passing_yards_allowed = models.FloatField(default=0)
    avg_rushing_yards_allowed = models.FloatField(default=0)
    avg_receiving_yards_allowed = models.FloatField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.team.team_abbr} Defense - {self.season} Week {self.week}"
    
    class Meta:
        unique_together = ['team', 'season', 'week']
        ordering = ['season', 'week', 'team']


class TeamOffense(models.Model):
    """Team Offensive Statistics and Rankings"""
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='offense_stats')
    season = models.IntegerField(validators=[MinValueValidator(2024), MaxValueValidator(2025)])
    week = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(18)])
    
    # Passing Offense (what the team produces)
    passing_attempts = models.FloatField(default=0)
    passing_yards = models.FloatField(default=0)
    passing_tds = models.FloatField(default=0)
    passing_interceptions = models.FloatField(default=0)
    sacks_taken = models.FloatField(default=0)
    passing_epa = models.FloatField(default=0)
    
    # Rushing Offense
    rushing_yards = models.FloatField(default=0)
    rushing_tds = models.FloatField(default=0)
    rushing_epa = models.FloatField(default=0)
    
    # Receiving Offense
    receiving_yards = models.FloatField(default=0)
    receiving_tds = models.FloatField(default=0)
    targets = models.FloatField(default=0)
    receiving_epa = models.FloatField(default=0)
    
    # Offensive Rankings (1 = best offense, 32 = worst)
    passing_offense_rank = models.IntegerField(null=True, blank=True)
    rushing_offense_rank = models.IntegerField(null=True, blank=True)
    receiving_offense_rank = models.IntegerField(null=True, blank=True)
    overall_offense_rank = models.IntegerField(null=True, blank=True)
    
    # Season-to-date averages
    avg_passing_yards = models.FloatField(default=0)
    avg_rushing_yards = models.FloatField(default=0)
    avg_receiving_yards = models.FloatField(default=0)
    
    def __str__(self):
        return f"{self.team.team_abbr} Offense - {self.season} Week {self.week}"
    
    class Meta:
        ordering = ['team', 'season', 'week']
        unique_together = ['team', 'season', 'week']


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
    
    @property
    def team_name(self):
        """Return the team name for easy display"""
        if self.team:
            return self.team.team_name
        return "Unknown Team"
    
    @property
    def team_abbr(self):
        """Return the team abbreviation for easy display"""
        if self.team:
            return self.team.team_abbr
        return "UNK"
    
    def __str__(self):
        return f"{self.player_name} ({self.position}) - {self.team_abbr}"
    
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
    
    # Kickoff times for proper grading
    kickoff_utc = models.DateTimeField(null=True, blank=True, help_text="Game kickoff time in UTC")
    kickoff_et = models.DateTimeField(null=True, blank=True, help_text="Game kickoff time in Eastern")
    kickoff_local = models.DateTimeField(null=True, blank=True, help_text="Game kickoff time in local stadium time")
    
    def __str__(self):
        return f"Week {self.week}: {self.away_team} @ {self.home_team}"
    
    class Meta:
        ordering = ['-game_date']
        unique_together = ['season', 'week', 'home_team', 'away_team']


class PlayerStats(models.Model):
    """Weekly player statistics"""
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    player_name = models.CharField(max_length=100, blank=True, help_text="Player name for easy reference")
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
    
    # Next Gen Stats - Passing
    avg_time_to_throw = models.FloatField(null=True, blank=True, help_text="Average time to throw in seconds")
    avg_completed_air_yards = models.FloatField(null=True, blank=True, help_text="Average completed air yards")
    avg_intended_air_yards = models.FloatField(null=True, blank=True, help_text="Average intended air yards")
    avg_air_yards_differential = models.FloatField(null=True, blank=True, help_text="Air yards differential")
    aggressiveness = models.FloatField(null=True, blank=True, help_text="Aggressiveness percentage")
    completion_percentage_above_expectation = models.FloatField(null=True, blank=True, help_text="Completion % above expectation")
    
    # Next Gen Stats - Receiving
    avg_cushion = models.FloatField(null=True, blank=True, help_text="Average cushion at snap")
    avg_separation = models.FloatField(null=True, blank=True, help_text="Average separation at catch")
    avg_expected_yac = models.FloatField(null=True, blank=True, help_text="Average expected YAC")
    avg_yac_above_expectation = models.FloatField(null=True, blank=True, help_text="YAC above expectation")
    
    # Next Gen Stats - Rushing
    efficiency = models.FloatField(null=True, blank=True, help_text="Rushing efficiency")
    avg_time_to_los = models.FloatField(null=True, blank=True, help_text="Average time to line of scrimmage")
    expected_rush_yards = models.FloatField(null=True, blank=True, help_text="Expected rush yards")
    rush_yards_over_expected = models.FloatField(null=True, blank=True, help_text="Rush yards over expected")
    rush_yards_over_expected_per_att = models.FloatField(null=True, blank=True, help_text="Rush yards over expected per attempt")
    
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
    """Historical tracking of prop line changes - PURE SNAPSHOT LOG"""
    game_id = models.CharField(max_length=50, default='unknown')  # e.g., '2025_03_ATL_CAR'
    player_name = models.CharField(max_length=100, default='unknown')  # e.g., 'Bryce Young'
    market_key = models.CharField(max_length=50, default='unknown')  # e.g., 'player_pass_yds'
    line_value = models.FloatField(default=0.0)  # The actual line (e.g., 250.5)
    over_odds = models.IntegerField(null=True, blank=True)  # American odds
    under_odds = models.IntegerField(null=True, blank=True)  # American odds
    source = models.CharField(max_length=50, default='prizepicks')
    captured_at = models.DateTimeField(auto_now_add=True)
    
    # CLV (Closing Line Value) tracking
    is_opening_line = models.BooleanField(default=False, help_text="Is this the opening line?")
    is_closing_line = models.BooleanField(default=False, help_text="Is this the closing line?")
    is_our_capture = models.BooleanField(default=False, help_text="Is this our capture time?")
    clv_vs_opening = models.FloatField(null=True, blank=True, help_text="CLV vs opening line")
    clv_vs_closing = models.FloatField(null=True, blank=True, help_text="CLV vs closing line")
    
    class Meta:
        ordering = ['-captured_at']
        indexes = [
            models.Index(fields=['game_id', 'player_name', 'market_key']),
            models.Index(fields=['captured_at']),
        ]
    
    def __str__(self):
        return f"{self.player_name} {self.market_key} {self.line_value} @ {self.captured_at.strftime('%m/%d %H:%M')}"


class PropGrade(models.Model):
    """Graded results for prop lines - references the snapshot that was graded"""
    proplinehistory = models.ForeignKey(PropLineHistory, on_delete=models.CASCADE, related_name='grades')
    label_value = models.FloatField()  # Actual result (e.g., 275.0)
    outcome = models.CharField(max_length=10, choices=[
        ('over', 'Over'),
        ('under', 'Under'),
        ('push', 'Push'),
        ('void', 'Void')
    ])
    graded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['proplinehistory']
        ordering = ['-graded_at']
    
    def __str__(self):
        return f"{self.proplinehistory.player_name} {self.outcome} ({self.label_value} vs {self.proplinehistory.line_value})"


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


class PlayerMapping(models.Model):
    """Maps nflreadpy player names to PrizePicks player names"""
    nflreadpy_name = models.CharField(max_length=100, unique=True)  # e.g., "S.Darnold"
    prizepicks_name = models.CharField(max_length=100)  # e.g., "Sam Darnold"
    player_id = models.CharField(max_length=50, unique=True)  # e.g., "sam_darnold"
    position = models.CharField(max_length=10)  # e.g., "QB"
    current_team = models.CharField(max_length=10)  # e.g., "SEA"
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.nflreadpy_name} → {self.prizepicks_name} ({self.current_team})"
    
    class Meta:
        ordering = ['nflreadpy_name']
        indexes = [
            models.Index(fields=['nflreadpy_name']),
            models.Index(fields=['prizepicks_name']),
            models.Index(fields=['player_id']),
        ]