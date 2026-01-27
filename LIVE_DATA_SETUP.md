# Tennis Predictor - Live Data Integration Guide

## Overview

The tennis predictor system includes built-in support for fetching **real-time match data** from APIs. By default, it uses sample data for development, but you can easily switch to live data.

## Currently Available Options

### Option 1: RapidAPI Tennis Endpoint (Recommended)

**Pros:**
- Free tier: 100 requests/month
- Comprehensive match data
- Easy setup

**Setup Steps:**

1. **Sign up** at https://rapidapi.com/api-sports/api/api-tennis
2. **Copy your API key** from the dashboard
3. **Set environment variable:**
   ```bash
   export RAPIDAPI_KEY="your-api-key-here"
   ```

4. **Test it:**
   ```python
   from tennis_stats_predictor import get_todays_matches
   matches = get_todays_matches()
   ```

**Example .bashrc / .zshrc:**
```bash
# Add to your shell config file
export RAPIDAPI_KEY="xxxxxxxxxxxxxxxxxxxxxx"
```

**Example Docker setup:**
```dockerfile
ENV RAPIDAPI_KEY=your-api-key
```

### Option 2: Sports Game Odds (SGO)

**Pros:**
- Free tier: 50 requests/month
- Good for betting-related data
- Simple integration

**Setup Steps:**

1. **Sign up** at https://sgo.click/
2. **Get your API key** from dashboard
3. **Set environment variable:**
   ```bash
   export SGO_API_KEY="your-api-key-here"
   ```

4. **The system will automatically use it:**
   ```python
   from tennis_stats_predictor import get_todays_matches
   matches = get_todays_matches()
   ```

### Option 3: ESPN (Web Scraping)

**Current Status:** Limited - ESPN uses JavaScript rendering which makes scraping difficult

**Fallback Behavior:** The system attempts ESPN scraping but gracefully falls back to sample data if unsuccessful.

## Integration Priority

When you run the code, it tries data sources in this order:

```
1. RapidAPI Tennis (if RAPIDAPI_KEY is set)
   ↓ (if fails)
2. Sports Game Odds (if SGO_API_KEY is set)
   ↓ (if fails)
3. ESPN Web Scraping (always attempted)
   ↓ (if fails)
4. Sample Data (fallback - always works)
```

## Complete Example with Live Data

```python
import os
from tennis_stats_predictor import get_todays_matches, predict_matchup

# Make sure you've set RAPIDAPI_KEY environment variable
# export RAPIDAPI_KEY="your-key"

def analyze_todays_matches():
    print("Fetching today's tennis matches...")
    matches = get_todays_matches()
    
    print(f"\nFound {len(matches)} matches:")
    for i, (p1, p2) in enumerate(matches, 1):
        print(f"\n{i}. {p1} vs {p2}")
        
        # Get prediction
        prediction = predict_matchup(p1, p2)
        if prediction:
            pred = prediction.get('prediction', {})
            favorite = pred.get('favorite', 'Unknown')
            confidence = pred.get('confidence', 0)
            
            print(f"   Predicted winner: {favorite}")
            print(f"   Confidence: {confidence:.0f}%")

if __name__ == "__main__":
    analyze_todays_matches()
```

## Troubleshooting

### Issue: Getting sample data instead of live data

**Solution:** Check that your API key is properly set:
```bash
# Verify key is in environment
echo $RAPIDAPI_KEY

# If empty, set it:
export RAPIDAPI_KEY="your-actual-key"

# Check it's working
python -c "import os; print(os.environ.get('RAPIDAPI_KEY'))"
```

### Issue: API returns "401 Unauthorized"

**Solution:** Your API key is invalid or expired
1. Log into your RapidAPI account
2. Copy the key again (it may have changed)
3. Update your environment variable

### Issue: Hitting rate limits

**Solution:** Use multiple APIs or increase wait time between requests:
```python
import time

matches = get_todays_matches()
# Wait before next call
time.sleep(2)
```

## API Response Handling

The system automatically handles different API response formats and extracts:
- Player 1 name
- Player 2 name
- Match status (upcoming/live/finished)
- Surface type (if available)
- Tournament info (if available)

## Advanced: Custom Data Source

To add your own data source, modify `get_todays_matches()`:

```python
def get_todays_matches() -> List[Tuple[str, str]]:
    # ... existing code ...
    
    # Add your custom source
    try:
        matches = my_custom_tennis_api()
        if matches:
            print(f"[INFO] Found {len(matches)} matches from custom API")
            return matches
    except Exception as e:
        print(f"[DEBUG] Custom API failed: {e}")
    
    # ... rest of fallback code ...
```

## Free vs Paid Tiers

| Provider | Free Tier | Rate Limit | Cost |
|----------|-----------|-----------|------|
| RapidAPI Tennis | 100/month | 30 req/second | $0-$50/month |
| Sports Game Odds | 50/month | 10 req/second | $0-$30/month |
| ESPN | Limited | Site-dependent | $0 (scraped) |

## Recommended Setup for Production

1. **Use RapidAPI** as primary (best data quality)
2. **Set up caching** to avoid duplicate requests
3. **Add error handling** for API outages
4. **Monitor rate limits** in logs

```python
from tennis_stats_predictor import get_todays_matches

# First call (uses API if available)
matches = get_todays_matches()

# Cache results locally
import json
with open('today_matches.json', 'w') as f:
    json.dump(matches, f)

# Subsequent calls can use cache
```

## FAQ

**Q: Can I use multiple API keys?**
A: Yes, the system automatically tries them in order. Set both `RAPIDAPI_KEY` and `SGO_API_KEY` for redundancy.

**Q: How do I know which source was used?**
A: Check the debug output - it shows `[INFO] Found X matches from <source>`

**Q: Do I need to pay for live data?**
A: No! Free tiers have enough quota for development/testing (50-100 requests/month).

**Q: Can this work offline?**
A: Yes, it gracefully falls back to sample data. Useful for training/testing.

## Next Steps

1. Choose an API provider above
2. Sign up and get your API key
3. Set the environment variable
4. Run your predictions with live data!

```bash
export RAPIDAPI_KEY="your-key"
python tennis_stats_predictor.py
```
