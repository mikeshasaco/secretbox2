"""
Management command to refresh player props data from Odds API.
Stores data in database and tracks line changes over time.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from core.models import OddsEvent, PlayerProp, PropLineHistory, DataRefreshLog, OddsEventMap
from services.nfl import load_schedule_2025, game_id_map
from services.odds_provider import resolve_odds_event_id, fetch_event_player_props, parse_props_response
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Refresh player props data from Odds API for current week games'

    def add_arguments(self, parser):
        parser.add_argument(
            '--game-id',
            type=str,
            help='Refresh specific game ID only'
        )
        parser.add_argument(
            '--markets',
            type=str,
            default='player_pass_yds,player_rush_yds,player_reception_yds,player_pass_tds,player_rush_tds,player_reception_tds,player_pass_attempts,player_rush_attempts,player_receptions',
            help='Comma-separated list of markets to fetch'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force refresh even if data exists'
        )

    def handle(self, *args, **options):
        game_id = options.get('game_id')
        markets_csv = options.get('markets')
        force = options.get('force')
        
        if game_id:
            games_to_process = [game_id]
        else:
            # Get current week games
            sch = load_schedule_2025()
            gm = game_id_map(sch)
            from services.nfl import get_current_week
            current_week = get_current_week(2025)
            games_to_process = [gid for gid, game in gm.items() if game['week'] == current_week]
        
        self.stdout.write(f"Processing {len(games_to_process)} games...")
        
        total_events = 0
        total_props = 0
        
        for game_id in games_to_process:
            try:
                result = self.refresh_game_props(game_id, markets_csv, force)
                if result:
                    total_events += 1
                    total_props += result['props_count']
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ {game_id}: {result['props_count']} props")
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"✗ {game_id}: No data available")
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ {game_id}: {str(e)}")
                )
                logger.error(f"Error refreshing {game_id}: {e}")
        
        self.stdout.write(
            self.style.SUCCESS(f"Completed: {total_events} events, {total_props} total props")
        )

    def refresh_game_props(self, game_id, markets_csv, force=False):
        """Refresh props for a specific game"""
        # Get or create OddsEvent
        try:
            event_map = OddsEventMap.objects.get(game_id=game_id)
            odds_event_id = event_map.odds_event_id
        except OddsEventMap.DoesNotExist:
            # Resolve event ID
            sch = load_schedule_2025()
            gm = game_id_map(sch)
            game = gm.get(game_id)
            if not game:
                return None
            
            try:
                odds_event_id, ev_json = resolve_odds_event_id(game)
                # Create mapping
                OddsEventMap.objects.create(
                    game_id=game_id,
                    odds_event_id=odds_event_id
                )
            except Exception as e:
                logger.error(f"Could not resolve event for {game_id}: {e}")
                return None
        
        # Check if we already have recent data (unless force)
        if not force:
            try:
                event = OddsEvent.objects.get(event_id=odds_event_id)
                if event.last_updated > timezone.now() - timezone.timedelta(minutes=30):
                    self.stdout.write(f"  {game_id}: Data is recent, skipping")
                    return {'props_count': event.props.count()}
            except OddsEvent.DoesNotExist:
                pass
        
        # Fetch fresh data from API
        try:
            api_data = fetch_event_player_props(odds_event_id, markets_csv)
            markets = parse_props_response(api_data, markets_csv)
        except Exception as e:
            logger.error(f"API fetch failed for {game_id}: {e}")
            return None
        
        if not markets:
            return None
        
        # Get or create OddsEvent
        sch = load_schedule_2025()
        gm = game_id_map(sch)
        game = gm[game_id]
        
        event, created = OddsEvent.objects.get_or_create(
            event_id=odds_event_id,
            defaults={
                'game_id': game_id,
                'home_team': game['home_team'],
                'away_team': game['away_team'],
                'commence_time': game['kickoff'],
            }
        )
        
        if not created:
            event.last_updated = timezone.now()
            event.save()
        
        # Store/update player props
        props_count = 0
        for market in markets:
            market_key = market['key']
            market_display = market_key.replace('player_', '').replace('_', ' ').title()
            
            for line in market.get('lines', []):
                player_name = line.get('player', '')
                if not player_name:
                    continue
                
                over_data = line.get('over', {})
                under_data = line.get('under', {})
                
                # Check if line has changed
                existing_prop = PlayerProp.objects.filter(
                    event=event,
                    player_name=player_name,
                    market_key=market_key
                ).first()
                
                if existing_prop:
                    # Check for line changes
                    over_changed = (
                        existing_prop.over_odds != over_data.get('odds') or
                        existing_prop.over_point != over_data.get('point')
                    )
                    under_changed = (
                        existing_prop.under_odds != under_data.get('odds') or
                        existing_prop.under_point != under_data.get('point')
                    )
                    
                    if over_changed or under_changed:
                        # Store old values in history
                        PropLineHistory.objects.create(
                            prop=existing_prop,
                            over_odds=existing_prop.over_odds,
                            over_point=existing_prop.over_point,
                            under_odds=existing_prop.under_odds,
                            under_point=existing_prop.under_point
                        )
                
                # Update or create prop
                prop, created = PlayerProp.objects.update_or_create(
                    event=event,
                    player_name=player_name,
                    market_key=market_key,
                    defaults={
                        'market_display': market_display,
                        'over_odds': over_data.get('odds'),
                        'over_point': over_data.get('point'),
                        'under_odds': under_data.get('odds'),
                        'under_point': under_data.get('point'),
                        'last_updated': timezone.now(),
                        'is_active': True
                    }
                )
                props_count += 1
        
        # Log the refresh
        DataRefreshLog.objects.create(
            event=event,
            markets_requested=markets_csv,
            markets_found=len(markets),
            total_lines=props_count,
            api_status='success'
        )
        
        return {'props_count': props_count}
