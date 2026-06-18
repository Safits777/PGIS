# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import csv
import html
import io
import json
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import streamlit as st
import streamlit.components.v1 as components


APP_DIR = Path(__file__).resolve().parent
INDEX_HTML_PATH = APP_DIR / "index.html"
SPOT_DATA_DIR = APP_DIR / "data" / "spots"
SPOT_DATA_FILE = SPOT_DATA_DIR / "spots.json"
LEGACY_SPOT_DATA_FILE = SPOT_DATA_DIR / "sample_spots.json"
DATABASE_URL_ENV_KEYS = ("DATABASE_URL", "PGIS_DATABASE_URL", "POSTGRES_URL")
DEFAULT_SPOT_PASSWORD = "0000"
COLOR_TOKEN_RE = re.compile(r"--(color-[a-z0-9-]+)\s*:\s*([^;]+);", re.IGNORECASE)
COLOR_TOKEN_FALLBACKS = {
    "color-canvas": "#f7f8f6",
    "color-surface": "#ffffff",
    "color-surface-soft": "#f0f2f0",
    "color-border": "#d8ddd8",
    "color-border-strong": "#b8c0ba",
    "color-text": "#1f2328",
    "color-muted": "#69737d",
    "color-accent": "#0078d4",
    "color-accent-strong": "#005a9e",
    "color-accent-soft": "#dcebfa",
    "color-track": "#e2e7e3",
    "color-highlight": "rgba(255, 255, 255, 0.92)",
    "color-shadow": "rgba(31, 35, 40, 0.14)",
    "color-shadow-soft": "rgba(31, 35, 40, 0.08)",
    "color-weather-sunny": "#f59e0b",
    "color-weather-cloud": "#64748b",
    "color-weather-rain": "#2563eb",
    "color-weather-snow": "#7dd3fc",
    "color-weather-fog": "#8b949e",
}
THEME_DARK_TOKENS = {
    "color-canvas": "#111315",
    "color-surface": "#181b1f",
    "color-surface-soft": "#20252a",
    "color-border": "#343a40",
    "color-border-strong": "#4b5560",
    "color-text": "#eef2f4",
    "color-muted": "#a6b0ba",
    "color-accent-soft": "rgba(0, 120, 212, 0.28)",
    "color-track": "#30363d",
    "color-highlight": "rgba(255, 255, 255, 0.08)",
    "color-shadow": "rgba(0, 0, 0, 0.42)",
    "color-shadow-soft": "rgba(0, 0, 0, 0.28)",
}


def load_color_tokens() -> dict[str, str]:
    tokens = COLOR_TOKEN_FALLBACKS.copy()
    try:
        with INDEX_HTML_PATH.open("r", encoding="utf-8") as token_file:
            token_source = token_file.read()
    except OSError:
        return tokens
    for name, value in COLOR_TOKEN_RE.findall(token_source):
        if name in tokens:
            tokens[name] = value.strip()
    return tokens


def current_color_tokens() -> dict[str, str]:
    tokens = load_color_tokens()
    if bool(st.session_state.get("dark_mode", False)):
        tokens.update(THEME_DARK_TOKENS)
    return tokens


def ui_color(name: str) -> str:
    return current_color_tokens().get(name, COLOR_TOKEN_FALLBACKS.get(name, COLOR_TOKEN_FALLBACKS["color-text"]))


def css_color_token_block() -> str:
    tokens = current_color_tokens()
    return "\n".join(f"            --{name}: {value};" for name, value in tokens.items())


def spot_data_files() -> list[Path]:
    if SPOT_DATA_FILE.is_file():
        return [SPOT_DATA_FILE]
    if LEGACY_SPOT_DATA_FILE.is_file():
        return [LEGACY_SPOT_DATA_FILE]
    return []


def spots_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = payload.get("spots") or payload.get("records") or []
    else:
        records = []
    return [dict(record) for record in records if isinstance(record, dict)]


def configured_database_url() -> str:
    for key in DATABASE_URL_ENV_KEYS:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def database_storage_enabled() -> bool:
    return bool(configured_database_url())


SPOTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS spots (
    id integer PRIMARY KEY,
    title text NOT NULL DEFAULT '',
    url text NOT NULL DEFAULT '',
    lat double precision NOT NULL,
    lng double precision NOT NULL,
    drct integer NOT NULL DEFAULT 0 CHECK (drct >= 0 AND drct < 360),
    weather text NOT NULL DEFAULT '',
    shot_date date,
    shot_time time,
    body text NOT NULL DEFAULT '',
    lens text NOT NULL DEFAULT '',
    comp jsonb NOT NULL DEFAULT '{}'::jsonb,
    password text NOT NULL DEFAULT '0000',
    available integer NOT NULL DEFAULT 1 CHECK (available IN (0, 1)),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
"""


SPOTS_SELECT_SQL = """
SELECT
    id,
    title,
    url AS "URL",
    lat,
    lng,
    drct,
    weather,
    COALESCE(shot_date::text, '') AS date,
    COALESCE(to_char(shot_time, 'HH24:MI'), '') AS time,
    body,
    lens,
    comp,
    password,
    available AS "Available"
FROM spots
ORDER BY id;
"""


SPOTS_UPSERT_SQL = """
INSERT INTO spots (
    id,
    title,
    url,
    lat,
    lng,
    drct,
    weather,
    shot_date,
    shot_time,
    body,
    lens,
    comp,
    password,
    available
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, NULLIF(%s, '')::date, NULLIF(%s, '')::time, %s, %s, %s, %s, %s
)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title,
    url = EXCLUDED.url,
    lat = EXCLUDED.lat,
    lng = EXCLUDED.lng,
    drct = EXCLUDED.drct,
    weather = EXCLUDED.weather,
    shot_date = EXCLUDED.shot_date,
    shot_time = EXCLUDED.shot_time,
    body = EXCLUDED.body,
    lens = EXCLUDED.lens,
    comp = EXCLUDED.comp,
    password = EXCLUDED.password,
    available = EXCLUDED.available,
    updated_at = now();
"""


def import_database_driver() -> tuple[Any, Any, Any]:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb

    return psycopg, dict_row, Jsonb


def ensure_spots_table(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute(SPOTS_TABLE_SQL)
        cur.execute("ALTER TABLE spots ADD COLUMN IF NOT EXISTS password text NOT NULL DEFAULT '0000';")
        cur.execute(
            "UPDATE spots SET password = '0000' "
            "WHERE password IS NULL OR password = '' OR password = 'shzzang0222';"
        )


def load_spot_records_from_database() -> list[dict[str, Any]] | None:
    if not database_storage_enabled():
        return None
    try:
        psycopg, dict_row, _ = import_database_driver()
        with psycopg.connect(configured_database_url(), row_factory=dict_row) as conn:
            ensure_spots_table(conn)
            with conn.cursor() as cur:
                cur.execute(SPOTS_SELECT_SQL)
                return [dict(row) for row in cur.fetchall()]
    except Exception as exc:
        st.warning(f"DB에서 스팟을 불러오지 못해 JSON 파일을 사용합니다: {exc}")
        return None


def save_spot_records_to_database(spots: list[dict[str, Any]]) -> bool:
    if not database_storage_enabled():
        return False
    try:
        psycopg, _, Jsonb = import_database_driver()
        normalized_spots = [normalize_spot(spot, index + 1) for index, spot in enumerate(spots)]
        with psycopg.connect(configured_database_url()) as conn:
            ensure_spots_table(conn)
            with conn.cursor() as cur:
                spot_ids = [int(spot["id"]) for spot in normalized_spots]
                if spot_ids:
                    cur.execute("DELETE FROM spots WHERE NOT (id = ANY(%s));", (spot_ids,))
                else:
                    cur.execute("DELETE FROM spots;")
                for spot in normalized_spots:
                    cur.execute(
                        SPOTS_UPSERT_SQL,
                        (
                            int(spot["id"]),
                            spot["title"],
                            spot_url(spot),
                            float(spot["lat"]),
                            float(spot["lng"]),
                            int(spot["drct"]) % 360,
                            spot["weather"],
                            spot["date"],
                            spot["time"],
                            spot["body"],
                            spot["lens"],
                            Jsonb(spot_comp(spot)),
                            spot_password(spot),
                            spot_available(spot),
                        ),
                    )
        return True
    except Exception as exc:
        st.error(f"DB 저장에 실패해 JSON 파일에만 저장합니다: {exc}")
        return False


def load_spot_records() -> list[dict[str, Any]]:
    db_spots = load_spot_records_from_database()
    if db_spots is not None:
        return db_spots

    spots: list[dict[str, Any]] = []
    for path in spot_data_files():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        spots.extend(spots_from_payload(payload))
    return spots


def save_spot_records(spots: list[dict[str, Any]]) -> None:
    if save_spot_records_to_database(spots):
        return

    SPOT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "kind": "pgis.spots",
        "spots": [normalize_spot(spot, index + 1) for index, spot in enumerate(spots)],
    }
    temp_path = SPOT_DATA_FILE.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(SPOT_DATA_FILE)


def persist_spots() -> bool:
    try:
        save_spot_records(st.session_state.spots)
        return True
    except OSError as exc:
        st.error(f"spots.json 저장에 실패했습니다: {exc}")
        return False


def _inside_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


if not _inside_streamlit() and os.environ.get("PGIS_STREAMLIT_BOOTSTRAPPED") != "1":
    os.environ["PGIS_STREAMLIT_BOOTSTRAPPED"] = "1"
    port = os.environ.get("PORT", "8501")
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            os.path.abspath(__file__),
            "--server.port",
            port,
            "--server.address",
            "0.0.0.0",
            "--server.headless",
            "true",
        ],
    )


import folium
import osmnx as ox
from branca.element import MacroElement, Template
from PIL import Image
from streamlit_folium import st_folium


ox.settings.use_cache = False


st.set_page_config(
    page_title="GlassShot PGIS",
    page_icon="📷",
    layout="wide",
    initial_sidebar_state="collapsed",
)


WEATHER_OPTIONS = ["맑음", "구름", "비", "눈", "안개"]
TIME_OPTIONS = ["오전", "오후"]
WEATHER_COLORS = {
    WEATHER_OPTIONS[0]: ui_color("color-weather-sunny"),
    WEATHER_OPTIONS[1]: ui_color("color-weather-cloud"),
    WEATHER_OPTIONS[2]: ui_color("color-weather-rain"),
    WEATHER_OPTIONS[3]: ui_color("color-weather-snow"),
    WEATHER_OPTIONS[4]: ui_color("color-weather-fog"),
}
TIME_COLORS = {
    TIME_OPTIONS[0]: ui_color("color-accent-strong"),
    TIME_OPTIONS[1]: ui_color("color-accent"),
}
SEOUL_CENTER = (37.5665, 126.9780)
DIRECTION_DIAL_COMPONENT = components.declare_component(
    "direction_dial",
    path=os.path.join(os.path.dirname(__file__), "components", "direction_dial"),
)


def inject_css() -> None:
    color_scheme = "dark" if bool(st.session_state.get("dark_mode", False)) else "light"
    st.markdown(
        f"""
        <style>
        :root {{
{css_color_token_block()}
            color-scheme: {color_scheme};
            --glass-bg: var(--color-surface);
            --glass-line: var(--color-border);
            --glass-text: var(--color-text);
            --glass-muted: var(--color-muted);
            --glass-cyan: var(--color-accent);
            --glass-rose: var(--color-accent-strong);
            --glass-amber: var(--color-border-strong);
            --glass-green: var(--color-muted);
            --panel-black: var(--color-surface);
            --panel-line: var(--color-border);
            --neon-cyan: var(--color-accent);
            --neon-blue: var(--color-accent);
            --neon-pink: var(--color-accent-strong);
            --neon-violet: var(--color-border-strong);
            --record-panel-width: min(330px, calc(100vw - 24px));
            --record-panel-left: calc(100vw - 360px);
            --record-panel-top: 18px;
            --record-panel-opacity: 0;
            --record-panel-pointer-events: none;
            --record-danger: #ff5f57;
            --record-danger-strong: #d93630;
            --radius-sm: 5px;
            --radius-md: 8px;
            --radius-pill: 999px;
        }}

        * {{
            box-sizing: border-box;
        }}

        html, body, [data-testid="stAppViewContainer"], .stApp {{
            background: var(--color-canvas) !important;
            color: var(--color-text) !important;
            overflow: hidden;
        }}

        [data-testid="stAppViewContainer"],
        section.main,
        [data-testid="stMain"] {{
            width: 100vw !important;
            max-width: 100vw !important;
            min-width: 100vw !important;
            margin-left: 0 !important;
        }}

        .stApp::before,
        .stApp::after {{
            content: none !important;
        }}

        [data-testid="stHeader"] {{
            display: none;
        }}

        [data-baseweb="tooltip"],
        [data-baseweb="popover"],
        [role="tooltip"],
        [data-testid="stTooltipContent"] {{
            color-scheme: {color_scheme} !important;
            border-color: var(--color-border) !important;
            background: var(--color-surface) !important;
            color: var(--color-text) !important;
            box-shadow: 0 10px 26px var(--color-shadow) !important;
        }}

        [data-baseweb="tooltip"] > div,
        [data-baseweb="popover"] > div,
        [role="tooltip"] > div,
        [data-testid="stTooltipContent"] > div {{
            border: 1px solid var(--color-border) !important;
            background: var(--color-surface) !important;
            color: var(--color-text) !important;
            box-shadow: 0 10px 26px var(--color-shadow) !important;
        }}

        [data-baseweb="tooltip"] *,
        [data-baseweb="popover"] *,
        [role="tooltip"] *,
        [data-testid="stTooltipContent"] * {{
            color: var(--color-text) !important;
        }}

        [data-baseweb="tooltip"] svg,
        [data-baseweb="popover"] svg,
        [role="tooltip"] svg,
        [data-testid="stTooltipContent"] svg {{
            color: var(--color-surface) !important;
            fill: var(--color-surface) !important;
        }}

        .st-key-options_menu_button {{
            position: fixed;
            top: 14px;
            right: 14px;
            z-index: 96;
            width: 38px !important;
            height: 38px !important;
        }}

        .st-key-route_mode_button {{
            position: fixed;
            top: 14px;
            right: 60px;
            z-index: 96;
            width: 58px !important;
            height: 38px !important;
        }}

        .st-key-route_mode_button button {{
            width: 58px !important;
            min-width: 58px !important;
            height: 38px !important;
            min-height: 38px !important;
            padding: 0 10px !important;
            border-radius: var(--radius-md) !important;
            border: 1px solid var(--color-border) !important;
            background: var(--color-surface) !important;
            color: var(--color-text) !important;
            box-shadow: 0 10px 26px var(--color-shadow-soft);
            font-size: 0.82rem !important;
            font-weight: 800 !important;
            line-height: 1 !important;
        }}

        .st-key-route_mode_button button:hover {{
            border-color: var(--color-accent) !important;
            background: var(--color-accent-soft) !important;
        }}

        .st-key-route_mode_button button:disabled {{
            border-color: var(--color-accent) !important;
            background: var(--color-accent) !important;
            color: #fff !important;
            opacity: 1 !important;
        }}

        .st-key-options_menu_button button {{
            width: 38px !important;
            min-width: 38px !important;
            height: 38px !important;
            min-height: 38px !important;
            padding: 0 !important;
            border-radius: var(--radius-md) !important;
            border: 1px solid var(--color-border) !important;
            background: var(--color-surface) !important;
            color: var(--color-text) !important;
            box-shadow: 0 10px 26px var(--color-shadow-soft);
            font-size: 1.05rem !important;
            line-height: 1 !important;
        }}

        .st-key-options_menu_button button:hover {{
            border-color: var(--color-border-strong) !important;
            background: var(--color-surface-soft) !important;
        }}

        .st-key-options_panel {{
            position: fixed;
            top: 58px;
            right: 14px;
            z-index: 95;
            width: min(240px, calc(100vw - 28px));
            padding: 0.75rem;
            border: 1px solid var(--color-border);
            border-radius: var(--radius-md);
            background: var(--color-surface);
            box-shadow: 0 18px 44px var(--color-shadow);
            transform: translateY(-8px) scale(0.98);
            opacity: 0;
            pointer-events: none;
            transition:
                opacity 160ms ease,
                transform 180ms cubic-bezier(.2, .8, .2, 1);
        }}

        .st-key-options_panel:has(.options-panel-state.is-open) {{
            transform: translateY(0) scale(1);
            opacity: 1;
            pointer-events: auto;
        }}

        .st-key-options_panel [data-testid="stVerticalBlock"] {{
            gap: 0.55rem;
        }}

        .options-panel-title {{
            margin: 0;
            color: var(--color-text);
            font-size: 0.82rem;
            line-height: 1.2;
            font-weight: 900;
        }}

        .st-key-options_panel label {{
            color: var(--color-text) !important;
            font-weight: 750;
        }}

        .block-container {{
            width: 100vw;
            max-width: 100vw;
            min-height: 100vh;
            padding: 0 !important;
        }}

        h1, h2, h3, h4, p, label, span {{
            color: inherit;
            letter-spacing: 0;
        }}

        [data-testid="stSidebar"] {{
            position: fixed;
            inset: 0 auto 0 0;
            width: var(--drawer-width) !important;
            min-width: var(--drawer-width) !important;
            max-width: var(--drawer-width) !important;
            height: 100vh;
            background: var(--color-surface);
            border-right: 1px solid var(--color-border);
            box-shadow: 18px 0 46px var(--color-shadow);
            transform: translateX(var(--left-drawer-x));
            transition: transform 220ms cubic-bezier(.2, .8, .2, 1), box-shadow 220ms ease;
            z-index: 40;
        }}

        [data-testid="stSidebar"]::before {{
            content: none;
        }}

        [data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
            padding: 1rem;
            overflow-x: hidden;
        }}

        .hero,
        .stat-tile,
        .glass-panel,
        .spot-card,
        .st-key-right_drawer_panel {{
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-md);
            box-shadow: 0 14px 36px var(--color-shadow-soft), 0 2px 8px var(--color-shadow-soft);
            color: var(--color-text);
        }}

        .hero {{
            padding: 1.05rem 1.2rem;
            margin-bottom: 1rem;
            overflow: hidden;
        }}

        .hero-title {{
            margin: 0;
            color: var(--color-text);
            font-size: clamp(2rem, 5vw, 4.5rem);
            line-height: 0.98;
            font-weight: 900;
        }}

        .hero-sub {{
            max-width: 780px;
            margin: 0.55rem 0 0;
            color: var(--color-muted);
            font-size: 1rem;
        }}

        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.7rem;
            margin: 0.8rem 0 1rem;
        }}

        .stat-tile {{
            min-height: 88px;
            padding: 0.9rem;
        }}

        .stat-label,
        .muted,
        .record-advanced-note,
        .filter-mini {{
            color: var(--color-muted);
        }}

        .stat-label {{
            margin-bottom: 0.35rem;
            font-size: 0.76rem;
        }}

        .stat-value,
        .spot-title,
        .record-title,
        .filter-mini strong,
        [data-testid="stSidebar"] h3,
        .st-key-right_drawer_panel h3 {{
            color: var(--color-text);
            font-weight: 850;
        }}

        .stat-value {{
            overflow-wrap: anywhere;
            font-size: 1.45rem;
            line-height: 1.15;
        }}

        .glass-panel {{
            position: relative;
            padding: 1rem;
            margin-bottom: 1rem;
        }}

        .glass-panel::before,
        .st-key-right_drawer_panel::before {{
            content: none;
        }}

        .spot-card {{
            padding: 0.85rem;
            margin-bottom: 0.75rem;
        }}

        .spot-title {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            font-size: 1rem;
        }}

        .pill-row {{
            display: flex;
            gap: 0.35rem;
            flex-wrap: wrap;
            margin-top: 0.55rem;
        }}

        .pill {{
            display: inline-flex;
            align-items: center;
            min-height: 26px;
            padding: 0.2rem 0.48rem;
            border-radius: var(--radius-pill);
            border: 1px solid var(--color-border);
            background: var(--color-surface-soft);
            color: var(--color-text);
            font-size: 0.78rem;
        }}

        .muted {{
            font-size: 0.88rem;
            line-height: 1.6;
        }}

        .map-wrap {{
            position: absolute;
            width: 0;
            height: 0;
            border: 0;
            background: transparent;
            border-radius: 0;
            padding: 0;
            overflow: visible;
            pointer-events: none;
        }}

        .map-wrap iframe,
        div[data-testid="stHorizontalBlock"]:has(.map-wrap) iframe,
        iframe[title^="streamlit_folium"] {{
            position: fixed;
            inset: 0;
            width: 100vw !important;
            height: 100vh !important;
            border: 0;
            border-radius: 0;
            display: block;
            z-index: 1;
        }}

        .st-key-right_drawer_panel {{
            position: fixed;
            left: 0;
            top: 0;
            width: var(--record-panel-width) !important;
            min-width: var(--record-panel-width) !important;
            max-width: var(--record-panel-width) !important;
            max-height: min(72vh, calc(100vh - 24px));
            height: auto;
            padding: 0.58rem;
            overflow-y: auto;
            overflow-x: hidden;
            transform: translate3d(
                min(calc(100vw - var(--record-panel-width) - 16px), max(16px, var(--record-panel-left))),
                min(calc(100vh - 78px), max(12px, var(--record-panel-top))),
                0
            );
            transition: opacity 160ms ease, box-shadow 180ms ease;
            will-change: transform, opacity;
            opacity: var(--record-panel-opacity);
            pointer-events: var(--record-panel-pointer-events);
            contain: layout paint style;
            z-index: 72;
        }}

        .st-key-right_drawer_panel .glass-panel {{
            margin-bottom: 0;
            padding: 0;
            border: 0;
            background: transparent;
            box-shadow: none;
        }}

        .record-head {{
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 0.55rem;
            align-items: center;
            margin-bottom: 0.35rem;
        }}

        .record-title {{
            font-size: 1rem;
            line-height: 1.15;
            font-weight: 900;
        }}

        .record-coord,
        .filter-count {{
            display: inline-flex;
            align-items: center;
            min-height: 24px;
            padding: 0.18rem 0.46rem;
            border-radius: var(--radius-pill);
            border: 1px solid var(--color-border);
            background: var(--color-surface-soft);
            color: var(--color-accent-strong);
            font: 800 0.72rem/1.2 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }}

        .record-coord {{
            max-width: 100%;
        }}

        .st-key-record_lat_text,
        .st-key-record_lng_text {{
            position: absolute !important;
            width: 1px !important;
            height: 1px !important;
            margin: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }}

        .st-key-right_drawer_panel [data-testid="stVerticalBlock"] {{
            gap: 0.35rem;
        }}

        .st-key-right_drawer_panel [data-testid="stHorizontalBlock"] {{
            gap: 0.45rem;
        }}

        .st-key-right_drawer_panel label {{
            margin-bottom: 0.1rem !important;
            font-size: 0.74rem !important;
            line-height: 1.2 !important;
        }}

        .st-key-right_drawer_panel input,
        .st-key-right_drawer_panel [data-baseweb="select"] > div {{
            min-height: 34px !important;
            font-size: 0.84rem !important;
        }}

        [data-testid="stTextInputRoot"] [data-baseweb="input"] button,
        [data-testid="stTextInputRoot"] [data-baseweb="input"] button[kind="icon"] {{
            width: 26px !important;
            min-width: 26px !important;
            height: 26px !important;
            min-height: 26px !important;
            padding: 0 !important;
        }}

        [data-testid="stTextInputRoot"] [data-baseweb="input"] button svg {{
            width: 14px !important;
            height: 14px !important;
        }}

        .st-key-right_drawer_panel [data-testid="stTextInputRoot"] [data-baseweb="input"] button,
        .st-key-right_drawer_panel [data-testid="stTextInputRoot"] [data-baseweb="input"] button[kind="icon"] {{
            width: 22px !important;
            min-width: 22px !important;
            height: 22px !important;
            min-height: 22px !important;
        }}

        .st-key-right_drawer_panel [data-testid="stTextInputRoot"] [data-baseweb="input"] button svg {{
            width: 12px !important;
            height: 12px !important;
        }}

        .st-key-right_drawer_panel .stButton > button,
        .st-key-right_drawer_panel [data-testid="stBaseButton-secondary"],
        .st-key-right_drawer_panel [data-testid="stBaseButton-primary"] {{
            min-height: 34px !important;
            padding: 0.25rem 0.55rem !important;
            font-size: 0.82rem !important;
        }}

        .st-key-close_record_panel {{
            display: flex;
            justify-content: flex-end;
            padding-top: 0.15rem;
        }}

        .record-dial-caption {{
            margin: -0.15rem 0 0;
            text-align: center;
            color: var(--color-accent-strong);
            font: 900 0.72rem/1.2 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }}

        .record-time-row {{
            margin-top: -0.1rem;
        }}

        .record-advanced-note {{
            margin: 0.1rem 0 0;
            font-size: 0.74rem;
            line-height: 1.35;
        }}

        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stBaseButton-secondary"],
        [data-testid="stBaseButton-primary"] {{
            min-height: 42px;
            border-radius: var(--radius-md) !important;
            border: 1px solid var(--color-border) !important;
            background: var(--color-surface) !important;
            color: var(--color-text) !important;
            box-shadow: 0 1px 2px var(--color-shadow-soft);
        }}

        [data-testid="stBaseButton-primary"] {{
            border-color: var(--color-accent-strong) !important;
            background: var(--color-accent) !important;
            color: #fff !important;
            font-weight: 850;
        }}

        [data-testid="stBaseButton-primary"] *,
        .st-key-right_drawer_panel [data-testid="stBaseButton-primary"] *,
        .st-key-right_drawer_panel button[kind="primary"] *,
        .st-key-right_drawer_panel .stFormSubmitButton button * {{
            color: #fff !important;
        }}

        .st-key-right_drawer_panel .st-key-close_record_panel button {{
            width: 15px !important;
            min-width: 15px !important;
            height: 15px !important;
            min-height: 15px !important;
            padding: 0 !important;
            border-radius: 50% !important;
            border: 1px solid var(--record-danger-strong) !important;
            background: var(--record-danger) !important;
            color: transparent !important;
            font-size: 0 !important;
            line-height: 0 !important;
            box-shadow: 0 1px 3px var(--color-shadow-soft) !important;
        }}

        .st-key-right_drawer_panel .st-key-close_record_panel button *,
        .st-key-right_drawer_panel .st-key-close_record_panel button p {{
            display: none !important;
        }}

        .st-key-right_drawer_panel .st-key-close_record_panel button:hover {{
            background: #ff6b63 !important;
            border-color: var(--record-danger-strong) !important;
        }}

        [data-testid="stSidebar"] h3,
        .st-key-right_drawer_panel h3 {{
            border-bottom: 1px solid var(--color-border);
            padding-bottom: 0.45rem;
        }}

        [data-testid="stSidebar"] label,
        .st-key-right_drawer_panel label,
        label {{
            color: var(--color-muted) !important;
            font-weight: 750;
        }}

        .st-key-record_long_exposure {{
            margin: 0.18rem 0;
        }}

        .st-key-record_long_exposure label {{
            color: var(--color-text) !important;
            transition: color 180ms ease;
        }}

        .st-key-record_long_exposure [data-baseweb="checkbox"] {{
            display: inline-flex !important;
            align-items: center !important;
            gap: 0.42rem !important;
        }}

        .st-key-record_long_exposure input[type="checkbox"] + div:not([data-testid="stMarkdownContainer"]):not(:has([data-testid="stMarkdownContainer"])) {{
            background: var(--color-surface) !important;
            border: 1.5px solid var(--color-border-strong) !important;
            border-radius: 4px !important;
            box-shadow: inset 0 0 0 1px var(--color-highlight), 0 1px 3px var(--color-shadow-soft) !important;
            transition:
                background-color 180ms ease,
                border-color 180ms ease,
                box-shadow 180ms ease !important;
        }}

        .st-key-record_long_exposure input[type="checkbox"]:checked + div:not([data-testid="stMarkdownContainer"]):not(:has([data-testid="stMarkdownContainer"])) {{
            background: var(--record-danger) !important;
            border-color: var(--record-danger-strong) !important;
            box-shadow: 0 0 0 3px rgba(255, 95, 87, 0.2), 0 1px 4px var(--color-shadow-soft) !important;
        }}

        .st-key-record_long_exposure [data-baseweb="checkbox"]:hover input[type="checkbox"] + div:not([data-testid="stMarkdownContainer"]):not(:has([data-testid="stMarkdownContainer"])) {{
            border-color: var(--record-danger) !important;
        }}

        .st-key-record_long_exposure input[type="checkbox"]:focus-visible + div:not([data-testid="stMarkdownContainer"]):not(:has([data-testid="stMarkdownContainer"])) {{
            box-shadow: 0 0 0 3px rgba(255, 95, 87, 0.22), 0 1px 4px var(--color-shadow-soft) !important;
        }}

        .st-key-record_long_exposure input[type="checkbox"]:checked + div:not([data-testid="stMarkdownContainer"]):not(:has([data-testid="stMarkdownContainer"])) svg {{
            color: #fff !important;
            fill: #fff !important;
        }}

        .st-key-record_shutter_value_text label [data-testid="stMarkdownContainer"] p {{
            position: relative;
            color: transparent !important;
        }}

        .st-key-record_shutter_value_text label [data-testid="stMarkdownContainer"] p::after {{
            content: "셔터 1/N";
            position: absolute;
            inset: 0 auto auto 0;
            color: var(--color-muted) !important;
            white-space: nowrap;
        }}

        .st-key-right_drawer_panel:has(.st-key-record_long_exposure input[type="checkbox"]:checked) .st-key-record_shutter_value_text label [data-testid="stMarkdownContainer"] p::after,
        .st-key-right_drawer_panel:has(.st-key-record_long_exposure [aria-checked="true"]) .st-key-record_shutter_value_text label [data-testid="stMarkdownContainer"] p::after {{
            content: "셔터 N";
        }}

        .st-key-right_drawer_panel [data-testid="stExpander"] details,
        .st-key-right_drawer_panel [data-testid="stExpander"] details[open],
        .st-key-right_drawer_panel [data-testid="stExpander"] summary,
        .st-key-right_drawer_panel [data-testid="stExpander"] summary *,
        .st-key-right_drawer_panel [data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
            background: var(--color-surface) !important;
            color: var(--color-text) !important;
            border-color: var(--color-border) !important;
            box-shadow: none !important;
        }}

        .st-key-right_drawer_panel [data-testid="stExpander"] summary:hover {{
            background: var(--color-surface-soft) !important;
        }}

        .st-key-right_drawer_panel [data-testid="stExpander"] [data-testid="stExpanderDetails"] > div {{
            background: var(--color-surface) !important;
        }}

        .st-key-record_weather,
        .st-key-record_weather [data-baseweb="select"],
        .st-key-record_weather [data-baseweb="select"] > div {{
            min-width: 86px !important;
        }}

        input,
        textarea,
        [data-baseweb="select"] > div {{
            border-radius: var(--radius-sm) !important;
            background: var(--color-surface) !important;
            border-color: var(--color-border) !important;
            color: var(--color-text) !important;
            box-shadow: inset 0 0 0 1px var(--color-highlight) !important;
        }}

        input::placeholder,
        textarea::placeholder,
        .st-key-right_drawer_panel input::placeholder,
        .st-key-right_drawer_panel textarea::placeholder {{
            color: var(--color-muted) !important;
            opacity: 1 !important;
        }}

        input:focus,
        textarea:focus {{
            border-color: var(--color-accent) !important;
            box-shadow: 0 0 0 2px var(--color-accent-soft) !important;
        }}

        [data-baseweb="select"] *,
        [data-testid="stMarkdownContainer"],
        [data-testid="stCaptionContainer"] {{
            color: var(--color-text);
        }}

        [data-testid="stBaseButton-primary"] [data-testid="stMarkdownContainer"],
        [data-testid="stBaseButton-primary"] [data-testid="stMarkdownContainer"] *,
        .st-key-right_drawer_panel .stFormSubmitButton button [data-testid="stMarkdownContainer"],
        .st-key-right_drawer_panel .stFormSubmitButton button [data-testid="stMarkdownContainer"] * {{
            color: #fff !important;
        }}

        div[data-testid="stFileUploaderDropzone"] {{
            border-radius: var(--radius-md);
            border-color: var(--color-border);
            background: var(--color-surface-soft);
        }}

        .leaflet-popup-content-wrapper,
        .leaflet-popup-tip {{
            background: var(--color-surface) !important;
            color: var(--color-text) !important;
            border: 1px solid var(--color-border);
            box-shadow: 0 18px 42px var(--color-shadow);
            border-radius: var(--radius-md);
        }}

        .leaflet-popup-content {{
            margin: 12px;
        }}

        .leaflet-popup-close-button {{
            top: 12px !important;
            right: 12px !important;
            width: 12px !important;
            height: 12px !important;
            box-sizing: border-box !important;
            display: block !important;
            padding: 0 !important;
            border-radius: 999px !important;
            border: 1px solid rgba(127, 29, 29, 0.45) !important;
            background: #ef4444 !important;
            color: transparent !important;
            font-size: 0 !important;
            line-height: 0 !important;
            text-shadow: none !important;
        }}

        .leaflet-popup-close-button:hover {{
            background: #dc2626 !important;
        }}

        @media (max-width: 900px) {{
            .stat-grid {{
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }}

            .hero {{
                padding: 0.95rem;
            }}
        }}

        @media (max-width: 520px) {{
            .stat-grid {{
                grid-template-columns: 1fr;
            }}

            .hero-title {{
                font-size: 2.2rem;
            }}


        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    return

def inject_layout_vars() -> None:
    record_left = int(st.session_state.get("record_panel_x", 24)) + 18
    record_top = int(st.session_state.get("record_panel_y", 24)) + 18
    record_open = bool(st.session_state.get("right_drawer_open", False))
    record_opacity = "1" if record_open else "0"
    record_pointer_events = "auto" if record_open else "none"
    st.markdown(
        f"""
        <style>
        :root {{
            --record-panel-left: {record_left}px;
            --record-panel-top: {record_top}px;
            --record-panel-opacity: {record_opacity};
            --record-panel-pointer-events: {record_pointer_events};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_direction_preview_bridge() -> None:
    components.html(
        """
        <script>
        (function() {
            var host = window.parent;
            if (!host || host.__pgisDirectionPreviewBridgeInstalled) {
                return;
            }
            host.__pgisDirectionPreviewBridgeInstalled = true;
            host.addEventListener("message", function(event) {
                var data = event.data || {};
                if (data.type !== "pgis:directionPreview" || !host.document) {
                    return;
                }
                host.document.querySelectorAll("iframe").forEach(function(frame) {
                    if (frame.contentWindow && frame.contentWindow !== event.source) {
                        frame.contentWindow.postMessage(data, "*");
                    }
                });
            });
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def ensure_state() -> None:
    now = datetime.now()
    defaults = {
        "spots": load_spot_records(),
        "selected_point": None,
        "map_center": SEOUL_CENTER,
        "active_spot_id": 1,
        "map_zoom": 12,
        "right_drawer_open": False,
        "form_lat": SEOUL_CENTER[0],
        "form_lng": SEOUL_CENTER[1],
        "record_panel_x": 24,
        "record_panel_y": 24,
        "record_long_exposure": False,
        "picking_location": False,
        "last_context_click_nonce": None,
        "last_panel_close_nonce": None,
        "last_delete_spot_nonce": None,
        "last_spot_select_nonce": None,
        "delete_feedback": "",
        "options_panel_open": False,
        "dark_mode": False,
        "route_enabled": False,
        "route_mode": "차량",
        "route_spot_ids": [],
        "route_coordinates": [],
        "route_segment_distances": [],
        "route_error": "",
        "route_result_signature": None,
        "last_route_spot_nonce": None,
        "record_direction": 45,
        "record_date_text": now.strftime("%Y-%m-%d"),
        "record_time_text": now.strftime("%H:%M"),
        "record_iso_text": "",
        "record_f_value": "",
        "record_focal": "",
        "record_shutter_value_text": "",
        "record_lat_text": f"{SEOUL_CENTER[0]:.6f}",
        "record_lng_text": f"{SEOUL_CENTER[1]:.6f}",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    st.session_state.spots = [
        normalize_spot(spot, index + 1)
        for index, spot in enumerate(st.session_state.get("spots", []))
    ]
    visible_spots = available_spots(st.session_state.spots)
    visible_spot_ids = {int(spot["id"]) for spot in visible_spots}
    st.session_state.route_spot_ids = [
        int(spot_id)
        for spot_id in st.session_state.get("route_spot_ids", [])
        if int(spot_id) in visible_spot_ids
    ]
    if not any(spot["id"] == st.session_state.active_spot_id for spot in visible_spots):
        st.session_state.active_spot_id = visible_spots[0]["id"] if visible_spots else None


def selected_point_value(default: tuple[float, float] | None = SEOUL_CENTER) -> tuple[float, float] | None:
    point = st.session_state.get("selected_point")
    if isinstance(point, (list, tuple)) and len(point) == 2:
        try:
            return float(point[0]), float(point[1])
        except (TypeError, ValueError):
            pass
    return default


def clear_record_selection() -> None:
    st.session_state.right_drawer_open = False
    st.session_state.picking_location = False
    st.session_state.selected_point = None


def close_record_panel() -> None:
    clear_record_selection()


def toggle_options_panel() -> None:
    st.session_state.options_panel_open = not bool(st.session_state.get("options_panel_open", False))


def clear_route_selection() -> None:
    st.session_state.route_spot_ids = []
    invalidate_route_result()


def invalidate_route_result() -> None:
    st.session_state.route_coordinates = []
    st.session_state.route_segment_distances = []
    st.session_state.route_error = ""
    st.session_state.route_result_signature = None


def route_signature() -> tuple[str, tuple[int, ...]]:
    return (
        str(st.session_state.get("route_mode", "차량")),
        tuple(int(spot_id) for spot_id in st.session_state.get("route_spot_ids", [])),
    )


def exit_route_mode() -> None:
    st.session_state.route_enabled = False
    clear_route_selection()


def enter_route_mode() -> None:
    st.session_state.route_enabled = True
    st.session_state.options_panel_open = False


def toggle_record_location_picker() -> None:
    st.session_state.picking_location = not st.session_state.picking_location
    st.session_state.right_drawer_open = True


def parse_coordinate(value: Any, fallback: float) -> float:
    try:
        return round(float(str(value).strip()), 6)
    except (TypeError, ValueError):
        return round(float(fallback), 6)


def escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def compass_label(degrees: int | float) -> str:
    labels = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((float(degrees) + 22.5) // 45) % 8
    return labels[idx]


def spot_drct(spot: dict[str, Any]) -> int:
    try:
        return int(float(spot.get("drct", spot.get("direction", 0)))) % 360
    except (TypeError, ValueError):
        return 0


def spot_available(spot: dict[str, Any]) -> int:
    value = spot.get("Available", spot.get("available", 1))
    try:
        return 1 if int(float(value)) == 1 else 0
    except (TypeError, ValueError):
        return 1


def spot_password(spot: dict[str, Any]) -> str:
    password = str(spot.get("password") or "").strip()
    return password or DEFAULT_SPOT_PASSWORD


def available_spots(spots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [spot for spot in spots if spot_available(spot) == 1]


def spot_url(spot: dict[str, Any]) -> str:
    return str(spot.get("URL") or spot.get("url") or spot.get("memo") or "").strip()


def spot_comp(spot: dict[str, Any]) -> dict[str, str]:
    comp = spot.get("comp")
    if not isinstance(comp, dict):
        comp = {}
    return {
        "F값": str(comp.get("F값") or spot.get("aperture") or "").strip(),
        "ISO값": str(comp.get("ISO값") or spot.get("iso") or "").strip(),
        "셔터스피드": str(comp.get("셔터스피드") or spot.get("shutter_speed") or "").strip(),
        "화각": str(comp.get("화각") or "").strip(),
    }


def advanced_items(spot: dict[str, Any]) -> list[tuple[str, str]]:
    comp = spot_comp(spot)
    items = [
        ("BODY", str(spot.get("body") or "").strip()),
        ("LENS", str(spot.get("lens") or "").strip()),
        ("F", comp.get("F값", "")),
        ("ISO", comp.get("ISO값", "")),
        ("SHUTTER", comp.get("셔터스피드", "")),
        ("FOCAL", comp.get("화각", "")),
    ]
    return [(label, value) for label, value in items if value]


def has_advanced_info(spot: dict[str, Any]) -> bool:
    return bool(advanced_items(spot))


def time_meridiem(value: str | None) -> str:
    text = str(value or "").strip()
    if text.startswith("오후"):
        return "오후"
    if text.startswith("오전"):
        return "오전"
    clock = normalize_24h_clock(text)
    if not clock:
        return "오전"
    return "오전" if int(clock.split(":", 1)[0]) < 12 else "오후"


def normalize_24h_clock(value: str | None) -> str | None:
    text = str(value or "").strip().replace(".", ":")
    if not text:
        return None
    meridiem = None
    for marker in TIME_OPTIONS:
        if text.startswith(marker):
            meridiem = marker
            text = text[len(marker) :].strip()
            break
    if ":" in text:
        hour_text, minute_text = text.split(":", 1)
    elif text.isdigit() and len(text) in {3, 4}:
        hour_text, minute_text = text[:-2], text[-2:]
    else:
        hour_text, minute_text = text, "00"
    if not hour_text.isdigit() or not minute_text.isdigit():
        try:
            parsed = datetime.fromisoformat(text)
            return f"{parsed.hour:02d}:{parsed.minute:02d}"
        except ValueError:
            return None
    hour = int(hour_text)
    minute = int(minute_text)
    if meridiem:
        if not 1 <= hour <= 12 or not 0 <= minute <= 59:
            return None
        if meridiem == "오전":
            hour = 0 if hour == 12 else hour
        else:
            hour = 12 if hour == 12 else hour + 12
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def normalize_date_value(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.isdigit() and len(text) == 8:
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return datetime.fromisoformat(text).date().isoformat()
    except ValueError:
        pass
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def normalize_time_value(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        text = datetime.now().strftime("%H:%M")
    clock = normalize_24h_clock(text)
    if clock:
        return clock
    legacy_map = {
        "새벽": "05:30",
        "아침": "08:00",
        "낮": "12:00",
        "해질녘": "18:30",
        "밤": "21:00",
    }
    if value in legacy_map:
        return legacy_map[str(value)]
    return datetime.now().strftime("%H:%M")


def normalize_spot(spot: dict[str, Any], fallback_id: int | None = None) -> dict[str, Any]:
    comp = spot_comp(spot)
    weather = spot.get("weather") if spot.get("weather") in WEATHER_OPTIONS else WEATHER_OPTIONS[0]
    time_value = spot.get("time") or spot.get("shot_at") or spot.get("time_band")
    date_value = spot.get("date") or spot.get("shot_at") or spot.get("created_at")
    return {
        "id": spot.get("id", fallback_id or 0),
        "title": str(spot.get("title") or "").strip(),
        "URL": spot_url(spot),
        "lat": float(spot.get("lat", SEOUL_CENTER[0])),
        "lng": float(spot.get("lng", SEOUL_CENTER[1])),
        "drct": spot_drct(spot),
        "Available": spot_available(spot),
        "weather": weather,
        "time": normalize_time_value(str(time_value or "")),
        "date": normalize_date_value(str(date_value or "")) or "",
        "body": str(spot.get("body") or "").strip(),
        "lens": str(spot.get("lens") or spot.get("camera") or "").strip(),
        "comp": comp,
        "password": spot_password(spot),
    }


def render_direction_dial() -> int:
    current = int(st.session_state.get("record_direction", 45)) % 360
    returned = DIRECTION_DIAL_COMPONENT(
        value=current,
        dark=bool(st.session_state.get("dark_mode", False)),
        key="record_direction_dial",
        default=current,
    )
    direction = current
    if returned is not None:
        try:
            direction = int(round(float(returned))) % 360
        except (TypeError, ValueError):
            direction = current
    st.session_state.record_direction = direction
    st.markdown(
        f"""
        <div class="record-dial-caption">{direction:03d} {compass_label(direction)}</div>
        """,
        unsafe_allow_html=True,
    )
    return direction


def destination_point(lat: float, lng: float, bearing: float, distance_m: float = 360) -> tuple[float, float]:
    radius = 6_371_000
    bearing_rad = math.radians(bearing)
    lat_rad = math.radians(lat)
    lng_rad = math.radians(lng)
    angular_distance = distance_m / radius

    end_lat = math.asin(
        math.sin(lat_rad) * math.cos(angular_distance)
        + math.cos(lat_rad) * math.sin(angular_distance) * math.cos(bearing_rad)
    )
    end_lng = lng_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat_rad),
        math.cos(angular_distance) - math.sin(lat_rad) * math.sin(end_lat),
    )
    return math.degrees(end_lat), math.degrees(end_lng)


def is_valid_link(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def link_html(value: str | None, label: str = "링크 열기") -> str:
    if not is_valid_link(value):
        return f'<span style="color:{ui_color("color-muted")};">링크 없음</span>'
    url = escape(str(value).strip())
    text = escape(label)
    accent = ui_color("color-accent-strong")
    accent_soft = ui_color("color-accent-soft")
    return (
        f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
        f'style="color:{accent};text-decoration:none;font-weight:900;'
        f'border-bottom:1px solid {accent_soft};">'
        f"{text}</a>"
    )


def compress_photo(uploaded_file: Any) -> tuple[bytes, str]:
    raw = uploaded_file.getvalue()
    mime = uploaded_file.type or "image/jpeg"
    try:
        image = Image.open(io.BytesIO(raw))
        image.thumbnail((1100, 1100))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=86, optimize=True)
        return out.getvalue(), "image/jpeg"
    except Exception:
        return raw, mime


def data_uri(photo_bytes: bytes | None, mime: str | None) -> str | None:
    if not photo_bytes:
        return None
    encoded = base64.b64encode(photo_bytes).decode("ascii")
    return f"data:{mime or 'image/jpeg'};base64,{encoded}"


def popup_html(spot: dict[str, Any]) -> str:
    color = WEATHER_COLORS.get(spot.get("weather", WEATHER_OPTIONS[0]), ui_color("color-accent"))
    surface = ui_color("color-surface")
    surface_soft = ui_color("color-surface-soft")
    border = ui_color("color-border")
    text = ui_color("color-text")
    muted = ui_color("color-muted")
    img = data_uri(spot.get("photo_bytes"), spot.get("photo_mime"))
    image_html = ""
    if img:
        image_html = (
            f'<img src="{img}" style="width:100%;max-height:150px;object-fit:cover;'
            f'margin-bottom:10px;border:1px solid {border};border-radius:8px;" />'
        )
    link = link_html(spot_url(spot))
    return f"""
    <div style="width:282px;box-sizing:border-box;font-family:Inter,Arial,sans-serif;color:{text};background:{surface};">
        {image_html}
        <div style="border-left:3px solid {color};padding-left:10px;margin-bottom:10px;">
            <div style="font-size:12px;color:{muted};font-weight:800;text-transform:uppercase;">SPOT NODE</div>
            <div style="font-size:16px;font-weight:900;line-height:1.25;color:{text};">{escape(spot["title"])}</div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;">
            <div style="border:1px solid {border};background:{surface_soft};padding:8px;border-radius:8px;">
                <div style="font-size:10px;color:{muted};font-weight:800;">LINK</div>
                <div style="font-size:12px;margin-top:8px;">{link}</div>
            </div>
            <div style="border:1px solid {border};background:{surface_soft};padding:8px;border-radius:8px;">
                <div style="font-size:10px;color:{muted};font-weight:800;">CONDITION</div>
                <div style="font-size:12px;color:{text};font-weight:850;margin-top:4px;">{escape(spot.get("weather"))}</div>
                <div style="font-size:12px;color:{muted};font-weight:750;">{escape(spot.get("time"))}</div>
            </div>
        </div>
        <div style="font-size:12px;line-height:1.55;color:{muted};border-top:1px solid {border};padding-top:9px;">{escape(spot.get("body") or spot.get("lens") or "상세 정보 없음")}</div>
    </div>
    """


def record_popup_html(spot: dict[str, Any]) -> str:
    color = WEATHER_COLORS.get(spot.get("weather", WEATHER_OPTIONS[0]), ui_color("color-accent"))
    surface = ui_color("color-surface")
    surface_soft = ui_color("color-surface-soft")
    border = ui_color("color-border")
    text = ui_color("color-text")
    muted = ui_color("color-muted")
    link = link_html(spot_url(spot), "OPEN URL")
    shot_date = spot.get("date") or "-"
    shot_time = spot.get("time") or "-"
    advanced_html = ""
    items = advanced_items(spot)
    if items:
        advanced_html = (
            '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;'
            f'font-size:12px;line-height:1.45;color:{muted};'
            f'border-top:1px solid {border};padding-top:9px;">'
            + "".join(
                f'<div><span style="color:{muted};font-weight:800;">{escape(label)}</span><br />{escape(value)}</div>'
                for label, value in items
            )
            + "</div>"
        )
    spot_id = int(spot.get("id", 0))
    return f"""
    <div style="position:relative;width:282px;box-sizing:border-box;font-family:Inter,Arial,sans-serif;color:{text};background:{surface};padding-top:16px;">
        <button type="button" class="pgis-popup-delete" data-spot-id="{spot_id}" title="삭제"
            style="position:absolute;top:-1px;right:32px;width:12px;height:12px;box-sizing:border-box;border-radius:999px;border:1px solid rgba(120,53,15,.45);background:#f59e0b;margin:0;padding:0;cursor:pointer;font-size:0;line-height:0;transform:none;"></button>
        <div style="border-left:3px solid {color};padding-left:10px;margin-bottom:10px;">
            <div style="font-size:12px;color:{muted};font-weight:800;text-transform:uppercase;">SPOT NODE</div>
            <div style="font-size:16px;font-weight:900;line-height:1.25;color:{text};">{escape(spot.get("title"))}</div>
            <div style="font-size:12px;color:{color};font-weight:900;margin-top:4px;">{compass_label(spot_drct(spot))}</div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;">
            <div style="border:1px solid {border};background:{surface_soft};padding:8px;border-radius:8px;">
                <div style="font-size:10px;color:{muted};font-weight:800;">URL</div>
                <div style="font-size:12px;margin-top:8px;">{link}</div>
            </div>
            <div style="border:1px solid {border};background:{surface_soft};padding:8px;border-radius:8px;">
                <div style="font-size:10px;color:{muted};font-weight:800;">SHOT</div>
                <div style="font-size:12px;color:{text};font-weight:850;margin-top:4px;">{escape(shot_date)}</div>
                <div style="font-size:12px;color:{muted};font-weight:750;">{escape(shot_time)}</div>
            </div>
        </div>
        {advanced_html}
    </div>
    """


def add_direction_vector(fmap: folium.Map, spot: dict[str, Any]) -> None:
    color = WEATHER_COLORS.get(spot.get("weather", WEATHER_OPTIONS[0]), ui_color("color-accent"))
    surface = ui_color("color-surface")
    text = ui_color("color-text")
    end_lat, end_lng = destination_point(spot["lat"], spot["lng"], spot_drct(spot))
    folium.CircleMarker(
        location=(spot["lat"], spot["lng"]),
        radius=10,
        color=surface,
        weight=2,
        fill=True,
        fill_color=color,
        fill_opacity=0.52,
        opacity=0.92,
    ).add_to(fmap)
    folium.CircleMarker(
        location=(spot["lat"], spot["lng"]),
        radius=4,
        color=surface,
        weight=1,
        fill=True,
        fill_color=text,
        fill_opacity=0.95,
    ).add_to(fmap)
    folium.PolyLine(
        locations=[(spot["lat"], spot["lng"]), (end_lat, end_lng)],
        color=color,
        weight=4,
        opacity=0.92,
        dash_array="10, 8",
    ).add_to(fmap)
    folium.CircleMarker(
        location=(end_lat, end_lng),
        radius=4,
        color=color,
        weight=2,
        fill=True,
        fill_color=color,
        fill_opacity=0.95,
    ).add_to(fmap)


class DirectionClickScript(MacroElement):
    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var marker = {{ this.marker_name }};
            var map = {{ this.map_name }};
            var start = [{{ this.start_lat }}, {{ this.start_lng }}];
            var end = [{{ this.end_lat }}, {{ this.end_lng }}];
            var color = "{{ this.color }}";
            var surface = "{{ this.surface }}";
            var text = "{{ this.text }}";
            var spotId = {{ this.spot_id }};
            var recordPanelOpen = {{ this.record_panel_open }};
            function streamlitValue(payload) {
                payload.center = map.getCenter();
                payload.zoom = map.getZoom();
                if (window.__GLOBAL_DATA__) {
                    window.__GLOBAL_DATA__.previous_data = payload;
                }
                if (window.Streamlit && window.Streamlit.setComponentValue) {
                    window.Streamlit.setComponentValue(payload);
                    return;
                }
                window.parent.postMessage({
                    isStreamlitMessage: true,
                    type: "streamlit:setComponentValue",
                    value: payload,
                    dataType: "json"
                }, "*");
            }
            function clearDirectionLayer() {
                if (window.__pgisDirectionLayer) {
                    map.removeLayer(window.__pgisDirectionLayer);
                    window.__pgisDirectionLayer = null;
                }
            }
            marker.on("click", function(event) {
                if (event && event.originalEvent) {
                    L.DomEvent.stopPropagation(event.originalEvent);
                }
                clearDirectionLayer();
                if (window.__pgisRouteModeActive && window.__pgisSelectRouteSpot) {
                    marker.closePopup();
                    window.__pgisSelectRouteSpot(spotId);
                    return;
                }
                if (recordPanelOpen) {
                    recordPanelOpen = false;
                    streamlitValue({
                        _pgis_event: "select_spot",
                        _pgis_nonce: String(Date.now()) + "-" + String(Math.random()),
                        spot_id: spotId
                    });
                }
                window.__pgisDirectionLayer = L.layerGroup([
                    L.circleMarker(start, {
                        radius: 12,
                        color: surface,
                        weight: 2,
                        fill: true,
                        fillColor: color,
                        fillOpacity: 0.52,
                        opacity: 0.94,
                        interactive: false
                    }),
                    L.circleMarker(start, {
                        radius: 4,
                        color: surface,
                        weight: 1,
                        fill: true,
                        fillColor: text,
                        fillOpacity: 0.98,
                        interactive: false
                    }),
                    L.polyline([start, end], {
                        color: color,
                        weight: 4,
                        opacity: 0.94,
                        dashArray: "10 8",
                        interactive: false
                    }),
                    L.circleMarker(end, {
                        radius: 4,
                        color: color,
                        weight: 2,
                        fill: true,
                        fillColor: color,
                        fillOpacity: 0.96,
                        interactive: false
                    })
                ]).addTo(map);
            });
            marker.on("popupclose", clearDirectionLayer);
        })();
        {% endmacro %}
        """
    )

    def __init__(self, fmap: folium.Map, marker_name: str, spot: dict[str, Any]) -> None:
        super().__init__()
        self._name = "DirectionClickScript"
        end_lat, end_lng = destination_point(spot["lat"], spot["lng"], spot_drct(spot))
        self.map_name = fmap.get_name()
        self.marker_name = marker_name
        self.spot_id = int(spot.get("id", 0))
        self.start_lat = f"{float(spot['lat']):.8f}"
        self.start_lng = f"{float(spot['lng']):.8f}"
        self.end_lat = f"{end_lat:.8f}"
        self.end_lng = f"{end_lng:.8f}"
        self.color = WEATHER_COLORS.get(spot.get("weather", WEATHER_OPTIONS[0]), ui_color("color-accent"))
        self.surface = ui_color("color-surface")
        self.text = ui_color("color-text")
        self.record_panel_open = "true" if st.session_state.get("right_drawer_open", False) else "false"


class SpotDeleteScript(MacroElement):
    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            function streamlitValue(payload) {
                payload.center = map.getCenter();
                payload.zoom = map.getZoom();
                if (window.__GLOBAL_DATA__) {
                    window.__GLOBAL_DATA__.previous_data = payload;
                }
                if (window.Streamlit && window.Streamlit.setComponentValue) {
                    window.Streamlit.setComponentValue(payload);
                    return;
                }
                window.parent.postMessage({
                    isStreamlitMessage: true,
                    type: "streamlit:setComponentValue",
                    value: payload,
                    dataType: "json"
                }, "*");
            }
            document.addEventListener("click", function(event) {
                var target = event.target;
                var button = target && target.closest ? target.closest(".pgis-popup-delete") : null;
                if (!button) {
                    return;
                }
                event.preventDefault();
                event.stopPropagation();
                var spotId = Number(button.getAttribute("data-spot-id"));
                if (!Number.isFinite(spotId) || spotId <= 0) {
                    return;
                }
                var password = window.prompt("삭제 password를 입력하세요.");
                if (password === null) {
                    return;
                }
                streamlitValue({
                    _pgis_event: "delete_spot",
                    _pgis_nonce: String(Date.now()) + "-" + String(Math.random()),
                    spot_id: spotId,
                    password: password
                });
            }, true);
        })();
        {% endmacro %}
        """
    )

    def __init__(self, fmap: folium.Map) -> None:
        super().__init__()
        self._name = "SpotDeleteScript"
        self.map_name = fmap.get_name()


class RouteModeScript(MacroElement):
    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            var entries = {{ this.marker_entries_js }};
            var selectedIds = {{ this.selected_ids_json }};
            var routeMode = {{ this.route_mode_json }};
            var initialActive = {{ this.initial_active }};
            var resultReady = {{ this.result_ready }};
            var segmentDistances = {{ this.segment_distances_json }};
            var routeError = {{ this.route_error_json }};
            var routeLayer = {{ this.route_layer_js }};
            var active = initialActive;
            var savedPopups = new Map();
            var badgeLayer = L.layerGroup().addTo(map);
            var container = map.getContainer();
            var root = document.createElement("div");
            root.className = "pgis-route-ui";
            root.innerHTML = [
                '<button type="button" class="pgis-route-activate" title="경로 계산 모드">경로</button>',
                '<section class="pgis-route-panel" aria-live="polite"></section>',
                '<div class="pgis-route-loading"><div class="pgis-route-loading-spinner"></div><strong>경로 계산 중</strong></div>'
            ].join("");
            container.appendChild(root);
            var activateButton = root.querySelector(".pgis-route-activate");
            var panel = root.querySelector(".pgis-route-panel");
            var loading = root.querySelector(".pgis-route-loading");

            L.DomEvent.disableClickPropagation(root);
            L.DomEvent.disableScrollPropagation(panel);

            function streamlitValue(payload) {
                payload.center = map.getCenter();
                payload.zoom = map.getZoom();
                if (window.__GLOBAL_DATA__) {
                    window.__GLOBAL_DATA__.previous_data = payload;
                }
                if (window.Streamlit && window.Streamlit.setComponentValue) {
                    window.Streamlit.setComponentValue(payload);
                    return;
                }
                window.parent.postMessage({
                    isStreamlitMessage: true,
                    type: "streamlit:setComponentValue",
                    value: payload,
                    dataType: "json"
                }, "*");
            }

            function entryById(spotId) {
                return entries.find(function(entry) {
                    return Number(entry.id) === Number(spotId);
                });
            }

            function escapeHtml(value) {
                return String(value || "")
                    .replaceAll("&", "&amp;")
                    .replaceAll("<", "&lt;")
                    .replaceAll(">", "&gt;")
                    .replaceAll('"', "&quot;")
                    .replaceAll("'", "&#039;");
            }

            function formatDistance(meters) {
                var value = Number(meters) || 0;
                if (value >= 1000) {
                    return (value / 1000).toFixed(value >= 10000 ? 0 : 1) + " km";
                }
                return Math.round(value) + " m";
            }

            function suspendPopups() {
                map.closePopup();
                entries.forEach(function(entry) {
                    if (!savedPopups.has(entry.id)) {
                        savedPopups.set(entry.id, entry.marker.getPopup());
                    }
                    entry.marker.unbindPopup();
                });
            }

            function restorePopups() {
                entries.forEach(function(entry) {
                    var popup = savedPopups.get(entry.id);
                    if (popup) {
                        entry.marker.bindPopup(popup);
                    }
                });
                savedPopups.clear();
            }

            function renderBadges() {
                badgeLayer.clearLayers();
                selectedIds.forEach(function(spotId, index) {
                    var entry = entryById(spotId);
                    if (!entry) {
                        return;
                    }
                    L.marker([entry.lat, entry.lng], {
                        interactive: false,
                        icon: L.divIcon({
                            className: "pgis-route-order-icon",
                            html: '<span class="pgis-route-order">' + String(index + 1) + "</span>",
                            iconSize: [24, 24],
                            iconAnchor: [12, 12]
                        })
                    }).addTo(badgeLayer);
                });
            }

            function routeListHtml(withRemove) {
                if (!selectedIds.length) {
                    return '<p class="pgis-route-empty">지도에서 경유할 지점을 순서대로 선택하세요.</p>';
                }
                return '<ol class="pgis-route-list">' + selectedIds.map(function(spotId, index) {
                    var entry = entryById(spotId);
                    if (!entry) {
                        return "";
                    }
                    var removeButton = withRemove
                        ? '<button type="button" class="pgis-route-remove" data-spot-id="' + String(spotId) + '" title="선택 지점 삭제">×</button>'
                        : "";
                    return [
                        '<li class="pgis-route-item">',
                        '<span class="pgis-route-number">' + String(index + 1) + "</span>",
                        '<span class="pgis-route-name" title="' + escapeHtml(entry.title) + '">' + escapeHtml(entry.title || "제목 없음") + "</span>",
                        removeButton,
                        "</li>"
                    ].join("");
                }).join("") + "</ol>";
            }

            function resultListHtml() {
                if (!selectedIds.length) {
                    return '<p class="pgis-route-empty">계산된 지점이 없습니다.</p>';
                }
                var html = '<div class="pgis-route-result-list">';
                selectedIds.forEach(function(spotId, index) {
                    var entry = entryById(spotId);
                    if (!entry) {
                        return;
                    }
                    html += [
                        '<div class="pgis-route-result-item">',
                        '<span class="pgis-route-number">' + String(index + 1) + "</span>",
                        '<span class="pgis-route-name">' + escapeHtml(entry.title || "제목 없음") + "</span>",
                        "</div>"
                    ].join("");
                    if (index < selectedIds.length - 1) {
                        html += [
                            '<div class="pgis-route-leg">',
                            '<span class="pgis-route-arrow">↓</span>',
                            '<span>' + formatDistance(segmentDistances[index]) + "</span>",
                            "</div>"
                        ].join("");
                    }
                });
                return html + "</div>";
            }

            function renderSelectionPanel() {
                panel.innerHTML = [
                    '<div class="pgis-route-head"><strong>경로 계산 모드</strong><span>' + String(selectedIds.length) + "개 지점</span></div>",
                    routeListHtml(true),
                    '<button type="button" class="pgis-route-clear" ' + (selectedIds.length ? "" : "disabled") + '>선택 초기화</button>',
                    '<div class="pgis-route-mode" role="group" aria-label="이동 방식">',
                    '<button type="button" data-mode="차량" class="' + (routeMode === "차량" ? "is-active" : "") + '">차량</button>',
                    '<button type="button" data-mode="도보" class="' + (routeMode === "도보" ? "is-active" : "") + '">도보</button>',
                    "</div>",
                    '<button type="button" class="pgis-route-calculate" ' + (selectedIds.length >= 2 ? "" : "disabled") + '>경로 계산</button>',
                    '<button type="button" class="pgis-route-exit">나가기</button>'
                ].join("");
            }

            function renderResultPanel() {
                var status = routeError
                    ? '<p class="pgis-route-error">' + escapeHtml(routeError) + "</p>"
                    : resultListHtml();
                panel.innerHTML = [
                    '<div class="pgis-route-head"><strong>계산 경로</strong><span>' + escapeHtml(routeMode) + "</span></div>",
                    status,
                    '<button type="button" class="pgis-route-exit">나가기</button>'
                ].join("");
            }

            function render() {
                activateButton.hidden = active;
                panel.classList.toggle("is-open", active);
                window.__pgisRouteModeActive = active;
                renderBadges();
                if (!active) {
                    return;
                }
                if (resultReady) {
                    renderResultPanel();
                } else {
                    renderSelectionPanel();
                }
            }

            function activate() {
                active = true;
                resultReady = false;
                suspendPopups();
                render();
            }

            function exit() {
                var notifyServer = initialActive;
                active = false;
                selectedIds = [];
                badgeLayer.clearLayers();
                restorePopups();
                if (routeLayer && map.hasLayer(routeLayer)) {
                    map.removeLayer(routeLayer);
                }
                render();
                if (notifyServer) {
                    streamlitValue({
                        _pgis_event: "exit_route_mode",
                        _pgis_nonce: String(Date.now()) + "-" + String(Math.random())
                    });
                }
            }

            window.__pgisSelectRouteSpot = function(spotId) {
                if (!active || resultReady || selectedIds.includes(Number(spotId))) {
                    return;
                }
                selectedIds.push(Number(spotId));
                render();
            };

            activateButton.addEventListener("click", activate);
            panel.addEventListener("click", function(event) {
                var target = event.target;
                var removeButton = target.closest(".pgis-route-remove");
                if (removeButton) {
                    var removeId = Number(removeButton.getAttribute("data-spot-id"));
                    selectedIds = selectedIds.filter(function(spotId) {
                        return Number(spotId) !== removeId;
                    });
                    render();
                    return;
                }
                if (target.closest(".pgis-route-clear")) {
                    selectedIds = [];
                    render();
                    return;
                }
                var modeButton = target.closest(".pgis-route-mode button");
                if (modeButton) {
                    routeMode = modeButton.getAttribute("data-mode") || "차량";
                    render();
                    return;
                }
                if (target.closest(".pgis-route-calculate")) {
                    if (selectedIds.length < 2) {
                        return;
                    }
                    loading.classList.add("is-visible");
                    streamlitValue({
                        _pgis_event: "calculate_route",
                        _pgis_nonce: String(Date.now()) + "-" + String(Math.random()),
                        route_spot_ids: selectedIds.slice(),
                        route_mode: routeMode
                    });
                    return;
                }
                if (target.closest(".pgis-route-exit")) {
                    exit();
                }
            });

            if (initialActive) {
                suspendPopups();
            }
            render();
            if (initialActive && resultReady) {
                loading.classList.add("is-visible");
                map.whenReady(function() {
                    var hidden = false;
                    function hideLoading() {
                        if (hidden) {
                            return;
                        }
                        hidden = true;
                        loading.classList.remove("is-visible");
                    }
                    var tileLayer = null;
                    map.eachLayer(function(layer) {
                        if (!tileLayer && layer instanceof L.TileLayer) {
                            tileLayer = layer;
                        }
                    });
                    if (tileLayer) {
                        tileLayer.once("load", hideLoading);
                    }
                    window.setTimeout(hideLoading, 900);
                });
            }
        })();
        {% endmacro %}
        """
    )

    def __init__(
        self,
        fmap: folium.Map,
        marker_records: list[tuple[str, dict[str, Any]]],
        route_layer_name: str | None,
    ) -> None:
        super().__init__()
        self._name = "RouteModeScript"
        self.map_name = fmap.get_name()
        marker_entries = []
        for marker_name, spot in marker_records:
            marker_entries.append(
                "{"
                f"id:{int(spot.get('id', 0))},"
                f"title:{json.dumps(str(spot.get('title') or ''), ensure_ascii=False)},"
                f"lat:{float(spot['lat']):.8f},"
                f"lng:{float(spot['lng']):.8f},"
                f"marker:{marker_name}"
                "}"
            )
        self.marker_entries_js = "[" + ",".join(marker_entries) + "]"
        self.selected_ids_json = json.dumps(
            [int(spot_id) for spot_id in st.session_state.get("route_spot_ids", [])]
        )
        self.route_mode_json = json.dumps(str(st.session_state.get("route_mode", "차량")), ensure_ascii=False)
        self.initial_active = "true" if st.session_state.get("route_enabled", False) else "false"
        self.result_ready = (
            "true"
            if st.session_state.get("route_result_signature") == route_signature()
            else "false"
        )
        self.segment_distances_json = json.dumps(
            [float(value) for value in st.session_state.get("route_segment_distances", [])]
        )
        self.route_error_json = json.dumps(str(st.session_state.get("route_error") or ""), ensure_ascii=False)
        self.route_layer_js = route_layer_name or "null"


class RightClickSelectScript(MacroElement):
    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            var selectedLatLng = {{ this.panel_open }} ? L.latLng({{ this.selected_lat }}, {{ this.selected_lng }}) : null;
            var recordPanelOpen = {{ this.panel_open }};
            var panelCloseNotified = false;
            var panelSyncFrame = 0;
            var panelOffset = { x: 18, y: 18 };
            function destinationPoint(latlng, bearing, distanceMeters) {
                var radius = 6371000;
                var bearingRad = bearing * Math.PI / 180;
                var latRad = latlng.lat * Math.PI / 180;
                var lngRad = latlng.lng * Math.PI / 180;
                var angularDistance = distanceMeters / radius;
                var endLat = Math.asin(
                    Math.sin(latRad) * Math.cos(angularDistance) +
                    Math.cos(latRad) * Math.sin(angularDistance) * Math.cos(bearingRad)
                );
                var endLng = lngRad + Math.atan2(
                    Math.sin(bearingRad) * Math.sin(angularDistance) * Math.cos(latRad),
                    Math.cos(angularDistance) - Math.sin(latRad) * Math.sin(endLat)
                );
                return L.latLng(endLat * 180 / Math.PI, endLng * 180 / Math.PI);
            }
            function compassLabel(degrees) {
                var labels = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
                return labels[Math.floor((((degrees % 360) + 360) % 360 + 22.5) / 45) % 8];
            }
            function getHostDocument() {
                try {
                    return window.parent && window.parent.document ? window.parent.document : null;
                } catch (error) {
                    return null;
                }
            }
            function setNativeValue(input, value) {
                if (!input) {
                    return;
                }
                var inputWindow = input.ownerDocument && input.ownerDocument.defaultView ? input.ownerDocument.defaultView : window;
                var setter = Object.getOwnPropertyDescriptor(inputWindow.HTMLInputElement.prototype, "value").set;
                setter.call(input, value);
                input.setAttribute("value", value);
                input.dispatchEvent(new inputWindow.Event("input", { bubbles: true }));
                input.dispatchEvent(new inputWindow.Event("change", { bubbles: true }));
            }
            function updateHostRecordCoordinates(latlng) {
                var hostDocument = getHostDocument();
                if (!hostDocument) {
                    return;
                }
                var lat = Number(latlng.lat).toFixed(6);
                var lng = Number(latlng.lng).toFixed(6);
                var panel = hostDocument.querySelector(".st-key-right_drawer_panel");
                if (panel) {
                    var coord = panel.querySelector(".record-coord");
                    if (coord) {
                        coord.textContent = lat + ", " + lng;
                    }
                }
                setNativeValue(hostDocument.querySelector(".st-key-record_lat_text input"), lat);
                setNativeValue(hostDocument.querySelector(".st-key-record_lng_text input"), lng);
            }
            function setHostRecordPanelPosition(point) {
                var hostDocument = getHostDocument();
                if (!hostDocument || !hostDocument.documentElement) {
                    return;
                }
                hostDocument.documentElement.style.setProperty(
                    "--record-panel-left",
                    Math.round(point.x + panelOffset.x) + "px"
                );
                hostDocument.documentElement.style.setProperty(
                    "--record-panel-top",
                    Math.round(point.y + panelOffset.y) + "px"
                );
                hostDocument.documentElement.style.setProperty("--record-panel-opacity", "1");
                hostDocument.documentElement.style.setProperty("--record-panel-pointer-events", "auto");
                var panel = hostDocument.querySelector(".st-key-right_drawer_panel");
                if (panel) {
                    panel.style.opacity = "1";
                    panel.style.pointerEvents = "auto";
                }
            }
            function hideHostRecordPanel() {
                var hostDocument = getHostDocument();
                if (!hostDocument) {
                    return;
                }
                if (hostDocument.documentElement) {
                    hostDocument.documentElement.style.setProperty("--record-panel-opacity", "0");
                    hostDocument.documentElement.style.setProperty("--record-panel-pointer-events", "none");
                }
                var panel = hostDocument.querySelector(".st-key-right_drawer_panel");
                if (panel) {
                    panel.style.opacity = "0";
                    panel.style.pointerEvents = "none";
                }
            }
            function attachHostRecordPanelCloseHandler() {
                var hostDocument = getHostDocument();
                if (!hostDocument) {
                    return;
                }
                if (hostDocument.__pgisRecordCloseHandler) {
                    hostDocument.removeEventListener("click", hostDocument.__pgisRecordCloseHandler, true);
                }
                hostDocument.__pgisRecordCloseHandler = function(event) {
                    var target = event.target;
                    var button = target && target.closest ? target.closest(".st-key-close_record_panel button") : null;
                    if (!button) {
                        return;
                    }
                    recordPanelOpen = false;
                    panelCloseNotified = true;
                    selectedLatLng = null;
                    hideHostRecordPanel();
                    clearSelectedPointMarkers();
                };
                hostDocument.addEventListener("click", hostDocument.__pgisRecordCloseHandler, true);
            }
            function selectedPointIsInsideMap(point) {
                var size = map.getSize();
                return (
                    map.getBounds().contains(selectedLatLng) &&
                    point.x >= 0 &&
                    point.y >= 0 &&
                    point.x <= size.x &&
                    point.y <= size.y
                );
            }
            function closeRecordPanelOutOfBounds() {
                if (!recordPanelOpen || panelCloseNotified) {
                    return;
                }
                recordPanelOpen = false;
                panelCloseNotified = true;
                hideHostRecordPanel();
                selectedLatLng = null;
                clearSelectedPointMarkers();
            }
            function syncRecordPanelPosition() {
                if (!recordPanelOpen || !selectedLatLng) {
                    return;
                }
                var point = map.latLngToContainerPoint(selectedLatLng);
                if (!selectedPointIsInsideMap(point)) {
                    closeRecordPanelOutOfBounds();
                    return;
                }
                setHostRecordPanelPosition(point);
            }
            function requestRecordPanelSync() {
                if (!recordPanelOpen || panelSyncFrame) {
                    return;
                }
                panelSyncFrame = (window.requestAnimationFrame || function(callback) {
                    return window.setTimeout(callback, 16);
                })(function() {
                    panelSyncFrame = 0;
                    syncRecordPanelPosition();
                });
            }
            function clearSelectedPointMarkers() {
                if (window.__pgisSelectedPointLayer) {
                    map.removeLayer(window.__pgisSelectedPointLayer);
                    window.__pgisSelectedPointLayer = null;
                }
                if (window.__pgisSelectedDirectionLayer) {
                    map.removeLayer(window.__pgisSelectedDirectionLayer);
                    window.__pgisSelectedDirectionLayer = null;
                }
                if (window.__pgisSelectedDirectionLayers) {
                    window.__pgisSelectedDirectionLayers.forEach(function(layer) {
                        if (layer && map.hasLayer(layer)) {
                            map.removeLayer(layer);
                        }
                    });
                    window.__pgisSelectedDirectionLayers = [];
                }
                if (window.__pgisSelectedPointLayers) {
                    window.__pgisSelectedPointLayers.forEach(function(layer) {
                        if (layer && map.hasLayer(layer)) {
                            map.removeLayer(layer);
                        }
                    });
                    window.__pgisSelectedPointLayers = [];
                }
                var removable = [];
                map.eachLayer(function(layer) {
                    if (layer && layer.options && layer.options.pgisSelectedPoint) {
                        removable.push(layer);
                    }
                    if (layer && layer.options && layer.options.pgisSelectedDirection) {
                        removable.push(layer);
                    }
                });
                removable.forEach(function(layer) {
                    if (map.hasLayer(layer)) {
                        map.removeLayer(layer);
                    }
                });
            }
            function drawSelectedPoint(latlng) {
                clearSelectedPointMarkers();
                window.__pgisSelectedPointLayer = L.layerGroup([
                    L.circleMarker(latlng, {
                        radius: 12,
                        color: "{{ this.selected_ring }}",
                        weight: 2,
                        fill: true,
                        fillColor: "{{ this.selected_fill }}",
                        fillOpacity: 0.34,
                        opacity: 0.94,
                        pgisSelectedPoint: true,
                        interactive: false
                    }),
                    L.circleMarker(latlng, {
                        radius: 4,
                        color: "{{ this.selected_inner_stroke }}",
                        weight: 1,
                        fill: true,
                        fillColor: "{{ this.selected_inner_fill }}",
                        fillOpacity: 0.96,
                        pgisSelectedPoint: true,
                        interactive: false
                    })
                ]).addTo(map);
            }
            function drawDirectionPreview(latlng, bearing) {
                if (window.__pgisSelectedDirectionLayer) {
                    map.removeLayer(window.__pgisSelectedDirectionLayer);
                }
                var end = destinationPoint(latlng, bearing, 420);
                var label = String(Math.round(bearing)).padStart(3, "0") + " " + compassLabel(bearing);
                window.__pgisSelectedDirectionLayer = L.layerGroup([
                    L.polyline([latlng, end], {
                        color: "{{ this.direction_color }}",
                        weight: 4,
                        opacity: 0.94,
                        dashArray: "10 8",
                        interactive: false
                    }),
                    L.circleMarker(end, {
                        radius: 5,
                        color: "{{ this.direction_color }}",
                        weight: 2,
                        fill: true,
                        fillColor: "{{ this.direction_color }}",
                        fillOpacity: 0.92,
                        interactive: false
                    }),
                    L.marker(end, {
                        interactive: false,
                        icon: L.divIcon({
                            className: "pgis-direction-label",
                            html: "<span>" + label + "</span>",
                            iconSize: [90, 26],
                            iconAnchor: [-8, 13]
                        })
                    })
                ]).addTo(map);
            }
            window.addEventListener("message", function(event) {
                var data = event.data || {};
                if (data.type !== "pgis:directionPreview" || !recordPanelOpen || !selectedLatLng) {
                    return;
                }
                var bearing = Number(data.value);
                if (!Number.isFinite(bearing)) {
                    return;
                }
                bearing = ((Math.round(bearing) % 360) + 360) % 360;
                drawDirectionPreview(selectedLatLng, bearing);
            });
            attachHostRecordPanelCloseHandler();
            map.on("move zoom resize", requestRecordPanelSync);
            map.on("moveend zoomend", syncRecordPanelPosition);
            if (recordPanelOpen && selectedLatLng) {
                map.whenReady(function() {
                    drawSelectedPoint(selectedLatLng);
                    drawDirectionPreview(selectedLatLng, {{ this.default_direction }});
                    requestRecordPanelSync();
                });
            }
            map.on("contextmenu", function(event) {
                if (event && event.originalEvent) {
                    event.originalEvent.preventDefault();
                    L.DomEvent.stop(event.originalEvent);
                }
                selectedLatLng = event.latlng;
                recordPanelOpen = true;
                panelCloseNotified = false;
                if (window.__pgisDirectionLayer) {
                    map.removeLayer(window.__pgisDirectionLayer);
                    window.__pgisDirectionLayer = null;
                }
                map.closePopup();
                drawSelectedPoint(selectedLatLng);
                drawDirectionPreview(selectedLatLng, {{ this.default_direction }});
                var point = map.latLngToContainerPoint(selectedLatLng);
                updateHostRecordCoordinates(selectedLatLng);
                setHostRecordPanelPosition(point);
            });
        })();
        {% endmacro %}
        """
    )

    def __init__(self, fmap: folium.Map) -> None:
        super().__init__()
        self._name = "RightClickSelectScript"
        self.map_name = fmap.get_name()
        self.selected_ring = ui_color("color-text")
        self.selected_fill = ui_color("color-accent")
        self.selected_inner_stroke = ui_color("color-surface")
        self.selected_inner_fill = ui_color("color-text")
        self.direction_color = ui_color("color-accent")
        self.default_direction = int(st.session_state.get("record_direction", 45)) % 360
        selected_lat, selected_lng = selected_point_value(
            (
                float(st.session_state.get("form_lat", SEOUL_CENTER[0])),
                float(st.session_state.get("form_lng", SEOUL_CENTER[1])),
            )
        )
        self.selected_lat = f"{float(selected_lat):.8f}"
        self.selected_lng = f"{float(selected_lng):.8f}"
        self.panel_open = "true" if st.session_state.get("right_drawer_open", False) else "false"


@st.cache_resource(show_spinner=False, ttl=3600, max_entries=8)
def load_route_graph(
    bbox: tuple[float, float, float, float],
    network_type: str,
) -> Any:
    return ox.graph.graph_from_bbox(bbox, network_type=network_type, simplify=True)


def route_edge_coordinates(graph: Any, route: list[int]) -> list[tuple[float, float]]:
    coordinates: list[tuple[float, float]] = []
    for start_node, end_node in zip(route, route[1:]):
        edge_options = graph.get_edge_data(start_node, end_node) or {}
        if not edge_options:
            continue
        edge = min(edge_options.values(), key=lambda item: float(item.get("length", math.inf)))
        geometry = edge.get("geometry")
        if geometry is None:
            edge_coordinates = [
                (float(graph.nodes[start_node]["y"]), float(graph.nodes[start_node]["x"])),
                (float(graph.nodes[end_node]["y"]), float(graph.nodes[end_node]["x"])),
            ]
        else:
            edge_coordinates = [(float(y), float(x)) for x, y in geometry.coords]
            start_coordinate = (
                float(graph.nodes[start_node]["y"]),
                float(graph.nodes[start_node]["x"]),
            )
            if math.dist(edge_coordinates[-1], start_coordinate) < math.dist(edge_coordinates[0], start_coordinate):
                edge_coordinates.reverse()
        if coordinates and edge_coordinates and coordinates[-1] == edge_coordinates[0]:
            edge_coordinates = edge_coordinates[1:]
        coordinates.extend(edge_coordinates)
    return coordinates


def selected_route_spots(spots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spots_by_id = {int(spot["id"]): spot for spot in spots}
    return [
        spots_by_id[int(spot_id)]
        for spot_id in st.session_state.get("route_spot_ids", [])
        if int(spot_id) in spots_by_id
    ]


def calculate_route(
    spots: list[dict[str, Any]],
) -> tuple[list[tuple[float, float]], list[float], str | None]:
    if not st.session_state.get("route_enabled", False):
        return [], [], None
    route_spots = selected_route_spots(spots)
    if len(route_spots) < 2:
        return [], [], None

    latitudes = [float(spot["lat"]) for spot in route_spots]
    longitudes = [float(spot["lng"]) for spot in route_spots]
    lat_padding = max(0.01, (max(latitudes) - min(latitudes)) * 0.15)
    lng_padding = max(0.01, (max(longitudes) - min(longitudes)) * 0.15)
    bbox = (
        round(min(longitudes) - lng_padding, 5),
        round(min(latitudes) - lat_padding, 5),
        round(max(longitudes) + lng_padding, 5),
        round(max(latitudes) + lat_padding, 5),
    )
    network_type = "drive" if st.session_state.get("route_mode") == "차량" else "walk"

    try:
        graph = load_route_graph(bbox, network_type)
        nodes = ox.distance.nearest_nodes(graph, X=longitudes, Y=latitudes)
        all_coordinates: list[tuple[float, float]] = []
        segment_distances: list[float] = []
        for origin, destination in zip(nodes, nodes[1:]):
            route = ox.routing.shortest_path(graph, origin, destination, weight="length")
            if not route:
                return [], [], "선택한 지점 사이의 경로를 찾지 못했습니다."
            segment_distance = 0.0
            for start_node, end_node in zip(route, route[1:]):
                edge_options = graph.get_edge_data(start_node, end_node) or {}
                if edge_options:
                    segment_distance += min(
                        float(edge.get("length", 0.0))
                        for edge in edge_options.values()
                    )
            segment_distances.append(segment_distance)
            segment = route_edge_coordinates(graph, list(route))
            if all_coordinates and segment and all_coordinates[-1] == segment[0]:
                segment = segment[1:]
            all_coordinates.extend(segment)
        return all_coordinates, segment_distances, None
    except Exception as exc:
        return [], [], f"OSM 경로를 불러오지 못했습니다: {exc}"


def add_route_layer(fmap: folium.Map, spots: list[dict[str, Any]]) -> str | None:
    if not st.session_state.get("route_enabled", False):
        return None
    route_spots = selected_route_spots(spots)
    if not route_spots:
        return None

    route_coordinates: list[tuple[float, float]] = []
    route_error = ""
    if st.session_state.get("route_result_signature") == route_signature():
        route_coordinates = [
            (float(lat), float(lng))
            for lat, lng in st.session_state.get("route_coordinates", [])
        ]
        route_error = str(st.session_state.get("route_error") or "")
    if route_error:
        st.toast(route_error, icon="⚠️")
    if route_coordinates:
        route_layer = folium.FeatureGroup(name="route_result", control=False)
        folium.PolyLine(
            locations=route_coordinates,
            color=ui_color("color-surface"),
            weight=9,
            opacity=0.78,
            interactive=False,
        ).add_to(route_layer)
        folium.PolyLine(
            locations=route_coordinates,
            color=ui_color("color-accent"),
            weight=5,
            opacity=0.96,
            tooltip=f"{st.session_state.get('route_mode', '차량')} 경로",
            interactive=False,
        ).add_to(route_layer)
        route_layer.add_to(fmap)
        return route_layer.get_name()
    return None


def build_map(spots: list[dict[str, Any]]) -> folium.Map:
    center = st.session_state.get("map_center") or selected_point_value() or SEOUL_CENTER
    pending_popup_spot_id = st.session_state.pop("pending_popup_spot_id", None)
    active_spot = None
    if st.session_state.active_spot_id:
        active_spot = next((spot for spot in spots if spot["id"] == st.session_state.active_spot_id), None)
        if active_spot:
            center = (active_spot["lat"], active_spot["lng"])
    dark_mode = bool(st.session_state.get("dark_mode", False))
    tile_url = (
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        if dark_mode
        else "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
    )
    tile_name = "Dark Matter" if dark_mode else "Voyager"
    map_bg = ui_color("color-canvas")
    popup_surface = ui_color("color-surface")
    popup_text = ui_color("color-text")
    popup_border = ui_color("color-border")
    popup_shadow = f"0 20px 50px {ui_color('color-shadow')}"
    popup_inset = ui_color("color-highlight")
    popup_close_hover = ui_color("color-text")
    fmap = folium.Map(
        location=center,
        zoom_start=st.session_state.map_zoom,
        tiles=None,
        control_scale=True,
        prefer_canvas=True,
        max_zoom=19,
    )
    folium.TileLayer(
        tiles=tile_url,
        attr="&copy; OpenStreetMap contributors &copy; CARTO",
        name=tile_name,
        control=False,
        max_zoom=19,
        max_native_zoom=19,
    ).add_to(fmap)
    route_layer_name = add_route_layer(fmap, spots)
    fmap.get_root().header.add_child(
        folium.Element(
            f"""
            <style>
            html, body {{
                width: 100%;
                height: 100%;
                margin: 0;
                padding: 0;
                overflow: hidden;
                background: {map_bg};
            }}
            .folium-map {{
                width: 100% !important;
                height: 100vh !important;
            }}
            .leaflet-container {{
                background: {map_bg};
            }}
            .folium-map,
            .leaflet-container,
            .leaflet-container.leaflet-grab,
            .leaflet-container .leaflet-grab,
            .leaflet-container .leaflet-interactive,
            .leaflet-container .leaflet-marker-icon,
            .leaflet-container .leaflet-marker-shadow,
            .leaflet-container .leaflet-control,
            .leaflet-container .leaflet-control *,
            .leaflet-container a,
            .leaflet-dragging .leaflet-container,
            .leaflet-dragging .leaflet-grab,
            .leaflet-dragging .leaflet-marker-draggable {{
                cursor: default !important;
            }}
            .leaflet-tile-pane img {{
                filter: saturate(1.22) contrast(1.04);
            }}
            .pgis-route-order-icon {{
                background: transparent !important;
                border: 0 !important;
                pointer-events: none !important;
            }}
            .pgis-route-order {{
                display: grid;
                place-items: center;
                width: 24px;
                height: 24px;
                border: 2px solid {popup_surface};
                border-radius: 50%;
                background: {ui_color("color-accent")};
                color: #fff;
                box-shadow: 0 3px 10px {ui_color("color-shadow")};
                font: 900 11px/1 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
                pointer-events: none;
            }}
            .pgis-route-ui {{
                position: absolute;
                inset: 0;
                z-index: 1000;
                pointer-events: none;
                font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }}
            .pgis-route-activate {{
                position: absolute;
                right: 14px;
                bottom: 24px;
                min-width: 82px;
                min-height: 40px;
                padding: 0 14px;
                border: 1px solid {ui_color("color-accent-strong")};
                border-radius: 8px;
                background: {ui_color("color-accent")};
                color: #fff;
                box-shadow: 0 12px 30px {ui_color("color-shadow")};
                cursor: pointer;
                font-size: 13px;
                font-weight: 850;
                pointer-events: auto;
            }}
            .pgis-route-activate[hidden] {{
                display: none;
            }}
            .pgis-route-panel {{
                position: absolute;
                top: 68px;
                right: 14px;
                display: none;
                width: min(300px, calc(100vw - 28px));
                max-height: calc(100vh - 82px);
                padding: 12px;
                overflow-y: auto;
                border: 1px solid {popup_border};
                border-radius: 8px;
                background: {popup_surface};
                color: {popup_text};
                box-shadow: {popup_shadow};
                pointer-events: auto;
            }}
            .pgis-route-panel.is-open {{
                display: block;
                animation: pgis-route-panel-in 180ms cubic-bezier(.2, .8, .2, 1);
            }}
            .pgis-route-head {{
                display: flex;
                align-items: baseline;
                justify-content: space-between;
                gap: 10px;
                padding-bottom: 9px;
                border-bottom: 1px solid {popup_border};
            }}
            .pgis-route-head strong {{
                font-size: 14px;
                font-weight: 900;
            }}
            .pgis-route-head span {{
                color: {ui_color("color-muted")};
                font-size: 11px;
                font-weight: 800;
            }}
            .pgis-route-list {{
                margin: 5px 0 8px;
                padding: 0;
                list-style: none;
            }}
            .pgis-route-item,
            .pgis-route-result-item {{
                display: grid;
                grid-template-columns: 24px minmax(0, 1fr) 26px;
                gap: 8px;
                align-items: center;
                min-height: 40px;
                border-bottom: 1px solid {popup_border};
            }}
            .pgis-route-result-item {{
                grid-template-columns: 24px minmax(0, 1fr);
            }}
            .pgis-route-number {{
                display: grid;
                place-items: center;
                width: 22px;
                height: 22px;
                border-radius: 50%;
                background: {ui_color("color-accent")};
                color: #fff;
                font: 900 11px/1 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            }}
            .pgis-route-name {{
                overflow: hidden;
                color: {popup_text};
                font-size: 12px;
                font-weight: 800;
                text-overflow: ellipsis;
                white-space: nowrap;
            }}
            .pgis-route-remove {{
                width: 24px;
                height: 24px;
                padding: 0;
                border: 1px solid {popup_border};
                border-radius: 50%;
                background: {ui_color("color-surface-soft")};
                color: {ui_color("color-muted")};
                cursor: pointer;
                font-size: 16px;
                line-height: 1;
            }}
            .pgis-route-clear,
            .pgis-route-calculate,
            .pgis-route-exit {{
                display: flex;
                align-items: center;
                justify-content: center;
                width: 100%;
                height: 38px;
                min-height: 38px;
                box-sizing: border-box;
                margin-top: 8px;
                padding: 0 12px;
                border: 1px solid {popup_border};
                border-radius: 6px;
                background: {ui_color("color-surface")};
                color: {popup_text};
                cursor: pointer;
                font-size: 12px;
                font-weight: 850;
                line-height: 1;
                vertical-align: top;
            }}
            .pgis-route-calculate {{
                border-color: {ui_color("color-accent-strong")};
                background: {ui_color("color-accent")};
                color: #fff;
            }}
            .pgis-route-clear:disabled,
            .pgis-route-calculate:disabled {{
                cursor: default;
                opacity: 0.45;
            }}
            .pgis-route-mode {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 4px;
                margin-top: 8px;
                padding: 3px;
                border: 1px solid {popup_border};
                border-radius: 6px;
                background: {ui_color("color-surface-soft")};
            }}
            .pgis-route-mode button {{
                min-height: 32px;
                border: 0;
                border-radius: 4px;
                background: transparent;
                color: {ui_color("color-muted")};
                cursor: pointer;
                font-size: 12px;
                font-weight: 850;
            }}
            .pgis-route-mode button.is-active {{
                background: {ui_color("color-surface")};
                color: {ui_color("color-accent")};
                box-shadow: 0 1px 4px {ui_color("color-shadow-soft")};
            }}
            .pgis-route-empty,
            .pgis-route-error {{
                margin: 10px 0 4px;
                color: {ui_color("color-muted")};
                font-size: 12px;
                line-height: 1.45;
            }}
            .pgis-route-error {{
                color: #ef4444;
            }}
            .pgis-route-result-list {{
                margin-top: 5px;
            }}
            .pgis-route-leg {{
                display: flex;
                align-items: center;
                gap: 8px;
                min-height: 34px;
                padding-left: 7px;
                color: {ui_color("color-muted")};
                font-size: 11px;
                font-weight: 800;
            }}
            .pgis-route-arrow {{
                color: {ui_color("color-accent")};
                font-size: 16px;
                font-weight: 900;
            }}
            .pgis-route-loading {{
                position: absolute;
                inset: 0;
                display: none;
                place-items: center;
                align-content: center;
                gap: 12px;
                background: {ui_color("color-canvas")};
                color: {popup_text};
                pointer-events: auto;
            }}
            .pgis-route-loading.is-visible {{
                display: grid;
            }}
            .pgis-route-loading-spinner {{
                width: 28px;
                height: 28px;
                border: 3px solid {popup_border};
                border-top-color: {ui_color("color-accent")};
                border-radius: 50%;
                animation: pgis-route-spin 700ms linear infinite;
            }}
            @keyframes pgis-route-panel-in {{
                from {{ transform: translateX(10px); opacity: 0; }}
                to {{ transform: translateX(0); opacity: 1; }}
            }}
            @keyframes pgis-route-spin {{
                to {{ transform: rotate(360deg); }}
            }}
            .leaflet-popup-content-wrapper,
            .leaflet-popup-tip {{
                background: {popup_surface} !important;
                color: {popup_text} !important;
                border: 1px solid {popup_border};
                border-radius: 8px !important;
                box-shadow:
                    {popup_shadow},
                    inset 0 0 0 1px {popup_inset};
            }}
            .leaflet-popup-content {{
                margin: 12px !important;
            }}
            .leaflet-popup-close-button {{
                top: 12px !important;
                right: 12px !important;
                width: 12px !important;
                height: 12px !important;
                box-sizing: border-box !important;
                display: block !important;
                margin: 0 !important;
                padding: 0 !important;
                border-radius: 999px !important;
                border: 1px solid rgba(127, 29, 29, 0.45) !important;
                background: #ef4444 !important;
                color: transparent !important;
                font-size: 0 !important;
                line-height: 0 !important;
                text-shadow: none !important;
                transform: none !important;
                vertical-align: top !important;
            }}
            .pgis-popup-delete {{
                top: -1px !important;
                width: 12px !important;
                height: 12px !important;
                box-sizing: border-box !important;
                margin: 0 !important;
                padding: 0 !important;
                transform: none !important;
                vertical-align: top !important;
            }}
            .leaflet-popup-close-button:hover {{
                background: #dc2626 !important;
            }}
            .pgis-direction-label {{
                background: transparent !important;
                border: 0 !important;
            }}
            .pgis-direction-label span {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 74px;
                height: 24px;
                padding: 0 9px;
                border-radius: 999px;
                font: 900 11px/1 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
                letter-spacing: 0;
                white-space: nowrap;
            }}
            </style>
            """
        )
    )
    RightClickSelectScript(fmap).add_to(fmap)
    SpotDeleteScript(fmap).add_to(fmap)

    marker_records: list[tuple[str, dict[str, Any]]] = []
    for spot in spots:
        color = WEATHER_COLORS.get(spot.get("weather", WEATHER_OPTIONS[0]), ui_color("color-accent"))
        active = spot["id"] == st.session_state.active_spot_id
        marker = folium.CircleMarker(
            location=(spot["lat"], spot["lng"]),
            radius=6 if active else 4,
            color=color,
            weight=2 if active else 1,
            fill=True,
            fill_color=color,
            fill_opacity=0.92 if active else 0.72,
            tooltip=str(spot.get("title") or ""),
            popup=folium.Popup(
                record_popup_html(spot),
                max_width=320,
                show=int(spot["id"]) == pending_popup_spot_id,
            ),
            bubbling_mouse_events=False,
        ).add_to(fmap)
        marker_records.append((marker.get_name(), spot))
        DirectionClickScript(fmap, marker.get_name(), spot).add_to(fmap)

    RouteModeScript(fmap, marker_records, route_layer_name).add_to(fmap)
    return fmap

def spot_csv(spots: list[dict[str, Any]]) -> bytes:
    out = io.StringIO()
    writer = csv.DictWriter(
        out,
        fieldnames=[
            "id",
            "title",
            "URL",
            "Available",
            "lat",
            "lng",
            "drct",
            "weather",
            "date",
            "time",
            "body",
            "lens",
            "comp",
            "password",
        ],
    )
    writer.writeheader()
    for spot in spots:
        row = {key: spot.get(key, "") for key in writer.fieldnames}
        row["URL"] = spot_url(spot)
        row["Available"] = spot_available(spot)
        row["drct"] = spot_drct(spot)
        row["comp"] = json.dumps(spot_comp(spot), ensure_ascii=False)
        writer.writerow(row)
    return out.getvalue().encode("utf-8-sig")


def stats(spots: list[dict[str, Any]]) -> tuple[str, str, str, str]:
    total = str(len(st.session_state.spots))
    visible = str(len(spots))
    if st.session_state.spots:
        weather = max(
            WEATHER_OPTIONS,
            key=lambda item: sum(spot.get("weather", WEATHER_OPTIONS[0]) == item for spot in st.session_state.spots),
        )
        meridiem = max(
            TIME_OPTIONS,
            key=lambda item: sum(time_meridiem(spot.get("time")) == item for spot in st.session_state.spots),
        )
    else:
        weather = "-"
        meridiem = "-"
    active = next((spot for spot in st.session_state.spots if spot["id"] == st.session_state.active_spot_id), None)
    direction = compass_label(spot_drct(active)) if active else "-"
    return total, visible, f"{weather} · {meridiem}", direction


def render_header(spots: list[dict[str, Any]]) -> None:
    total, visible, favorite, direction = stats(spots)
    st.markdown(
        """
        <section class="hero">
            <p class="hero-title">GlassShot PGIS</p>
            <p class="hero-sub">사진 스팟을 위치, 방향, 날씨, 시간대, 실제 컷으로 기록하는 다크 글래스 지도.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="stat-grid">
            <div class="stat-tile"><div class="stat-label">등록 스팟</div><div class="stat-value">{total}</div></div>
            <div class="stat-tile"><div class="stat-label">표시 중</div><div class="stat-value">{visible}</div></div>
            <div class="stat-tile"><div class="stat-label">주요 조건</div><div class="stat-value">{escape(favorite)}</div></div>
            <div class="stat-tile"><div class="stat-label">선택 방향</div><div class="stat-value">{escape(direction)}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_options_menu() -> None:
    st.button(
        "경로",
        key="route_mode_button",
        use_container_width=False,
        on_click=enter_route_mode,
        disabled=bool(st.session_state.get("route_enabled", False)),
        help="본 기능은 실험적 기능입니다.",
    )
    st.button(
        "☰",
        key="options_menu_button",
        use_container_width=False,
        on_click=toggle_options_panel,
    )
    panel_state = "is-open" if st.session_state.get("options_panel_open", False) else "is-closed"
    with st.container(key="options_panel"):
        st.markdown(f'<div class="options-panel-state {panel_state}"></div>', unsafe_allow_html=True)
        st.markdown('<p class="options-panel-title">옵션</p>', unsafe_allow_html=True)
        st.checkbox("다크모드", key="dark_mode")


def add_spot(
    title: str,
    lat: float,
    lng: float,
    drct: int,
    weather: str | None = None,
    date_value: str = "",
    time_value: str = "",
    body: str = "",
    lens: str = "",
    comp: dict[str, str] | None = None,
    *,
    url: str = "",
    password: str = "",
) -> bool:
    next_id = max([spot["id"] for spot in st.session_state.spots], default=0) + 1
    spot = {
        "id": next_id,
        "title": title.strip(),
        "URL": url.strip(),
        "lat": float(lat),
        "lng": float(lng),
        "drct": int(drct) % 360,
        "Available": 1,
        "weather": weather or WEATHER_OPTIONS[0],
        "date": date_value.strip(),
        "body": body.strip(),
        "lens": lens.strip(),
        "time": time_value.strip(),
        "password": spot_password({"password": password}),
        "comp": comp or {"F값": "", "ISO값": "", "셔터스피드": "", "화각": ""},
    }
    st.session_state.spots.append(spot)
    st.session_state.active_spot_id = next_id
    st.session_state.selected_point = None
    st.session_state.map_center = (spot["lat"], spot["lng"])
    st.session_state.form_lat = spot["lat"]
    st.session_state.form_lng = spot["lng"]
    return persist_spots()


def hide_spot(spot_id: int) -> bool:
    st.session_state.spots = [
        spot for spot in st.session_state.spots if int(spot.get("id", 0)) != int(spot_id)
    ]
    visible_spots = available_spots(st.session_state.spots)
    st.session_state.active_spot_id = visible_spots[0]["id"] if visible_spots else None
    return persist_spots()


def hide_spot_with_password(spot_id: int, password: str) -> bool:
    for spot in st.session_state.spots:
        if int(spot.get("id", 0)) != int(spot_id):
            continue
        if str(password or "").strip() != spot_password(spot):
            st.toast("password가 일치하지 않아 삭제하지 않았습니다.", icon="⚠️")
            return False
        st.session_state.spots = [
            item for item in st.session_state.spots if int(item.get("id", 0)) != int(spot_id)
        ]
        visible_spots = available_spots(st.session_state.spots)
        st.session_state.active_spot_id = visible_spots[0]["id"] if visible_spots else None
        if persist_spots():
            st.session_state.delete_feedback = "deleted"
            return True
        return False
    st.toast("삭제할 지점을 찾지 못했습니다.", icon="⚠️")
    return False


def render_form() -> None:
    st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
    st.markdown("### 스팟 기록")
    lat = float(st.session_state.form_lat)
    lng = float(st.session_state.form_lng)
    coord_label = f"{lat:.6f}, {lng:.6f}"
    st.markdown(
        f"""
        <div class="spot-card">
            <div class="spot-title">
                <span>기록 좌표</span>
                <span style="color:var(--color-accent-strong);">{escape(coord_label)}</span>
            </div>
            <p class="muted" style="margin:.45rem 0 0;">
                {"지도에서 기록할 위치를 클릭하세요." if st.session_state.picking_location else "위치 선택 버튼을 누른 뒤 지도에서 지점을 클릭하세요."}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.button(
        "선택 취소" if st.session_state.picking_location else "위치 선택",
        key="pick_location_button",
        use_container_width=True,
        on_click=toggle_record_location_picker,
    )

    with st.form("spot_form", clear_on_submit=True):
        title = st.text_input("스팟명", placeholder="예: 유리창 노을 반사 포인트")

        direction_raw = st.text_input("촬영 방향", value="45", placeholder="0~359")
        try:
            direction = int(float(direction_raw)) % 360
        except (TypeError, ValueError):
            direction = 45
        st.markdown(
            f"""
            <div class="pill-row">
                <span class="pill">VECTOR {compass_label(direction)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_weather, col_time = st.columns(2)
        with col_weather:
            weather = st.selectbox("날씨", WEATHER_OPTIONS, index=0)
        with col_time:
            time_text = st.text_input("시간", value="17:30", placeholder="17:30")
        date_text = st.text_input("촬영 날짜", value=datetime.now().strftime("%Y-%m-%d"), placeholder="YYYY-MM-DD")

        col_mood, col_camera = st.columns(2)
        with col_mood:
            mood = st.text_input("무드", placeholder="예: 반사, 역광, 안개")
        with col_camera:
            camera = st.text_input("렌즈/구도", placeholder="예: 35mm low angle")

        uploaded_file = st.file_uploader("사진", type=["jpg", "jpeg", "png", "webp"])
        memo = st.text_input("링크", placeholder="https://example.com")
        password = st.text_input("password", type="password", placeholder="삭제 시 사용할 비밀번호")
        submitted = st.form_submit_button("마커 생성", type="primary", use_container_width=True)

    if submitted:
        if not title.strip():
            st.error("스팟명을 입력해주세요.")
        elif memo.strip() and not is_valid_link(memo):
            st.error("링크는 http:// 또는 https:// 형식으로 입력해주세요.")
        elif not normalize_date_value(date_text):
            st.error("촬영 날짜는 YYYY-MM-DD 형식으로 입력해주세요.")
        elif not normalize_24h_clock(time_text):
            st.error("시간은 24시간 형식으로 입력해주세요. 예: 17:30")
        else:
            saved = add_spot(
                title,
                lat,
                lng,
                direction,
                weather=weather,
                date_value=normalize_date_value(date_text) or "",
                time_value=normalize_time_value(time_text),
                lens=camera,
                url=memo,
                password=password,
            )
            if saved:
                st.success("스팟이 지도에 추가됐습니다.")
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_record_form() -> None:
    lat = float(st.session_state.form_lat)
    lng = float(st.session_state.form_lng)
    coord_label = f"{lat:.6f}, {lng:.6f}"
    head_col, close_col = st.columns([1, 0.09])
    with head_col:
        st.markdown(
            f"""
            <div class="record-head">
                <div>
                    <div class="record-title">기록</div>
                    <div class="record-coord">{escape(coord_label)}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with close_col:
        st.button(
            "닫기",
            key="close_record_panel",
            use_container_width=False,
            on_click=close_record_panel,
        )

    with st.form("record_form", clear_on_submit=False):
        record_lat_text = st.text_input("LAT", key="record_lat_text")
        record_lng_text = st.text_input("LNG", key="record_lng_text")
        dial_col, main_col = st.columns([0.42, 1.0])
        with dial_col:
            direction = render_direction_dial()
        with main_col:
            title = st.text_input("제목", placeholder="촬영 지점 이름", key="record_title")
            url = st.text_input("URL", placeholder="https://instagram.com/...", key="record_url")
            password = st.text_input("password", type="password", placeholder="삭제 시 사용할 비밀번호", key="record_password")

        weather_col, date_col, time_col = st.columns([0.9, 1.0, 0.78])
        with weather_col:
            weather = st.selectbox("날씨", WEATHER_OPTIONS, key="record_weather")
        with date_col:
            date_text = st.text_input("촬영 날짜", placeholder="YYYY-MM-DD", key="record_date_text")
        with time_col:
            time_text = st.text_input("시간", placeholder="17:30", key="record_time_text")

        body = ""
        lens = ""
        comp = {"F값": "", "ISO값": "", "셔터스피드": "", "화각": ""}
        shutter_raw = ""
        shutter_speed = ""

        with st.expander("ADVANCE"):
            body_col, lens_col = st.columns(2)
            with body_col:
                body = st.text_input("바디", placeholder="Sony A7R V", key="record_body")
            with lens_col:
                lens = st.text_input("렌즈", placeholder="35mm F1.4", key="record_lens")

            f_col, iso_col = st.columns(2)
            with f_col:
                f_value = st.text_input("F값", placeholder="2.8", key="record_f_value")
            with iso_col:
                iso_value = st.text_input("ISO값", placeholder="100", key="record_iso_text")

            long_exposure = bool(st.session_state.get("record_long_exposure", False))
            shutter_col, focal_col = st.columns(2)
            with shutter_col:
                shutter_label = "셔터 N" if long_exposure else "셔터 1/N"
                shutter_placeholder = "1" if long_exposure else "125"
                shutter_raw = st.text_input(
                    shutter_label,
                    placeholder=shutter_placeholder,
                    key="record_shutter_value_text",
                )
                shutter_speed = f"{shutter_raw.strip()}s" if long_exposure and shutter_raw.strip() else ""
                if not long_exposure and shutter_raw.strip():
                    shutter_speed = f"1/{shutter_raw.strip()}"
            with focal_col:
                focal = st.text_input("화각", placeholder="35mm", key="record_focal")

            long_exposure = st.checkbox("장노출", key="record_long_exposure")

            comp = {
                "F값": f_value.strip(),
                "ISO값": iso_value.strip(),
                "셔터스피드": shutter_speed.strip(),
                "화각": focal.strip(),
            }

        submitted = st.form_submit_button("마커 생성", type="primary", use_container_width=True)

    if submitted:
        lat = parse_coordinate(record_lat_text, st.session_state.form_lat)
        lng = parse_coordinate(record_lng_text, st.session_state.form_lng)
        date_value = normalize_date_value(date_text)
        clock = normalize_24h_clock(time_text)
        if not title.strip():
            st.error("제목을 입력하세요.")
        elif url.strip() and not is_valid_link(url):
            st.error("URL은 http:// 또는 https:// 형식이어야 합니다.")
        elif not date_value:
            st.error("촬영 날짜는 YYYY-MM-DD 형식으로 입력하세요.")
        elif not clock:
            st.error("시간은 24시간 형식으로 입력하세요. 예: 17:30")
        elif st.session_state.record_long_exposure and shutter_raw.strip() and not shutter_raw.strip().isdigit():
            st.error("장노출 셔터스피드는 초 단위 숫자로 입력하세요.")
        elif not st.session_state.record_long_exposure and shutter_raw.strip() and not shutter_raw.strip().isdigit():
            st.error("셔터스피드 1/N은 숫자로 입력하세요.")
        else:
            saved = add_spot(
                title,
                lat,
                lng,
                direction,
                weather=weather,
                date_value=date_value,
                time_value=clock,
                body=body,
                lens=lens,
                comp=comp,
                url=url,
                password=password,
            )
            if saved:
                clear_record_selection()
                st.success("마커를 추가했습니다.")
                st.rerun()


@st.fragment
def render_record_panel() -> None:
    with st.container(key="right_drawer_panel"):
        render_record_form()


def render_active_detail() -> None:
    active = next((spot for spot in st.session_state.spots if spot["id"] == st.session_state.active_spot_id), None)
    st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
    st.markdown("### 선택 스팟")
    if not active:
        st.markdown('<p class="muted">지도나 목록에서 스팟을 선택하세요.</p>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    color = WEATHER_COLORS.get(active["weather"], ui_color("color-accent"))
    link = link_html(spot_url(active))
    lens_pill = ""
    detail_note = f'<p class="muted" style="margin-bottom:0;">{link}</p>'
    if has_advanced_info(active):
        body_text = escape(active.get("body") or "")
        lens_text = escape(active.get("lens") or "")
        lens_pill = f'<span class="pill">{lens_text}</span>' if lens_text else ""
        if body_text:
            detail_note = f'<p class="muted" style="margin-bottom:0;">{body_text} · {link}</p>'
    st.markdown(
        f"""
        <div class="spot-card">
            <div class="spot-title">
                <span>{escape(active["title"])}</span>
                <span style="color:{color};">{compass_label(spot_drct(active))}</span>
            </div>
            <div class="pill-row">
                <span class="pill" style="border-color:{color};">{escape(active["weather"])}</span>
                <span class="pill">{escape(active.get("date") or "-")}</span>
                <span class="pill" style="border-color:{TIME_COLORS.get(time_meridiem(active.get("time")), ui_color("color-border-strong"))};">{escape(active.get("time"))}</span>
                <span class="pill">{compass_label(spot_drct(active))}</span>
                {lens_pill}
            </div>
            {detail_note}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"{active['lat']:.6f}, {active['lng']:.6f}")

    col_focus, col_delete = st.columns(2)
    with col_focus:
        if st.button("좌표 사용", use_container_width=True):
            st.session_state.selected_point = (active["lat"], active["lng"])
            st.session_state.form_lat = active["lat"]
            st.session_state.form_lng = active["lng"]
            st.rerun()
    with col_delete:
        if st.button("삭제", use_container_width=True):
            if hide_spot(active["id"]):
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_record_detail() -> None:
    active = next((spot for spot in st.session_state.spots if spot["id"] == st.session_state.active_spot_id), None)
    st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
    st.markdown("### SELECTED")
    if not active:
        st.markdown('<p class="muted">No selected spot.</p>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    color = WEATHER_COLORS.get(active.get("weather", WEATHER_OPTIONS[0]), ui_color("color-accent"))
    link = link_html(spot_url(active), "OPEN URL")
    shot_date = active.get("date") or "-"
    shot_time = active.get("time") or "-"
    items = advanced_items(active)
    advanced_pills = ""
    advanced_grid = ""
    if items:
        comp_items = [(label, value) for label, value in items if label in {"F", "ISO", "SHUTTER", "FOCAL"}]
        body_lens_items = [(label, value) for label, value in items if label in {"BODY", "LENS"}]
        advanced_pills = "".join(
            f'<span class="pill">{escape(label)} {escape(value)}</span>'
            for label, value in comp_items
        )
        if body_lens_items:
            advanced_grid = (
                '<div style="display:grid;grid-template-columns:1fr 1fr;gap:.55rem;margin-top:.75rem;">'
                + "".join(
                    f'<div class="pill" style="display:block;">{escape(label)}<br /><strong>{escape(value)}</strong></div>'
                    for label, value in body_lens_items
                )
                + "</div>"
            )
    st.markdown(
        f"""
        <div class="spot-card">
            <div class="spot-title">
                <span>{escape(active.get("title"))}</span>
                <span style="color:{color};">{compass_label(spot_drct(active))}</span>
            </div>
            <div class="pill-row">
                <span class="pill">{escape(shot_date)}</span>
                <span class="pill">{escape(shot_time)}</span>
                {advanced_pills}
            </div>
            {advanced_grid}
            <p class="muted" style="margin-bottom:0;margin-top:.7rem;">{link}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"{active['lat']:.6f}, {active['lng']:.6f}")

    col_focus, col_delete = st.columns(2)
    with col_focus:
        if st.button("USE COORD", use_container_width=True):
            st.session_state.selected_point = (active["lat"], active["lng"])
            st.session_state.form_lat = active["lat"]
            st.session_state.form_lng = active["lng"]
            st.rerun()
    with col_delete:
        if st.button("DELETE", use_container_width=True):
            if hide_spot(active["id"]):
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def store_map_view(map_data: dict[str, Any]) -> None:
    center = map_data.get("center") or {}
    try:
        st.session_state.map_center = (
            round(float(center["lat"]), 6),
            round(float(center["lng"]), 6),
        )
    except (KeyError, TypeError, ValueError):
        pass
    try:
        st.session_state.map_zoom = int(map_data.get("zoom", st.session_state.map_zoom))
    except (TypeError, ValueError):
        pass


def handle_map_return(map_data: dict[str, Any] | None) -> None:
    if not map_data:
        return
    event_type = map_data.get("_pgis_event")
    if event_type == "calculate_route":
        nonce = map_data.get("_pgis_nonce")
        if nonce and nonce == st.session_state.get("last_route_spot_nonce"):
            return
        st.session_state.last_route_spot_nonce = nonce
        store_map_view(map_data)
        available_ids = {int(spot["id"]) for spot in available_spots(st.session_state.spots)}
        route_spot_ids = []
        for value in map_data.get("route_spot_ids") or []:
            try:
                spot_id = int(value)
            except (TypeError, ValueError):
                continue
            if spot_id in available_ids and spot_id not in route_spot_ids:
                route_spot_ids.append(spot_id)
        if len(route_spot_ids) < 2:
            st.toast("경로 계산에는 지점이 2개 이상 필요합니다.", icon="⚠️")
            return
        route_mode = str(map_data.get("route_mode") or "차량")
        st.session_state.route_enabled = True
        st.session_state.route_spot_ids = route_spot_ids
        st.session_state.route_mode = route_mode if route_mode in {"차량", "도보"} else "차량"
        invalidate_route_result()
        coordinates, segment_distances, route_error = calculate_route(st.session_state.spots)
        st.session_state.route_coordinates = coordinates
        st.session_state.route_segment_distances = segment_distances
        st.session_state.route_error = route_error or ""
        st.session_state.route_result_signature = route_signature()
        st.rerun()
    if event_type == "exit_route_mode":
        nonce = map_data.get("_pgis_nonce")
        if nonce and nonce == st.session_state.get("last_route_spot_nonce"):
            return
        st.session_state.last_route_spot_nonce = nonce
        store_map_view(map_data)
        exit_route_mode()
        st.rerun()
    if event_type in {"calculate_route", "exit_route_mode"}:
        return
    if event_type == "select_spot":
        nonce = map_data.get("_pgis_nonce")
        if nonce and nonce == st.session_state.get("last_spot_select_nonce"):
            return
        st.session_state.last_spot_select_nonce = nonce
        store_map_view(map_data)
        try:
            spot_id = int(map_data.get("spot_id"))
        except (TypeError, ValueError):
            return
        available_ids = {int(spot["id"]) for spot in available_spots(st.session_state.spots)}
        if spot_id not in available_ids:
            return
        clear_record_selection()
        st.session_state.active_spot_id = spot_id
        st.session_state.pending_popup_spot_id = spot_id
        st.rerun()
    if event_type == "record_panel_out_of_bounds":
        nonce = map_data.get("_pgis_nonce")
        if nonce and nonce == st.session_state.get("last_panel_close_nonce"):
            return
        st.session_state.last_panel_close_nonce = nonce
        store_map_view(map_data)
        clear_record_selection()
        return
    if event_type == "delete_spot":
        nonce = map_data.get("_pgis_nonce")
        if nonce and nonce == st.session_state.get("last_delete_spot_nonce"):
            return
        st.session_state.last_delete_spot_nonce = nonce
        store_map_view(map_data)
        try:
            spot_id = int(map_data.get("spot_id"))
        except (TypeError, ValueError):
            st.toast("삭제할 지점을 찾지 못했습니다.", icon="⚠️")
            return
        if hide_spot_with_password(spot_id, str(map_data.get("password") or "")):
            st.rerun()
        return
    if event_type != "contextmenu":
        return

    clicked = map_data.get("last_clicked")
    if clicked and "lat" in clicked and "lng" in clicked:
        nonce = map_data.get("_pgis_nonce")
        if nonce and nonce == st.session_state.get("last_context_click_nonce"):
            return
        st.session_state.last_context_click_nonce = nonce
        store_map_view(map_data)
        lat = round(float(clicked["lat"]), 6)
        lng = round(float(clicked["lng"]), 6)
        st.session_state.selected_point = (lat, lng)
        st.session_state.form_lat = lat
        st.session_state.form_lng = lng
        st.session_state.record_lat_text = f"{lat:.6f}"
        st.session_state.record_lng_text = f"{lng:.6f}"
        client_point = map_data.get("client_point") or map_data.get("container_point") or {}
        try:
            st.session_state.record_panel_x = int(round(float(client_point.get("x", 24))))
            st.session_state.record_panel_y = int(round(float(client_point.get("y", 24))))
        except (TypeError, ValueError):
            st.session_state.record_panel_x = 24
            st.session_state.record_panel_y = 24
        st.session_state.active_spot_id = None
        st.session_state.right_drawer_open = True
        st.session_state.picking_location = False


def render_map(spots: list[dict[str, Any]]) -> None:
    st.markdown('<div class="map-wrap">', unsafe_allow_html=True)
    fmap = build_map(spots)
    map_data = st_folium(
        fmap,
        height=1200,
        use_container_width=True,
        returned_objects=[],
        key="photo_spot_map",
    )
    st.markdown("</div>", unsafe_allow_html=True)
    handle_map_return(map_data)


def main() -> None:
    ensure_state()
    inject_css()
    render_options_menu()
    inject_direction_preview_bridge()
    if st.session_state.get("delete_feedback") == "deleted":
        st.toast("지점을 삭제했습니다.", icon="✅")
        st.session_state.delete_feedback = ""
    spots = available_spots(st.session_state.spots)

    render_map(spots)
    inject_layout_vars()
    render_record_panel()


if __name__ == "__main__":
    main()
