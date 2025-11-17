# ========================= NBA Trends Phase 3 =========================
# All players in today's games (ET), last 10 games (Reg+Playoffs),
# avg MIN >= 15, best single line per category (>=80% hit),
# categories: PTS, REB, AST, 3PM, STL, BLK
# =====================================================================

import warnings
warnings.filterwarnings("ignore")

import time
from datetime import datetime
from typing import Dict, List, Tuple

import pandas as pd
from nba_api.stats.endpoints import ScoreboardV2, PlayerGameLog, CommonTeamRoster

# ------------------------ CONFIG ------------------------
LOOKBACK_GAMES = 10
MIN_AVG_MINUTES = 15
MIN_HIT_RATE = 0.80  # Option C you chose (>=80%)
SLEEP = 0.25         # polite delay between NBA API calls

# Thresholds (highest to lowest)
THRESHOLDS: Dict[str, List[int]] = {
    "PTS": [30, 25, 20, 15, 10],   # 35+ removed per your request
    "REB": [12, 10, 8, 6],
    "AST": [10, 8, 6, 4],
    "3PM": [4, 3, 2, 1],
    "STL": [3, 2, 1],
    "BLK": [3, 2, 1],
}

STAT_PRETTY = {
    "PTS": "Points",
    "REB": "Rebounds",
    "AST": "Assists",
    "3PM": "3-Pointers",
    "STL": "Steals",
    "BLK": "Blocks",
}

# Seasons to pull (mix them, then take latest 10)
SEASONS = ["2025-26", "2024-25"]


# ------------------------ HELPERS ------------------------
def today_mmddyyyy_et() -> str:
    """Return today's date formatted the way ScoreboardV2 expects (MM/DD/YYYY)."""
    # Your timezone is ET per your choice (America/New_York)
    # datetime.today() will be your local (Windows) time which is ET for you.
    return datetime.today().strftime("%m/%d/%Y")


def get_today_team_ids() -> List[int]:
    """Get unique NBA team IDs playing today."""
    date_str = today_mmddyyyy_et()
    print(f"\n📅 Checking NBA games for (ET): {date_str}")
    sb = ScoreboardV2(game_date=date_str)
    games_df = sb.get_data_frames()[0]

    if games_df.empty:
        print("⚠ No NBA games scheduled for today (per NBA API).")
        return []

    print(f"Games found: {len(games_df)}")
    # Uncomment next line to see raw IDs
    # print(games_df[["GAME_DATE_EST", "HOME_TEAM_ID", "VISITOR_TEAM_ID"]])

    team_ids = list(set(games_df["HOME_TEAM_ID"].tolist() + games_df["VISITOR_TEAM_ID"].tolist()))
    print(f"Teams playing today: {team_ids}\n")
    return team_ids


def get_players_from_teams(team_ids: List[int]) -> List[Dict]:
    """Return unique players (id, name) from today's teams using CommonTeamRoster."""
    print("🔍 Fetching live rosters via CommonTeamRoster...")
    roster_players: Dict[int, Dict] = {}

    for tid in team_ids:
        try:
            roster = CommonTeamRoster(team_id=int(tid)).get_data_frames()[0]
            for _, row in roster.iterrows():
                pid = int(row["PLAYER_ID"])
                name = str(row["PLAYER"])
                # store
                roster_players[pid] = {"id": pid, "name": name}
            time.sleep(SLEEP)
        except Exception as e:
            print(f"   ⚠ Roster fetch failed for team {tid}: {e}")

    players_list = list(roster_players.values())
    print(f"✅ Players found: {len(players_list)}\n")
    return players_list


def get_player_logs(player_id: int, lookback: int = LOOKBACK_GAMES) -> pd.DataFrame:
    """Fetch last `lookback` games for a player, mixing current & prior season,
    including playoffs. Filters out DNP (MIN=0). Returns a DF with needed columns."""
    df_all = pd.DataFrame()

    for season in SEASONS:
        try:
            gl = PlayerGameLog(player_id=player_id, season=season)
            df = gl.get_data_frames()[0]
            # Remove DNP / 0 minutes
            if "MIN" in df.columns:
                df = df[df["MIN"] > 0]
            # Normalize date + fields
            if "GAME_DATE" in df.columns:
                df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
            if "FG3M" in df.columns:
                df["3PM"] = df["FG3M"]
            else:
                df["3PM"] = 0
            # Some payloads may miss these; fill if needed
            for col in ["PTS", "REB", "AST", "STL", "BLK"]:
                if col not in df.columns:
                    df[col] = 0

            df_all = pd.concat([df_all, df], ignore_index=True)
            time.sleep(SLEEP)
        except Exception as e:
            # Keep going; some players/seasons can fail
            # print(f"   (info) Logs failed for {player_id} {season}: {e}")
            pass

        # Early exit if we already have enough (we'll sort/trim after loop)
        if len(df_all) >= lookback:
            break

    if df_all.empty:
        return pd.DataFrame()

    # Sort newest first, then take last N
    df_all.sort_values("GAME_DATE", ascending=False, inplace=True)
    df_recent = df_all.head(lookback).copy()

    needed = ["GAME_DATE", "MIN", "PTS", "REB", "AST", "3PM", "STL", "BLK"]
    for c in needed:
        if c not in df_recent.columns:
            df_recent[c] = 0

    return df_recent[needed]


def best_line_for_category(df: pd.DataFrame, stat_key: str) -> Tuple[int, int, float] or None:
    """Return (best_threshold, hits, rate) for a single stat category if meets 80%+, else None."""
    levels = THRESHOLDS[stat_key]
    total = len(df)
    if total == 0:
        return None

    for lvl in levels:
        hits = int((df[stat_key] >= lvl).sum())
        rate = hits / total
        if rate >= MIN_HIT_RATE:
            return (lvl, hits, rate)
        # stop-on-first-fail behavior (as requested)
        # If you want to test all levels regardless, comment this out
        # and it will keep checking lower lines.
        break
    return None


def evaluate_player(name: str, logs: pd.DataFrame) -> List[Tuple[str, int, int, float]]:
    """Return list of (stat_pretty, threshold, hits, rate) for the player across categories.
       One best line per category; multiple categories allowed."""
    if logs.empty:
        return []
    if logs["MIN"].mean() < MIN_AVG_MINUTES:
        return []

    picks = []
    for key in ["PTS", "REB", "AST", "3PM", "STL", "BLK"]:
        best = best_line_for_category(logs, key)
        if best:
            lvl, hits, rate = best
            picks.append((STAT_PRETTY[key], lvl, hits, rate))
    return picks


# ------------------------ MAIN ------------------------
def main():
    team_ids = get_today_team_ids()
    if not team_ids:
        return

    players_today = get_players_from_teams(team_ids)
    if not players_today:
        print("⚠ No players found on today's rosters.")
        return

    print("⚙ Analyzing trends (this will take ~1–2 minutes)...\n")

    results = []  # (player, stat, lvl, hits, rate)
    processed = 0

    for p in players_today:
        processed += 1
        if processed % 10 == 1:
            print(f"⏳ Processing players {processed}/{len(players_today)} ...")

        logs = get_player_logs(p["id"], LOOKBACK_GAMES)
        if logs.empty:
            continue

        picks = evaluate_player(p["name"], logs)
        for (stat, lvl, hits, rate) in picks:
            results.append((p["name"], stat, lvl, hits, rate))

    if not results:
        print("\n⚠ No high-confidence trends (>=80%) met the minutes filter today.")
        return

    # Sort by highest hit rate, then by threshold (desc), then name
    results.sort(key=lambda x: (x[4], x[2]), reverse=True)

    print("\n✅ High-Confidence Trends (>=80% hit, last 10, avg ≥15 MIN)\n")
    print(f"{'Player':22}  {'Prop':18} {'Hits':>8}  {'Rate':>6}")
    print("-" * 60)
    for (name, stat, lvl, hits, rate) in results:
        prop = f"{stat} {lvl}+"
        print(f"{name:22}  {prop:18}  {hits}/{LOOKBACK_GAMES:>3}   {int(rate*100):>3}%")

    print("\nDone.")


if __name__ == "__main__":
    main()
