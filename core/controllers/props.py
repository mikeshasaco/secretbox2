"""
Props controller for PrizePicks parlay functionality.
Handles parlay context and evaluation for current-week games only.
"""
import json
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from services.nfl import get_current_week, get_current_week_games
from services import nfl
from services.odds_provider import (
    fetch_prizepicks_props_for_games,
    resolve_odds_event_id,
    fetch_event_player_props,
    parse_props_response,
)
from core.models import OddsEventMap
from django.views.decorators.http import require_GET
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def get_parlay_context(season: int, game_id_sb: str):
    """
    Get parlay context for a specific game.
    Only returns data for current-week games.
    """
    wk = get_current_week(season)
    games = get_current_week_games(season, wk)
    
    if game_id_sb not in set(games["game_id_sb"]):
        return {"enabled": False, "reason": "not_current_week"}

    rows = fetch_prizepicks_props_for_games(season, wk, games["game_id_sb"].tolist())
    props_for_game = [r for r in rows if r["game_id_sb"] == game_id_sb]
    
    if not rows:
        return {"enabled": True, "available": False, "props": [], "week": wk}  # API unavailable or empty
    
    return {"enabled": True, "available": True, "props": props_for_game, "week": wk}


def evaluate_parlay(request):
    """
    POST {game_id, mode: "power"|"flex", legs:[{player_id, prop_type, line, side}]}
    Uses existing projection engine for win prob per leg.
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
        season = int(settings.NFL_SEASON)
        game_id_sb = body["game_id"]
        mode = body.get("mode", "power")
        legs = body["legs"]

        # For now, return a simple response since we don't have the full ML pipeline
        # In a real implementation, this would use the projection engine
        win_prob = 0.5  # Placeholder - would be calculated from ML model
        ev = 0.0  # Placeholder - would be calculated from win prob and payout structure
        
        detail = []
        for leg in legs:
            detail.append({
                **leg, 
                "win_prob": round(win_prob, 3)
            })

        return JsonResponse({
            "legs": detail, 
            "win_prob": round(win_prob, 3), 
            "ev": round(ev, 3)
        })
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@require_GET
def game_props(request, game_id: str):
    """GET /game/<game_id>/props
    Returns player props from database first, falls back to API if needed.
    Returns 204 if no data available, 404 if game not found.
    """
    markets_csv = request.GET.get('markets', 'player_pass_yds')
    # deny-list apiKey param in inbound
    if 'apiKey' in request.GET:
        return JsonResponse({"error": "apiKey_not_allowed"}, status=400)

    # Build internal game from nfl service
    schedule = nfl.load_schedule_2025()
    games_map = nfl.game_id_map(schedule)
    game = games_map.get(game_id)
    if not game:
        return JsonResponse({"error": "game_not_found"}, status=404)

    # Try to get data from database first
    try:
        from core.models import OddsEvent, PlayerProp
        from django.utils import timezone
        
        # Get the event for this game
        event = OddsEvent.objects.filter(game_id=game_id, is_active=True).first()
        if not event:
            # Try to resolve and create event
            try:
                event_id, ev_json = resolve_odds_event_id(game)
                event = OddsEvent.objects.create(
                    event_id=event_id,
                    game_id=game_id,
                    home_team=game['home_team'],
                    away_team=game['away_team'],
                    commence_time=game['kickoff']
                )
            except Exception as e:
                logger.info("props_resolve_failed", extra={"game_id": game_id})
                return JsonResponse({
                    "game_id": game_id,
                    "markets": markets_csv,
                    "note": "prizepicks_unavailable",
                }, status=204)
        
        # Get requested markets
        requested_markets = [m.strip() for m in markets_csv.split(',') if m.strip()]
        
        # Query props from database
        props = PlayerProp.objects.filter(
            event=event,
            market_key__in=requested_markets,
            is_active=True
        ).order_by('market_key', 'player_name')
        
        # Get ML predictions for these props
        from core.models import Prediction
        predictions = {}
        if props.exists():
            # Get predictions for the same players and markets
            preds = Prediction.objects.filter(
                game__game_id=game_id,
                prop_type__in=requested_markets
            ).select_related('player')
            
            for pred in preds:
                key = f"{pred.player.player_name}_{pred.prop_type}"
                predictions[key] = {
                    'over_probability': pred.over_probability,
                    'under_probability': pred.under_probability,
                    'predicted_value': pred.predicted_value,
                    'edge': pred.edge,
                    'model_version': pred.model_version
                }
        
        if not props.exists():
            # No data in database, try API as fallback
            return fetch_from_api_fallback(game_id, game, markets_csv)
        
        # Group props by market
        market_groups = {}
        for prop in props:
            if prop.market_key not in market_groups:
                market_groups[prop.market_key] = {
                    'key': prop.market_key,
                    'last_update': prop.last_updated.isoformat() if prop.last_updated else None,
                    'lines': []
                }
            
            # Get player team information
            from core.models import Player
            player = Player.objects.filter(player_name=prop.player_name).first()
            team_abbr = player.team_abbr if player else "UNK"
            team_name = player.team_name if player else "Unknown Team"
            
            # Build line data
            line = {
                'player': prop.player_name,
                'team_abbr': team_abbr,
                'team_name': team_name,
                'over': {
                    'odds': prop.over_odds,
                    'point': prop.over_point
                } if prop.over_odds is not None and prop.over_point is not None else None,
                'under': {
                    'odds': prop.under_odds,
                    'point': prop.under_point
                } if prop.under_odds is not None and prop.under_point is not None else None
            }
            
            # Add ML predictions if available
            pred_key = f"{prop.player_name}_{prop.market_key}"
            if pred_key in predictions:
                pred = predictions[pred_key]
                line['ml_prediction'] = {
                    'over_probability': pred['over_probability'],
                    'under_probability': pred['under_probability'],
                    'predicted_value': pred['predicted_value'],
                    'edge': pred['edge'],
                    'model_version': pred['model_version']
                }
            market_groups[prop.market_key]['lines'].append(line)
        
        markets = list(market_groups.values())
        if not markets:
            return JsonResponse({
                "game_id": game_id,
                "markets": markets_csv,
                "note": "prizepicks_unavailable",
            }, status=204)
        
        resp = {
            "game_id": game_id,
            "odds_event_id": event.event_id,
            "home_team": game.get('home_team'),
            "away_team": game.get('away_team'),
            "kickoff_utc": game.get('kickoff'),
            "markets": markets,
            "source": "database"
        }
        return JsonResponse(resp)
        
    except Exception as e:
        logger.error(f"Database query failed for {game_id}: {e}")
        # Fall back to API
        return fetch_from_api_fallback(game_id, game, markets_csv)


def fetch_from_api_fallback(game_id: str, game: dict, markets_csv: str):
    """Fallback to API when database doesn't have data"""
    try:
        resolved = None
        odds_map = OddsEventMap.objects.filter(game_id=game_id).first()
        if odds_map:
            resolved = odds_map.odds_event_id

        if not resolved:
            try:
                event_id, ev_json = resolve_odds_event_id(game)
                resolved = event_id
                if odds_map:
                    odds_map.odds_event_id = event_id
                    odds_map.save(update_fields=["odds_event_id", "last_checked_at"])
                else:
                    OddsEventMap.objects.create(game_id=game_id, odds_event_id=event_id)
            except Exception as e:
                logger.info("props_resolve_failed", extra={"game_id": game_id})
                return JsonResponse({"error": "odds_event_not_found"}, status=404)

        try:
            event_payload = fetch_event_player_props(resolved, markets_csv)
        except Exception as e:
            logger.info("props_fetch_failed", extra={"game_id": game_id})
            return JsonResponse({"error": "fetch_failed"}, status=502)

        markets = parse_props_response(event_payload, markets_csv)
        if not markets:
            return JsonResponse({
                "game_id": game_id,
                "markets": markets_csv,
                "note": "prizepicks_unavailable",
            }, status=204)

        resp = {
            "game_id": game_id,
            "odds_event_id": resolved,
            "home_team": game.get('home_team'),
            "away_team": game.get('away_team'),
            "kickoff_utc": game.get('kickoff'),
            "markets": markets,
            "source": "api"
        }
        return JsonResponse(resp)
    except Exception as e:
        logger.error(f"API fallback failed for {game_id}: {e}")
        return JsonResponse({"error": "fetch_failed"}, status=502)
