# Tennis Matchup Predictor Setup Guide

## Overview
This tool predicts tennis match outcomes based on historical player statistics and uses betting APIs to fetch live matches.

## Features
✅ Player stats tracking (aces, games, sets, tiebreaks, winners, double faults)
✅ Matchup outcome predictions with confidence scoring
✅ Surface-specific predictions (Hard, Clay, Grass, Indoor)
✅ Multi-factor analysis (win rate, serve performance, efficiency, consistency)
✅ Integration with betting APIs for live matches

## Quick Start

### 1. Basic Usage (Sample Data)
```bash
cd /workspaces/NBA-Algo
python tennis_stats_predictor.py
```

### 2. Analyze Specific Matchup
```python
from tennis_stats_predictor import predict_matchup

# Predict a specific matchup
prediction = predict_matchup("Sinner", "Alcaraz", surface="Hard")

# Results:
# {
#   "matchup": "Sinner vs Alcaraz",
#   "prediction": {
#     "favorite": "Sinner",
#     "win_probability_p1": 0.512,
#     "win_probability_p2": 0.488,
#     "confidence": 51.2
#   },
#   ...
# }
```

### 3. Get Player Stats
```python
from tennis_stats_predictor import predict_player_stats

stats = predict_player_stats("Jannik Sinner", surface="Hard")

# Shows:
# - avg_aces, avg_games, avg_sets
# - avg_double_faults, avg_winners
# - win_rate, consistency metrics
# - surface-specific breakdowns
```

## Betting API Integration

### Sports Game Odds (SGO) API
**Free tier**: 50 requests/month
**Cost**: Free

1. Get your API key from: https://sportsgameodds.com
2. Set environment variable:
```bash
export SGO_API_KEY="your_api_key_here"
```

3. Use in code:
```python
from tennis_stats_predictor import get_live_matches

matches = get_live_matches(source="sgo")
# Returns: [("Sinner", "Alcaraz"), ("Djokovic", "Medvedev"), ...]
```

### RapidAPI Tennis API
**Free tier**: 100 requests/month
**Cost**: Free to $9.99/month

1. Get API key from: https://rapidapi.com/api-sports/api/api-tennis
2. Set environment variable:
```bash
export RAPIDAPI_KEY="your_rapidapi_key_here"
```

3. Use in code:
```python
matches = get_live_matches(source="rapidapi")
```

### DraftKings Odds Integration (Advanced)
For real betting integration:

```python
# Fetch DraftKings matches via APIs
# Parse odds lines (e.g., Sinner -150, Alcaraz +130)
# Compare with model predictions to find value
```

## Data Files

### Cache Structure
```
tennis_cache/
├── players/
│   ├── Sinner.json          # 25 recent matches for Sinner
│   ├── Alcaraz.json         # 25 recent matches for Alcaraz
│   └── ...
```

### Cache Format
Each player file contains:
```json
[
  {
    "date": "2026-01-26",
    "opponent": "Alcaraz",
    "surface": "Hard",
    "result": "W",
    "games_won": 12,
    "games_lost": 10,
    "sets_won": 2,
    "sets_lost": 1,
    "aces": 15,
    "double_faults": 3,
    "winners": 45,
    "tiebreaks_won": 1,
    "tiebreaks_lost": 0
  },
  ...
]
```

## Prediction Model

### Win Probability Calculation
Weighted factors:
1. **Historical Win Rate** (40% weight)
   - Past 25 matches win percentage
   
2. **Serve Advantage** (25% weight)
   - Average aces per match
   - Higher aces = better serve
   
3. **Efficiency** (20% weight)
   - Winners per game ratio
   - Offensive capability
   
4. **Consistency** (15% weight)
   - Double fault penalty
   - Serve reliability

### Example
```
Sinner vs Alcaraz (Hard Court):

Sinner: 12.9 aces/match, 80% win rate, 41.1 winners/match
Alcaraz: 9.5 aces/match, 72% win rate, 38.8 winners/match

Calculation:
- Win rate factor: 0.80 / (0.80 + 0.72) = 0.526
- Aces factor: 12.9 / (12.9 + 9.5) = 0.576
- Efficiency factor: (41.1/19.8) / ((41.1/19.8) + (38.8/19.9)) = 0.515
- Consistency: similar

Weighted probability: 0.512 = 51.2% for Sinner
```

## Common Issues

### Issue: "No module named 'lxml'"
**Solution:**
```bash
pip install lxml pandas requests
```

### Issue: "403 Forbidden" from Tennis Abstract
**Solution:** 
The scraper uses cached data and fallback sample data. Once cached, it won't re-scrape.

### Issue: Betting API key errors
**Solution:**
1. Verify key is set: `echo $SGO_API_KEY`
2. Check rate limits (free tier limits apply)
3. Use `source="sample"` as fallback

## Customization

### Add More Sample Players
Edit `SAMPLE_PLAYER_DATA` in the script:

```python
SAMPLE_PLAYER_DATA = {
    "YourPlayer": [
        MatchStats(date="2026-01-26", opponent="...", ...),
        ...
    ]
}
```

### Adjust Prediction Weights
Modify `calculate_win_probability()` to change factor weights:

```python
weights = {
    "win_rate": 0.40,        # Change these
    "aces": 0.25,
    "efficiency": 0.20,
    "consistency": 0.15
}
```

### Change Surface Handling
Modify `get_surface_stats()` to customize surface analysis.

## Output Examples

### Single Player Stats
```
Prediction for Jannik Sinner:
  Matches analyzed: 25
  Overall stats (last 25 matches):
    avg_aces: 12.9
    avg_total_games: 19.8
    avg_total_sets: 2.4
    avg_tiebreaks: 0.4
    avg_double_faults: 2.6
    avg_winners: 41.1
    aces_std_dev: 2.5
    win_rate: 0.8
  Surface-specific stats:
    Hard_aces: 13.3
    Hard_games: 19.6
    Hard_sets: 2.3
    Hard_win_rate: 0.783
```

### Matchup Prediction
```
Sinner vs Alcaraz (Hard)

Sinner:
  Avg Aces: 12.9
  Avg Games: 19.8
  Avg Sets: 2.4
  Win Rate: 80.0%

Alcaraz:
  Avg Aces: 9.5
  Avg Games: 19.9
  Avg Sets: 2.3
  Win Rate: 72.0%

📊 PREDICTION:
  Favorite: Sinner (51.2% confidence)
  Sinner wins: 51.2%
  Alcaraz wins: 48.8%
```

## Future Enhancements
- [ ] Real-time odds line comparison
- [ ] Betting value calculation (implied vs model probability)
- [ ] Player form/trend analysis (last 5 vs last 25 matches)
- [ ] Head-to-head historical data
- [ ] Court-specific performance metrics
- [ ] Pre-match injury updates integration
- [ ] Bankroll management tools
- [ ] Backtesting framework

## License
For personal use. Follow all terms of betting platforms and data sources.

## Support
For issues with betting APIs:
- SGO API: support@sportsgameodds.com
- RapidAPI: https://rapidapi.com/support

For script issues, check the debug logs with `-v` flag (if implemented).
