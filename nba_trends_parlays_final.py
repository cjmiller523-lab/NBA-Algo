"""
NBA Trends → FanDuel Parlays (Debug, Alt Lines, Top 15)
------------------------------------------------------
• Auto-thresholds (>= 90% default), caching, FanDuel odds via The Odds API
• Fetches standard + alternate markets and prefers the HIGHEST alternate line
• Bench filter (skip players < 10 avg minutes)
• Skip trivial 1+ REB/AST/3PM props
• Builds Double (~+100) & Triple (~+200) parlays
• PDF report + console output
• Debug mode prints ONLY players with >=70% in any stat (clean), plus end summary
"""

import os
import time
import json
import unicodedata
import requests
import numpy as np
import pandas as pd
from itertools import combinations
from datetime import datetime, timedelta
from tqdm import tqdm

from nba_api.stats.endpoints import scoreboardv2, playergamelog, commonteamroster
from nba_api.stats.static import teams, players

# PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet


# =========================
# CONFIG
# =========================
CONFIG = {
    "SEASON": "2024-25",
    "NUM_GAMES_LOOKBACK": 20,       # wider sample helps early season
    "CONSISTENCY_THRESHOLD": 0.90,  # keepers for leg pool (90%)
    "DEBUG_MODE": True,
    "DEBUG_MIN_RATE": 0.70,         # show players with any stat >= 70%
    "API_SLEEP": 0.25,
    "CACHE_DIR": "cache",
    "OUTPUT_FILE": "output/trends_parlays_debug.pdf",
    "CACHE_EXPIRY_HOURS": 24,

    # Odds (FanDuel only)
    "ODDS_API_KEY": "73767ec5534de481bc1d7f15bb9ea4b5",
    "ODDS_SPORT_KEY": "basketball_nba",
    "ODDS_REGIONS": "us",
    "ODDS_BOOKMAKER": "fanduel",
    # Include standard + alternate markets (Odds API may omit _alt on free tier; we handle gracefully)
    "ODDS_MARKETS": [
        "player_points", "player_points_alt",
        "player_rebounds", "player_rebounds_alt",
        "player_assists", "player_assists_alt",
        "player_three_points", "player_three_points_alt"
    ],

    # Parlay targets (decimal odds)
    "DOUBLE_TARGET_DEC": 2.00,  # ≈ +100
    "DOUBLE_TOLERANCE": 0.20,
    "TRIPLE_TARGET_DEC": 3.00,  # ≈ +200
    "TRIPLE_TOLERANCE": 0.30,

    # Pool size — take the top 15 consistent legs to search combos
    "MAX_LEGS_POOL": 15,

    # Roster filter
    "MIN_MINUTES_AVG": 10
}

os.makedirs("output", exist_ok=True)
os.makedirs(CONFIG["CACHE_DIR"], exist_ok=True)


# =========================
# HELPERS
# =========================
def normalize_name(n: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', n) if unicodedata.category(c) != 'Mn').lower()

def american_to_decimal(american):
    try:
        a = int(american)
    except Exception:
        return None
    return 1 + (a/100.0) if a > 0 else 1 + (100.0/abs(a))

def cache_path(player_name):
    safe = player_name.replace(" ", "_").replace(".", "")
    return os.path.join(CONFIG["CACHE_DIR"], f"{safe}.json")

def is_cache_valid(path):
    if not os.path.exists(path):
        return False
    mod_time = datetime.fromtimestamp(os.path.getmtime(path))
    return datetime.now() - mod_time < timedelta(hours=CONFIG["CACHE_EXPIRY_HOURS"])

def save_cache(player_name, df):
    try:
        df.to_json(cache_path(player_name), orient="records", indent=2)
    except Exception:
        pass

def load_cache(player_name):
    try:
        with open(cache_path(player_name), "r") as f:
            data = json.load(f)
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()


# =========================
# NBA DATA
# =========================
def get_todays_games():
    today = datetime.now().strftime('%Y-%m-%d')
    sb = scoreboardv2.ScoreboardV2(game_date=today)
    games = sb.game_header.get_data_frame()
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

def get_team_roster_df(team_abbrev) -> pd.DataFrame:
    tinfo = next((t for t in teams.get_teams() if t["abbreviation"] == team_abbrev), None)
    if not tinfo:
        return pd.DataFrame(columns=["PLAYER", "MIN"])
    try:
        roster = commonteamroster.CommonTeamRoster(
            team_id=tinfo["id"], season=CONFIG["SEASON"]
        ).get_data_frames()[0]
        roster = roster[["PLAYER", "MIN"]].copy()
        roster["MIN"] = pd.to_numeric(roster["MIN"], errors="coerce").fillna(0)
        roster = roster[roster["MIN"] >= CONFIG["MIN_MINUTES_AVG"]]
        return roster.reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["PLAYER", "MIN"])

def get_last_n_games(player_name, num_games):
    # Use cached if fresh
    path = cache_path(player_name)
    if is_cache_valid(path):
        return load_cache(player_name).head(num_games)

    # Otherwise fetch
    all_players = players.get_players()
    match = next((p for p in all_players if normalize_name(p["full_name"]) == normalize_name(player_name)), None)
    if not match:
        return pd.DataFrame()

    for attempt in range(3):
        try:
            logs = playergamelog.PlayerGameLog(
                player_id=match["id"], season=CONFIG["SEASON"]
            ).get_data_frames()[0]
            # If early season, logs may be short; fall back to all-time for more rows
            if len(logs) < num_games:
                try:
                    logs = playergamelog.PlayerGameLog(
                        player_id=match["id"], season_all_time='Y'
                    ).get_data_frames()[0]
                except Exception:
                    pass
            save_cache(player_name, logs)
            return logs.head(num_games)
        except Exception:
            time.sleep(1.0 * (attempt + 1))
    return load_cache(player_name)


# =========================
# THRESHOLDS
# =========================
def calculate_auto_thresholds(df, min_rate=0.90):
    """
    Returns list of dicts for stats that meet min_rate:
      {"Stat","Threshold","RateValue","Hits","Total"}
    Skips trivial 1+ for REB/AST/FG3M.
    """
    results = []
    if df.empty:
        return results
    total = len(df)
    for stat in ["PTS", "REB", "AST", "FG3M"]:
        if stat not in df.columns:
            continue
        vals = df[stat].dropna().sort_values(ascending=False).tolist()
        if not vals:
            continue
        idx = int(min_rate * len(vals)) - 1
        if idx < 0:
            idx = 0
        threshold = int(np.floor(vals[idx]))
        hits = int((df[stat] >= threshold).sum())
        rate = hits / total if total else 0.0
        if rate >= min_rate and threshold > 0:
            if stat in ["REB", "AST", "FG3M"] and threshold <= 1:
                continue
            label = {"PTS": "points", "REB": "rebounds", "AST": "assists", "FG3M": "threes"}[stat]
            results.append({
                "Stat": label,
                "Threshold": threshold,
                "RateValue": rate,
                "Hits": hits,
                "Total": total
            })
    return results


# =========================
# ODDS (FanDuel via The Odds API)
# =========================
MARKET_FOR_STAT = {
    "points": ("player_points", "player_points_alt"),
    "rebounds": ("player_rebounds", "player_rebounds_alt"),
    "assists": ("player_assists", "player_assists_alt"),
    "threes": ("player_three_points", "player_three_points_alt")
}

def fetch_fanduel_player_props_today():
    """
    Light calls: 1 request per market key (8 total including _alt).
    Builds a lookup of both standard and alternate lines.

    lookup key:
      (player_lower, market_key, point_float, "over"|"under") -> {american, decimal, book}
    """
    api_key = CONFIG["ODDS_API_KEY"]
    if not api_key or api_key.startswith("REPLACE_"):
        print("⚠️  No Odds API key set. Skipping odds fetch.")
        return {}, set()

    base = "https://api.the-odds-api.com/v4/sports"
    sport = CONFIG["ODDS_SPORT_KEY"]
    markets = CONFIG["ODDS_MARKETS"]
    lookup = {}
    returned_markets = set()

    print("🔍 Fetching FanDuel odds (standard + alternate markets when available)...")
    for m in markets:
        url = f"{base}/{sport}/odds"
        params = {
            "apiKey": api_key,
            "regions": CONFIG["ODDS_REGIONS"],
            "markets": m,
            "oddsFormat": "american",
            "bookmakers": CONFIG["ODDS_BOOKMAKER"]
        }
        try:
            resp = requests.get(url, params=params, timeout=14)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"⚠️  Odds fetch failed for {m}: {e}")
            time.sleep(0.4)
            continue

        # Some responses include only events with no prop markets yet; guard for that
        got_any = False
        for ev in data:
            for bm in ev.get("bookmakers", []):
                # Accept either 'key' == fanduel or 'title' == FanDuel
                if CONFIG["ODDS_BOOKMAKER"] not in (bm.get("key",""), bm.get("title","").lower()):
                    continue
                for mk in bm.get("markets", []):
                    if mk.get("key") != m:
                        continue
                    for oc in mk.get("outcomes", []):
                        desc = str(oc.get("description","")).lower()
                        if desc != "over":  # only using over legs for "X+" style
                            continue
                        name = oc.get("name", "")
                        point = oc.get("point")
                        price = oc.get("price")
                        if not name or point is None or price is None:
                            continue
                        player_key = normalize_name(name)
                        dec = american_to_decimal(price)
                        if dec is None:
                            continue
                        lookup[(player_key, m, float(point), "over")] = {
                            "american": price,
                            "decimal": dec,
                            "book": "FanDuel"
                        }
                        got_any = True
        if got_any:
            returned_markets.add(m)
        time.sleep(0.35)

    missing_alt = [m for m in markets if m.endswith("_alt") and m not in returned_markets]
    if missing_alt:
        print("⚠️  Alternate markets not returned for:", ", ".join(missing_alt), "— using base props when needed.")

    return lookup, returned_markets

def stat_to_markets(stat_label):
    return MARKET_FOR_STAT.get(stat_label, (None, None))

def threshold_to_over_point(threshold):
    # map ">= threshold" → Over (threshold - 0.5) for standard; alt markets use whole numbers
    return float(threshold) - 0.5

def pick_highest_alt_or_best_standard(player, stat_label, threshold, odds_lookup, returned_markets):
    """
    Preference:
      1) If alt market exists for this stat and player, pick the HIGHEST alt line (point is integer ladder: 10, 15, 20...)
      2) Else fall back to standard Over (threshold-0.5) nearest line (bias towards <= target).
    Returns dict {point, american, decimal, book, used_market}
    """
    pkey = normalize_name(player)
    std_key, alt_key = stat_to_markets(stat_label)
    best = None

    # 1) Try alternates — choose HIGHEST
    if alt_key and alt_key in returned_markets:
        alts = [(pt, val) for (pk, mk, pt, side), val in odds_lookup.items()
                if pk == pkey and mk == alt_key and side == "over"]
        if alts:
            # Highest point wins
            alts.sort(key=lambda x: x[0], reverse=True)
            pt, val = alts[0]
            best = {
                "point": int(pt),  # alt ladders are integers like 10, 15, 20
                "american": val["american"],
                "decimal": val["decimal"],
                "book": val["book"],
                "used_market": alt_key
            }

    # 2) Fallback to standard Over near (threshold - 0.5)
    if not best and std_key and std_key in returned_markets:
        target_point = threshold_to_over_point(threshold)
        stds = [(pt, val) for (pk, mk, pt, side), val in odds_lookup.items()
                if pk == pkey and mk == std_key and side == "over"]
        if stds:
            # choose line closest to target; bias towards <= target (safer)
            stds.sort(key=lambda x: (abs(x[0] - target_point), 0 if x[0] <= target_point else 1))
            pt, val = stds[0]
            best = {
                "point": pt,
                "american": val["american"],
                "decimal": val["decimal"],
                "book": val["book"],
                "used_market": std_key
            }

    return best


# =========================
# PARLAY BUILDER
# =========================
def build_parlay_suggestions(legs, target_dec, tol, size):
    best = None
    domain = legs[:CONFIG["MAX_LEGS_POOL"]]
    if len(domain) < size:
        return None
    for combo in combinations(domain, size):
        product_dec = np.prod([l["odds"]["decimal"] for l in combo])
        product_prob = np.prod([l["rate"] for l in combo])  # naive independence
        ev = product_dec * product_prob
        if abs(product_dec - target_dec) <= tol:
            if not best or ev > best["ev"]:
                best = {"legs": combo, "decimal": product_dec, "ev": ev}
    if not best and domain:
        # pick closest even if not in band
        def dist(c): return abs(np.prod([l["odds"]["decimal"] for l in c]) - target_dec)
        closest = min(combinations(domain, size), key=dist)
        best = {
            "legs": closest,
            "decimal": np.prod([l["odds"]["decimal"] for l in closest]),
            "ev": np.prod([l["rate"] for l in closest]) * np.prod([l["odds"]["decimal"] for l in closest])
        }
    return best


# =========================
# PDF
# =========================
def save_pdf_report(rows, double_pick, triple_pick, raw_rows=None):
    styles = getSampleStyleSheet()
    story = []
    doc = SimpleDocTemplate(CONFIG["OUTPUT_FILE"], pagesize=letter)

    title = Paragraph(f"NBA Auto-Threshold Trends + Parlays — {datetime.now():%B %d, %Y}", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 10))

    # --- Helper: Parlay Table ---
    def parlay_table(title_txt, p):
        story.append(Paragraph(title_txt, styles['Heading2']))
        if not p:
            story.append(Paragraph("No suitable combination found.", styles['Normal']))
            story.append(Spacer(1, 10))
            return
        data = [["#", "Player", "Stat / Over", "Odds (Am)", "Dec", "Book"]]
        for i, leg in enumerate(p["legs"], 1):
            o = leg["odds"]
            data.append([
                i, leg["player"],
                f"{leg['stat']} Over {o['point']}",
                o["american"],
                f"{o['decimal']:.2f}",
                o["book"]
            ])
        data.append(["Combined", "", "", "", f"{p['decimal']:.2f}", ""])
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#002b5c")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ]))
        story.append(t)
        story.append(Spacer(1, 14))

    # --- Parlays ---
    parlay_table("Double-Up (~ +100)", double_pick)
    parlay_table("Triple-Up (~ +200)", triple_pick)

    # --- Consistent Players (>=90%) ---
    if rows:
        rows = sorted(rows, key=lambda x: x["RateValue"], reverse=True)
        story.append(Paragraph("Consistent Players (≥ 90%) — Top 15 Pool", styles['Heading2']))
        data = [["Player", "Team", "Stat", "Threshold", "Hit Rate"]]
        for r in rows[:CONFIG["MAX_LEGS_POOL"]]:
            data.append([
                r["Player"], r["Team"], r["Stat"],
                f"{r['Threshold']}+",
                f"{r['Hits']}/{r['Total']} ({r['RateValue']*100:.0f}%)"
            ])
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#003366")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ]))
        story.append(t)
        story.append(Spacer(1, 14))

    # --- Raw Trends (>=70%) ---
    if raw_rows:
        story.append(Paragraph("Raw Trends (≥70%) — For Debugging", styles['Heading2']))
        data = [["Player", "Team", "Stat", "Threshold", "Hit Rate"]]
        raw_rows = sorted(raw_rows, key=lambda x: x["RateValue"], reverse=True)
        for r in raw_rows:
            data.append([
                r["Player"], r["Team"], r["Stat"],
                f"{r['Threshold']}+",
                f"{r['Hits']}/{r['Total']} ({r['RateValue']*100:.0f}%)"
            ])
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#555555")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ]))
        story.append(t)

    doc.build(story)
    print(f"✅ PDF saved to {CONFIG['OUTPUT_FILE']}")
    try:
        os.startfile(os.path.abspath(CONFIG["OUTPUT_FILE"]))
    except Exception:
        pass



# =========================
# MAIN
# =========================
def main():
    games = get_todays_games()
    if not games:
        print("No NBA games today.")
        return

    print("📅 Today's Games:")
    for g in games:
        print(f"   {g['away_team']} @ {g['home_team']}")
    print(f"\nAnalyzing player consistency (last {CONFIG['NUM_GAMES_LOOKBACK']} games)...\n")

    consistent_rows = []
    # Debug stash
    debug_lines = []
    raw_rows = []

    for g in games:
        for team in [g["home_team"], g["away_team"]]:
            roster_df = get_team_roster_df(team)
            if roster_df.empty:
                continue
            print(f"🔍 {team}: analyzing {len(roster_df)} players...")

            team_debug = []

for _, row in tqdm(roster_df.iterrows(), total=len(roster_df), desc=f"{team}", leave=False):
    player = row["PLAYER"]
    avg_min = float(row["MIN"])
    logs = get_last_n_games(player, CONFIG["NUM_GAMES_LOOKBACK"])
    trends_90 = calculate_auto_thresholds(logs, CONFIG["CONSISTENCY_THRESHOLD"])
    trends_70 = calculate_auto_thresholds(logs, CONFIG["DEBUG_MIN_RATE"])

    # Collect raw trends (>=70%) for PDF debug table
    for t in trends_70:
        raw_rows.append({
            "Player": player,
            "Team": team,
            "Stat": t["Stat"],
            "Threshold": t["Threshold"],
            "RateValue": t["RateValue"],
            "Hits": t["Hits"],
            "Total": t["Total"]
        })

    # Debug print (>=70% only)
    if CONFIG["DEBUG_MODE"] and trends_70:
        lines = [f"📊 {player} (avg {avg_min:.1f} min)"]
        set90 = {(t["Stat"], t["Threshold"]) for t in trends_90}
        for t7 in trends_70:
            hit_str = f"{t7['Hits']}/{t7['Total']} ({t7['RateValue']*100:.0f}%)"
            mark = "✅" if (t7["Stat"], t7["Threshold"]) in set90 else "❌"
            lines.append(f"    {t7['Stat']} {t7['Threshold']}+ → {hit_str} {mark}")
        team_debug.append("\n".join(lines))


            if CONFIG["DEBUG_MODE"] and team_debug:
                print("\n".join(team_debug))
                print("—" * 60)

    if not consistent_rows:
        print("⚠️ No consistent players found (≥ 90%). Try lowering CONSISTENCY_THRESHOLD to 0.85.")
        save_pdf_report([], None, None)
        return

    # Sort and keep top 15 for odds/parlay search
    consistent_rows.sort(key=lambda x: x["RateValue"], reverse=True)
    consistent_rows = consistent_rows[:CONFIG["MAX_LEGS_POOL"]]

    # Fetch FanDuel odds (std + alt)
    odds_lookup, returned_markets = fetch_fanduel_player_props_today()

    # Build leg pool with odds (prefer HIGHEST alt)
    leg_pool = []
    for r in consistent_rows:
        best_line = pick_highest_alt_or_best_standard(
            r["Player"], r["Stat"], r["Threshold"], odds_lookup, returned_markets
        )
        if best_line and best_line.get("decimal"):
            leg_pool.append({
                "player": r["Player"],
                "team": r["Team"],
                "stat": r["Stat"],
                "threshold": r["Threshold"],
                "rate": r["RateValue"],
                "odds": {
                    "american": best_line["american"],
                    "decimal": best_line["decimal"],
                    "point": best_line["point"],
                    "book": best_line["book"],
                    "market": best_line["used_market"]
                }
            })

    # Parlay suggestions
    double_pick = build_parlay_suggestions(leg_pool, CONFIG["DOUBLE_TARGET_DEC"], CONFIG["DOUBLE_TOLERANCE"], 2)
    triple_pick = build_parlay_suggestions(leg_pool, CONFIG["TRIPLE_TARGET_DEC"], CONFIG["TRIPLE_TOLERANCE"], 3)

    # Console parlay print
    def print_parlay(tag, p):
        print(f"\n=== {tag} ===")
        if not p:
            print("No suitable combination found.")
            return
        for i, leg in enumerate(p["legs"], start=1):
            o = leg["odds"]
            print(f"{i}) {leg['player']} — {leg['stat']} Over {o['point']}  "
                  f"{o['book']} {o['american']}  (dec {o['decimal']:.2f})  | hit {int(leg['rate']*100)}%  "
                  f"[{o.get('market','')}]")
        print(f"Combined decimal: {p['decimal']:.2f}")

    print_parlay("Double-Up (~ +100)", double_pick)
    print_parlay("Triple-Up (~ +200)", triple_pick)

    # Console summary: Top 5 most consistent
    print("\n─────────────── SUMMARY: Top 5 Most Consistent (≥ 90%) ───────────────")
    for i, r in enumerate(sorted(consistent_rows, key=lambda x: x["RateValue"], reverse=True)[:5], start=1):
        print(f"{i}. {r['Player']} ({r['Team']}) — {r['Stat']} {r['Threshold']}+  "
              f"{r['Hits']}/{r['Total']} ({r['RateValue']*100:.0f}%)")

    # PDF
    save_pdf_report(consistent_rows, double_pick, triple_pick, raw_rows)
    print("\n✅ Done! Check the PDF and the console summary above.")


if __name__ == "__main__":
    main()
