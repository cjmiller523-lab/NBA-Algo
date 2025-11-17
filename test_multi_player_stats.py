from nba_api.stats.endpoints import ScoreboardV2, PlayerGameLog, CommonTeamRoster
from nba_api.stats.static import players, teams
import pandas as pd
import time
from datetime import date

# -----------------------------
# SETTINGS
# -----------------------------
NUM_GAMES = 10
SEASONS = ["2025-26", "2024-25"]
SEASON_TYPES = ["Regular Season", "Playoffs"]
HIT_RATE_CUTOFF = 70

POINT_THRESHOLDS = [10, 15, 20, 25, 30]
REB_THRESHOLDS   = [5, 7, 8, 10]
AST_THRESHOLDS   = [3, 5, 7, 8]

TODAY = date.today()


# -----------------------------
# FUNCTION: get recent logs
# -----------------------------
def get_recent_games(player_id):
    """Combine 2 seasons + playoffs and return the most recent 10 games."""
    all_logs = pd.DataFrame()

    for season in SEASONS:
        for stype in SEASON_TYPES:
            try:
                logs = PlayerGameLog(
                    player_id=player_id,
                    season=season,
                    season_type_all_star=stype
                ).get_data_frames()[0]
                all_logs = pd.concat([all_logs, logs], ignore_index=True)
                time.sleep(0.6)
            except Exception as e:
                pass

    if all_logs.empty:
        return pd.DataFrame()

    all_logs["GAME_DATE"] = pd.to_datetime(all_logs["GAME_DATE"])
    all_logs.sort_values("GAME_DATE", ascending=False, inplace=True)
    all_logs = all_logs[["GAME_DATE", "MATCHUP", "MIN", "PTS", "REB", "AST", "FG3M"]]
    return all_logs.head(NUM_GAMES)


def hit_rate(series, threshold):
    return (series >= threshold).mean() * 100


# -----------------------------
# STEP 1: Get today's games
# -----------------------------
scoreboard = ScoreboardV2(game_date=TODAY.strftime("%m/%d/%Y"))
games = scoreboard.game_header.get_data_frame()
line_df = scoreboard.line_score.get_data_frame()

if games.empty:
    print("No NBA games today.")
    exit()


# -----------------------------
# STEP 2: Loop through each game
# -----------------------------
for _, game in games.iterrows():
    game_id = game["GAME_ID"]
    teams_playing = line_df[line_df["GAME_ID"] == game_id]

    if len(teams_playing) < 2:
        continue

    away_team = teams_playing.iloc[0]["TEAM_ABBREVIATION"]
    home_team = teams_playing.iloc[1]["TEAM_ABBREVIATION"]

    print(f"\n🏀 {away_team}@{home_team} - Hit Rate Trends")
    print("-" * 60)

    for team_abbr in [away_team, home_team]:
        team_info = teams.find_teams_by_abbreviation(team_abbr)
        if not team_info:
            continue
        team_id = team_info[0]["id"]

        try:
            roster = CommonTeamRoster(team_id=team_id, season="2025-26").get_data_frames()[0]
        except:
            print(f"Could not fetch roster for {team_abbr}")
            continue

        # For now: take top 5 by minutes (approx starters)
        starters = roster.sort_values("MIN", ascending=False).head(5)
        print(f"\n{team_abbr} projected starters:")

        for _, player_row in starters.iterrows():
            player_name = player_row["PLAYER"]
            player_found = players.find_players_by_full_name(player_name)
            if not player_found:
                continue
            player_id = player_found[0]["id"]

            recent = get_recent_games(player_id)
            if recent.empty:
                continue

            # --- Calculate hit rates ---
            results = []
            for p in POINT_THRESHOLDS:
                rate = hit_rate(recent["PTS"], p)
                if rate >= HIT_RATE_CUTOFF:
                    results.append(f"{p}+ Points - {rate:.0f}%")

            for r in REB_THRESHOLDS:
                rate = hit_rate(recent["REB"], r)
                if rate >= HIT_RATE_CUTOFF:
                    results.append(f"{r}+ Rebounds - {rate:.0f}%")

            for a in AST_THRESHOLDS:
                rate = hit_rate(recent["AST"], a)
                if rate >= HIT_RATE_CUTOFF:
                    results.append(f"{a}+ Assists - {rate:.0f}%")

            if results:
                print(f"  {player_name}: " + ", ".join(results))
