"""
Odds API service for fetching live PrizePicks props.
Must hit a real HTTP endpoint; return empty on failure; NEVER return mock.
"""
import os
import requests
import time
from typing import List, Dict, Tuple, Any
import random
from django.conf import settings

BASE = getattr(settings, 'ODDS_API_BASE_URL', '')
KEY = getattr(settings, 'ODDS_API_KEY', '')
BOOK = getattr(settings, 'ODDS_API_BOOK', 'prizepicks')
ENABLED = getattr(settings, 'ODDS_API_ENABLED', False)


class OddsError(RuntimeError):
    """Custom exception for odds API errors"""
    pass


def _sleep_ms(ms: int) -> None:
    time.sleep(ms / 1000.0)


def _backoff_sleep(attempt: int) -> None:
    base = min(2000, 250 * (2 ** attempt))
    jitter = random.randint(0, 150)
    _sleep_ms(base + jitter)


def fetch_prizepicks_props_for_games(season: int, week: int, game_ids: List[str]) -> List[Dict]:
    """
    Fetch live player props for the specified games from the odds provider.
    
    NOTE: The Odds API only provides game-level odds (moneyline, spreads, totals), 
    not player props. This function returns empty for now as player props require
    a different API service (e.g., OpticOdds, or web scraping PrizePicks directly).
    
    Output rows:
      {game_id_sb, player_id, player_name, team, opp, prop_type, line_value, market, updated_at}
    """
    if not ENABLED or not BASE or not KEY:
        return []  # unavailable; caller will render 'unavailable'

    # The Odds API provides game-level odds, not player props
    # For player props, you would need a different service like:
    # - OpticOdds API (supports player props)
    # - Web scraping PrizePicks directly
    # - Other specialized sports betting APIs
    
    # This function is kept for backwards compatibility with parlay panel.
    # It now returns empty because real player props are exposed via /game/<id>/props.
    return []


def resolve_odds_event_id(game: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Resolve our internal game (home/away/kickoff) to Odds API event id.
    Strict normalization and ±10min tolerance.
    Returns (event_id, event_json).
    Raises OddsError if not found.
    """
    # Fetch current events index (consider caching per 60s at a higher layer)
    params = {"apiKey": KEY, "dateFormat": "iso", "regions": "us_dfs"}
    resp = requests.get(f"{BASE}/sports/americanfootball_nfl/events", params=params, timeout=8)
    if resp.status_code != 200:
        raise OddsError(f"events_index_http_{resp.status_code}")
    events = resp.json()

    def norm_team(t: str) -> str:
        t0 = (t or "").strip()
        # Accept both city/nickname and 2-3 letter abbreviations
        abbr_map = {
            "ARI": "cardinals", "ATL": "falcons", "BAL": "ravens", "BUF": "bills",
            "CAR": "panthers", "CHI": "bears", "CIN": "bengals", "CLE": "browns",
            "DAL": "cowboys", "DEN": "broncos", "DET": "lions", "GB": "packers", "GNB": "packers",
            "HOU": "texans", "IND": "colts", "JAX": "jaguars", "JAC": "jaguars",
            "KC": "chiefs", "KAN": "chiefs", "LA": "rams", "LAR": "rams", "LAC": "chargers",
            "MIA": "dolphins", "MIN": "vikings", "NE": "patriots", "NWE": "patriots",
            "NO": "saints", "NOR": "saints", "NYG": "giants", "NYJ": "jets",
            "PHI": "eagles", "PIT": "steelers", "SEA": "seahawks", "SF": "49ers", "SFO": "49ers",
            "TB": "buccaneers", "TAM": "buccaneers", "TEN": "titans", "WAS": "commanders",
        }
        if t0.upper() in abbr_map:
            return abbr_map[t0.upper()]
        t = t0.lower()
        repl = {
            "washington football team": "commanders",
            "washington": "commanders",
            "san francisco": "49ers",
            "new york giants": "giants",
            "new york jets": "jets",
            "tampa bay": "buccaneers",
            "green bay": "packers",
            "kansas city": "chiefs",
            "los angeles rams": "rams",
            "los angeles chargers": "chargers",
        }
        t = repl.get(t, t)
        t = t.replace(".", "").replace("-", " ")
        # If looks like "Carolina Panthers" → take last token as nickname
        parts = [p for p in t.split() if p]
        if len(parts) >= 2:
            return parts[-1]
        return t

    import pandas as pd
    kickoff = pd.to_datetime(game.get('kickoff'))

    candidates: List[Tuple[str, Dict[str, Any], float]] = []
    for ev in events:
        if norm_team(ev.get('home_team')) == norm_team(game.get('home_team')) and \
           norm_team(ev.get('away_team')) == norm_team(game.get('away_team')):
            ev_time = pd.to_datetime(ev.get('commence_time'))
            diff_min = abs((ev_time - kickoff).total_seconds()) / 60.0
            candidates.append((ev.get('id'), ev, diff_min))

    if not candidates:
        raise OddsError("odds_event_not_found")

    candidates.sort(key=lambda x: x[2])
    best = candidates[0]
    if best[2] > 10.0:
        raise OddsError("odds_event_not_found")
    return best[0], best[1]


def fetch_event_player_props(event_id: str, markets_csv: str) -> Dict[str, Any]:
    """Fetch player props for a specific event id from PrizePicks bookmaker.
    Retries with backoff on 429/5xx. Returns JSON dict.
    """
    attempt = 0
    headers = {}
    while True:
        params = {
            "apiKey": KEY,
            "regions": "us_dfs",
            "bookmakers": "prizepicks",
            "oddsFormat": "american",
            "markets": markets_csv,
        }
        resp = requests.get(f"{BASE}/sports/americanfootball_nfl/events/{event_id}/odds", params=params, timeout=8)
        status = resp.status_code
        if status == 200:
            return resp.json()
        if status in (429, 500, 502, 503, 504) and attempt < 4:
            # log headers without apiKey
            remaining = resp.headers.get('X-Requests-Remaining')
            used = resp.headers.get('X-Requests-Used')
            _backoff_sleep(attempt)
            attempt += 1
            continue
        raise OddsError(f"event_odds_http_{status}")


def parse_props_response(event_json: Dict[str, Any], markets_csv: str) -> List[Dict[str, Any]]:
    """Flatten Odds API response into UI-friendly markets with Over/Under pairs."""
    markets = []
    wanted = set([m.strip() for m in markets_csv.split(',') if m.strip()])
    bookmakers = [b for b in event_json if isinstance(event_json, list)]
    # The actual payload from event odds is a list of bookmakers; handle both shapes defensively
    payload = event_json
    if isinstance(event_json, dict):
        payload = event_json.get('bookmakers') or []
    if isinstance(event_json, list):
        payload = event_json

    pp = None
    for b in payload:
        if (b.get('key') or b.get('bookmaker_key')) == 'prizepicks':
            pp = b
            break
    if not pp:
        return markets

    last_update = pp.get('last_update') or pp.get('lastUpdate')
    for m in pp.get('markets', []):
        key = m.get('key')
        if wanted and key not in wanted:
            continue
        lines_map: Dict[str, Dict[str, Any]] = {}
        for outc in m.get('outcomes', []):
            player = outc.get('description')
            name = outc.get('name')
            entry = lines_map.setdefault(player, {"player": player, "over": None, "under": None})
            side = 'over' if (name or '').lower() == 'over' else ('under' if (name or '').lower() == 'under' else None)
            if side:
                entry[side] = {"odds": outc.get('price'), "point": outc.get('point')}
        lines = [v for v in lines_map.values() if v['over'] and v['under']]
        markets.append({
            "key": key,
            "last_update": last_update,
            "lines": lines,
        })
    return markets
