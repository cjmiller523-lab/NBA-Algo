"""
NBA Trends (Auto-Threshold PDF Version with Progress Bar + Auto-Open)
---------------------------------------------------------------------
Analyzes each player's last N games to find what stat thresholds
(points, rebounds, assists, threes) they hit >=80% of the time.
Generates a color-coded PDF report and automatically opens it.
"""

import time
import unicodedata
import numpy as np
import pandas as pd
import os
import subprocess
from datetime import datetime
from nba_api.stats.endpoints import scoreboardv2, playergamelog, commonteamroster
from nba_api.stats.static import teams
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
    "NUM_GAMES_LOOKBACK": 10,  # Change to 20 for full analysis
    "API_SLEEP": 0.3,          # Delay between API calls
    "OUTPUT_FILE": "output/trends_auto.pdf"
}

# -----------------------------
# PREP
# -----------------------------
# Make sure output folder exists
os.makedirs("output", exist_ok=True)

# -----------------------------
# UTILITIES
# -----------------------------
def normalize_name(n):
    """Remove accents and lowercase a name for matching."""
    return ''.join(c for c in unicodedata.normalize('NFD', n) if unicodedata.category(c) != 'Mn').lower()

def get_todays_games():
    """Get today's NBA games using team IDs."""
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
    """Return a list of players for a team."""
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
    """Fetch last N game logs for a player."""
    from nba_api.stats.static import players
    all_players = players.get_players()
    match = next((p for p in all_players if normalize_name(p["full_name"]) == normalize_name(player_name)), None)
    if not match:
        return pd.DataFrame()
    try:
        logs = playergamelog.PlayerGameLog(
            player_id=match["id"],
            season=CONFIG["SEASON"]
        ).get_data_frames()[0]
        return logs.head(num_games)
    except Exception:
        return pd.DataFrame()

def calculate_auto_thresholds(df):
    """Find thresholds each player hits >=80% of the time."""
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
# PDF CREATION
# -----------------------------
def save_pdf_report(rows):
    if not rows:
        print("⚠️  No players met 80%+ consistency.")
        return

    # Sort highest hit-rate first
    rows = sorted(rows, key=lambda x: x["RateValue"], reverse=True)

    doc = SimpleDocTemplate(CONFIG["OUTPUT_FILE"], pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    title = Paragraph(f"NBA Auto-Threshold Trends — {datetime.now().strftime('%B %d, %Y')}", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))

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

    # Auto-open PDF
    try:
        abs_path = os.path.abspath(CONFIG["OUTPUT_FILE"])
        os.startfile(abs_path)  # Windows only
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
