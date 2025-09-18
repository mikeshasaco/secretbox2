from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

import pandas as pd
import polars as pl
from django.conf import settings


CACHE_DIR: Path = Path(getattr(settings, 'CACHE_DIR', Path('/tmp/secretbox_cache')))
SEASON: int = int(getattr(settings, 'NFL_SEASON', 2025))


def _ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path(name: str) -> Path:
    _ensure_cache_dir()
    return CACHE_DIR / name


def _read_parquet_if_exists(path: Path) -> Optional[pd.DataFrame]:
    if path.exists():
        return pd.read_parquet(path)
    return None


def load_schedule_2025(refresh: bool = False) -> pd.DataFrame:
    import nflreadpy

    path = _cache_path(f'schedule_{SEASON}.parquet')
    if not refresh:
        cached = _read_parquet_if_exists(path)
        if cached is not None:
            return cached

    # nflreadpy returns Polars DataFrame, convert to pandas
    df_polars = nflreadpy.load_schedules()
    df_polars = df_polars.filter(pl.col('season') == SEASON)
    df = df_polars.to_pandas()
    df.to_parquet(path, index=False)
    return df


def load_weekly_2025(week: int, refresh: bool = False) -> pd.DataFrame:
    import nflreadpy

    path = _cache_path(f'weekly_{SEASON}_w{week}.parquet')
    if not refresh:
        cached = _read_parquet_if_exists(path)
        if cached is not None:
            return cached

    # nflreadpy returns Polars DataFrame, convert to pandas
    df_polars = nflreadpy.load_player_stats(seasons=[SEASON], summary_level='week')
    df_polars = df_polars.filter((pl.col('season') == SEASON) & (pl.col('week') == week))
    df = df_polars.to_pandas()
    df.to_parquet(path, index=False)
    return df


def load_pbp_2025_weeks(weeks: list[int], refresh: bool = False) -> pd.DataFrame:
    import nflreadpy

    path = _cache_path(f'pbp_{SEASON}_w{"-".join(map(str, weeks))}.parquet')
    if not refresh:
        cached = _read_parquet_if_exists(path)
        if cached is not None:
            return cached

    # nflreadpy returns Polars DataFrame, convert to pandas
    df_polars = nflreadpy.load_pbp(seasons=[SEASON])
    # Filter by weeks after loading
    df_polars = df_polars.filter((pl.col('season') == SEASON) & pl.col('week').is_in(weeks))
    df = df_polars.to_pandas()
    df.to_parquet(path, index=False)
    return df


def guess_current_week(schedule: Optional[pd.DataFrame] = None) -> int:
    if schedule is None:
        schedule = load_schedule_2025(refresh=False)
    # Find latest week with non-null kickoff that is not in the future (approx)
    schedule = schedule.sort_values(['week', 'gameday'])
    last_week = int(schedule['week'].max()) if not schedule.empty else 1
    # Clamp to NFL regular weeks 1..18
    return min(max(1, last_week), 18)


def game_id_map(schedule: Optional[pd.DataFrame] = None) -> Dict[str, Dict[str, Any]]:
    if schedule is None:
        schedule = load_schedule_2025()
    out: Dict[str, Dict[str, Any]] = {}
    for _, r in schedule.iterrows():
        gid = str(r.get('game_id') or f"{r['season']}_{r['week']}_{r['home_team']}")
        out[gid] = {
            'game_id': gid,
            'week': int(r['week']),
            'home_team': r['home_team'],
            'away_team': r['away_team'],
            'gameday': r.get('gameday'),
            'kickoff': r.get('gametime') or None,
        }
    return out


def starting_qbs_for_week(week: int, weekly_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    if weekly_df is None:
        weekly_df = load_weekly_2025(week)
    # Filter for QB with highest pass attempts per team that week as proxy for starter
    qb = weekly_df[weekly_df['position'] == 'QB'].copy()
    # Use actual column names from nflreadpy
    pass_attempts_col = 'passing_att' if 'passing_att' in qb.columns else 'attempts'
    qb['pass_attempts'] = qb.get(pass_attempts_col, 0)
    qb = qb.sort_values(['team', 'pass_attempts'], ascending=[True, False])
    qb = qb.groupby('team', as_index=False).head(1)
    return qb[['player_id', 'player_display_name', 'team', 'week', 'pass_attempts']]


def previous_week_qb_line(week: int, player_id: str) -> Optional[Dict[str, Any]]:
    prev_week = week - 1
    if prev_week < 1:
        return None
    df_prev = load_weekly_2025(prev_week)
    row = df_prev[(df_prev['player_id'] == player_id) & (df_prev['position'] == 'QB')]
    if row.empty:
        return None
    r = row.iloc[0]
    # Use actual column names from nflreadpy
    attempts = int(r.get('passing_att', r.get('attempts', 0)))
    completions = int(r.get('passing_cmp', r.get('completions', 0)))
    yards = int(r.get('passing_yards', r.get('pass_yards', 0)))
    td = int(r.get('passing_tds', r.get('pass_td', 0)))
    inter = int(r.get('passing_int', r.get('interceptions', 0)))
    return {
        'att': attempts,
        'cmp': completions,
        'yds': yards,
        'td': td,
        'int': inter,
    }


def refresh_week_cache(week: int) -> None:
    load_schedule_2025(refresh=True)
    load_weekly_2025(week=week, refresh=True)
    # Preload small window of pbp for features: weeks up to selected week
    weeks = list(range(1, max(1, min(18, week)) + 1))
    load_pbp_2025_weeks(weeks=weeks, refresh=True)


