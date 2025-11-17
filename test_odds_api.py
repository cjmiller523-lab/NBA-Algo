import requests, json

API_KEY = "73767ec5534de481bc1d7f15bb9ea4b5"
url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
params = {
    "apiKey": API_KEY,
    "regions": "us",
    "markets": "player_points",
    "bookmakers": "fanduel",
    "oddsFormat": "american"
}

resp = requests.get(url, params=params)
print("Status:", resp.status_code)
data = resp.json()
print("Events returned:", len(data))
print(json.dumps(data[:1], indent=2))  # preview first event
