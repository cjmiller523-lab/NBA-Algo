# ===================== NBA Trends — Phase 4 (Starters Optimized) =====================
# - Timezone: ET (uses your local Windows time)
# - Today’s teams (ScoreboardV2)
# - Players: Top 5 by average minutes over their last 10 games (per team)
# - Games used: last 10 (Regular Season + Playoffs mixed)
# - Categories: PTS, REB, AST, 3PM, STL, BLK
# - Threshold logic: high → low, stop on first fail; keep only best per category
# - Filter: hit rate >= 80%
# - Output: grouped by category (PTS, REB, AST, 3PM, STL, BLK)
# ====================================================================================

import warnings
warnings.filterwarnings("ignore")

import time
from datetime import datetime
from typing import Dict, List, Tuple

import pandas as pd
from nba_api.stats.endpoints import ScoreboardV2, PlayerGameLog, CommonTeamRoster
from nba_api.stats.static import teams as static_teams

# ------------------- CONFIG -------------------
LOOKBACK_GAMES = 10
MIN_HIT_RATE = 0.80                 # (Option C you chose)
REQ_STARTERS = 5                    # Always try to return 5 per team (Option D)
SLEEP = 0.20                        # Polite pause between NBA API calls
TIMEOUT = 10                        # Per-request timeout seconds

# Thresholds (top → down; stop at first success ≥ MIN_HIT_RATE)
THRESHOLDS: Dict[str, List[int]] = {
    "PTS": [30, 25, 20, 15, 10],    # 35+ removed as requested
    "REB": [12, 10, 8, 6],
    "AST": [10, 8, 6, 4],
    "3PM": [4, 3, 2, 1],
    "STL": [3, 2, 1],
    "BLK": [3, 2, 1],
}

STAT_LABEL = {
    "PTS": "Points",
    "REB": "Rebounds",
    "AST": "Assists",
    "3PM": "3-Pointers",
    "STL": "Steals",
    "BLK": "Blocks",
}

ORDERED_CATEGORIES = ["PTS", "REB", "AST", "3PM", "STL", "BLK"]

SEASONS = ["2025-26", "2024-25"]   # mix seasons, sort newest, take last 10


# ------------------- HELPERS -------------------
def today_mmddyyyy_et() -> str:
    return datetime.today().strftime("%m/%d/%Y")


def build_team_maps():
    tlist = static_teams.get_teams()
    id2abbr = {t["id"]: t["abbreviation"] for t in tlist}
    id2name = {t["id"]: t["full_name"] for t in tlist}
    return id2abbr, id2name


def get_today_team_ids() -> List[int]:
    date_str = today_mmddyyyy_et()
    print(f"\n📅 NBA games for (ET): {date_str}")
    sb = ScoreboardV2(game_date=date_str)
    games_df = sb.get_data_frames()[0]
    if games_df.empty:
        print("⚠ No NBA games listed by API for today.")
        return []
    team_ids = list(set(games_df["HOME_TEAM_ID"].tolist() + games_df["VISITOR_TEAM_ID"].tolist()))
    print(f"Games found: {len(games_df)}  |  Teams: {len(team_ids)}\n")
    return team_ids


def get_team_roster(team_id: int) -> pd.DataFrame:
    try:
        df = CommonTeamRoster(team_id=int(team_id), timeout=TIMEOUT).get_data_frames()[0]
        time.sleep(SLEEP)
        return df
    except Exception:
        return pd.DataFrame()


def get_player_logs(player_id: int, lookback: int = LOOKBACK_GAMES) -> pd.DataFrame:
    """Last `lookback` games (Reg + Playoffs), newest first, MIN>0 only."""
    df_all = pd.DataFrame()
    for season in SEASONS:
        try:
            gl = PlayerGameLog(player_id=player_id, season=season, timeout=TIMEOUT)
            df = gl.get_data_frames()[0]
            if "MIN" in df.columns:
                df = df[df["MIN"] > 0]
            if "GAME_DATE" in df.columns:
                df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
            if "FG3M" in df.columns:
                df["3PM"] = df["FG3M"]
            else:
                df["3PM"] = 0
            for k in ["PTS", "REB", "AST", "STL", "BLK"]:
                if k not in df.columns:
                    df[k] = 0
            df_all = pd.concat([df_all, df], ignore_index=True)
            time.sleep(SLEEP)
        except Exception:
            # skip this season if timeout/failure
            pass
        if len(df_all) >= lookback:
            break

    if df_all.empty:
        return df_all
    df_all.sort_values("GAME_DATE", ascending=False, inplace=True)
    df_recent = df_all.head(lookback).copy()
    needed = ["GAME_DATE", "MIN", "PTS", "REB", "AST", "3PM", "STL", "BLK"]
    for c in needed:
        if c not in df_recent.columns:
            df_recent[c] = 0
    return df_recent[needed]


def pick_top5_by_minutes(roster_df: pd.DataFrame) -> List[Dict]:
    """Return up to 5 players (dicts) with highest avg minutes over their last 10 games."""
    candidates = []
    for _, row in roster_df.iterrows():
        pid = int(row["PLAYER_ID"])
        name = str(row["PLAYER"])
        logs = get_player_logs(pid, LOOKBACK_GAMES)
        if logs.empty:
            avg_min = 0.0
        else:
            avg_min = float(logs["MIN"].mean())
        candidates.append({"id": pid, "name": name, "avg_min": avg_min, "logs": logs})

    # Sort by avg minutes desc and take top 5 always (Option D)
    candidates.sort(key=lambda x: x["avg_min"], reverse=True)
    chosen = [c for c in candidates[:REQ_STARTERS] if c["logs"] is not None]
    return chosen


def best_line_for_category(df: pd.DataFrame, stat_key: str) -> Tuple[int, int, float] or None:
    total = len(df)
    if total == 0:
        return None
    for lvl in THRESHOLDS[stat_key]:
        hits = int((df[stat_key] >= lvl).sum())
        rate = hits / total
        if rate >= MIN_HIT_RATE:
            return (lvl, hits, rate)
        # stop-on-first-fail as requested
        break
    return None


def evaluate_player_across_categories(name: str, team_abbr: str, logs: pd.DataFrame):
    """Return list of dicts with best prop per category that qualifies."""
    picks = []
    if logs.empty:
        return picks
    # No minutes floor here since we took top5 by minutes already
    for key in ORDERED_CATEGORIES:
        best = best_line_for_category(logs, key)
        if best:
            lvl, hits, rate = best
            picks.append({
                "player": name,
                "team": team_abbr,
                "cat": key,
                "label": STAT_LABEL[key],
                "line": lvl,
                "hits": hits,
                "rate": rate
            })
    return picks


# ------------------- MAIN -------------------
def main():
    id2abbr, id2name = build_team_maps()
    team_ids = get_today_team_ids()
    if not team_ids:
        return

    print("🔎 Selecting top-5 minute-getters for each team...")
    starters_all_teams = []  # list of dicts: {id, name, team_id, team_abbr, logs}
    for tid in team_ids:
        roster = get_team_roster(tid)
        if roster.empty:
            print(f"   ⚠ Roster unavailable for team {tid}. Skipping.")
            continue
        top5 = pick_top5_by_minutes(roster)
        for p in top5:
            starters_all_teams.append({
                "id": p["id"],
                "name": p["name"],
                "team_id": tid,
                "team_abbr": id2abbr.get(tid, str(tid)),
                "logs": p["logs"]
            })
        abbr = id2abbr.get(tid, str(tid))
        print(f"   {abbr}: selected {len(top5)} players.")
    if not starters_all_teams:
        print("⚠ No starters were selected. Exiting.")
        return

    print(f"\n🧮 Evaluating trends for {len(starters_all_teams)} players (last {LOOKBACK_GAMES})...\n")
    results_by_cat = {k: [] for k in ORDERED_CATEGORIES}

    # Evaluate best per category (multiple categories allowed per player)
    for idx, p in enumerate(starters_all_teams, start=1):
        if idx % 8 == 1:
            print(f"   Progress: {idx}/{len(starters_all_teams)}")
        picks = evaluate_player_across_categories(p["name"], p["team_abbr"], p["logs"])
        for rec in picks:
            results_by_cat[rec["cat"]].append(rec)

    any_results = any(len(v) > 0 for v in results_by_cat.values())
    if not any_results:
        print("⚠ No high-confidence picks (>=80% hit) found for selected starters today.")
        return

    # ---------- Output: Grouped by Category ----------
    print("\n✅ High-Confidence Trends (≥80% hit, last 10, starters by minutes)\n")
    for cat in ORDERED_CATEGORIES:
        group = results_by_cat[cat]
        if not group:
            continue
        # Sort inside category: highest rate → higher line → player name
        group.sort(key=lambda r: (r["rate"], r["line"], r["player"]), reverse=True)

        header = STAT_LABEL[cat]
        print(f"=== {header} ===")
        print(f"{'Player':22} {'Team':5} {'Prop':12} {'Hits':>7}  {'Rate':>6}")
        print("-" * 56)
        for r in group:
            prop = f"{r['line']}+"
            print(f"{r['player']:22} {r['team']:<5} {prop:<12}  {r['hits']:>2}/{LOOKBACK_GAMES}   {int(r['rate']*100):>3}%")
        print()

    print("Done.")


if __name__ == "__main__":
    main()
