import requests
import json

# ================================
# INSERT YOUR SGO API KEY HERE
# ================================
SGO_API_KEY = "7243468c02f981445249730c03b426c1"

# Sample: Pistons @ Hawks eventID – you can replace this dynamically
EVENT_ID = None   # auto-detects Drummond's game if left None

BASE_URL = "https://api.sgo-sports.com/api/v2/odds/match"


def fetch_sgo():
    """Pull SGO odds for all NBA games."""
    headers = {"x-api-key": SGO_API_KEY}
    url = BASE_URL + "?leagueID=NBA&sportID=BASKETBALL&limit=40"

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    return data["data"]


def find_drummond_event(events):
    """Return the event that contains Drummond rebounds."""
    for ev in events:
        for odd_id, odd in ev["odds"].items():
            if odd.get("statEntityID") == "ANDRE_DRUMMOND_1_NBA":
                return ev
    return None


def print_drummond_rebound_lines(event):
    odds = event["odds"]

    print("\n===============================")
    print("   DRUMMOND REBOUND LINES")
    print("===============================\n")

    found = False

    for odd_id, item in odds.items():
        if item["statID"] != "rebounds":
            continue
        if item["playerID"] != "ANDRE_DRUMMOND_1_NBA":
            continue

        found = True

        main_line = item.get("bookOverUnder")
        main_odds = item.get("bookOdds")

        print(f"Main Line: {main_line}+  @ {main_odds}   ({odd_id})")

        fd = item.get("byBookmaker", {}).get("fanduel", {})
        alt = fd.get("altLines", [])

        if alt:
            print("Alt Lines:")
            for a in alt:
                print(f"  {a['overUnder']}+  @ {a['odds']}")
        else:
            print("No alt lines found.")

        print()

    if not found:
        print("❌ No Drummond rebound markets found.")


def main():
    events = fetch_sgo()

    global EVENT_ID

    # Auto-detect event if user didn’t provide ID
    if EVENT_ID is None:
        event = find_drummond_event(events)
    else:
        event = next((ev for ev in events if ev["eventID"] == EVENT_ID), None)

    if not event:
        print("❌ Could not find Drummond event in SGO feed.")
        return

    print(f"Event found: {event['teams']['away']['names']['short']} @ "
          f"{event['teams']['home']['names']['short']}")

    print_drummond_rebound_lines(event)


if __name__ == "__main__":
    main()
