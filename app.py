# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import csv
import html
import io
import math
import os
import sys
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import streamlit as st
import streamlit.components.v1 as components


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
from branca.element import MacroElement, Template
from PIL import Image
from streamlit_folium import st_folium


st.set_page_config(
    page_title="GlassShot PGIS",
    page_icon="📷",
    layout="wide",
    initial_sidebar_state="collapsed",
)


WEATHER_OPTIONS = ["맑음", "흐림", "비", "눈", "안개", "노을"]
TIME_OPTIONS = ["새벽", "아침", "낮", "해질녘", "밤"]
WEATHER_COLORS = {
    "맑음": "#facc15",
    "흐림": "#94a3b8",
    "비": "#38bdf8",
    "눈": "#f8fafc",
    "안개": "#c4b5fd",
    "노을": "#fb7185",
}
TIME_COLORS = {
    "새벽": "#67e8f9",
    "아침": "#fde68a",
    "낮": "#34d399",
    "해질녘": "#fb7185",
    "밤": "#a78bfa",
}
SEOUL_CENTER = (37.5665, 126.9780)
DIRECTION_DIAL_COMPONENT = components.declare_component(
    "direction_dial",
    path=os.path.join(os.path.dirname(__file__), "components", "direction_dial"),
)


SAMPLE_SPOTS: list[dict[str, Any]] = [
    {
        "id": 1,
        "title": "청계천 유리 반사 라인",
        "lat": 37.5684,
        "lng": 126.9845,
        "direction": 62,
        "weather": "비",
        "time_band": "밤",
        "mood": "네온 반사",
        "camera": "24mm wide",
        "memo": "https://www.openstreetmap.org/?mlat=37.5684&mlon=126.9845#map=17/37.5684/126.9845",
        "photo_bytes": None,
        "photo_mime": None,
        "created_at": "sample",
    },
    {
        "id": 2,
        "title": "남산 실루엣 컷",
        "lat": 37.5512,
        "lng": 126.9882,
        "direction": 300,
        "weather": "노을",
        "time_band": "해질녘",
        "mood": "역광 실루엣",
        "camera": "50mm",
        "memo": "https://www.openstreetmap.org/?mlat=37.5512&mlon=126.9882#map=17/37.5512/126.9882",
        "photo_bytes": None,
        "photo_mime": None,
        "created_at": "sample",
    },
    {
        "id": 3,
        "title": "한강 수면 컬러 패치",
        "lat": 37.5287,
        "lng": 126.9326,
        "direction": 255,
        "weather": "맑음",
        "time_band": "새벽",
        "mood": "낮은 채도",
        "camera": "35mm",
        "memo": "https://www.openstreetmap.org/?mlat=37.5287&mlon=126.9326#map=17/37.5287/126.9326",
        "photo_bytes": None,
        "photo_mime": None,
        "created_at": "sample",
    },
]


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            color-scheme: dark;
            --glass-bg: rgba(10, 14, 24, 0.78);
            --glass-line: rgba(226, 232, 240, 0.18);
            --glass-text: #f8fafc;
            --glass-muted: #94a3b8;
            --glass-cyan: #22d3ee;
            --glass-rose: #fb7185;
            --glass-amber: #f59e0b;
            --glass-green: #34d399;
            --drawer-width: min(420px, calc(100vw - 62px));
            --drawer-handle: 46px;
            --left-drawer-x: calc(-100% - 1px);
            --right-drawer-x: calc(100% + 1px);
            --left-handle-left: 0px;
            --right-handle-right: 0px;
            --panel-black: rgba(2, 6, 15, 0.94);
            --panel-line: rgba(148, 163, 184, 0.26);
            --neon-cyan: #22d3ee;
            --neon-blue: #38bdf8;
            --neon-pink: #fb7185;
            --neon-violet: #a78bfa;
        }

        html, body, [data-testid="stAppViewContainer"], .stApp {
            background: #060811;
            color: var(--glass-text);
            overflow: hidden;
        }

        [data-testid="stAppViewContainer"],
        section.main,
        [data-testid="stMain"] {
            width: 100vw !important;
            max-width: 100vw !important;
            min-width: 100vw !important;
            margin-left: 0 !important;
        }

        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            background:
                linear-gradient(116deg, transparent 0 18%, rgba(34, 211, 238, 0.14) 18% 18.5%, transparent 18.5% 43%, rgba(251, 113, 133, 0.12) 43% 43.45%, transparent 43.45% 71%, rgba(245, 158, 11, 0.11) 71% 71.5%, transparent 71.5%),
                linear-gradient(38deg, rgba(52, 211, 153, 0.08) 0 10%, transparent 10% 36%, rgba(167, 139, 250, 0.10) 36% 36.45%, transparent 36.45% 66%, rgba(56, 189, 248, 0.08) 66% 66.4%, transparent 66.4%),
                #060811;
            opacity: 0.82;
            z-index: -2;
        }

        .stApp::after {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            background-image:
                linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px),
                linear-gradient(0deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
            background-size: 140px 140px, 140px 140px;
            mix-blend-mode: screen;
            opacity: 0.34;
            z-index: -1;
        }

        [data-testid="stHeader"] {
            display: none;
        }

        [data-testid="stSidebar"] {
            position: fixed;
            inset: 0 auto 0 0;
            width: var(--drawer-width) !important;
            min-width: var(--drawer-width) !important;
            max-width: var(--drawer-width) !important;
            height: 100vh;
            background:
                linear-gradient(128deg, rgba(34, 211, 238, 0.14), transparent 18% 52%, rgba(167, 139, 250, 0.11)),
                repeating-linear-gradient(135deg, transparent 0 18px, rgba(148, 163, 184, 0.045) 18px 19px),
                var(--panel-black);
            border-right: 1px solid var(--panel-line);
            box-shadow: 22px 0 74px rgba(0, 0, 0, 0.66), inset -1px 0 rgba(34, 211, 238, 0.28);
            transform: translateX(var(--left-drawer-x));
            transition: transform 220ms cubic-bezier(.2, .8, .2, 1), box-shadow 220ms ease;
            z-index: 40;
        }

        [data-testid="stSidebar"]::before {
            content: "";
            position: absolute;
            top: 0;
            right: 0;
            width: 4px;
            height: 100%;
            background:
                linear-gradient(180deg, #22d3ee, #a78bfa 42%, #fb7185 74%, #f59e0b);
            opacity: 0.82;
        }

        [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            padding: 1rem 1rem 1.2rem;
            overflow-x: hidden;
        }

        .block-container {
            padding: 0 !important;
            max-width: 100vw;
            width: 100vw;
            min-height: 100vh;
        }

        h1, h2, h3, h4, p, label, span {
            letter-spacing: 0;
        }

        .hero {
            border: 1px solid rgba(226, 232, 240, 0.16);
            background:
                linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(8, 13, 24, 0.76)),
                linear-gradient(60deg, rgba(34, 211, 238, 0.18), rgba(251, 113, 133, 0.14), rgba(245, 158, 11, 0.10));
            box-shadow: 0 22px 70px rgba(0, 0, 0, 0.38);
            border-radius: 8px;
            padding: 1.05rem 1.2rem;
            margin-bottom: 1rem;
            overflow: hidden;
        }

        .hero-title {
            font-size: clamp(2rem, 5vw, 4.5rem);
            line-height: 0.98;
            font-weight: 900;
            color: #ffffff;
            margin: 0;
        }

        .hero-sub {
            margin: 0.55rem 0 0;
            color: #cbd5e1;
            max-width: 780px;
            font-size: 1rem;
        }

        .stat-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.7rem;
            margin: 0.8rem 0 1rem;
        }

        .stat-tile, .glass-panel, .spot-card {
            border: 1px solid rgba(226, 232, 240, 0.18);
            background:
                linear-gradient(132deg, rgba(34, 211, 238, 0.10), transparent 24% 58%, rgba(251, 113, 133, 0.09)),
                rgba(2, 6, 14, 0.86);
            backdrop-filter: blur(20px) saturate(1.15);
            border-radius: 0;
            box-shadow: 0 18px 46px rgba(0, 0, 0, 0.34), inset 0 0 0 1px rgba(255, 255, 255, 0.04);
        }

        .stat-tile {
            min-height: 88px;
            padding: 0.9rem;
        }

        .stat-label {
            color: var(--glass-muted);
            font-size: 0.76rem;
            margin-bottom: 0.35rem;
        }

        .stat-value {
            font-size: 1.45rem;
            font-weight: 850;
            color: #ffffff;
            line-height: 1.15;
            overflow-wrap: anywhere;
        }

        .glass-panel {
            padding: 1rem;
            margin-bottom: 1rem;
            position: relative;
        }

        .glass-panel::before {
            content: "";
            position: absolute;
            inset: 0;
            pointer-events: none;
            background:
                linear-gradient(115deg, transparent 0 34%, rgba(34, 211, 238, 0.16) 34% 34.35%, transparent 34.35% 68%, rgba(251, 113, 133, 0.14) 68% 68.35%, transparent 68.35%),
                linear-gradient(34deg, transparent 0 48%, rgba(245, 158, 11, 0.12) 48% 48.35%, transparent 48.35%);
        }

        .spot-card {
            padding: 0.85rem;
            margin-bottom: 0.75rem;
        }

        .spot-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            color: #ffffff;
            font-weight: 850;
            font-size: 1rem;
        }

        .pill-row {
            display: flex;
            gap: 0.35rem;
            flex-wrap: wrap;
            margin-top: 0.55rem;
        }

        .pill {
            display: inline-flex;
            align-items: center;
            min-height: 26px;
            padding: 0.2rem 0.48rem;
            border-radius: 0;
            border: 1px solid rgba(226, 232, 240, 0.20);
            color: #e2e8f0;
            background: rgba(3, 7, 18, 0.78);
            font-size: 0.78rem;
        }

        .muted {
            color: #94a3b8;
            font-size: 0.88rem;
            line-height: 1.6;
        }

        .map-wrap {
            position: absolute;
            width: 0;
            height: 0;
            border: 0;
            background: transparent;
            border-radius: 0;
            padding: 0;
            overflow: visible;
            pointer-events: none;
        }

        .map-wrap iframe,
        div[data-testid="stHorizontalBlock"]:has(.map-wrap) iframe,
        iframe[title^="streamlit_folium"] {
            position: fixed;
            inset: 0;
            width: 100vw !important;
            height: 100vh !important;
            border-radius: 0;
            border: 0;
            display: block;
            z-index: 1;
        }

        .st-key-right_drawer_panel {
            position: fixed;
            inset: 0 0 0 auto;
            width: var(--drawer-width) !important;
            min-width: var(--drawer-width) !important;
            max-width: var(--drawer-width) !important;
            height: 100vh;
            padding: 1rem;
            overflow-y: auto;
            overflow-x: hidden;
            background:
                linear-gradient(232deg, rgba(251, 113, 133, 0.13), transparent 20% 55%, rgba(34, 211, 238, 0.12)),
                repeating-linear-gradient(45deg, transparent 0 18px, rgba(148, 163, 184, 0.045) 18px 19px),
                var(--panel-black);
            border-left: 1px solid var(--panel-line);
            box-shadow: -22px 0 74px rgba(0, 0, 0, 0.66), inset 1px 0 rgba(251, 113, 133, 0.28);
            transform: translateX(var(--right-drawer-x));
            transition: transform 220ms cubic-bezier(.2, .8, .2, 1), box-shadow 220ms ease;
            z-index: 35;
        }

        .st-key-right_drawer_panel::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background:
                linear-gradient(180deg, #fb7185, #a78bfa 38%, #22d3ee 70%, #34d399);
            opacity: 0.82;
        }

        .st-key-right_drawer_panel .glass-panel {
            margin-bottom: 0.8rem;
        }

        .st-key-filter_floating_panel {
            position: fixed;
            left: 18px;
            bottom: 18px;
            width: min(360px, calc(100vw - 36px)) !important;
            max-height: min(70vh, 640px);
            overflow-y: auto;
            overflow-x: hidden;
            z-index: 46;
            padding: 0.78rem;
            background:
                linear-gradient(132deg, rgba(34, 211, 238, 0.16), transparent 22% 58%, rgba(251, 113, 133, 0.12)),
                repeating-linear-gradient(135deg, transparent 0 16px, rgba(248, 250, 252, 0.045) 16px 17px),
                rgba(2, 6, 15, 0.92);
            border: 1px solid rgba(248, 250, 252, 0.24);
            box-shadow:
                0 20px 56px rgba(0, 0, 0, 0.58),
                inset 0 0 0 1px rgba(255, 255, 255, 0.045),
                inset 4px 0 rgba(34, 211, 238, 0.42);
            backdrop-filter: blur(18px) saturate(1.18);
        }

        .filter-head {
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 0.65rem;
            align-items: center;
            margin-bottom: 0.65rem;
        }

        .filter-count {
            min-width: 68px;
            padding: 0.52rem 0.58rem;
            border: 1px solid rgba(148, 163, 184, 0.22);
            background: rgba(3, 7, 18, 0.78);
            color: #e2e8f0;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            font-size: 0.78rem;
            font-weight: 900;
            text-align: center;
        }

        .filter-mini {
            border-top: 1px solid rgba(148, 163, 184, 0.18);
            padding-top: 0.62rem;
            color: #cbd5e1;
            font-size: 0.82rem;
            line-height: 1.45;
        }

        .filter-mini strong {
            color: #f8fafc;
            font-weight: 900;
        }

        .drawer-handle,
        .st-key-left_drawer_handle,
        .st-key-right_drawer_handle {
            position: fixed;
            top: 50%;
            width: var(--drawer-handle) !important;
            min-width: var(--drawer-handle) !important;
            transform: translateY(-50%);
            z-index: 70;
            filter: drop-shadow(0 18px 32px rgba(0, 0, 0, 0.52));
        }

        .drawer-handle-left,
        .st-key-left_drawer_handle {
            left: var(--left-handle-left);
        }

        .drawer-handle-right,
        .st-key-right_drawer_handle {
            right: var(--right-handle-right);
        }

        .drawer-handle button,
        .st-key-left_drawer_handle button,
        .st-key-right_drawer_handle button {
            width: var(--drawer-handle) !important;
            min-width: var(--drawer-handle) !important;
            height: 148px;
            padding: 0 !important;
            border-radius: 0 !important;
            writing-mode: vertical-rl;
            text-orientation: mixed;
            letter-spacing: 0 !important;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            font-size: 0.72rem;
            font-weight: 900;
            color: #f8fafc !important;
            clip-path: polygon(0 8px, 100% 0, 100% calc(100% - 8px), 0 100%);
            background:
                linear-gradient(180deg, rgba(34, 211, 238, 0.30), transparent 36% 64%, rgba(251, 113, 133, 0.26)),
                linear-gradient(90deg, rgba(255,255,255,0.06), transparent),
                rgba(2, 6, 15, 0.96) !important;
            border: 1px solid rgba(226, 232, 240, 0.34) !important;
            box-shadow:
                0 0 0 1px rgba(34, 211, 238, 0.16),
                0 18px 44px rgba(0, 0, 0, 0.52),
                inset 0 0 24px rgba(34, 211, 238, 0.10);
        }

        .st-key-left_drawer_handle button {
            border-left: 3px solid var(--neon-cyan) !important;
        }

        .st-key-right_drawer_handle button {
            border-right: 3px solid var(--neon-pink) !important;
            clip-path: polygon(0 0, 100% 8px, 100% 100%, 0 calc(100% - 8px));
        }

        .drawer-handle button:hover,
        .st-key-left_drawer_handle button:hover,
        .st-key-right_drawer_handle button:hover {
            border-color: rgba(34, 211, 238, 0.86) !important;
            color: #ffffff !important;
            background:
                linear-gradient(180deg, rgba(34, 211, 238, 0.40), transparent 36% 64%, rgba(251, 113, 133, 0.36)),
                linear-gradient(90deg, rgba(255,255,255,0.08), transparent),
                rgba(2, 6, 14, 0.98) !important;
        }

        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stBaseButton-secondary"],
        [data-testid="stBaseButton-primary"] {
            border-radius: 0;
            border: 1px solid rgba(226, 232, 240, 0.22);
            background:
                linear-gradient(115deg, rgba(34, 211, 238, 0.12), transparent 40% 62%, rgba(251, 113, 133, 0.12)),
                rgba(3, 7, 18, 0.86);
            color: #f8fafc;
            min-height: 42px;
        }

        [data-testid="stSidebar"] h3,
        .st-key-right_drawer_panel h3 {
            color: #f8fafc;
            font-weight: 900;
            border-bottom: 1px solid rgba(148, 163, 184, 0.20);
            padding-bottom: 0.45rem;
        }

        [data-testid="stSidebar"] label,
        .st-key-right_drawer_panel label {
            color: #cbd5e1 !important;
            font-weight: 750;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            border-color: rgba(34, 211, 238, 0.7);
            color: #ffffff;
        }

        [data-testid="stBaseButton-primary"] {
            background:
                linear-gradient(90deg, rgba(34, 211, 238, 0.34), rgba(251, 113, 133, 0.30)),
                rgba(3, 7, 18, 0.96);
            color: #ffffff;
            font-weight: 850;
        }

        input, textarea, [data-baseweb="select"] > div {
            border-radius: 0 !important;
            background: rgba(2, 6, 17, 0.78) !important;
            border-color: rgba(148, 163, 184, 0.24) !important;
            color: #f8fafc !important;
            box-shadow: inset 0 0 0 1px rgba(34, 211, 238, 0.04) !important;
        }

        input:focus, textarea:focus {
            border-color: rgba(34, 211, 238, 0.72) !important;
            box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.28) !important;
        }

        div[data-testid="stFileUploaderDropzone"] {
            border-radius: 0;
            border-color: rgba(34, 211, 238, 0.36);
            background: rgba(3, 7, 18, 0.72);
        }

        .leaflet-popup-content-wrapper,
        .leaflet-popup-tip {
            background:
                linear-gradient(135deg, rgba(255,255,255,0.08), transparent 24% 72%, rgba(34,211,238,0.08)),
                rgba(2, 6, 17, 0.98);
            color: #f8fafc;
            border: 1px solid rgba(248, 250, 252, 0.34);
            box-shadow: 0 24px 56px rgba(0, 0, 0, 0.62), inset 0 0 0 1px rgba(255,255,255,0.08);
            border-radius: 0;
        }

        .leaflet-popup-content {
            margin: 12px;
        }

        .leaflet-popup-close-button {
            color: #e2e8f0 !important;
            font-size: 20px !important;
            font-weight: 900 !important;
            text-shadow: 0 0 14px rgba(34, 211, 238, 0.66);
        }

        .leaflet-popup-close-button:hover {
            color: #ffffff !important;
            background: transparent !important;
        }

        @media (max-width: 900px) {
            .stat-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .hero {
                padding: 0.95rem;
            }
        }

        @media (max-width: 520px) {
            .stat-grid {
                grid-template-columns: 1fr;
            }
            .hero-title {
                font-size: 2.2rem;
            }
            .st-key-filter_floating_panel {
                left: 10px;
                right: 10px;
                bottom: 10px;
                width: auto !important;
                max-height: 56vh;
                padding: 0.68rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    left_open = bool(st.session_state.get("left_drawer_open", False))
    right_open = bool(st.session_state.get("right_drawer_open", False))
    st.markdown(
        f"""
        <style>
        :root {{
            --left-drawer-x: {"0" if left_open else "calc(-100% - 1px)"};
            --right-drawer-x: {"0" if right_open else "calc(100% + 1px)"};
            --left-handle-left: {"var(--drawer-width)" if left_open else "0px"};
            --right-handle-right: {"var(--drawer-width)" if right_open else "0px"};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_layout_vars() -> None:
    left_open = bool(st.session_state.get("left_drawer_open", False))
    right_open = bool(st.session_state.get("right_drawer_open", False))
    st.markdown(
        f"""
        <style>
        :root {{
            --left-drawer-x: {"0" if left_open else "calc(-100% - 1px)"};
            --right-drawer-x: {"0" if right_open else "calc(100% + 1px)"};
            --left-handle-left: {"var(--drawer-width)" if left_open else "0px"};
            --right-handle-right: {"var(--drawer-width)" if right_open else "0px"};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def ensure_state() -> None:
    defaults = {
        "spots": [spot.copy() for spot in SAMPLE_SPOTS],
        "selected_point": SEOUL_CENTER,
        "active_spot_id": 1,
        "weather_filter": WEATHER_OPTIONS.copy(),
        "time_filter": TIME_OPTIONS.copy(),
        "search_query": "",
        "map_zoom": 12,
        "left_drawer_open": False,
        "right_drawer_open": False,
        "form_lat": SEOUL_CENTER[0],
        "form_lng": SEOUL_CENTER[1],
        "picking_location": False,
        "filter_open": False,
        "last_context_click_nonce": None,
        "record_direction": 45,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def compass_label(degrees: int | float) -> str:
    labels = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((float(degrees) + 22.5) // 45) % 8
    return labels[idx]


def render_direction_dial() -> int:
    current = int(st.session_state.get("record_direction", 45)) % 360
    returned = DIRECTION_DIAL_COMPONENT(value=current, key="record_direction_dial", default=current)
    direction = current
    if returned is not None:
        try:
            direction = int(round(float(returned))) % 360
        except (TypeError, ValueError):
            direction = current
    st.session_state.record_direction = direction
    st.markdown(
        f"""
        <div class="pill-row" style="justify-content:center;margin-top:-.35rem;margin-bottom:.9rem;">
            <span class="pill">VECTOR {direction:03d} {compass_label(direction)}</span>
        </div>
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
        return '<span style="color:#64748b;">링크 없음</span>'
    url = escape(str(value).strip())
    text = escape(label)
    return (
        f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
        'style="color:#67e8f9;text-decoration:none;font-weight:900;'
        'border-bottom:1px solid rgba(103,232,249,.45);">'
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
    color = WEATHER_COLORS.get(spot["weather"], "#38bdf8")
    img = data_uri(spot.get("photo_bytes"), spot.get("photo_mime"))
    image_html = ""
    if img:
        image_html = (
            f'<img src="{img}" style="width:100%;max-height:150px;object-fit:cover;'
            'margin-bottom:10px;border:1px solid rgba(148,163,184,0.24);" />'
        )
    link = link_html(spot.get("memo"))
    return f"""
    <div style="width:282px;font-family:Inter,Arial,sans-serif;color:#f8fafc;background:#020611;">
        {image_html}
        <div style="border-left:3px solid {color};padding-left:10px;margin-bottom:10px;">
            <div style="font-size:12px;color:#94a3b8;font-weight:800;text-transform:uppercase;">SPOT NODE</div>
            <div style="font-size:16px;font-weight:900;line-height:1.25;color:#ffffff;">{escape(spot["title"])}</div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;">
            <div style="border:1px solid rgba(148,163,184,.22);background:rgba(3,7,18,.88);padding:8px;">
                <div style="font-size:10px;color:#94a3b8;font-weight:800;">LINK</div>
                <div style="font-size:12px;margin-top:8px;">{link}</div>
            </div>
            <div style="border:1px solid rgba(148,163,184,.22);background:rgba(3,7,18,.88);padding:8px;">
                <div style="font-size:10px;color:#94a3b8;font-weight:800;">CONDITION</div>
                <div style="font-size:12px;color:#f8fafc;font-weight:850;margin-top:4px;">{escape(spot["weather"])}</div>
                <div style="font-size:12px;color:#cbd5e1;font-weight:750;">{escape(spot["time_band"])}</div>
            </div>
        </div>
        <div style="font-size:12px;line-height:1.55;color:#cbd5e1;border-top:1px solid rgba(148,163,184,.18);padding-top:9px;">{escape(spot.get("mood") or spot.get("camera") or "상세 정보 없음")}</div>
    </div>
    """


def record_popup_html(spot: dict[str, Any]) -> str:
    color = WEATHER_COLORS.get(spot.get("weather", WEATHER_OPTIONS[0]), "#38bdf8")
    link = link_html(spot.get("url") or spot.get("memo"), "OPEN URL")
    shot_at = spot.get("shot_at") or spot.get("created_at") or "-"
    body = spot.get("body") or "-"
    lens = spot.get("lens") or spot.get("camera") or "-"
    iso = spot.get("iso") or "-"
    aperture = spot.get("aperture") or "-"
    shutter_speed = spot.get("shutter_speed") or "-"
    return f"""
    <div style="width:282px;font-family:Inter,Arial,sans-serif;color:#f8fafc;background:#020611;">
        <div style="border-left:3px solid {color};padding-left:10px;margin-bottom:10px;">
            <div style="font-size:12px;color:#94a3b8;font-weight:800;text-transform:uppercase;">SPOT NODE</div>
            <div style="font-size:16px;font-weight:900;line-height:1.25;color:#ffffff;">{escape(spot.get("title"))}</div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;">
            <div style="border:1px solid rgba(148,163,184,.22);background:rgba(3,7,18,.88);padding:8px;">
                <div style="font-size:10px;color:#94a3b8;font-weight:800;">URL</div>
                <div style="font-size:12px;margin-top:8px;">{link}</div>
            </div>
            <div style="border:1px solid rgba(148,163,184,.22);background:rgba(3,7,18,.88);padding:8px;">
                <div style="font-size:10px;color:#94a3b8;font-weight:800;">SHOT TIME</div>
                <div style="font-size:12px;color:#f8fafc;font-weight:850;margin-top:4px;">{escape(shot_at)}</div>
            </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:12px;line-height:1.45;color:#cbd5e1;border-top:1px solid rgba(148,163,184,.18);padding-top:9px;">
            <div><span style="color:#94a3b8;font-weight:800;">BODY</span><br />{escape(body)}</div>
            <div><span style="color:#94a3b8;font-weight:800;">LENS</span><br />{escape(lens)}</div>
            <div><span style="color:#94a3b8;font-weight:800;">ISO</span><br />{escape(iso)}</div>
            <div><span style="color:#94a3b8;font-weight:800;">F</span><br />{escape(aperture)}</div>
            <div><span style="color:#94a3b8;font-weight:800;">SHUTTER</span><br />{escape(shutter_speed)}</div>
            <div><span style="color:#94a3b8;font-weight:800;">VECTOR</span><br />{compass_label(spot.get("direction", 0))}</div>
        </div>
    </div>
    """


def add_direction_vector(fmap: folium.Map, spot: dict[str, Any]) -> None:
    color = WEATHER_COLORS.get(spot.get("weather", WEATHER_OPTIONS[0]), "#38bdf8")
    end_lat, end_lng = destination_point(spot["lat"], spot["lng"], spot["direction"])
    folium.CircleMarker(
        location=(spot["lat"], spot["lng"]),
        radius=10,
        color="#f8fafc",
        weight=2,
        fill=True,
        fill_color=color,
        fill_opacity=0.52,
        opacity=0.92,
    ).add_to(fmap)
    folium.CircleMarker(
        location=(spot["lat"], spot["lng"]),
        radius=4,
        color="#020611",
        weight=1,
        fill=True,
        fill_color="#ffffff",
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
                window.__pgisDirectionLayer = L.layerGroup([
                    L.circleMarker(start, {
                        radius: 12,
                        color: "#f8fafc",
                        weight: 2,
                        fill: true,
                        fillColor: color,
                        fillOpacity: 0.52,
                        opacity: 0.94,
                        interactive: false
                    }),
                    L.circleMarker(start, {
                        radius: 4,
                        color: "#020611",
                        weight: 1,
                        fill: true,
                        fillColor: "#ffffff",
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
        end_lat, end_lng = destination_point(spot["lat"], spot["lng"], spot["direction"])
        self.map_name = fmap.get_name()
        self.marker_name = marker_name
        self.start_lat = f"{float(spot['lat']):.8f}"
        self.start_lng = f"{float(spot['lng']):.8f}"
        self.end_lat = f"{end_lat:.8f}"
        self.end_lng = f"{end_lng:.8f}"
        self.color = WEATHER_COLORS.get(spot.get("weather", WEATHER_OPTIONS[0]), "#38bdf8")


class RightClickSelectScript(MacroElement):
    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            map.on("contextmenu", function(event) {
                if (event && event.originalEvent) {
                    event.originalEvent.preventDefault();
                    L.DomEvent.stop(event.originalEvent);
                }
                if (window.__pgisDirectionLayer) {
                    map.removeLayer(window.__pgisDirectionLayer);
                    window.__pgisDirectionLayer = null;
                }
                map.closePopup();
                if (window.__pgisSelectedPointLayer) {
                    map.removeLayer(window.__pgisSelectedPointLayer);
                }
                window.__pgisSelectedPointLayer = L.layerGroup([
                    L.circleMarker(event.latlng, {
                        radius: 12,
                        color: "#f8fafc",
                        weight: 2,
                        fill: true,
                        fillColor: "#22d3ee",
                        fillOpacity: 0.34,
                        opacity: 0.94,
                        interactive: false
                    }),
                    L.circleMarker(event.latlng, {
                        radius: 4,
                        color: "#020611",
                        weight: 1,
                        fill: true,
                        fillColor: "#ffffff",
                        fillOpacity: 0.96,
                        interactive: false
                    })
                ]).addTo(map);
                var nonce = String(Date.now()) + "-" + Math.random().toString(36).slice(2);
                var payload = {
                    _pgis_event: "contextmenu",
                    _pgis_nonce: nonce,
                    zoom: map.getZoom(),
                    last_clicked: {
                        lat: event.latlng.lat,
                        lng: event.latlng.lng
                    }
                };
                if (window.Streamlit && window.Streamlit.setComponentValue) {
                    window.Streamlit.setComponentValue(payload);
                } else {
                    window.parent.postMessage({
                        isStreamlitMessage: true,
                        type: "streamlit:setComponentValue",
                        value: payload,
                        dataType: "json"
                    }, "*");
                }
            });
        })();
        {% endmacro %}
        """
    )

    def __init__(self, fmap: folium.Map) -> None:
        super().__init__()
        self._name = "RightClickSelectScript"
        self.map_name = fmap.get_name()


def build_map(spots: list[dict[str, Any]]) -> folium.Map:
    center = st.session_state.selected_point
    active_spot = None
    if st.session_state.active_spot_id:
        active_spot = next((spot for spot in st.session_state.spots if spot["id"] == st.session_state.active_spot_id), None)
        if active_spot:
            center = (active_spot["lat"], active_spot["lng"])

    fmap = folium.Map(
        location=center,
        zoom_start=st.session_state.map_zoom,
        tiles=None,
        control_scale=True,
        prefer_canvas=True,
        max_zoom=19,
    )
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr="&copy; OpenStreetMap contributors &copy; CARTO",
        name="Dark Matter",
        control=False,
        max_zoom=19,
        max_native_zoom=19,
    ).add_to(fmap)
    fmap.get_root().header.add_child(
        folium.Element(
            """
            <style>
            html, body {
                width: 100%;
                height: 100%;
                margin: 0;
                padding: 0;
                overflow: hidden;
                background: #060811;
            }
            .folium-map {
                width: 100% !important;
                height: 100vh !important;
            }
            .leaflet-container {
                background: #060811;
            }
            .leaflet-popup-content-wrapper,
            .leaflet-popup-tip {
                background:
                    linear-gradient(135deg, rgba(255,255,255,0.08), transparent 24% 72%, rgba(34,211,238,0.08)),
                    rgba(2, 6, 17, 0.98) !important;
                color: #f8fafc !important;
                border: 1px solid rgba(248, 250, 252, 0.34);
                border-radius: 0 !important;
                box-shadow:
                    0 22px 58px rgba(0, 0, 0, 0.62),
                    inset 0 0 0 1px rgba(255,255,255,0.08);
            }
            .leaflet-popup-content {
                margin: 12px !important;
            }
            .leaflet-popup-close-button {
                color: #f8fafc !important;
                font-weight: 900 !important;
                text-shadow: 0 0 12px rgba(255,255,255,0.45);
            }
            .leaflet-popup-close-button:hover {
                background: transparent !important;
                color: #ffffff !important;
            }
            </style>
            """
        )
    )
    RightClickSelectScript(fmap).add_to(fmap)

    lat, lng = st.session_state.selected_point
    folium.CircleMarker(
        location=(lat, lng),
        radius=12,
        color="#f8fafc",
        fill=True,
        fill_color="#22d3ee",
        fill_opacity=0.34,
        opacity=0.94,
        weight=2,
        tooltip="선택 지점",
    ).add_to(fmap)

    folium.CircleMarker(
        location=(lat, lng),
        radius=4,
        color="#020611",
        fill=True,
        fill_color="#ffffff",
        fill_opacity=0.96,
        weight=1,
        tooltip="selected point",
    ).add_to(fmap)

    for spot in spots:
        color = WEATHER_COLORS.get(spot.get("weather", WEATHER_OPTIONS[0]), "#38bdf8")
        active = spot["id"] == st.session_state.active_spot_id
        marker = folium.CircleMarker(
            location=(spot["lat"], spot["lng"]),
            radius=6 if active else 4,
            color=color,
            weight=2 if active else 1,
            fill=True,
            fill_color=color,
            fill_opacity=0.92 if active else 0.72,
            tooltip=f"{spot['id']} · {spot['title']}",
            popup=folium.Popup(record_popup_html(spot), max_width=320),
            bubbling_mouse_events=False,
        ).add_to(fmap)
        DirectionClickScript(fmap, marker.get_name(), spot).add_to(fmap)

    return fmap

    """
        <div style="font-weight:800;margin-bottom:5px;">날씨</div>


    """


def filtered_spots() -> list[dict[str, Any]]:
    weather_filter = set(st.session_state.weather_filter or WEATHER_OPTIONS)
    time_filter = set(st.session_state.time_filter or TIME_OPTIONS)
    query = st.session_state.search_query.strip().lower()
    result: list[dict[str, Any]] = []
    for spot in st.session_state.spots:
        weather = spot.get("weather", WEATHER_OPTIONS[0])
        time_band = spot.get("time_band", TIME_OPTIONS[0])
        haystack = " ".join(
            [
                spot.get("title", ""),
                weather,
                time_band,
                spot.get("mood", ""),
                spot.get("camera", ""),
                spot.get("memo", ""),
                str(spot.get("url", "")),
                str(spot.get("shot_at", "")),
                str(spot.get("body", "")),
                str(spot.get("lens", "")),
                str(spot.get("iso", "")),
                str(spot.get("aperture", "")),
                str(spot.get("shutter_speed", "")),
            ]
        ).lower()
        if weather not in weather_filter:
            continue
        if time_band not in time_filter:
            continue
        if query and query not in haystack:
            continue
        result.append(spot)
    return result


def spot_csv(spots: list[dict[str, Any]]) -> bytes:
    out = io.StringIO()
    writer = csv.DictWriter(
        out,
        fieldnames=[
            "id",
            "title",
            "lat",
            "lng",
            "direction",
            "url",
            "shot_at",
            "body",
            "lens",
            "iso",
            "aperture",
            "shutter_speed",
            "created_at",
        ],
    )
    writer.writeheader()
    for spot in spots:
        row = {key: spot.get(key, "") for key in writer.fieldnames}
        row["url"] = spot.get("url") or spot.get("memo", "")
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
        time_band = max(
            TIME_OPTIONS,
            key=lambda item: sum(spot.get("time_band", TIME_OPTIONS[0]) == item for spot in st.session_state.spots),
        )
    else:
        weather = "-"
        time_band = "-"
    active = next((spot for spot in st.session_state.spots if spot["id"] == st.session_state.active_spot_id), None)
    direction = compass_label(active["direction"]) if active else "-"
    return total, visible, f"{weather} · {time_band}", direction


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


def render_sidebar(spots: list[dict[str, Any]]) -> None:
    with st.sidebar:
        st.markdown("### 필터")
        st.session_state.search_query = st.text_input("검색", value=st.session_state.search_query, placeholder="장소, 무드, 메모")
        st.session_state.weather_filter = st.multiselect("날씨", WEATHER_OPTIONS, default=st.session_state.weather_filter)
        st.session_state.time_filter = st.multiselect("시간대", TIME_OPTIONS, default=st.session_state.time_filter)

        st.divider()
        st.markdown("### 스팟")
        for spot in spots:
            color = WEATHER_COLORS.get(spot["weather"], "#38bdf8")
            active = spot["id"] == st.session_state.active_spot_id
            label = f"{'● ' if active else ''}{spot['title']}"
            if st.button(label, key=f"select_spot_{spot['id']}", use_container_width=True):
                st.session_state.active_spot_id = spot["id"]
                st.session_state.selected_point = (spot["lat"], spot["lng"])
                st.session_state.form_lat = spot["lat"]
                st.session_state.form_lng = spot["lng"]
                st.rerun()
            st.markdown(
                f"""
                <div class="pill-row" style="margin-top:-.45rem;margin-bottom:.6rem;">
                    <span class="pill" style="border-color:{color};">{escape(spot["weather"])}</span>
                    <span class="pill">{escape(spot["time_band"])}</span>
                    <span class="pill">{compass_label(spot["direction"])}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.divider()
        st.download_button(
            "CSV 내보내기",
            data=spot_csv(st.session_state.spots),
            file_name=f"glassshot-pgis-{datetime.now().strftime('%Y%m%d-%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
        )


def render_filter_floating(spots: list[dict[str, Any]]) -> None:
    total = len(st.session_state.spots)
    visible = len(spots)
    active = next((spot for spot in st.session_state.spots if spot["id"] == st.session_state.active_spot_id), None)

    with st.container(key="filter_floating_panel"):
        st.markdown(
            f"""
            <div class="filter-head">
                <div></div>
                <div class="filter-count">{visible}/{total}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("FILTER", key="filter_floating_toggle", use_container_width=True):
            st.session_state.filter_open = not st.session_state.filter_open
            st.rerun()

        if not st.session_state.filter_open:
            active_title = escape(active["title"]) if active else "NO ACTIVE SPOT"
            st.markdown(
                f"""
                <div class="filter-mini">
                    <strong>{active_title}</strong><br />
                    VIEW {visible} / TOTAL {total}
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

        st.text_input("Search", key="search_query", placeholder="name, url, body, lens")
        st.multiselect("Weather", WEATHER_OPTIONS, key="weather_filter")
        st.multiselect("Time", TIME_OPTIONS, key="time_filter")

        st.divider()
        if not spots:
            st.markdown('<p class="muted">NO MATCHED SPOTS</p>', unsafe_allow_html=True)
        for spot in spots:
            color = WEATHER_COLORS.get(spot.get("weather", WEATHER_OPTIONS[0]), "#38bdf8")
            active_mark = "ACTIVE " if spot["id"] == st.session_state.active_spot_id else ""
            if st.button(f"{active_mark}{spot.get('title', '')}", key=f"float_select_spot_{spot['id']}", use_container_width=True):
                st.session_state.active_spot_id = spot["id"]
                st.session_state.selected_point = (spot["lat"], spot["lng"])
                st.session_state.form_lat = spot["lat"]
                st.session_state.form_lng = spot["lng"]
                st.rerun()
            primary_meta = spot.get("body") or spot.get("weather", WEATHER_OPTIONS[0])
            secondary_meta = spot.get("lens") or spot.get("time_band", TIME_OPTIONS[0])
            st.markdown(
                f"""
                <div class="pill-row" style="margin-top:-.45rem;margin-bottom:.6rem;">
                    <span class="pill" style="border-color:{color};">{escape(primary_meta)}</span>
                    <span class="pill">{escape(secondary_meta)}</span>
                    <span class="pill">{compass_label(spot.get("direction", 0))}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.download_button(
            "EXPORT CSV",
            data=spot_csv(st.session_state.spots),
            file_name=f"glassshot-pgis-{datetime.now().strftime('%Y%m%d-%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
        )


def render_drawer_handles() -> None:
    left_label = "FILTER"
    right_label = "LOG"

    if st.button(left_label, key="left_drawer_handle", help="필터 패널 열기/닫기"):
        st.session_state.left_drawer_open = not st.session_state.left_drawer_open
        st.rerun()

    if st.button(right_label, key="right_drawer_handle", help="기록 패널 열기/닫기"):
        next_open = not st.session_state.right_drawer_open
        st.session_state.right_drawer_open = next_open
        if not next_open:
            st.session_state.picking_location = False
        st.rerun()


def add_spot(
    title: str,
    lat: float,
    lng: float,
    direction: int,
    weather: str | None = None,
    time_band: str | None = None,
    mood: str = "",
    camera: str = "",
    memo: str = "",
    uploaded_file: Any = None,
    *,
    url: str = "",
    shot_at: str = "",
    body: str = "",
    lens: str = "",
    iso: str | int = "",
    aperture: str = "",
    shutter_speed: str = "",
) -> None:
    photo_bytes = None
    photo_mime = None
    if uploaded_file is not None:
        photo_bytes, photo_mime = compress_photo(uploaded_file)

    next_id = max([spot["id"] for spot in st.session_state.spots], default=0) + 1
    url_value = (url or memo).strip()
    spot = {
        "id": next_id,
        "title": title.strip(),
        "lat": float(lat),
        "lng": float(lng),
        "direction": int(direction),
        "weather": weather or WEATHER_OPTIONS[0],
        "time_band": time_band or TIME_OPTIONS[0],
        "mood": mood.strip(),
        "camera": camera.strip(),
        "memo": url_value,
        "url": url_value,
        "shot_at": shot_at.strip(),
        "body": body.strip(),
        "lens": lens.strip(),
        "iso": str(iso).strip(),
        "aperture": aperture.strip(),
        "shutter_speed": shutter_speed.strip(),
        "photo_bytes": photo_bytes,
        "photo_mime": photo_mime,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    st.session_state.spots.append(spot)
    st.session_state.active_spot_id = next_id
    st.session_state.selected_point = (spot["lat"], spot["lng"])
    st.session_state.form_lat = spot["lat"]
    st.session_state.form_lng = spot["lng"]


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
                <span style="color:#67e8f9;">{escape(coord_label)}</span>
            </div>
            <p class="muted" style="margin:.45rem 0 0;">
                {"지도에서 기록할 위치를 클릭하세요." if st.session_state.picking_location else "위치 선택 버튼을 누른 뒤 지도에서 지점을 클릭하세요."}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("선택 취소" if st.session_state.picking_location else "위치 선택", key="pick_location_button", use_container_width=True):
        st.session_state.picking_location = not st.session_state.picking_location
        st.session_state.right_drawer_open = True
        st.rerun()

    with st.form("spot_form", clear_on_submit=True):
        title = st.text_input("스팟명", placeholder="예: 유리창 노을 반사 포인트")

        direction = st.slider("촬영 방향", min_value=0, max_value=359, value=45, step=1)
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
            time_band = st.selectbox("시간대", TIME_OPTIONS, index=3)

        col_mood, col_camera = st.columns(2)
        with col_mood:
            mood = st.text_input("무드", placeholder="예: 반사, 역광, 안개")
        with col_camera:
            camera = st.text_input("렌즈/구도", placeholder="예: 35mm low angle")

        uploaded_file = st.file_uploader("사진", type=["jpg", "jpeg", "png", "webp"])
        memo = st.text_input("링크", placeholder="https://example.com")
        submitted = st.form_submit_button("마커 생성", type="primary", use_container_width=True)

    if submitted:
        if not title.strip():
            st.error("스팟명을 입력해주세요.")
        elif memo.strip() and not is_valid_link(memo):
            st.error("링크는 http:// 또는 https:// 형식으로 입력해주세요.")
        else:
            add_spot(title, lat, lng, direction, weather, time_band, mood, camera, memo, uploaded_file)
            st.success("스팟이 지도에 추가됐습니다.")
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_record_form() -> None:
    st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
    title_col, close_col = st.columns([1, 0.36])
    with title_col:
        st.markdown("### RECORD")
    with close_col:
        if st.button("CLOSE", key="close_record_panel", use_container_width=True):
            st.session_state.right_drawer_open = False
            st.session_state.picking_location = False
            st.rerun()

    lat = float(st.session_state.form_lat)
    lng = float(st.session_state.form_lng)
    coord_label = f"{lat:.6f}, {lng:.6f}"
    st.markdown(
        f"""
        <div class="spot-card">
            <div class="spot-title">
                <span>LOCKED COORD</span>
                <span style="color:#67e8f9;">{escape(coord_label)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### DIRECTION")
    direction = render_direction_dial()

    with st.form("record_form", clear_on_submit=True):
        title = st.text_input("Name", placeholder="Night reflection point")
        url = st.text_input("URL", placeholder="https://example.com")

        now = datetime.now()
        col_date, col_time = st.columns(2)
        with col_date:
            shot_date = st.date_input("Shot date", value=now.date())
        with col_time:
            shot_time = st.time_input("Shot time", value=now.time().replace(second=0, microsecond=0))

        col_body, col_lens = st.columns(2)
        with col_body:
            body = st.text_input("Body", placeholder="Sony A7R V")
        with col_lens:
            lens = st.text_input("Lens", placeholder="35mm F1.4")

        col_iso, col_f, col_shutter = st.columns(3)
        with col_iso:
            iso = st.number_input("ISO", min_value=1, max_value=409600, value=100, step=50)
        with col_f:
            aperture = st.text_input("F", placeholder="2.8")
        with col_shutter:
            shutter_speed = st.text_input("Shutter", placeholder="1/125")

        submitted = st.form_submit_button("CREATE MARKER", type="primary", use_container_width=True)

    if submitted:
        if not title.strip():
            st.error("Enter a name.")
        elif not is_valid_link(url):
            st.error("URL must start with http:// or https://.")
        else:
            shot_at = datetime.combine(shot_date, shot_time).strftime("%Y-%m-%d %H:%M")
            add_spot(
                title,
                lat,
                lng,
                direction,
                url=url,
                shot_at=shot_at,
                body=body,
                lens=lens,
                iso=iso,
                aperture=aperture,
                shutter_speed=shutter_speed,
            )
            st.success("Marker added.")
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_active_detail() -> None:
    active = next((spot for spot in st.session_state.spots if spot["id"] == st.session_state.active_spot_id), None)
    st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
    st.markdown("### 선택 스팟")
    if not active:
        st.markdown('<p class="muted">지도나 목록에서 스팟을 선택하세요.</p>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    uri = data_uri(active.get("photo_bytes"), active.get("photo_mime"))
    if uri:
        st.image(uri, use_container_width=True)

    color = WEATHER_COLORS.get(active["weather"], "#38bdf8")
    link = link_html(active.get("memo"))
    st.markdown(
        f"""
        <div class="spot-card">
            <div class="spot-title">
                <span>{escape(active["title"])}</span>
                <span style="color:{color};">{compass_label(active["direction"])}</span>
            </div>
            <div class="pill-row">
                <span class="pill" style="border-color:{color};">{escape(active["weather"])}</span>
                <span class="pill" style="border-color:{TIME_COLORS.get(active["time_band"], "#a78bfa")};">{escape(active["time_band"])}</span>
                <span class="pill">{compass_label(active["direction"])}</span>
                <span class="pill">{escape(active.get("camera") or "camera -")}</span>
            </div>
            <p class="muted" style="margin-bottom:0;">{escape(active.get("mood") or "상세 정보 없음")} · {link}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"{active['lat']:.6f}, {active['lng']:.6f} · {active.get('created_at', '')}")

    col_focus, col_delete = st.columns(2)
    with col_focus:
        if st.button("좌표 사용", use_container_width=True):
            st.session_state.selected_point = (active["lat"], active["lng"])
            st.session_state.form_lat = active["lat"]
            st.session_state.form_lng = active["lng"]
            st.rerun()
    with col_delete:
        if st.button("삭제", use_container_width=True):
            st.session_state.spots = [spot for spot in st.session_state.spots if spot["id"] != active["id"]]
            st.session_state.active_spot_id = st.session_state.spots[0]["id"] if st.session_state.spots else None
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

    color = WEATHER_COLORS.get(active.get("weather", WEATHER_OPTIONS[0]), "#38bdf8")
    link = link_html(active.get("url") or active.get("memo"), "OPEN URL")
    shot_at = active.get("shot_at") or active.get("created_at") or "-"
    body = active.get("body") or "-"
    lens = active.get("lens") or active.get("camera") or "-"
    iso = active.get("iso") or "-"
    aperture = active.get("aperture") or "-"
    shutter_speed = active.get("shutter_speed") or "-"
    st.markdown(
        f"""
        <div class="spot-card">
            <div class="spot-title">
                <span>{escape(active.get("title"))}</span>
                <span style="color:{color};">{compass_label(active.get("direction", 0))}</span>
            </div>
            <div class="pill-row">
                <span class="pill">{escape(shot_at)}</span>
                <span class="pill">ISO {escape(iso)}</span>
                <span class="pill">F {escape(aperture)}</span>
                <span class="pill">{escape(shutter_speed)}</span>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:.55rem;margin-top:.75rem;">
                <div class="pill" style="display:block;">BODY<br /><strong>{escape(body)}</strong></div>
                <div class="pill" style="display:block;">LENS<br /><strong>{escape(lens)}</strong></div>
            </div>
            <p class="muted" style="margin-bottom:0;margin-top:.7rem;">{link}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"{active['lat']:.6f}, {active['lng']:.6f} · {active.get('created_at', '')}")

    col_focus, col_delete = st.columns(2)
    with col_focus:
        if st.button("USE COORD", use_container_width=True):
            st.session_state.selected_point = (active["lat"], active["lng"])
            st.session_state.form_lat = active["lat"]
            st.session_state.form_lng = active["lng"]
            st.rerun()
    with col_delete:
        if st.button("DELETE", use_container_width=True):
            st.session_state.spots = [spot for spot in st.session_state.spots if spot["id"] != active["id"]]
            st.session_state.active_spot_id = st.session_state.spots[0]["id"] if st.session_state.spots else None
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def handle_map_return(map_data: dict[str, Any] | None) -> None:
    if not map_data:
        return
    if map_data.get("_pgis_event") != "contextmenu":
        return

    clicked = map_data.get("last_clicked")
    if clicked and "lat" in clicked and "lng" in clicked:
        nonce = map_data.get("_pgis_nonce")
        if nonce and nonce == st.session_state.get("last_context_click_nonce"):
            return
        st.session_state.last_context_click_nonce = nonce
        lat = round(float(clicked["lat"]), 6)
        lng = round(float(clicked["lng"]), 6)
        st.session_state.selected_point = (lat, lng)
        st.session_state.form_lat = lat
        st.session_state.form_lng = lng
        st.session_state.active_spot_id = None
        st.session_state.right_drawer_open = True
        st.session_state.picking_location = False
        try:
            st.session_state.map_zoom = int(map_data.get("zoom", st.session_state.map_zoom))
        except (TypeError, ValueError):
            pass
        st.rerun()


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
    spots = filtered_spots()

    render_map(spots)
    inject_layout_vars()
    render_filter_floating(spots)
    if st.session_state.right_drawer_open:
        with st.container(key="right_drawer_panel"):
            render_record_form()
            render_record_detail()


if __name__ == "__main__":
    main()
