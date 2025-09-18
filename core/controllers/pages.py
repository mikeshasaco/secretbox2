from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from services import nfl


def landing(request: HttpRequest) -> HttpResponse:
    schedule = nfl.load_schedule_2025()
    current_week = nfl.guess_current_week(schedule)
    week = current_week
    games_map = nfl.game_id_map(schedule)
    games = [g for g in games_map.values() if g['week'] == week]
    context = {
        'title': 'SecretBox',
        'season': nfl.SEASON,
        'week': week,
        'weeks': list(range(1, 19)),
        'games': games,
    }
    return render(request, 'pages/landing.html', context)


def week_view(request: HttpRequest, week: int) -> HttpResponse:
    schedule = nfl.load_schedule_2025()
    games_map = nfl.game_id_map(schedule)
    games = [g for g in games_map.values() if g['week'] == week]

    qb_df = nfl.starting_qbs_for_week(week)
    qb_prev = {}
    for _, r in qb_df.iterrows():
        qb_prev[str(r['player_id'])] = nfl.previous_week_qb_line(week, str(r['player_id']))

    context = {
        'title': 'Week',
        'season': nfl.SEASON,
        'week': week,
        'weeks': list(range(1, 19)),
        'games': games,
        'qb_df': qb_df.to_dict('records'),  # Convert DataFrame to list of dicts
        'qb_prev': qb_prev,
    }
    return render(request, 'pages/week.html', context)


def game_detail(request: HttpRequest, game_id: str) -> HttpResponse:
    schedule = nfl.load_schedule_2025()
    games_map = nfl.game_id_map(schedule)
    game = games_map.get(game_id)
    context = {
        'title': 'Game Detail',
        'game': game,
        'season': nfl.SEASON,
    }
    return render(request, 'pages/game.html', context)


