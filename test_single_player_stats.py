from nba_api.stats.endpoints import PlayerGameLog
from nba_api.stats.static import players
import pandas as pd
import time

PLAYER_NAME = "Cade Cunningham"
NUM_GAMES = 10

# Lookup player info
player_list = players.get_players()
player = next((p for p in player_list if p['full_name'] == PLAYER_NAME), None)

player_id = player["id"]
print(f"✅ Player: {PLAYER_NAME} (ID: {player_id})")

# Fetch both Regular Season + Playoffs for two seasons
seasons = ["2024-25", "2025-26"]
season_types = ["Regular Season", "Playoffs"]

all_logs = pd.DataFrame()

for season in seasons:
    for stype in season_types:
        print(f"📡 Fetching {stype} — {season}...")
        logs = PlayerGameLog(player_id=player_id,
                             season=season,
                             season_type_all_star=stype).get_data_frames()[0]
        all_logs = pd.concat([all_logs, logs], ignore_index=True)
        time.sleep(0.6)

# Clean + Sort
all_logs["GAME_DATE"] = pd.to_datetime(all_logs["GAME_DATE"])
all_logs = all_logs[["GAME_DATE", "MATCHUP", "MIN", "PTS", "REB", "AST", "FG3M"]]
all_logs.sort_values("GAME_DATE", ascending=False, inplace=True)

# Choose most recent games
df = all_logs.head(NUM_GAMES).copy()
df.rename(columns={"FG3M": "3PM"}, inplace=True)

print("\n📊 Correct Most Recent Games (Reg + Playoffs Mixed):\n")
print(df.to_string(index=False))
