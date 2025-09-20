# 🏈 SecretBox NFL Prop Prediction System

A comprehensive NFL player prop prediction system using machine learning, Next Gen Stats, and real-time data from `nflreadpy`.

## 🚀 Quick Start - Weekly Update Commands

### **Step 1: Update Player Stats (Run Every Tuesday)**
```bash
# Update player stats for current season (2025)
python3 manage.py populate_player_stats --seasons 2025

# This command will:
# - Fetch latest player stats from nflreadpy
# - Include Next Gen Stats (passing, receiving, rushing intelligence)
# - Update PlayerStats table with new data
# - Handle player name mapping automatically
```

### **Step 2: Update Team Defense Stats (Run Every Tuesday)**
```bash
# Update team defensive rankings and stats
python3 manage.py populate_team_defense --seasons 2025

# This command will:
# - Fetch latest team defensive stats
# - Calculate defensive rankings (passing, rushing, receiving)
# - Update TeamDefense table for opponent analysis
```

### **Step 3: Update Team Offense Stats (Run Every Tuesday)**
```bash
# Update team offensive rankings and stats
python3 manage.py populate_team_offense --seasons 2025

# This command will:
# - Fetch latest team offensive stats
# - Calculate offensive rankings and EPA
# - Update TeamOffense table for team strength analysis
```

### **Step 4: Refresh Prop Lines (Run Every Wednesday)**
```bash
# Get latest prop lines from PrizePicks API
python3 manage.py refresh_player_props

# This command will:
# - Fetch current week's prop lines
# - Update PlayerProp table with new odds
# - Handle new players and markets automatically
```

### **Step 5: Generate Predictions (Run Every Wednesday)**
```bash
# Generate ML predictions for all active props
python3 manage.py generate_predictions

# This command will:
# - Train models on latest 2025 data
# - Use all 75 features including Next Gen Stats
# - Generate over/under probabilities
# - Create Prediction records for web interface
```

## 📊 Complete Weekly Workflow

### **Tuesday (Data Update Day)**
```bash
# 1. Update all player performance data
python3 manage.py populate_player_stats --seasons 2025

# 2. Update team defensive strength
python3 manage.py populate_team_defense --seasons 2025

# 3. Update team offensive strength  
python3 manage.py populate_team_offense --seasons 2025

# 4. Check data quality
python3 manage.py shell -c "
from core.models import PlayerStats, TeamDefense, TeamOffense
print(f'PlayerStats: {PlayerStats.objects.filter(season=2025).count()}')
print(f'TeamDefense: {TeamDefense.objects.filter(season=2025).count()}')
print(f'TeamOffense: {TeamOffense.objects.filter(season=2025).count()}')
"
```

### **Wednesday (Prediction Day)**
```bash
# 1. Get latest prop lines
python3 manage.py refresh_player_props

# 2. Generate predictions
python3 manage.py generate_predictions

# 3. Check prediction quality
python3 manage.py shell -c "
from core.models import Prediction
recent = Prediction.objects.order_by('-created_at')[:5]
for p in recent:
    print(f'{p.player} - {p.prop_type}: {p.over_probability:.1f}% | {p.under_probability:.1f}%')
"
```

## 🔧 Model Features (75 Total)

### **1. Basic Player Stats (11 features)**
- Passing: attempts, completions, yards, TDs
- Rushing: attempts, yards, TDs
- Receiving: targets, receptions, yards, TDs

### **2. Rolling Averages (11 features)**
- 3-game averages for all basic stats
- Advanced metrics: air yards, YAC, target share

### **3. Season Averages (11 features)**
- Season-long performance trends
- Cumulative stats and averages

### **4. Game Context (7 features)**
- Week number, season, early/late season flags
- Season totals and timing factors

### **5. Opponent Defense (10 features)**
- Defensive rankings (passing, rushing, receiving)
- Yards allowed per game
- Prop-specific defensive adjustments

### **6. Team Offense (10 features)**
- Team offensive production and rankings
- EPA (Expected Points Added)
- Offensive efficiency metrics

### **7. Next Gen Stats (15 features)**
- **Passing Intelligence**: Time to throw, completion % above expectation, aggressiveness
- **Receiving Intelligence**: Separation at catch, YAC above expectation, cushion
- **Rushing Intelligence**: Efficiency, yards over expected, time to line of scrimmage

## 🛠️ Maintenance Commands

### **Fix Player Mappings**
```bash
# Fix player name inconsistencies between nflreadpy and PrizePicks
python3 manage.py fix_all_player_mappings

# Fix specific player team assignments
python3 manage.py fix_all_player_teams

# Add missing players manually
python3 manage.py add_missing_players
```

### **Data Quality Checks**
```bash
# Check for players with missing team assignments
python3 manage.py shell -c "
from core.models import Player
unknown = Player.objects.filter(team__team_abbr='Unknown')
print(f'Players with unknown teams: {unknown.count()}')
for p in unknown[:10]:
    print(f'  {p.player_name} - {p.position}')
"

# Check prediction quality
python3 manage.py shell -c "
from core.models import Prediction
total = Prediction.objects.count()
high_conf = Prediction.objects.filter(over_probability__gt=70).count()
print(f'Total predictions: {total}')
print(f'High confidence over (>70%): {high_conf}')
"
```

### **Database Management**
```bash
# Run migrations if needed
python3 manage.py migrate

# Create superuser (first time only)
python3 manage.py createsuperuser

# Start development server
python3 manage.py runserver
```

## 📈 Understanding Predictions

### **Probability Interpretation**
- **>70% Over**: Strong confidence in over hitting
- **60-70% Over**: Good confidence in over
- **50-60% Over**: Slight lean to over
- **40-50% Under**: Slight lean to under
- **30-40% Under**: Good confidence in under
- **<30% Under**: Strong confidence in under hitting

### **Edge Calculation**
- **Positive Edge**: Model predicts higher than line (favor over)
- **Negative Edge**: Model predicts lower than line (favor under)
- **Edge > 5**: Strong value play
- **Edge > 2**: Good value play

## 🚨 Troubleshooting

### **Common Issues**

1. **"No 2025 PlayerStats found"**
   ```bash
   python3 manage.py populate_player_stats --seasons 2025
   ```

2. **"Player not found" errors**
   ```bash
   python3 manage.py fix_all_player_mappings
   ```

3. **"Game not found" errors**
   ```bash
   python3 manage.py populate_games --seasons 2025
   ```

4. **Low prediction quality**
   ```bash
   # Check if Next Gen Stats are populated
   python3 manage.py shell -c "
   from core.models import PlayerStats
   ngs = PlayerStats.objects.filter(season=2025, avg_time_to_throw__isnull=False).count()
   print(f'Records with Next Gen Stats: {ngs}')
   "
   ```

### **Data Validation**
```bash
# Check all data sources
python3 manage.py shell -c "
from core.models import *
print('=== DATA SUMMARY ===')
print(f'Players: {Player.objects.count()}')
print(f'Teams: {Team.objects.count()}')
print(f'Games: {Game.objects.count()}')
print(f'PlayerStats (2025): {PlayerStats.objects.filter(season=2025).count()}')
print(f'TeamDefense (2025): {TeamDefense.objects.filter(season=2025).count()}')
print(f'TeamOffense (2025): {TeamOffense.objects.filter(season=2025).count()}')
print(f'PlayerProps: {PlayerProp.objects.filter(is_active=True).count()}')
print(f'Predictions: {Prediction.objects.count()}')
"
```

## 📝 Notes

- **Data Sources**: All data comes from `nflreadpy` (official NFL data)
- **Model Type**: Simple statistical model optimized for limited data
- **Update Frequency**: Weekly (Tuesday for data, Wednesday for predictions)
- **Season Focus**: Currently optimized for 2025 season only
- **Next Gen Stats**: Integrated for advanced player intelligence

## 🎯 Success Metrics

- **Prediction Accuracy**: Track over/under hit rates
- **Edge Performance**: Monitor value play success
- **Data Quality**: Ensure all players have correct team assignments
- **Model Confidence**: Aim for reasonable probability distributions (not all 100%)

---

**Last Updated**: Week 3, 2025 Season
**Model Version**: 4.0_simple with Next Gen Stats
**Total Features**: 75 (including 15 Next Gen Stats)