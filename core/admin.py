from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import redirect
from django.contrib import messages
from .models import (
    Team, Player, Game, PlayerStats, TeamStats, Prediction, GamePrediction,
    CachedData, PropLine, PropProjection, OddsEventMap, OddsEvent, 
    PlayerProp, PropLineHistory, DataRefreshLog
)
from .management.commands.refresh_player_props import Command as RefreshCommand


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['team_abbr', 'team_name', 'team_city']
    search_fields = ['team_abbr', 'team_name']


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ['player_name', 'position', 'team', 'jersey_number']
    list_filter = ['position', 'team']
    search_fields = ['player_name']


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'game_date', 'completed']
    list_filter = ['season', 'week', 'completed']
    search_fields = ['home_team__team_abbr', 'away_team__team_abbr']


@admin.register(OddsEvent)
class OddsEventAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'game_id', 'commence_time', 'last_updated', 'is_active']
    list_filter = ['is_active', 'commence_time']
    search_fields = ['event_id', 'home_team', 'away_team', 'game_id']
    readonly_fields = ['event_id', 'last_updated']
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('refresh-props/', self.admin_site.admin_view(self.refresh_props), name='refresh_props'),
        ]
        return custom_urls + urls
    
    def refresh_props(self, request):
        """Refresh player props for all active events"""
        if request.method == 'POST':
            try:
                # Run the refresh command
                refresh_cmd = RefreshCommand()
                refresh_cmd.handle()
                messages.success(request, 'Player props refreshed successfully!')
            except Exception as e:
                messages.error(request, f'Error refreshing props: {str(e)}')
        return redirect('..')
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['refresh_url'] = reverse('admin:refresh_props')
        return super().changelist_view(request, extra_context)


@admin.register(PlayerProp)
class PlayerPropAdmin(admin.ModelAdmin):
    list_display = ['player_name', 'market_display', 'event', 'over_point', 'under_point', 'last_updated']
    list_filter = ['market_key', 'event__is_active', 'last_updated']
    search_fields = ['player_name', 'market_key']
    readonly_fields = ['last_updated']


@admin.register(PropLineHistory)
class PropLineHistoryAdmin(admin.ModelAdmin):
    list_display = ['prop', 'over_point', 'under_point', 'timestamp']
    list_filter = ['timestamp', 'prop__market_key']
    search_fields = ['prop__player_name']
    readonly_fields = ['timestamp']


@admin.register(DataRefreshLog)
class DataRefreshLogAdmin(admin.ModelAdmin):
    list_display = ['event', 'api_status', 'markets_found', 'total_lines', 'timestamp']
    list_filter = ['api_status', 'timestamp']
    search_fields = ['event__home_team', 'event__away_team']
    readonly_fields = ['timestamp']


@admin.register(OddsEventMap)
class OddsEventMapAdmin(admin.ModelAdmin):
    list_display = ['game_id', 'odds_event_id', 'last_checked_at']
    search_fields = ['game_id', 'odds_event_id']


# Register other models
admin.site.register(PlayerStats)
admin.site.register(TeamStats)
admin.site.register(Prediction)
admin.site.register(GamePrediction)
admin.site.register(CachedData)
admin.site.register(PropLine)
admin.site.register(PropProjection)
