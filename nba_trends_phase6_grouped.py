import os
import json
import time
import tempfile
import pandas as pd
from tqdm import tqdm
from nba_api.stats.endpoints import LeagueGameFinder, PlayerGameLog, CommonTeamRoster
from nba_api.stats.static import players, teams

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

SEASONS = ["2025-26", "2024-25"]
NUM_GAMES = 10
SLEEP = 0.15
TIMEOUT = 8

THRESHOLDS = {
    "PTS": [30, 25, 20, 15, 10],
    "REB": [12, 10, 8, 6, 4],
    "AST": [9, 7, 5, 3],
    "3PM": [4, 3, 2, 1],
    "STL": [3, 2, 1],
    "BLK": [3, 2, 1],
}

CAT_ORDER = ["PTS", "REB", "AST", "3PM", "STL", "BLK"]
CAT_LABEL = {
    "PTS": "Points",
    "REB": "Rebounds",
    "AST": "Assists",
    "3PM": "3PM",
    "STL": "Steals",
    "BLK": "Blocks"
}

####################################################
# SAFE CACHE
####################################################
def safe_cache_save(pid, df):
    df2 = df.copy()
    df2["GAME_DATE"] = df2["GAME_DATE"].astype(str)
    path = os.path.join(CACHE_DIR, f"{pid}.json")

    with tempfile.NamedTemporaryFile("w", delete=False, dir=CACHE_DIR) as tmp:
        json.dump(df2.to_dict("records"), tmp, indent=2)
        temp = tmp.name
    os.replace(temp, path)


def safe_cache_load(pid):
    path = os.path.join(CACHE_DIR, f"{pid}.json")
    if not os.path.exists(path): return None
    try:
        df = pd.read_json(path)
        df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
        df.sort_values("GAME_DATE", ascending=False, inplace=True)
        return df
    except:
        os.remove(path)
        return None


####################################################
# GAME / ROSTER FETCHING
####################################################
def get_today_team_ids():
    today = pd.Timestamp.now().strftime("%Y-%m-%d")

    games = pd.concat([
        LeagueGameFinder(season_nullable="2025-26").get_data_frames()[0],
        LeagueGameFinder(season_nullable="2024-25").get_data_frames()[0]
    ], ignore_index=True)

    games["GAME_DATE"] = pd.to_datetime(games["GAME_DATE"])
    today_games = games[games["GAME_DATE"].dt.date == pd.Timestamp(today).date()]

    return list(set(today_games["TEAM_ID"].tolist() + today_games["OPPONENT_TEAM_ID"].tolist()))



def get_top5(team_id):
    roster = CommonTeamRoster(team_id=team_id).get_data_frames()[1]
    roster = roster.sort_values("MIN", ascending=False)
    return roster["PLAYER_ID"].head(5).tolist()


####################################################
# LOGS + HIT-RATE CALC
####################################################
def get_logs(pid):
    cached = safe_cache_load(pid)
    if cached is not None and len(cached) >= NUM_GAMES:
        return cached.head(NUM_GAMES).copy()

    all_logs = pd.DataFrame()
    for season in SEASONS:
        gl = PlayerGameLog(player_id=pid, season=season, timeout=TIMEOUT)
        df = gl.get_data_frames()[0]
        df = df[df["MIN"] > 0]
        df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
        all_logs = pd.concat([all_logs, df], ignore_index=True)
        time.sleep(SLEEP)
        if len(all_logs) >= NUM_GAMES:
            break

    if all_logs.empty:
        return None

    all_logs.sort_values("GAME_DATE", ascending=False, inplace=True)
    safe_cache_save(pid, all_logs)
    return all_logs.head(NUM_GAMES).copy()


def best_line(df, stat):
    total = len(df)
    if total < NUM_GAMES:
        return None

    for lvl in THRESHOLDS[stat]:
        hits = (df[stat] >= lvl).sum()
        rate = hits / total
        if rate >= 0.80:
            return lvl, hits, rate
        break
    return None


####################################################
# MAIN LOGIC
####################################################
def main():
    team_ids = get_today_team_ids()
    if not team_ids:
        print("No NBA games today.")
        return

    pool = []
    for tid in team_ids:
        pool.extend(get_top5(tid))
    pool = list(set(pool))

    results = {cat: {"safety": [], "value": []} for cat in CAT_ORDER}

    for pid in tqdm(pool, desc="Analyzing starters"):
        df = get_logs(pid)
        if df is None or len(df) < NUM_GAMES: continue

        p = players.find_player_by_id(pid)
        if not p: continue

        name = p["full_name"]

        for cat in CAT_ORDER:
            res = best_line(df, cat)
            if not res: continue
            lvl, hits, rate = res
            pct = int(rate * 100)

            rec = f"{name} {lvl}+ {CAT_LABEL[cat]}: {hits}/{NUM_GAMES} ({pct}%)"

            if pct >= 90:
                results[cat]["safety"].append(rec)
            else:
                results[cat]["value"].append(rec)

    print("\n✅ High-Confidence Prop Trends\n")

    for cat in CAT_ORDER:
        label = CAT_LABEL[cat]

        # Safety Tier
        if results[cat]["safety"]:
            print(f"🔥 {label} — SAFETY (90%+)\n")
            for r in results[cat]["safety"]:
                print("  " + r)
            print()

        # Value Tier
        if results[cat]["value"]:
            print(f"💰 {label} — VALUE (80–89%)\n")
            for r in results[cat]["value"]:
                print("  " + r)
            print()


if __name__ == "__main__":
    main()
