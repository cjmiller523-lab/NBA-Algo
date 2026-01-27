# Tennis Predictor - Quick Reference Card

## One-Liner Test
```bash
python -c "from tennis_stats_predictor import get_todays_matches; print(get_todays_matches())"
```

## Enable Live Data (Pick One)

### Option A: RapidAPI (Recommended)
```bash
export RAPIDAPI_KEY="your-api-key-from-rapidapi.com"
python tennis_stats_predictor.py
```

### Option B: Sports Game Odds
```bash
export SGO_API_KEY="your-api-key-from-sgo.click"
python tennis_stats_predictor.py
```

## Common Functions

```python
from tennis_stats_predictor import (
    get_todays_matches,          # Get today's matches
    predict_matchup,              # Predict match outcome
    predict_player_stats,         # Get player statistics
    get_sample_matches            # Get sample data (no API needed)
)

# Get matches
matches = get_todays_matches()

# Predict
pred = predict_matchup("Djokovic", "Musetti")
print(pred['prediction']['favorite'])  # Winner
print(pred['prediction']['confidence'])  # Confidence %

# Stats
stats = predict_player_stats("Sinner")
print(stats['overall']['win_rate'])  # Player win rate
```

## Data Flow Priority

```
RapidAPI (if RAPIDAPI_KEY set)
    ↓ fails
SGO API (if SGO_API_KEY set)
    ↓ fails
ESPN Scraper
    ↓ fails
Sample Data (always works)
```

## File Locations

| File | Purpose |
|------|---------|
| `tennis_stats_predictor.py` | Main module (import from here) |
| `tennis_examples.py` | 8 working usage examples |
| `LIVE_DATA_SETUP.md` | Detailed API setup guide |
| `LIVE_DATA_INTEGRATION.md` | Integration overview |
| `TENNIS_README.md` | Feature documentation |

## Set API Keys (Persistent)

### macOS/Linux (add to ~/.bashrc or ~/.zshrc)
```bash
echo 'export RAPIDAPI_KEY="your-key"' >> ~/.bashrc
source ~/.bashrc
```

### Docker
```dockerfile
ENV RAPIDAPI_KEY=your-key
```

### Python Script
```python
import os
os.environ['RAPIDAPI_KEY'] = 'your-key'
```

## Get Free API Keys

| Provider | Link | Free Tier |
|----------|------|-----------|
| RapidAPI Tennis | https://rapidapi.com/api-sports/api/api-tennis | 100/month |
| Sports Game Odds | https://sgo.click/ | 50/month |

## Response Format

```python
prediction = {
    'matchup': 'Sinner vs Alcaraz',
    'prediction': {
        'favorite': 'Sinner',              # Predicted winner
        'win_probability_p1': 0.512,       # 51.2%
        'win_probability_p2': 0.488,       # 48.8%
        'confidence': 51.2                 # Confidence %
    },
    'player1_stats': {
        'win_rate': 0.80,
        'avg_aces': 12.9,
        'avg_games': 19.8,
        'avg_sets': 2.4
    },
    'player2_stats': {
        'win_rate': 0.72,
        'avg_aces': 9.5,
        'avg_games': 19.9,
        'avg_sets': 2.3
    }
}
```

## Troubleshooting Checklist

- [ ] Is Python 3.6+ installed?
- [ ] Are required packages installed? (`pip install requests pandas lxml`)
- [ ] Is API key set? (`echo $RAPIDAPI_KEY`)
- [ ] Is API key valid? (Check RapidAPI dashboard)
- [ ] Is internet connection working?

## Performance Tips

1. **First run is slow** (loads data) - subsequent runs use cache
2. **Set RAPIDAPI_KEY** for faster API instead of web scraping
3. **Reuse data** - don't call `predict_matchup()` repeatedly for same players
4. **Cache locally** - save results to avoid re-fetching

```python
import json
from tennis_stats_predictor import get_todays_matches

# Fetch once
matches = get_todays_matches()

# Save
with open('matches.json', 'w') as f:
    json.dump(matches, f)

# Reuse
with open('matches.json', 'r') as f:
    matches = json.load(f)
```

## Examples

### Batch Analysis
```python
from tennis_stats_predictor import get_todays_matches, predict_matchup

for p1, p2 in get_todays_matches():
    pred = predict_matchup(p1, p2)
    print(f"{p1:15} vs {p2:15} → {pred['prediction']['favorite']} ({pred['prediction']['confidence']}%)")
```

### Find Upsets (Underdog wins)
```python
from tennis_stats_predictor import predict_matchup

matches = [("Sinner", "Alcaraz"), ("Djokovic", "Medvedev")]
for p1, p2 in matches:
    pred = predict_matchup(p1, p2)
    prob_p2 = pred['prediction']['win_probability_p2']
    if 0.3 < prob_p2 < 0.5:  # Moderate underdog
        print(f"Potential upset: {p2} at {prob_p2:.0%} odds")
```

### Surface Analysis
```python
from tennis_stats_predictor import predict_matchup

surfaces = ["Hard", "Clay", "Grass"]
for surface in surfaces:
    pred = predict_matchup("Djokovic", "Sinner", surface)
    print(f"{surface}: Djokovic wins {pred['prediction']['win_probability_p1']:.0%}")
```

## System Requirements

- Python 3.6+
- Internet connection (for live data)
- 100MB disk space (for cache)
- 50MB RAM minimum

## Common Errors & Fixes

**Error: `ModuleNotFoundError: No module named 'requests'`**
```bash
pip install requests pandas lxml beautifulsoup4
```

**Error: `401 Unauthorized`**
→ Your API key is invalid. Get new one from RapidAPI dashboard

**Error: `ConnectionError`**
→ No internet connection or API server is down. Sample data will be used automatically.

**Error: Empty matches returned**
→ All data sources failed. System fell back to sample data (this is OK for testing).

## Shortcuts & Aliases (Bash)

```bash
# Quick test
alias tennis="python -c 'from tennis_stats_predictor import get_todays_matches; print(get_todays_matches())'"

# With live data
alias tennis-live="RAPIDAPI_KEY=your-key python -c 'from tennis_stats_predictor import get_todays_matches; print(get_todays_matches())'"

# Full analysis
alias tennis-predict="python -c 'from tennis_examples import example_live_matches; example_live_matches()'"
```

## Documentation Links

- **Detailed Setup:** [LIVE_DATA_SETUP.md](LIVE_DATA_SETUP.md)
- **Integration Guide:** [LIVE_DATA_INTEGRATION.md](LIVE_DATA_INTEGRATION.md)
- **Algorithm Details:** [TENNIS_PREDICTOR_SETUP.md](TENNIS_PREDICTOR_SETUP.md)
- **Feature Overview:** [TENNIS_README.md](TENNIS_README.md)
- **Usage Examples:** [tennis_examples.py](tennis_examples.py)

---

**Last Updated:** 2024
**Python:** 3.6+
**Status:** ✅ Production Ready
