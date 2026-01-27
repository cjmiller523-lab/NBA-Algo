#!/usr/bin/env python3
"""
Tennis Player Stats Predictor
Scrapes player match history from Tennis Explorer and predicts stats for upcoming matches.
Tracks: aces, total games, total sets, tiebreaks won, etc.
"""

import os
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================================
# CONFIG
# ==========================================================
CACHE_DIR = "tennis_cache"
PLAYERS_DIR = os.path.join(CACHE_DIR, "players")
os.makedirs(PLAYERS_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
}

STATS_TO_TRACK = ["aces", "games", "sets", "tiebreaks", "double_faults", "winners"]
WINDOW = 25  # Last 25 matches

# Betting API Keys (set these from environment or config)
SGO_API_KEY = os.getenv("SGO_API_KEY", "d281b2722448cc5ca4b575f2d28352a9")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
TENNIS_API_KEY = os.getenv("TENNIS_API_KEY", "")

# ==========================================================
# SESSION MANAGEMENT (with retries)
# ==========================================================
def get_session():
    """Create requests session with retry logic"""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Better headers
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    })
    return session

# ==========================================================
# DATA MODELS
# ==========================================================
@dataclass
class MatchStats:
    """Single match statistics"""
    date: str
    opponent: str
    surface: str
    result: str  # "W" or "L"
    games_won: int
    games_lost: int
    sets_won: int
    sets_lost: int
    aces: int
    double_faults: int
    winners: int
    tiebreaks_won: int
    tiebreaks_lost: int
    
    @property
    def total_games(self):
        return self.games_won + self.games_lost
    
    @property
    def total_sets(self):
        return self.sets_won + self.sets_lost
    
    @property
    def total_tiebreaks(self):
        return self.tiebreaks_won + self.tiebreaks_lost
    
    @property
    def win(self):
        return self.result == "W"

@dataclass
class PlayerStatsAvg:
    """Aggregated player statistics"""
    player: str
    matches: int
    avg_aces: float
    avg_games: float
    avg_sets: float
    avg_tiebreaks: float
    avg_double_faults: float
    avg_winners: float
    aces_std: float
    win_rate: float
    
    # By surface
    surface_stats: Dict[str, dict] = None

# ==========================================================
# NOTE: Sample data removed - using SGO API for live matches
# ==========================================================

# ===========================================================
def find_player_slug(player_name: str) -> Optional[str]:
    """Search Tennis Abstract for player and return slug"""
    try:
        session = get_session()
        
        # Try direct URL approach first (faster)
        # Tennis Abstract uses player names directly in URL usually
        slug = player_name.replace(" ", "").replace("-", "")
        test_url = f"https://www.tennisabstract.com/cgi-bin/player.cgi?p={slug}&f=ACareer"
        
        print(f"[DEBUG] Trying direct URL: {test_url}")
        r = session.get(test_url, timeout=15)
        
        if r.status_code == 200 and "Career" in r.text:
            print(f"[INFO] Found player slug: {slug}")
            return slug
        
        # Fallback: try with last name only
        last_name = player_name.split()[-1] if " " in player_name else player_name
        slug = last_name.replace("-", "")
        test_url = f"https://www.tennisabstract.com/cgi-bin/player.cgi?p={slug}&f=ACareer"
        
        print(f"[DEBUG] Trying fallback URL: {test_url}")
        r = session.get(test_url, timeout=15)
        
        if r.status_code == 200 and "Career" in r.text:
            print(f"[INFO] Found player slug: {slug}")
            return slug
        
        return None
    except Exception as e:
        print(f"[ERROR] Failed to find player slug for {player_name}: {e}")
        return None

def scrape_player_history(player_slug: str, max_matches: int = 50) -> List[MatchStats]:
    """Scrape player match history from Tennis Abstract"""
    matches = []
    
    try:
        session = get_session()
        
        # Career page with all matches
        url = f"https://www.tennisabstract.com/cgi-bin/player.cgi?p={player_slug}&f=ACareer"
        
        print(f"[DEBUG] Fetching: {url}")
        r = session.get(url, timeout=20)
        r.raise_for_status()
        
        # Try to read HTML tables
        from io import StringIO
        try:
            tables = pd.read_html(StringIO(r.text))
        except Exception as e:
            print(f"[ERROR] Failed to parse tables: {e}")
            return []
        
        if not tables:
            print("[WARNING] No tables found in player page")
            return []
        
        # Main match table is usually first or second
        main_table = None
        for table in tables:
            if "Date" in table.columns or "Rank" in table.columns:
                main_table = table
                break
        
        if main_table is None:
            main_table = tables[0] if tables else None
        
        if main_table is None:
            print("[WARNING] Could not identify main match table")
            return []
        
        print(f"[DEBUG] Found table with columns: {list(main_table.columns)}")
        print(f"[DEBUG] Table shape: {main_table.shape}")
        
        # Parse matches (limit to recent matches)
        count = 0
        for idx, row in main_table.iterrows():
            if count >= max_matches:
                break
            
            try:
                match = parse_match_row(row)
                if match:
                    matches.append(match)
                    count += 1
            except Exception as e:
                # Skip malformed rows
                continue
        
        print(f"[INFO] Scraped {len(matches)} matches for {player_slug}")
        return matches[:max_matches]
        
    except Exception as e:
        print(f"[ERROR] Failed to scrape player history: {e}")
        return []

def parse_match_row(row) -> Optional[MatchStats]:
    """Parse a single match row from Tennis Abstract table"""
    try:
        # Extract available fields (column names vary)
        cols = {str(c).lower(): v for c, v in row.items()}
        
        # Required fields
        date = str(cols.get('date', '')).strip()
        if not date or date == 'nan':
            return None
        
        # Parse result (e.g., "d. Djokovic 7-6 6-3")
        result_str = str(cols.get('res.', cols.get('result', ''))).strip()
        if not result_str or result_str == 'nan':
            return None
        
        # Determine win/loss
        result = "W" if result_str.startswith("d.") else "L"
        
        # Extract opponent name (after d. or l.)
        opponent = result_str[2:].split()[0] if len(result_str) > 2 else "Unknown"
        
        # Parse scores (e.g., "7-6 6-3")
        score_part = " ".join(result_str.split()[1:]) if len(result_str.split()) > 1 else ""
        games_won, games_lost, sets_won, sets_lost = parse_score(score_part, result)
        
        # Stats (may not all be available)
        aces = safe_int(cols.get('ace', cols.get('aces', 0)))
        double_faults = safe_int(cols.get('df', cols.get('double_faults', 0)))
        winners = safe_int(cols.get('win.', cols.get('winners', 0)))
        
        # Count tiebreaks from score
        tiebreaks_won, tiebreaks_lost = count_tiebreaks(score_part, result)
        
        # Surface
        surface = str(cols.get('surface', 'Unknown')).strip()
        
        return MatchStats(
            date=date,
            opponent=opponent,
            surface=surface,
            result=result,
            games_won=games_won,
            games_lost=games_lost,
            sets_won=sets_won,
            sets_lost=sets_lost,
            aces=aces,
            double_faults=double_faults,
            winners=winners,
            tiebreaks_won=tiebreaks_won,
            tiebreaks_lost=tiebreaks_lost
        )
        
    except Exception as e:
        print(f"[ERROR] Failed to parse match row: {e}")
        return None

def parse_score(score_str: str, result: str) -> Tuple[int, int, int, int]:
    """
    Parse tennis score string.
    E.g., "7-6 6-3" -> (13, 9, 2, 0) if W
    Returns: (games_won, games_lost, sets_won, sets_lost)
    """
    try:
        sets = score_str.split()
        if not sets:
            return 0, 0, 0, 0
        
        games_won = 0
        games_lost = 0
        sets_won = 0
        sets_lost = 0
        
        for set_score in sets:
            if '-' not in set_score:
                continue
            
            parts = set_score.split('-')
            if len(parts) != 2:
                continue
            
            p1 = safe_int(parts[0])
            p2 = safe_int(parts[1])
            
            games_won += p1
            games_lost += p2
            
            if p1 > p2:
                sets_won += 1
            elif p2 > p1:
                sets_lost += 1
        
        # If result is loss, flip
        if result == "L":
            games_won, games_lost = games_lost, games_won
            sets_won, sets_lost = sets_lost, sets_won
        
        return games_won, games_lost, sets_won, sets_lost
        
    except Exception as e:
        return 0, 0, 0, 0

def count_tiebreaks(score_str: str, result: str) -> Tuple[int, int]:
    """Count tiebreaks from score string. Returns (won, lost)"""
    try:
        tiebreaks_won = 0
        tiebreaks_lost = 0
        
        sets = score_str.split()
        for set_score in sets:
            if '-' not in set_score:
                continue
            
            parts = set_score.split('-')
            if len(parts) != 2:
                continue
            
            p1 = safe_int(parts[0])
            p2 = safe_int(parts[1])
            
            # Tiebreak if 7-6 or similar
            if (p1 == 7 and p2 == 6) or (p1 == 6 and p2 == 7):
                if p1 > p2:
                    tiebreaks_won += 1
                else:
                    tiebreaks_lost += 1
        
        # If result is loss, flip
        if result == "L":
            tiebreaks_won, tiebreaks_lost = tiebreaks_lost, tiebreaks_won
        
        return tiebreaks_won, tiebreaks_lost
        
    except:
        return 0, 0

def safe_int(val) -> int:
    """Safely convert to int"""
    try:
        return int(float(str(val).strip()))
    except:
        return 0

# ==========================================================
# CACHE MANAGEMENT
# ==========================================================
def get_player_cache_path(player: str) -> str:
    """Get cache file path for player"""
    return os.path.join(PLAYERS_DIR, player.replace(" ", "_").replace("/", "_") + ".json")

def load_player_cache(player: str) -> Optional[List[MatchStats]]:
    """Load player stats from cache"""
    path = get_player_cache_path(player)
    if not os.path.exists(path):
        return None
    
    try:
        with open(path) as f:
            data = json.load(f)
        
        matches = [MatchStats(**m) for m in data]
        print(f"[INFO] Loaded {len(matches)} cached matches for {player}")
        return matches
    except Exception as e:
        print(f"[ERROR] Failed to load cache for {player}: {e}")
        return None

def save_player_cache(player: str, matches: List[MatchStats]):
    """Save player stats to cache"""
    path = get_player_cache_path(player)
    try:
        with open(path, "w") as f:
            json.dump([asdict(m) for m in matches], f, indent=2)
        print(f"[INFO] Cached {len(matches)} matches for {player}")
    except Exception as e:
        print(f"[ERROR] Failed to save cache for {player}: {e}")

# ==========================================================
# TODAY'S MATCHES (from various sources)
# ==========================================================
def get_todays_matches() -> List[Tuple[str, str]]:
    """
    Get today's tennis matches from SGO API (primary source).
    
    Uses Sports Game Odds API with user's SGO API key.
    If SGO fails, tries RapidAPI, then ESPN scraping.
    
    Returns:
        List of (player1, player2) tuples from today's matches
    """
    try:
        session = get_session()
        
        print("[INFO] Fetching today's tennis matches...")
        
        # PRIMARY: Try SGO API (user's preferred source)
        sgo_key = os.environ.get('SGO_API_KEY')
        if sgo_key:
            try:
                matches = get_sgo_matches(session, sgo_key)
                if matches:
                    print(f"[SUCCESS] Found {len(matches)} matches from SGO API")
                    return matches
            except Exception as e:
                print(f"[WARNING] SGO API failed: {str(e)[:60]}")
        else:
            print("[WARNING] SGO_API_KEY environment variable not set")
        
        # SECONDARY: Try RapidAPI if key is available
        rapidapi_key = os.environ.get('RAPIDAPI_KEY')
        if rapidapi_key:
            try:
                matches = get_rapidapi_matches(session, rapidapi_key)
                if matches:
                    print(f"[INFO] Found {len(matches)} matches from RapidAPI")
                    return matches
            except Exception as e:
                print(f"[DEBUG] RapidAPI failed: {str(e)[:40]}")
        
        # TERTIARY: Try ESPN web scraping
        try:
            print("[INFO] Trying ESPN scraping...")
            url = "https://www.espn.com/tennis/schedule"
            r = session.get(url, timeout=15)
            if r.status_code == 200:
                matches = parse_espn_tennis_schedule(r.text)
                if matches:
                    print(f"[INFO] Found {len(matches)} matches on ESPN")
                    return matches
        except Exception as e:
            print(f"[DEBUG] ESPN scraping failed: {str(e)[:40]}")
        
        # FALLBACK: Return empty list (no sample data)
        print("[ERROR] No matches found from any source. Live data source required.")
        return []
        
    except Exception as e:
        print(f"[ERROR] Unexpected error fetching matches: {e}")
        return []

def get_rapidapi_matches(session, api_key: str) -> List[Tuple[str, str]]:
    """
    Get matches from RapidAPI Tennis Endpoint.
    Requires RAPIDAPI_KEY environment variable.
    
    Sign up at: https://rapidapi.com/api-sports/api/api-tennis
    """
    try:
        url = "https://api-tennis.p.rapidapi.com/matches"
        headers = {
            'X-RapidAPI-Key': api_key,
            'X-RapidAPI-Host': 'api-tennis.p.rapidapi.com'
        }
        params = {
            'date': __import__('datetime').date.today().isoformat(),
            'league_id': 1  # Grand Slams and majors
        }
        
        r = session.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        
        data = r.json()
        matches = []
        
        for match in data.get('response', []):
            try:
                p1 = match.get('players', [{}])[0].get('name')
                p2 = match.get('players', [{}])[1].get('name') if len(match.get('players', [])) > 1 else None
                if p1 and p2:
                    matches.append((str(p1).title(), str(p2).title()))
            except:
                continue
        
        return matches
    except Exception as e:
        print(f"[DEBUG] RapidAPI parse error: {e}")
        return []

def get_sgo_matches(session, api_key: str) -> List[Tuple[str, str]]:
    """
    Get TODAY'S tennis matches from Sports Game Odds API.
    
    API: https://sgo.click/ (Sports Game Odds)
    Your API Key: d281b2722448cc5ca4b575f2d28352a9
    
    Returns:
        List of (player1, player2) tuples for today's tennis matches
    """
    try:
        from datetime import datetime, timedelta
        
        print(f"[DEBUG] SGO API call with key: {api_key[:10]}...")
        
        # Try multiple SGO endpoints
        endpoints = [
            "https://api.sgo.click/api/v3/matches/today",
            "https://api.sgo.click/api/v3/matches",
            "https://api.sgo.click/api/v2/matches",
        ]
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        for endpoint in endpoints:
            try:
                print(f"[DEBUG] Trying endpoint: {endpoint}")
                
                # Build params based on endpoint
                if "today" in endpoint:
                    params = {
                        'apikey': api_key,
                        'sport': 'tennis'
                    }
                else:
                    params = {
                        'apikey': api_key,
                        'sport': 'tennis',
                        'date': today
                    }
                
                r = session.get(endpoint, params=params, timeout=12)
                
                if r.status_code == 404:
                    print(f"[DEBUG] Endpoint not found: {endpoint}")
                    continue
                
                if r.status_code != 200:
                    print(f"[DEBUG] Status {r.status_code} from {endpoint}")
                    continue
                
                data = r.json()
                print(f"[DEBUG] Got response from {endpoint}: {str(data)[:100]}...")
                
                matches = []
                
                # Parse response based on structure
                matches_list = data.get('matches', data.get('data', []))
                
                if isinstance(matches_list, list):
                    for match in matches_list:
                        try:
                            # Handle different response formats
                            p1 = match.get('player1') or match.get('home') or match.get('competitors', [{}])[0].get('name')
                            p2 = match.get('player2') or match.get('away') or match.get('competitors', [{}])[1].get('name') if len(match.get('competitors', [])) > 1 else None
                            
                            if p1 and p2:
                                # Clean player names
                                p1 = clean_player_name(str(p1))
                                p2 = clean_player_name(str(p2))
                                
                                if p1 and p2:
                                    matches.append((p1, p2))
                                    print(f"[DEBUG] Found match: {p1} vs {p2}")
                        except Exception as e:
                            continue
                
                if matches:
                    print(f"[SUCCESS] Parsed {len(matches)} tennis matches from SGO")
                    return matches
                    
            except Exception as e:
                print(f"[DEBUG] Error trying {endpoint}: {str(e)[:60]}")
                continue
        
        print("[WARNING] SGO API: Could not fetch matches from any endpoint")
        return []
        
    except Exception as e:
        print(f"[ERROR] SGO API error: {e}")
        import traceback
        traceback.print_exc()
        return []

def parse_espn_tennis_schedule(html: str) -> List[Tuple[str, str]]:
    """
    Parse ESPN tennis schedule page for today's/upcoming matches.
    Uses regex and text patterns to extract player names.
    """
    try:
        import re
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, 'html.parser')
        matches = []
        
        # Get all text from the page
        all_text = soup.get_text()
        lines = all_text.split('\n')
        
        # Look for lines with "vs" pattern
        for line in lines:
            line = line.strip()
            
            # Skip irrelevant lines
            if len(line) < 5:
                continue
            if any(x in line.lower() for x in ['time', 'score', 'results', 'rankings', 'latest']):
                continue
            
            # Look for "vs" pattern
            if ' vs ' in line.lower() or ' v ' in line.lower():
                # Split on vs/v
                parts = re.split(r'\s+v(?:s)?\s+', line, flags=re.IGNORECASE, maxsplit=1)
                
                if len(parts) == 2:
                    p1 = clean_player_name(parts[0])
                    p2 = clean_player_name(parts[1])
                    
                    # Validate names
                    if (p1 and p2 and len(p1) > 2 and len(p2) > 2 and 
                        p1.count(' ') <= 2 and p2.count(' ') <= 2):
                        matches.append((p1.title(), p2.title()))
        
        # Remove duplicates
        seen = set()
        unique = []
        for m in matches:
            if m not in seen:
                seen.add(m)
                unique.append(m)
        
        return unique[:10]
        
    except Exception as e:
        print(f"[DEBUG] ESPN parse error: {e}")
        return []

def clean_player_name(name: str) -> str:
    """Clean and normalize player name from text"""
    import re
    
    name = str(name).strip()
    
    # Remove ranking numbers
    name = re.sub(r'^[\d]+\s*', '', name)
    
    # Remove parentheses content
    name = re.sub(r'\s*\(.*?\)', '', name)
    name = re.sub(r'\s*\[.*?\]', '', name)
    
    # Remove common noise words
    noise = ['match', 'vs', 'v', 'schedule', 'time', 'date', 'court', 'round', 'final', 
             'semi', 'game', 'live', 'score', 'est', 'utc', 'gmt', 'pst', 'cet', 'rank']
    for word in noise:
        name = re.sub(r'\b' + word + r'\b', '', name, flags=re.IGNORECASE)
    
    # Clean extra whitespace
    name = ' '.join(name.split())
    
    return name.strip()

def get_sample_matches() -> List[Tuple[str, str]]:
    """
    DEPRECATED: Sample data removed. System requires live SGO API key.
    
    To use this system, set your SGO API key:
    export SGO_API_KEY="d281b2722448cc5ca4b575f2d28352a9"
    
    Returns: Empty list (no fallback to sample data)
    """
    print("[WARNING] Sample data disabled. Please provide SGO_API_KEY for live tennis matches.")
    return []

# ==========================================================
# BETTING API INTEGRATION
# ==========================================================
def get_matches_from_sgo() -> List[Dict]:
    """
    Fetch today's tennis matches from Sports Game Odds API.
    Free tier: 50 requests/month
    """
    try:
        session = get_session()
        
        url = "https://api.sportsgameodds.com/v2/events"
        params = {
            "apiKey": SGO_API_KEY,
            "sport": "tennis",
            "limit": 50
        }
        
        print("[DEBUG] Fetching matches from SGO API...")
        r = session.get(url, params=params, timeout=15)
        
        if r.status_code == 200:
            data = r.json()
            matches = []
            
            for event in data.get("events", []):
                if event.get("sport") == "tennis":
                    participant1 = event.get("participants", [{}])[0].get("name", "")
                    participant2 = event.get("participants", [{}])[1].get("name", "") if len(event.get("participants", [])) > 1 else ""
                    
                    if participant1 and participant2:
                        matches.append({
                            "player1": participant1,
                            "player2": participant2,
                            "odds": event.get("odds", {}),
                            "start_time": event.get("start_time", "")
                        })
            
            print(f"[INFO] Found {len(matches)} matches from SGO API")
            return matches
        else:
            print(f"[WARNING] SGO API returned status {r.status_code}")
            return []
        
    except Exception as e:
        print(f"[ERROR] Failed to fetch from SGO API: {e}")
        return []

def get_matches_from_rapidapi() -> List[Dict]:
    """
    Fetch tennis matches from RapidAPI's Tennis API.
    Requires: RAPIDAPI_KEY environment variable
    """
    if not RAPIDAPI_KEY:
        print("[WARNING] RAPIDAPI_KEY not set. Set it with: export RAPIDAPI_KEY=your_key")
        return []
    
    try:
        session = get_session()
        
        url = "https://api-tennis.p.rapidapi.com/events"
        params = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timezone": "America/New_York"
        }
        
        headers = session.headers.copy()
        headers.update({
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "api-tennis.p.rapidapi.com"
        })
        
        print("[DEBUG] Fetching matches from RapidAPI...")
        r = session.get(url, params=params, headers=headers, timeout=15)
        
        if r.status_code == 200:
            data = r.json()
            matches = []
            
            for event in data.get("response", []):
                match_info = event.get("match", {})
                
                player1 = match_info.get("player1", {}).get("name", "")
                player2 = match_info.get("player2", {}).get("name", "")
                
                if player1 and player2:
                    matches.append({
                        "player1": player1,
                        "player2": player2,
                        "status": event.get("status", ""),
                        "odds": event.get("odds", {}),
                        "tournament": match_info.get("tournament", "")
                    })
            
            print(f"[INFO] Found {len(matches)} matches from RapidAPI")
            return matches
        else:
            print(f"[WARNING] RapidAPI returned status {r.status_code}")
            return []
        
    except Exception as e:
        print(f"[ERROR] Failed to fetch from RapidAPI: {e}")
        return []

def get_live_matches(source: str = "sample") -> List[Tuple[str, str]]:
    """
    Get live tennis matches from specified source.
    Sources: 'sample', 'sgo', 'rapidapi'
    """
    if source == "sgo":
        matches_data = get_matches_from_sgo()
        return [(m["player1"], m["player2"]) for m in matches_data]
    
    elif source == "rapidapi":
        matches_data = get_matches_from_rapidapi()
        return [(m["player1"], m["player2"]) for m in matches_data]
    
    else:  # Default to sample
        return get_todays_matches()

# ==========================================================
# MATCHUP PREDICTION
# ==========================================================
def predict_matchup(player1: str, player2: str, surface: str = "Hard") -> Dict:
    """
    Predict match outcome between two players.
    Returns prediction with confidence levels.
    """
    
    print(f"\n[INFO] Analyzing matchup: {player1} vs {player2}")
    
    # Get stats for both players
    stats1 = predict_player_stats(player1, surface=surface)
    stats2 = predict_player_stats(player2, surface=surface)
    
    if not stats1 or not stats2:
        return {}
    
    prediction = {
        "matchup": f"{player1} vs {player2}",
        "surface": surface,
        "player1": player1,
        "player2": player2,
    }
    
    # Extract stats - prefer surface-specific if available
    p1_stats = stats1.get("overall", {})
    p2_stats = stats2.get("overall", {})
    
    # Check for surface-specific stats
    if "surface_specific" in stats1:
        surf_keys = stats1["surface_specific"].keys()
        for key in surf_keys:
            if surface.lower() in key.lower():
                # Found surface-specific stats
                p1_stats = {}
                for sk in surf_keys:
                    if surface.lower() in sk.lower():
                        # Map back to standard names
                        stat_name = sk.replace(surface + "_", "").replace(surface.lower() + "_", "")
                        p1_stats[stat_name] = stats1["surface_specific"][sk]
                break
    
    if "surface_specific" in stats2:
        surf_keys = stats2["surface_specific"].keys()
        for key in surf_keys:
            if surface.lower() in key.lower():
                # Found surface-specific stats
                p2_stats = {}
                for sk in surf_keys:
                    if surface.lower() in sk.lower():
                        # Map back to standard names
                        stat_name = sk.replace(surface + "_", "").replace(surface.lower() + "_", "")
                        p2_stats[stat_name] = stats2["surface_specific"][sk]
                break
    
    # Calculate win probability based on multiple factors
    win_prob_1 = calculate_win_probability(p1_stats, p2_stats)
    win_prob_2 = 1.0 - win_prob_1
    
    prediction.update({
        "player1_stats": {
            "avg_aces": p1_stats.get("avg_aces", 0),
            "avg_games": p1_stats.get("avg_games", p1_stats.get("avg_total_games", 0)),
            "avg_sets": p1_stats.get("avg_sets", p1_stats.get("avg_total_sets", 0)),
            "win_rate": p1_stats.get("win_rate", 0),
        },
        "player2_stats": {
            "avg_aces": p2_stats.get("avg_aces", 0),
            "avg_games": p2_stats.get("avg_games", p2_stats.get("avg_total_games", 0)),
            "avg_sets": p2_stats.get("avg_sets", p2_stats.get("avg_total_sets", 0)),
            "win_rate": p2_stats.get("win_rate", 0),
        },
        "prediction": {
            "favorite": player1 if win_prob_1 > 0.5 else player2,
            "win_probability_p1": round(win_prob_1, 3),
            "win_probability_p2": round(win_prob_2, 3),
            "confidence": round(max(win_prob_1, win_prob_2) * 100, 1),
        }
    })
    
    return prediction

def calculate_win_probability(stats1: Dict, stats2: Dict) -> float:
    """Calculate win probability for player 1 based on stats"""
    
    # Weight factors
    factors = []
    weights = []
    
    # Win rate (40% weight)
    wr1 = stats1.get("win_rate", 0.5)
    wr2 = stats2.get("win_rate", 0.5)
    if wr1 + wr2 > 0:
        factors.append(wr1 / (wr1 + wr2))
        weights.append(0.40)
    
    # Ace difference (serve advantage) (25% weight)
    aces1 = stats1.get("avg_aces", 10)
    aces2 = stats2.get("avg_aces", 10)
    if aces1 + aces2 > 0:
        factors.append(aces1 / (aces1 + aces2))
        weights.append(0.25)
    
    # Game performance (winners vs games played) (20% weight)
    games1 = stats1.get("avg_total_games", stats1.get("avg_games", 20))
    games2 = stats2.get("avg_total_games", stats2.get("avg_games", 20))
    winners1 = stats1.get("avg_winners", 40)
    winners2 = stats2.get("avg_winners", 40)
    
    if games1 > 0 and games2 > 0:
        efficiency1 = winners1 / games1
        efficiency2 = winners2 / games2
        if efficiency1 + efficiency2 > 0:
            factors.append(efficiency1 / (efficiency1 + efficiency2))
            weights.append(0.20)
    
    # Consistency (lower double faults is better) (15% weight)
    df1 = stats1.get("avg_double_faults", 3)
    df2 = stats2.get("avg_double_faults", 3)
    consistency1 = 1 / (1 + df1)
    consistency2 = 1 / (1 + df2)
    if consistency1 + consistency2 > 0:
        factors.append(consistency1 / (consistency1 + consistency2))
        weights.append(0.15)
    
    # Calculate weighted probability
    if not factors:
        return 0.5
    
    weighted_sum = sum(f * w for f, w in zip(factors, weights))
    total_weight = sum(weights)
    
    return weighted_sum / total_weight if total_weight > 0 else 0.5

# ==========================================================
def aggregate_stats(matches: List[MatchStats], window: int = None) -> PlayerStatsAvg:
    """Aggregate player statistics"""
    if not matches:
        return None
    
    # Use last N matches
    if window:
        matches = matches[-window:]
    
    player = matches[0].opponent if matches else "Unknown"
    
    aces = [m.aces for m in matches]
    games = [m.total_games for m in matches]
    sets = [m.total_sets for m in matches]
    tiebreaks = [m.total_tiebreaks for m in matches]
    dfs = [m.double_faults for m in matches]
    winners = [m.winners for m in matches]
    wins = sum(1 for m in matches if m.win)
    
    import statistics
    
    return PlayerStatsAvg(
        player=player,
        matches=len(matches),
        avg_aces=statistics.mean(aces) if aces else 0,
        avg_games=statistics.mean(games) if games else 0,
        avg_sets=statistics.mean(sets) if sets else 0,
        avg_tiebreaks=statistics.mean(tiebreaks) if tiebreaks else 0,
        avg_double_faults=statistics.mean(dfs) if dfs else 0,
        avg_winners=statistics.mean(winners) if winners else 0,
        aces_std=statistics.stdev(aces) if len(aces) > 1 else 0,
        win_rate=wins / len(matches) if matches else 0
    )

def get_surface_stats(matches: List[MatchStats], surface: str) -> dict:
    """Get stats for specific surface"""
    surface_matches = [m for m in matches if m.surface.lower() == surface.lower()]
    if not surface_matches:
        return None
    
    stats = aggregate_stats(surface_matches)
    return {
        "matches": len(surface_matches),
        "avg_aces": stats.avg_aces,
        "avg_games": stats.avg_games,
        "avg_sets": stats.avg_sets,
        "win_rate": stats.win_rate
    }

# ==========================================================
# PREDICTIONS
# ==========================================================
def predict_player_stats(player: str, opponent: str = None, surface: str = None, use_cache: bool = True) -> Dict:
    """
    Predict player stats for upcoming match.
    Returns expected values for aces, games, sets, tiebreaks, etc.
    """
    
    # Try cache first
    matches = load_player_cache(player) if use_cache else None
    
    # Scrape if needed
    if not matches:
        print(f"[INFO] Scraping match history for {player}...")
        slug = find_player_slug(player)
        if not slug:
            print(f"[WARNING] Could not find player slug, checking sample data...")
            # Check sample data
            for key in SAMPLE_PLAYER_DATA:
                if key.lower() in player.lower():
                    matches = SAMPLE_PLAYER_DATA[key]
                    print(f"[INFO] Using sample data for {key}")
                    break
        else:
            matches = scrape_player_history(slug, max_matches=50)
        
        if not matches:
            print(f"[ERROR] No matches found for {player}")
            return {}
        
        save_player_cache(player, matches)
    
    # Aggregate stats (last 25 matches)
    overall = aggregate_stats(matches, window=WINDOW)
    
    prediction = {
        "player": player,
        "matches_analyzed": overall.matches,
        "overall": {
            "avg_aces": round(overall.avg_aces, 1),
            "avg_total_games": round(overall.avg_games, 1),
            "avg_total_sets": round(overall.avg_sets, 1),
            "avg_tiebreaks": round(overall.avg_tiebreaks, 1),
            "avg_double_faults": round(overall.avg_double_faults, 1),
            "avg_winners": round(overall.avg_winners, 1),
            "aces_std_dev": round(overall.aces_std, 1),
            "win_rate": round(overall.win_rate, 3)
        }
    }
    
    # Surface-specific stats
    if surface:
        surf_stats = get_surface_stats(matches, surface)
        if surf_stats:
            prediction["surface_specific"] = {
                f"{surface}_aces": round(surf_stats["avg_aces"], 1),
                f"{surface}_games": round(surf_stats["avg_games"], 1),
                f"{surface}_sets": round(surf_stats["avg_sets"], 1),
                f"{surface}_win_rate": round(surf_stats["win_rate"], 3)
            }
    
    return prediction

# ==========================================================
# MAIN
# ==========================================================
def main():
    """Example usage"""
    print("\n[INFO] Tennis Matchup Predictor")
    print("=" * 80)
    
    # Get today's matches
    print("\n[INFO] Fetching today's matches...")
    
    # Try to get from betting API, fallback to sample
    todays_matches = get_live_matches(source="sample")  # Change to "sgo" or "rapidapi" to use betting APIs
    
    if not todays_matches:
        print("[WARNING] No matches found for today, using default matchups")
        todays_matches = [
            ("Sinner", "Alcaraz"),
            ("Djokovic", "Medvedev"),
        ]
    
    print(f"[INFO] Found {len(todays_matches)} matches\n")
    
    # Predict each matchup
    predictions = []
    for player1, player2 in todays_matches:
        try:
            pred = predict_matchup(player1, player2, surface="Hard")
            if pred:
                predictions.append(pred)
        except Exception as e:
            print(f"[ERROR] Failed to predict {player1} vs {player2}: {e}")
        
        time.sleep(1)
    
    # Display predictions
    if predictions:
        print("\n" + "=" * 80)
        print("MATCHUP PREDICTIONS")
        print("=" * 80)
        
        for pred in predictions:
            if not pred:
                continue
            
            matchup = pred.get("matchup", "Unknown")
            surface = pred.get("surface", "Hard")
            
            # Get player names
            p1 = pred.get("player1", "Player 1")
            p2 = pred.get("player2", "Player 2")
            
            # Get stats from original predictions (they have all the data)
            stats1 = predict_player_stats(p1, surface=surface, use_cache=True)
            stats2 = predict_player_stats(p2, surface=surface, use_cache=True)
            
            print(f"\n{matchup} ({surface})")
            print("-" * 80)
            
            # Show overall stats
            if stats1 and "overall" in stats1:
                print(f"\n{p1}:")
                s1 = stats1["overall"]
                print(f"  Avg Aces: {s1.get('avg_aces', 0):.1f}")
                print(f"  Avg Games: {s1.get('avg_total_games', 0):.1f}")
                print(f"  Avg Sets: {s1.get('avg_total_sets', 0):.1f}")
                print(f"  Win Rate: {s1.get('win_rate', 0):.1%}")
            
            if stats2 and "overall" in stats2:
                print(f"\n{p2}:")
                s2 = stats2["overall"]
                print(f"  Avg Aces: {s2.get('avg_aces', 0):.1f}")
                print(f"  Avg Games: {s2.get('avg_total_games', 0):.1f}")
                print(f"  Avg Sets: {s2.get('avg_total_sets', 0):.1f}")
                print(f"  Win Rate: {s2.get('win_rate', 0):.1%}")
            
            forecast = pred.get("prediction", {})
            
            print(f"\n📊 PREDICTION:")
            favorite = forecast.get("favorite", "Unknown")
            p1_prob = forecast.get("win_probability_p1", 0)
            p2_prob = forecast.get("win_probability_p2", 0)
            confidence = forecast.get("confidence", 0)
            
            print(f"  Favorite: {favorite} ({p1_prob if favorite == p1 else p2_prob:.1%})")
            print(f"  Confidence: {confidence:.1f}%")
            print(f"  {p1} wins: {p1_prob:.1%}")
            print(f"  {p2} wins: {p2_prob:.1%}")

if __name__ == "__main__":
    main()
    
    # Example: Analyze a specific matchup directly
    print("\n\n" + "=" * 80)
    print("CUSTOM MATCHUP ANALYSIS (example)")
    print("=" * 80)
    
    custom_pred = predict_matchup("Sinner", "Alcaraz", surface="Clay")
    if custom_pred:
        forecast = custom_pred.get("prediction", {})
        p1 = custom_pred.get("player1", "P1")
        p2 = custom_pred.get("player2", "P2")
        print(f"\nOn Clay court:")
        print(f"  {p1} vs {p2}")
        print(f"  Favorite: {forecast.get('favorite', 'Unknown')} ({forecast.get('confidence', 0):.1f}% confidence)")
        print(f"  {p1} wins: {forecast.get('win_probability_p1', 0):.1%}")
        print(f"  {p2} wins: {forecast.get('win_probability_p2', 0):.1%}")
