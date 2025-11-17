import pandas as pd
import time
from datetime import datetime
from nba_api.stats.endpoints import ScoreboardV2, PlayerGameLog, TeamDetails
import warnings
warnings.filterwarnings("ignore")

NUM_GAMES = 10
MIN_MINUTES = 15
MIN_HIT_RATE = 0.80

THRESHOLDS = {
    "PTS": [30, 25, 20, 18, 15],
    "REB": [12, 10, 8, 6],
    "AST": [12, 10, 8, 6],
    "3PM": [4, 3, 2, 1],
    "STL": [3, 2, 1],
    "BLK": [3, 2, 1]
}

STAT_LABELS = {
    "PTS": "Points",
    "REB": "Rebounds",
    "AST": "Assists",
    "3PM": "3-Pointers",
    "STL": "Steals",
    "BLK": "Blocks"
}


def get_today_team_ids():
    today = datetime.today().strftime("%m/%d/%Y")
    print(f"\n📅 Checking NBA games for: {today}")
    
    sb = ScoreboardV2(game_date=today)
    games = sb.get_data_frames()[0]
    
    if games.empty:
        print("⚠ No NBA games scheduled for today.")
        return []
    
    print(f"Games found: {len(games)}")
    print(games[["GAME_DATE_EST", "HOME_TEAM_ID", "VISITOR_TEAM_ID"]])
    
    team_ids = list(set(games["HOME_TEAM_ID"].tolist() + games["VISITOR_TEAM_ID"].tolist()))
    return team_ids


from nba_api.stats.endpoints import CommonTeamRoster

def get_players_from_teams(team_ids):
    players_today = []
    print("\n🔍 Fetching rosters for today's teams...")

    for team_id in team_ids:
        try:
            data = CommonTeamRoster(team_id=team_id).get_data_frames()[0]
            for _, row in data.iterrows():
                players_today.append({
                    "id": row["PLAYER_ID"],
                    "name": row["PLAYER"]
                })
            time.sleep(0.4)
        except Exception as e:
            print(f"❌ Roster fetch failed for {team_id}: {e}")

    players_unique = {p["id"]: p for p in players_today}
    players_today = list(players_unique.values())

    print(f"✅ Players found: {len(players_today)}\n")
    return players_today



def get_player_logs(player_id, num_games=NUM_GAMES):
    print(f"\nFetching logs for player {player_id}...")

    seasons = ["2024-25", "2025-26"]
    season_types = ["Regular Season", "Playoffs"]

    all_logs = pd.DataFrame()

    for season in seasons:
        for stype in season_types:
            print(f"  ▶ Fetching {stype} — {season}")
            try:
                logs = PlayerGameLog(
                    player_id=player_id,
                    season=season,
                    season_type_all_star=stype
                ).get_data_frames()[0]

                logs["IS_PLAYOFF"] = (stype == "Playoffs")
                all_logs = pd.concat([all_logs, logs], ignore_index=True)

                time.sleep(0.4)

            except Exception as e:
                print(f"   ⚠ Error loading logs for {season} {stype}: {e}")

    if all_logs.empty:
        print("  ❌ No logs found for player")
        return all_logs

    # ✅ Clean & Sort
    all_logs['GAME_DATE'] = pd.to_datetime(all_logs['GAME_DATE'])
    all_logs.sort_values('GAME_DATE', ascending=False, inplace=True)

    # ✅ Select most recent games (mix reg + playoffs)
    df = all_logs.head(num_games).copy()
    df.rename(columns={"FG3M": "3PM"}, inplace=True)

    print(df[["GAME_DATE", "MATCHUP", "MIN", "PTS", "REB", "AST", "3PM", "IS_PLAYOFF"]])
    return df









def evaluate_trends(df):
    if df["MIN"].mean() < MIN_MINUTES:
        return None
    
    results = []

    for stat, lvls in THRESHOLDS.items():
        for lvl in lvls:
            hits = sum(df[stat] >= lvl)
            rate = hits / NUM_GAMES
            if rate >= MIN_HIT_RATE:
                results.append((stat, lvl, hits, int(rate * 100)))
                break

    return results


def main():
    team_ids = get_today_team_ids()



    if not team_ids:
        return
    
    players_today = get_players_from_teams(team_ids)

    final_results = []

    print("\n⚙ Analyzing prop trends...\n")

    for p in players_today:
        logs = get_player_logs(p["id"])
        if logs.empty:
            continue

        trends = evaluate_trends(logs)
        if trends:
            for stat, lvl, hits, pct in trends:
                final_results.append((p["name"], STAT_LABELS[stat], lvl, hits, pct))

    if not final_results:
        print("⚠ No high-confidence picks found at this moment. Try later closer to games.")
        return

    # Sort best first
    final_results.sort(key=lambda x: x[4], reverse=True)

    print("\n✅ High-Confidence Props (≥80% hit rate, last 10 games):\n")
    
    for name, stat, lvl, hits, pct in final_results[:40]:
        print(f"{name:<22} — {stat} {lvl}+  ✅ {pct}% ({hits}/{NUM_GAMES})")
    print(f"⏳ Processing: {p['name']}")


if __name__ == "__main__":
    main()
