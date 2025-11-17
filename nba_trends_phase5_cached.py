# ========== NBA Trends Phase 5 — STARTER OPTIMIZED + CACHING ==========
import os
import json
import time
import warnings
from datetime import datetime, timedelta
warnings.filterwarnings("ignore")

import pandas as pd
from nba_api.stats.endpoints import ScoreboardV2, PlayerGameLog, CommonTeamRoster
from nba_api.stats.static import teams as static_teams

# ===== CONFIG =====
LOOKBACK = 10
MIN_HIT = 0.80
REQ_STARTERS = 5
REQ_CACHE_FOLDER = "cache"
CACHE_MAX_AGE_HOURS = 24
TIMEOUT = 8
SLEEP = 0.15

CATEGORIES = {
    "PTS": [30, 25, 20, 15, 10],
    "REB": [12, 10, 8, 6],
    "AST": [10, 8, 6, 4],
    "3PM": [4, 3, 2, 1],
    "STL": [3, 2, 1],
    "BLK": [3, 2, 1],
}

CATEGORY_ORDER = ["PTS", "REB", "AST", "3PM", "STL", "BLK"]

CAT_LABEL = {
    "PTS": "Points",
    "REB": "Rebounds",
    "AST": "Assists",
    "3PM": "3-Pointers",
    "STL": "Steals",
    "BLK": "Blocks",
}

SEASONS = ["2025-26", "2024-25"]


# ===== UTIL =====
def ensure_cache():
    if not os.path.exists(REQ_CACHE_FOLDER):
        os.makedirs(REQ_CACHE_FOLDER)


def cache_path(pid: int):
    return os.path.join(REQ_CACHE_FOLDER, f"{pid}.json")

def today_mmddyyyy():
    return datetime.today().strftime("%m/%d/%Y")

def newest_game_date(df: pd.DataFrame):
    return df["GAME_DATE"].max() if not df.empty else None


# ===== CACHING PLAYER LOGS =====
def load_cached_logs(pid: int) -> pd.DataFrame:
    path = cache_path(pid)
    if not os.path.exists(path):
        return pd.DataFrame()

    with open(path, "r") as f:
        data = json.load(f)

    cached_date = datetime.strptime(data["updated"], "%Y-%m-%d")
    if datetime.now() - cached_date > timedelta(hours=CACHE_MAX_AGE_HOURS):
        return pd.DataFrame()

    df = pd.DataFrame(data["logs"])
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    df.sort_values("GAME_DATE", ascending=False, inplace=True)
    return df


def save_cached_logs(pid: int, df: pd.DataFrame):
    # Convert GAME_DATE to string for JSON storage
    if "GAME_DATE" in df.columns:
        df = df.copy()
        df["GAME_DATE"] = df["GAME_DATE"].dt.strftime("%Y-%m-%d")

    logs = df.to_dict(orient="records")
    out = {"updated": datetime.now().strftime("%Y-%m-%d"), "logs": logs}

    with open(cache_path(pid), "w") as f:
        json.dump(out, f, indent=2)

    print(f"💾 Cache updated for {pid}")



def fetch_player_logs(pid: int) -> pd.DataFrame:
    """Mix 2 seasons, return most recent LOOKBACK games (sort by GAME_DATE)."""
    df_all = pd.DataFrame()

    for season in SEASONS:
        try:
            gl = PlayerGameLog(player_id=pid, season=season, timeout=TIMEOUT)
            part = gl.get_data_frames()[0]
            if "MIN" in part.columns:
                part = part[part["MIN"] > 0]
            if "GAME_DATE" in part.columns:
                part["GAME_DATE"] = pd.to_datetime(part["GAME_DATE"])
            if "FG3M" in part.columns:
                part["3PM"] = part["FG3M"]
            else:
                part["3PM"] = 0
            for c in ["PTS", "REB", "AST", "STL", "BLK"]:
                if c not in part.columns:
                    part[c] = 0
            df_all = pd.concat([df_all, part], ignore_index=True)
            time.sleep(SLEEP)
        except:
            pass

        if len(df_all) >= LOOKBACK:
            break

    if df_all.empty:
        return df_all

    df_all.sort_values("GAME_DATE", ascending=False, inplace=True)
    return df_all.head(LOOKBACK)


def get_player_logs(pid: int) -> pd.DataFrame:
    """Load from cache if valid; else fetch & cache."""
    ensure_cache()
    cached = load_cached_logs(pid)
    if not cached.empty:
        newest = newest_game_date(cached)
        if newest and newest.date() >= datetime.today().date():
            return cached

    fresh = fetch_player_logs(pid)
    if not fresh.empty:
        save_cached_logs(pid, fresh)
    return fresh


# ===== ROSTER + STARTERS =====
def build_team_maps():
    t = static_teams.get_teams()
    return {x["id"]: x["abbreviation"] for x in t}

def get_today_team_ids():
    date_str = today_mmddyyyy()
    sb = ScoreboardV2(game_date=date_str)
    g = sb.get_data_frames()[0]
    if g.empty:
        return []
    return list(set(g["HOME_TEAM_ID"].tolist() + g["VISITOR_TEAM_ID"].tolist()))

def get_top5_by_minutes(tid: int, id2abbr: dict):
    try:
        df = CommonTeamRoster(team_id=tid, timeout=TIMEOUT).get_data_frames()[0]
    except:
        print(f"⚠ No roster for {tid}")
        return []

    players = []
    for _, row in df.iterrows():
        pid = int(row["PLAYER_ID"])
        name = str(row["PLAYER"])
        logs = get_player_logs(pid)
        avg = logs["MIN"].mean() if not logs.empty else 0
        players.append({"id": pid, "name": name, "logs": logs, "avg": avg})

    players.sort(key=lambda x: x["avg"], reverse=True)
    chosen = players[:REQ_STARTERS]
    abbr = id2abbr.get(tid, str(tid))
    print(f"⭐ {abbr}: top5 chosen: {[p['name'] for p in chosen]}")
    return chosen


# ===== STATS EVALUATION =====
def best_hit(df: pd.DataFrame, cat: str):
    total = len(df)
    if total == 0:
        return None
    for lvl in CATEGORIES[cat]:
        hits = int((df[cat] >= lvl).sum())
        rate = hits / total
        if rate >= MIN_HIT:
            return lvl, hits, rate
        break
    return None


# ===== MAIN =====
def main():
    ensure_cache()

    team_ids = get_today_team_ids()
    if not team_ids:
        print("No NBA games today per API.")
        return

    id2abbr = build_team_maps()

    starters_pool = []
    print("⏳ Selecting top5 by minutes per team...")
    for tid in team_ids:
        starters_pool.extend(get_top5_by_minutes(tid, id2abbr))
    print(f"\nTotal players selected: {len(starters_pool)}\n")

    results = {c: [] for c in CATEGORY_ORDER}

    print("📊 Evaluating trends...")
    for idx, p in enumerate(starters_pool, 1):
        if idx % 6 == 1:
            print(f"   Progress: {idx}/{len(starters_pool)}")
        name, logs = p["name"], p["logs"]
        if logs.empty:
            continue
        for cat in CATEGORY_ORDER:
            found = best_hit(logs, cat)
            if found:
                lvl, hits, rate = found
                results[cat].append({
                    "player": name,
                    "team": "UNK",
                    "prop": f"{CAT_LABEL[cat]} {lvl}+",
                    "hits": hits,
                    "rate": int(rate*100)
                })

    print("\n✅ HIGH-CONFIDENCE STARTER TREND RESULTS (≥80%)\n")
    for cat in CATEGORY_ORDER:
        group = results[cat]
        if not group:
            continue
        print(f"=== {CAT_LABEL[cat]} ===")
        print(f"{'Player':22}  {'Prop':20} {'Hits':>7} {'Rate':>5}")
        print("-" * 55)
        for r in sorted(group, key=lambda x: (x["rate"], x["hits"]), reverse=True):
            print(f"{r['player']:22}  {r['prop']:20} {r['hits']:>2}/{LOOKBACK}  {r['rate']:>2}%")
        print()
    print("Done ✅")


if __name__ == "__main__":
    main()
