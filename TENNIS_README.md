# Tennis Matchup Predictor with Betting API Integration

A powerful Python tool for predicting tennis match outcomes using historical player statistics and betting API integration.

## 📊 What It Does

- **Player Stats Tracking**: Collects and analyzes tennis player match data (aces, games, sets, winners, etc.)
- **Match Outcome Predictions**: Predicts winner probability using weighted factor analysis
- **Surface-Specific Analysis**: Adjusts predictions based on court surface (Hard, Clay, Grass)
- **Betting API Integration**: Fetches live matches from multiple betting data sources
- **Multi-Factor Algorithm**: Considers win rate, serve strength, efficiency, and consistency

## 🚀 Quick Start

### 1. Installation
```bash
# Install dependencies
pip install lxml pandas requests

# Navigate to directory
cd /workspaces/NBA-Algo
```

### 2. Run Analysis
```bash
# Analyze sample matchups
python tennis_stats_predictor.py

# See usage examples
python tennis_examples.py
```

### 3. Use in Your Code
```python
from tennis_stats_predictor import predict_matchup, predict_player_stats

# Get player stats
sinner_stats = predict_player_stats("Sinner", surface="Hard")
print(f"Sinner avg aces: {sinner_stats['overall']['avg_aces']}")

# Predict a match
prediction = predict_matchup("Sinner", "Alcaraz", surface="Hard")
print(f"Sinner win probability: {prediction['prediction']['win_probability_p1']:.1%}")
```

## 📈 Example Output

```
Sinner vs Alcaraz (Hard Court)

Sinner:
  Avg Aces: 12.9 per match
  Avg Games: 19.8 per match
  Avg Sets: 2.4 per match
  Win Rate: 80.0%

Alcaraz:
  Avg Aces: 9.5 per match
  Avg Games: 19.9 per match
  Avg Sets: 2.3 per match
  Win Rate: 72.0%

📊 PREDICTION:
  Favorite: Sinner (51.2% confidence)
  Sinner wins: 51.2%
  Alcaraz wins: 48.8%
```

## 🔌 Betting API Integration

### Available Data Sources

**1. Sports Game Odds (SGO) API** - Free Tier
- 50 requests/month
- Real-time match data with odds
- [Sign up here](https://sportsgameodds.com)

```bash
export SGO_API_KEY="your_key_here"
python tennis_stats_predictor.py  # Will use SGO data
```

**2. RapidAPI Tennis API** - Free/Paid Tier
- 100 requests/month (free)
- Professional sports data
- [Sign up here](https://rapidapi.com/api-sports/api/api-tennis)

```bash
export RAPIDAPI_KEY="your_key_here"
python tennis_stats_predictor.py
```

### Use in Code
```python
from tennis_stats_predictor import get_live_matches, predict_matchup

# Get today's matches from betting API
matches = get_live_matches(source="sgo")  # or "rapidapi"

# Predict each match
for player1, player2 in matches:
    prediction = predict_matchup(player1, player2, surface="Hard")
    print(f"{player1} vs {player2}: {prediction['prediction']['favorite']} favored")
```

## 📁 File Structure

```
/workspaces/NBA-Algo/
├── tennis_stats_predictor.py      # Main predictor module
├── tennis_examples.py              # Usage examples
├── TENNIS_PREDICTOR_SETUP.md       # Detailed setup guide
├── tennis_cache/
│   └── players/
│       ├── Sinner.json            # 25 recent matches (cached)
│       ├── Alcaraz.json
│       ├── Djokovic.json
│       └── Medvedev.json
└── README.md (this file)
```

## 🧮 Prediction Algorithm

Weighted probability calculation:

1. **Historical Win Rate** (40% weight)
   - Past 25 matches win/loss ratio

2. **Serve Advantage** (25% weight)
   - Average aces per match
   - Indicator of serve strength

3. **Playing Efficiency** (20% weight)
   - Winners per game ratio
   - Offensive shot making ability

4. **Consistency** (15% weight)
   - Double fault penalty
   - Serve reliability metric

**Example:**
```
Sinner: 12.9 aces, 80% win rate, 41.1 winners/match
Alcaraz: 9.5 aces, 72% win rate, 38.8 winners/match

Result: Sinner 51.2% | Alcaraz 48.8%
```

## 🎯 Use Cases

### 1. Find Betting Value
```python
# If model says Alcaraz 55% but odds are -110 (52.4% implied):
# That's 2.6% edge - potential value pick

from tennis_stats_predictor import predict_matchup
pred = predict_matchup("Alcaraz", "Opponent", surface="Hard")
model_prob = pred['prediction']['win_probability_p1']
```

### 2. Tournament Analysis
```python
# Analyze all day's matches
matches = get_live_matches(source="sample")
for p1, p2 in matches:
    pred = predict_matchup(p1, p2)
    print(f"{p1} vs {p2}: {pred['prediction']['favorite']} favorite")
```

### 3. Player Comparison
```python
# Compare players across surfaces
from tennis_stats_predictor import predict_player_stats

for surface in ["Hard", "Clay", "Grass"]:
    stats = predict_player_stats("Sinner", surface=surface)
    print(f"On {surface}: {stats['overall']['win_rate']:.1%}")
```

## 📊 Sample Data Included

Pre-loaded data for:
- **Jannik Sinner**: Aggressive baseline player, strong on hard courts
- **Carlos Alcaraz**: Young all-arounder, good on clay
- **Novak Djokovic**: Defensive specialist, returns expert
- **Daniil Medvedev**: Consistent server, good on hard courts

Each player has 25 recent match records with full stats.

## 🔧 Customization

### Change Prediction Weights
Edit `calculate_win_probability()`:
```python
weights = {
    "win_rate": 0.40,        # Increase for form-focused predictions
    "aces": 0.25,            # Increase for serve-heavy analysis
    "efficiency": 0.20,      # Increase for shot-making focus
    "consistency": 0.15      # Increase for reliability emphasis
}
```

### Add New Players
```python
from tennis_stats_predictor import MatchStats, SAMPLE_PLAYER_DATA

SAMPLE_PLAYER_DATA["YourPlayer"] = [
    MatchStats(date="2026-01-26", opponent="...", surface="Hard", result="W", 
               games_won=12, games_lost=10, sets_won=2, sets_lost=1, 
               aces=15, double_faults=3, winners=45, 
               tiebreaks_won=1, tiebreaks_lost=0),
    # ... more matches
]
```

## ⚙️ System Requirements

- Python 3.7+
- `pandas` - Data manipulation
- `requests` - API calls
- `lxml` - HTML parsing
- Internet connection (for betting APIs)

## 🛠️ Troubleshooting

### "No module named 'lxml'"
```bash
pip install lxml
```

### API Key Not Working
```bash
# Verify key is set
echo $SGO_API_KEY

# Or pass directly in code
os.environ["SGO_API_KEY"] = "your_key"
```

### No Matches Found
- Check betting API status
- Verify API key permissions
- Use `source="sample"` fallback

## 📚 Documentation

- `TENNIS_PREDICTOR_SETUP.md` - Detailed setup and configuration
- `tennis_examples.py` - 8 usage examples with code
- Comments in `tennis_stats_predictor.py` - Inline documentation

## 🤝 Integration Points

**Ready to integrate with:**
- DraftKings API
- FanDuel API
- BET365 API
- Pinnacle Sports API
- Your own betting system

## 💡 Tips for Better Predictions

1. **Use Surface-Specific Data**: Clay vs Hard court playing styles differ
2. **Check Recent Form**: Last 5 vs Last 25 matches shows trends
3. **Monitor Injuries**: Add injury tracking for accuracy
4. **Compare to Odds**: Look for probability mismatches
5. **Sample Multiple Data**: Different APIs may have different info

## 📝 License

For personal/educational use. Follow all terms of:
- Betting platforms
- Data source APIs
- Local gambling regulations

## 🐛 Known Limitations

- Web scraping from Tennis Abstract unreliable (uses cached/sample data)
- Free tier APIs have request limits
- Some surface-specific data limited for clay courts
- Historical data only goes back 25 matches

## 🚀 Future Features

- [ ] Real-time odds comparison
- [ ] Player form indicators
- [ ] Head-to-head history
- [ ] Injury tracking integration
- [ ] Backtest framework
- [ ] Bankroll management
- [ ] Multiple prediction models ensemble

## 📧 Support

For issues:
1. Check `TENNIS_PREDICTOR_SETUP.md`
2. Review `tennis_examples.py` for usage
3. Check betting API documentation
4. Verify API keys and rate limits

---

**Built for winning predictions!** 🎾
