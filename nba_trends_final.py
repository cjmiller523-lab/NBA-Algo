"""
NBA Trends (Final Version — Auto-Threshold + Caching + Summary)
---------------------------------------------------------------
Analyzes NBA player stats, finds what thresholds they hit >=80% of the time,
updates rosters dynamically, caches data locally, and generates a color-coded PDF
with a summary of the most consistent players.
"""

import time
import os
import json
import unicodedata
import numpy as np
import pandas as pd
import subprocess
from datetime import datetime, timedelta
from nba_api.stats.endpoints import scoreboardv2, playergamelog, commonteamroster
from nba_api.stats.static import teams, players
from tqdm import tqdm
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet


# -----------------------------
# CONFIG
# -----------------------------
CONFIG = {
    "SEASON": "2024-25",
    "NUM_GAMES_LOOKBACK": 10,
    "API_SLEEP": 0.3,
    "CACHE_DIR": "cache",
    "OUTPUT_FILE": "output/trends_final.pdf",
    "CACHE_EXPIRY_HOURS": 24
}

# -----------------------------
# SETUP
# -----------------------------
os.makedirs("output", exist_ok=True)
os.makedirs(CONFIG["CACHE_DIR"], exist_ok=True)

# -----------------------------
# UTILITIES
# -----------------------------
def normalize_name(n):
    return ''.join(c for c in unicodedata.normalize('NFD', n) if unicodedata.category(c) != 'Mn').lower()

def cache_path(player_name):
    safe_name = player_name.replace(" ", "_").replace(".", "")
    return os.path.join(CONFIG["CACHE_DIR"], f"{safe_name}.json")

def is_cache_valid(path):
    if not os.path.exists(path):
        return False
    mod_time = datetime.fromtimestamp(os.path.getmtime(path))
    return datetime.now() - mod_time < timedelta(hours=CONFIG["CACHE_EXPIRY_HOURS"])

def save_cache(player_name, df):
    try:
        df.to_json(cache_path(player_name), orient="records", indent=2)
    except Exception as e:
        print(f"Error caching {player_name}: {e}")

def load_cache(player_name):
    try:
        with open(cache_path(player_name), "r") as f:
            data = json.load(f)
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()

# -----------------------------
# DATA FETCHING
# -----------------------------
def get_todays_games():
    today = datetime.now().strftime('%Y-%m-%d')
    scoreboard = scoreboardv2.ScoreboardV2(game_date=today)
    games = scoreboard.game_header.get_data_frame()
    team_lookup = {t["id"]: t["abbreviation"] for t in teams.get_teams()}
    matchups = []
    for _, row in games.iterrows():
        home_abbrev = team_lookup.get(row["HOME_TEAM_ID"], "UNK")
        away_abbrev = team_lookup.get(row["VISITOR_TEAM_ID"], "UNK")
        matchups.append({
            "game_id": row["GAME_ID"],
            "home_team": home_abbrev,
            "away_team": away_abbrev
        })
    return matchups

def get_team_roster(team_abbrev):
    """Always pull the latest team roster for accuracy."""
    team_info = next((t for t in teams.get_teams() if t["abbreviation"] == team_abbrev), None)
    if not team_info:
        return []
    try:
        roster = commonteamroster.CommonTeamRoster(
            team_id=team_info["id"],
            season=CONFIG["SEASON"]
        ).get_data_frames()[0]
        return roster["PLAYER"].tolist()
    except Exception:
        return []

def get_last_n_games(player_name, num_games):
    """Load cached player stats if valid, else fetch new data."""
    path = cache_path(player_name)
    if is_cache_valid(path):
        return load_cache(player_name).head(num_games)

    all_players = players.get_players()
    match = next((p for p in all_players if normalize_name(p["full_name"]) == normalize_name(player_name)), None)
    if not match:
        return pd.DataFrame()

    for attempt in range(3):
        try:
            logs = playergamelog.PlayerGameLog(
                player_id=match["id"],
                season=CONFIG["SEASON"]
            ).get_data_frames()[0]
            save_cache(player_name, logs)
            return logs.head(num_games)
        except Exception as e:
            print(f"⚠️ Error fetching {player_name} (attempt {attempt+1}/3): {e}")
            time.sleep(1.5 * (attempt + 1))
    return load_cache(player_name)

# -----------------------------
# ANALYSIS
# -----------------------------
def calculate_auto_thresholds(df):
    """Find dynamic thresholds each player hits >=80% of the time."""
    results = []
    if df.empty:
        return results

    total = len(df)
    for stat in ["PTS", "REB", "AST", "FG3M"]:
        if stat not in df.columns:
            continue
        values = df[stat].dropna().sort_values(ascending=False).tolist()
        if not values:
            continue
        threshold_idx = int(0.8 * len(values)) - 1
        if threshold_idx < 0:
            threshold_idx = 0
        threshold = int(np.floor(values[threshold_idx]))
        hits = int((df[stat] >= threshold).sum())
        rate = hits / total if total else 0
        if rate >= 0.8 and threshold > 0:
            label = {"PTS": "points", "REB": "rebounds", "AST": "assists", "FG3M": "threes"}[stat]
            results.append({
                "Stat": label,
                "Threshold": threshold,
                "HitRate": f"{hits}/{total} ({rate*100:.0f}%)",
                "RateValue": rate
            })
    return results

# -----------------------------
# PDF REPORT
# -----------------------------
def save_pdf_report(rows):
    if not rows:
        print("⚠️ No players met 80%+ consistency.")
        return

    rows = sorted(rows, key=lambda x: x["RateValue"], reverse=True)

    doc = SimpleDocTemplate(CONFIG["OUTPUT_FILE"], pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    title = Paragraph(f"NBA Auto-Threshold Trends — {datetime.now().strftime('%B %d, %Y')}", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))

    # Summary Table: Top 10 Players
    top10 = rows[:10]
    summary_data = [["Top 10 Most Consistent Players", "Team", "Stat", "Threshold", "Hit Rate"]]
    for r in top10:
        summary_data.append([r["Player"], r["Team"], r["Stat"], f"{r['Threshold']}+", r["HitRate"]])

    summary_table = Table(summary_data, repeatRows=1)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#002b5c")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey)
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 16))

    # Full Results Table
    data = [["Player", "Team", "Stat", "Threshold", "Hit Rate"]] + [
        [r["Player"], r["Team"], r["Stat"], f"{r['Threshold']}+", r["HitRate"]] for r in rows
    ]

    table = Table(data, repeatRows=1)
    table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#003366")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey)
    ]

    for i, r in enumerate(rows, start=1):
        if r["RateValue"] >= 0.9:
            table_style.append(('BACKGROUND', (0, i), (-1, i), colors.lawngreen))
        elif r["RateValue"] >= 0.8:
            table_style.append(('BACKGROUND', (0, i), (-1, i), colors.lightyellow))

    table.setStyle(TableStyle(table_style))
    story.append(table)
    doc.build(story)

    print(f"✅ PDF saved to {CONFIG['OUTPUT_FILE']}")
    try:
        os.startfile(os.path.abspath(CONFIG["OUTPUT_FILE"]))
        print("📂 PDF opened automatically.")
    except Exception as e:
        print(f"Could not open PDF automatically: {e}")

# -----------------------------
# MAIN
# -----------------------------
def main():
    games = get_todays_games()
    if not games:
        print("No NBA games today.")
        return

    print("📅 Today's Games:")
    for g in games:
        print(f"   {g['away_team']} @ {g['home_team']}")
    print(f"\nAnalyzing player consistency (last {CONFIG['NUM_GAMES_LOOKBACK']} games)...")

    consistent_rows = []

    for g in games:
        for team in [g["home_team"], g["away_team"]]:
            roster = get_team_roster(team)
            if not roster:
                continue
            print(f"\n🔍 {team}: analyzing {len(roster)} players...")
            for player in tqdm(roster, desc=f"{team}", leave=False):
                logs = get_last_n_games(player, CONFIG["NUM_GAMES_LOOKBACK"])
                trends = calculate_auto_thresholds(logs)
                for t in trends:
                    consistent_rows.append({
                        "Player": player,
                        "Team": team,
                        **t
                    })
                time.sleep(CONFIG["API_SLEEP"])

    save_pdf_report(consistent_rows)


if __name__ == "__main__":
    main()
