# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import csv
import html
import io
import os
import sys
from datetime import datetime
from typing import Any

import streamlit as st


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
from PIL import Image
from streamlit_folium import st_folium


st.set_page_config(
    page_title="GlassShot PGIS",
    page_icon="📷",
    layout="wide",
    initial_sidebar_state="expanded",
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
        "memo": "비 온 직후 바닥 반사가 살아난다. 동쪽으로 낮게 잡으면 유리면과 물길이 같이 들어온다.",
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
        "memo": "노을이 건물 뒤로 내려갈 때 인물 실루엣이 가장 깔끔하다.",
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
        "memo": "해가 올라오기 전 20분 동안 수면과 하늘색이 가장 부드럽다.",
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
                linear-gradient(135deg, rgba(34, 211, 238, 0.10), transparent 38% 62%, rgba(251, 113, 133, 0.10)),
                rgba(2, 6, 17, 0.98);
            color: #f8fafc;
            border: 1px solid rgba(148, 163, 184, 0.28);
            box-shadow: 0 24px 56px rgba(0, 0, 0, 0.56), inset 0 0 0 1px rgba(255,255,255,0.04);
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
    direction = int(spot["direction"])
    return f"""
    <div style="width:282px;font-family:Inter,Arial,sans-serif;color:#f8fafc;background:#020611;">
        {image_html}
        <div style="border-left:3px solid {color};padding-left:10px;margin-bottom:10px;">
            <div style="font-size:12px;color:#94a3b8;font-weight:800;text-transform:uppercase;">SPOT VECTOR</div>
            <div style="font-size:16px;font-weight:900;line-height:1.25;color:#ffffff;">{escape(spot["title"])}</div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;">
            <div style="border:1px solid rgba(148,163,184,.22);background:rgba(3,7,18,.88);padding:8px;">
                <div style="font-size:10px;color:#94a3b8;font-weight:800;">DIRECTION</div>
                <div style="font-size:22px;font-weight:950;color:{color};line-height:1.1;">{direction}°</div>
                <div style="font-size:12px;color:#e2e8f0;font-weight:800;">{compass_label(direction)}</div>
            </div>
            <div style="border:1px solid rgba(148,163,184,.22);background:rgba(3,7,18,.88);padding:8px;">
                <div style="font-size:10px;color:#94a3b8;font-weight:800;">CONDITION</div>
                <div style="font-size:12px;color:#f8fafc;font-weight:850;margin-top:4px;">{escape(spot["weather"])}</div>
                <div style="font-size:12px;color:#cbd5e1;font-weight:750;">{escape(spot["time_band"])}</div>
            </div>
        </div>
        <div style="font-size:12px;line-height:1.55;color:#cbd5e1;border-top:1px solid rgba(148,163,184,.18);padding-top:9px;">{escape(spot.get("memo") or spot.get("mood") or "메모 없음")}</div>
    </div>
    """


def build_map(spots: list[dict[str, Any]]) -> folium.Map:
    center = st.session_state.selected_point
    if st.session_state.active_spot_id:
        active = next((spot for spot in st.session_state.spots if spot["id"] == st.session_state.active_spot_id), None)
        if active:
            center = (active["lat"], active["lng"])

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
            </style>
            """
        )
    )

    lat, lng = st.session_state.selected_point
    folium.CircleMarker(
        location=(lat, lng),
        radius=4,
        color="#22d3ee",
        fill=True,
        fill_color="#22d3ee",
        fill_opacity=0.66,
        weight=1,
        tooltip="선택 지점",
    ).add_to(fmap)

    for spot in spots:
        color = WEATHER_COLORS.get(spot["weather"], "#38bdf8")
        active = spot["id"] == st.session_state.active_spot_id
        folium.CircleMarker(
            location=(spot["lat"], spot["lng"]),
            radius=6 if active else 4,
            color=color,
            weight=2 if active else 1,
            fill=True,
            fill_color=color,
            fill_opacity=0.92 if active else 0.72,
            tooltip=f"{spot['id']} · {spot['title']}",
            popup=folium.Popup(popup_html(spot), max_width=320),
        ).add_to(fmap)

    legend_items = "".join(
        f"""
        <div style="display:flex;align-items:center;gap:6px;margin:4px 0;">
            <span style="width:10px;height:10px;border-radius:50%;background:{color};box-shadow:0 0 10px {color};"></span>
            <span>{escape(name)}</span>
        </div>
        """
        for name, color in WEATHER_COLORS.items()
    )
    legend = f"""
    <div style="
        position: fixed;
        right: 18px;
        bottom: 18px;
        z-index: 9999;
        padding: 10px 12px;
        border-radius: 0;
        background: linear-gradient(135deg, rgba(34,211,238,.10), transparent 58%, rgba(251,113,133,.10)), rgba(2, 6, 17, 0.90);
        border: 1px solid rgba(148, 163, 184, 0.24);
        color: #f8fafc;
        font-size: 12px;
        box-shadow: 0 18px 42px rgba(0,0,0,.46), inset 0 0 0 1px rgba(255,255,255,.04);
    ">
        <div style="font-weight:800;margin-bottom:5px;">날씨</div>
        {legend_items}
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(legend))
    return fmap


def filtered_spots() -> list[dict[str, Any]]:
    weather_filter = set(st.session_state.weather_filter or WEATHER_OPTIONS)
    time_filter = set(st.session_state.time_filter or TIME_OPTIONS)
    query = st.session_state.search_query.strip().lower()
    result: list[dict[str, Any]] = []
    for spot in st.session_state.spots:
        haystack = " ".join(
            [
                spot["title"],
                spot["weather"],
                spot["time_band"],
                spot.get("mood", ""),
                spot.get("camera", ""),
                spot.get("memo", ""),
            ]
        ).lower()
        if spot["weather"] not in weather_filter:
            continue
        if spot["time_band"] not in time_filter:
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
            "weather",
            "time_band",
            "mood",
            "camera",
            "memo",
            "created_at",
        ],
    )
    writer.writeheader()
    for spot in spots:
        writer.writerow({key: spot.get(key, "") for key in writer.fieldnames})
    return out.getvalue().encode("utf-8-sig")


def stats(spots: list[dict[str, Any]]) -> tuple[str, str, str, str]:
    total = str(len(st.session_state.spots))
    visible = str(len(spots))
    if st.session_state.spots:
        weather = max(WEATHER_OPTIONS, key=lambda item: sum(spot["weather"] == item for spot in st.session_state.spots))
        time_band = max(TIME_OPTIONS, key=lambda item: sum(spot["time_band"] == item for spot in st.session_state.spots))
    else:
        weather = "-"
        time_band = "-"
    active = next((spot for spot in st.session_state.spots if spot["id"] == st.session_state.active_spot_id), None)
    direction = f"{int(active['direction'])}° {compass_label(active['direction'])}" if active else "-"
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
                st.rerun()
            st.markdown(
                f"""
                <div class="pill-row" style="margin-top:-.45rem;margin-bottom:.6rem;">
                    <span class="pill" style="border-color:{color};">{escape(spot["weather"])}</span>
                    <span class="pill">{escape(spot["time_band"])}</span>
                    <span class="pill">{int(spot["direction"])}° {compass_label(spot["direction"])}</span>
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


def render_drawer_handles() -> None:
    left_label = "FILTER"
    right_label = "LOG"

    if st.button(left_label, key="left_drawer_handle", help="필터 패널 열기/닫기"):
        st.session_state.left_drawer_open = not st.session_state.left_drawer_open
        st.rerun()

    if st.button(right_label, key="right_drawer_handle", help="기록 패널 열기/닫기"):
        st.session_state.right_drawer_open = not st.session_state.right_drawer_open
        st.rerun()


def add_spot(
    title: str,
    lat: float,
    lng: float,
    direction: int,
    weather: str,
    time_band: str,
    mood: str,
    camera: str,
    memo: str,
    uploaded_file: Any,
) -> None:
    photo_bytes = None
    photo_mime = None
    if uploaded_file is not None:
        photo_bytes, photo_mime = compress_photo(uploaded_file)

    next_id = max([spot["id"] for spot in st.session_state.spots], default=0) + 1
    spot = {
        "id": next_id,
        "title": title.strip(),
        "lat": float(lat),
        "lng": float(lng),
        "direction": int(direction),
        "weather": weather,
        "time_band": time_band,
        "mood": mood.strip(),
        "camera": camera.strip(),
        "memo": memo.strip(),
        "photo_bytes": photo_bytes,
        "photo_mime": photo_mime,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    st.session_state.spots.append(spot)
    st.session_state.active_spot_id = next_id
    st.session_state.selected_point = (spot["lat"], spot["lng"])


def render_form() -> None:
    selected_lat, selected_lng = st.session_state.selected_point
    st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
    st.markdown("### 스팟 기록")

    with st.form("spot_form", clear_on_submit=True):
        title = st.text_input("스팟명", placeholder="예: 유리창 노을 반사 포인트")
        col_lat, col_lng = st.columns(2)
        with col_lat:
            lat = st.number_input("위도", value=float(selected_lat), format="%.6f")
        with col_lng:
            lng = st.number_input("경도", value=float(selected_lng), format="%.6f")

        direction = st.slider("촬영 방향", min_value=0, max_value=359, value=45, step=1)
        st.markdown(
            f"""
            <div class="pill-row">
                <span class="pill">방위 {compass_label(direction)}</span>
                <span class="pill">{direction}°</span>
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
        memo = st.text_area("메모", placeholder="빛 방향, 프레임, 대기 시간")
        submitted = st.form_submit_button("마커 생성", type="primary", use_container_width=True)

    if submitted:
        if not title.strip():
            st.error("스팟명을 입력해주세요.")
        else:
            add_spot(title, lat, lng, direction, weather, time_band, mood, camera, memo, uploaded_file)
            st.success("스팟이 지도에 추가됐습니다.")
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
    st.markdown(
        f"""
        <div class="spot-card">
            <div class="spot-title">
                <span>{escape(active["title"])}</span>
                <span style="color:{color};">{int(active["direction"])}°</span>
            </div>
            <div class="pill-row">
                <span class="pill" style="border-color:{color};">{escape(active["weather"])}</span>
                <span class="pill" style="border-color:{TIME_COLORS.get(active["time_band"], "#a78bfa")};">{escape(active["time_band"])}</span>
                <span class="pill">{compass_label(active["direction"])}</span>
                <span class="pill">{escape(active.get("camera") or "camera -")}</span>
            </div>
            <p class="muted" style="margin-bottom:0;">{escape(active.get("memo") or active.get("mood") or "메모 없음")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"{active['lat']:.6f}, {active['lng']:.6f} · {active.get('created_at', '')}")

    col_focus, col_delete = st.columns(2)
    with col_focus:
        if st.button("좌표 사용", use_container_width=True):
            st.session_state.selected_point = (active["lat"], active["lng"])
            st.rerun()
    with col_delete:
        if st.button("삭제", use_container_width=True):
            st.session_state.spots = [spot for spot in st.session_state.spots if spot["id"] != active["id"]]
            st.session_state.active_spot_id = st.session_state.spots[0]["id"] if st.session_state.spots else None
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def handle_map_return(map_data: dict[str, Any] | None) -> None:
    if not map_data:
        return

    tooltip = map_data.get("last_object_clicked_tooltip")
    if tooltip:
        try:
            spot_id = int(str(tooltip).split(" · ")[0])
            if any(spot["id"] == spot_id for spot in st.session_state.spots):
                st.session_state.active_spot_id = spot_id
        except ValueError:
            pass

    clicked = map_data.get("last_clicked")
    if clicked and "lat" in clicked and "lng" in clicked:
        lat = round(float(clicked["lat"]), 6)
        lng = round(float(clicked["lng"]), 6)
        st.session_state.selected_point = (lat, lng)


def render_map(spots: list[dict[str, Any]]) -> None:
    st.markdown('<div class="map-wrap">', unsafe_allow_html=True)
    fmap = build_map(spots)
    map_data = st_folium(
        fmap,
        height=1200,
        use_container_width=True,
        returned_objects=["last_clicked", "last_object_clicked_tooltip"],
        key="photo_spot_map",
    )
    st.markdown("</div>", unsafe_allow_html=True)
    handle_map_return(map_data)


def main() -> None:
    ensure_state()
    inject_css()
    spots = filtered_spots()
    render_drawer_handles()
    render_sidebar(spots)

    render_map(spots)
    with st.container(key="right_drawer_panel"):
        render_form()
        render_active_detail()


if __name__ == "__main__":
    main()
