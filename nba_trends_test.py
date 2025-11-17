"""
NBA Trends Script (Test Version)
--------------------------------
This version pulls today's NBA games and calculates recent player stat trends.
No email sending or sportsbook odds yet — just console output for testing.
"""

import time
from datetime import datetime
import pandas as pd
from nba_api.stats.endpoints import scoreboardv2, playergamelog
from nba_api.stats.static import players, teams


# -----------------------------
# CONFIG
# -----------------------------
CONFIG = {
    "SEASON": "2024-25",          # Change each year if needed
    "NUM_GAMES_LOOKBACK": 10,     # How many games to check
    "API_SLEEP": 0.6              # Delay between API calls to avoid rate limiting
}


# -----------------------------
# UTILITY FUNCTIONS
# -----------------------------
def get_todays_games():
    """Get today's NBA games with team abbreviations (using team IDs)."""
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        scoreboard = scoreboardv2.ScoreboardV2(game_date=today)
        games = scoreboard.game_header.get_data_frame()

        # Build lookup: team_id -> team_abbrev
        team_lookup = {t["id"]: t["abbreviation"] for t in teams.get_teams()}

        matchups = []
        for _, row in games.iterrows():
            home_id = row["HOME_TEAM_ID"]
            away_id = row["VISITOR_TEAM_ID"]
            home_abbrev = team_lookup.get(home_id, "UNK")
            away_abbrev = team_lookup.get(away_id, "UNK")
            matchups.append({
                "game_id": row["GAME_ID"],
                "home_team": home_abbrev,
                "away_team": away_abbrev
            })

        return matchups

    except Exception as e:
        print("Error fetching scoreboard:", e)
        return []


    except Exception as e:
        print("Error fetching scoreboard:", e)
        return []


def get_team_players(team_abbrev):
    """Return all active players for a given team abbreviation."""
    all_teams = teams.get_teams()
    team = next((t for t in all_teams if t["abbreviation"] == team_abbrev), None)
    if not team:
        return []
    all_players = players.get_players()
    # Not all players are tagged with team_id, so we'll just return all for now
    return all_players


def get_last_n_games(player_id, num_games=10, season="2024-25"):
    """Fetch last N game logs for a given player."""
    try:
        logs = playergamelog.PlayerGameLog(player_id=player_id, season=season)
        df = logs.get_data_frames()[0]
        return df.head(num_games)
    except Exception:
        return pd.DataFrame()


def calculate_trends(game_logs, thresholds):
    """Calculate how many times a player exceeded given thresholds."""
    results = {}
    total = len(game_logs)
    for label, (stat, value) in thresholds.items():
        if total == 0 or stat not in game_logs.columns:
            hits = 0
        else:
            hits = int((game_logs[stat] >= value).sum())
        results[label] = f"{hits}/{total} games"
    return results


# -----------------------------
# MAIN SCRIPT
# -----------------------------
def main():
    thresholds = {
        "20+ points": ("PTS", 20),
        "10+ rebounds": ("REB", 10),
        "5+ assists": ("AST", 5),
        "3+ threes": ("FG3M", 3)
    }

    games = get_todays_games()
    if not games:
        print("No NBA games today.")
        return

    print("📅 Today's Games:")
    for g in games:
        print(f"   {g['away_team']} @ {g['home_team']}")
    print("\n=============================\n")

    # Test with a few players (not full rosters yet)
    sample_players = ["LeBron James", "Jayson Tatum", "Nikola Jokic", "Stephen Curry"]

    for name in sample_players:
        all_players = players.get_players()
        import unicodedata

def normalize_name(n):
    return ''.join(c for c in unicodedata.normalize('NFD', n) if unicodedata.category(c) != 'Mn').lower()

match = next(
    (p for p in all_players if normalize_name(p["full_name"]) == normalize_name(name)),
    None
)
        if not match:
            print(f"{name}: not found")
            continue

        logs = get_last_n_games(match["id"], CONFIG["NUM_GAMES_LOOKBACK"], CONFIG["SEASON"])
        if logs.empty:
            print(f"{name}: no data found")
            continue

        print(f"📊 {name}")
        trends = calculate_trends(logs, thresholds)
        for label, summary in trends.items():
            print(f"   • {label}: {summary}")
        print("")
        time.sleep(CONFIG["API_SLEEP"])


if __name__ == "__main__":
    main()
