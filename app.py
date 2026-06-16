# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import csv
import html
import io
import json
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


WEATHER_OPTIONS = ["맑음", "구름", "비", "눈", "안개"]
TIME_OPTIONS = ["오전", "오후"]
WEATHER_COLORS = {
    "맑음": "#facc15",
    "구름": "#94a3b8",
    "비": "#38bdf8",
    "눈": "#f8fafc",
    "안개": "#c4b5fd",
}
TIME_COLORS = {
    "오전": "#67e8f9",
    "오후": "#fb7185",
}
SEOUL_CENTER = (37.5665, 126.9780)
DIRECTION_DIAL_COMPONENT = components.declare_component(
    "direction_dial",
    path=os.path.join(os.path.dirname(__file__), "components", "direction_dial"),
)


SAMPLE_SPOTS: list[dict[str, Any]] = [
    {
        "id": 1,
        "title": "You're my everything",
        "URL": "https://www.instagram.com/p/DY53jn5kjft/?igsh=MWl2bGs1Z2E1bjc0ag==",
        "lat": 37.5502,
        "lng": 127.0357,
        "drct": 167,
        "weather": "맑음",
        "date": "2026-05-23",
        "time": "17:00",
        "body": "Fujifilm X-T30",
        "lens": "TAMRON 18-300mm F3.5-6.3 Di III-A VC VXD",
        "comp": {"F값": "5.6", "ISO값": "640", "셔터스피드": "1/750", "화각": "261mm"},
    },
    {
        "id": 2,
        "title": "반포대교 윤슬",
        "URL": "https://www.instagram.com/p/DWZIoz0EjNn/?igsh=dW1mZGRyYmJ1bGg4",
        "lat": 37.5140,
        "lng": 127.0018,
        "drct": 269,
        "weather": "맑음",
        "date": "2026-03-27",
        "time": "17:45",
        "body": "Fujifilm X-T30",
        "lens": "TAMRON 18-300mm F3.5-6.3 Di III-A VC VXD",
        "comp": {"F값": "4.5", "ISO값": "640", "셔터스피드": "1/500", "화각": "68mm"},
    },
    {
        "id": 3,
        "title": "금호역 버스정류장에서.",
        "URL": "https://www.instagram.com/p/DZJ8tNRSdtB/?igsh=MTFtdHE2OWc3Y243bA==",
        "lat": 37.5443,
        "lng": 127.0169,
        "drct": 343,
        "weather": "구름",
        "date": "2026-06-04",
        "time": "16:20",
        "body": "Samsung Galaxy S24",
        "lens": "Samsung Galaxy S24",
        "comp": {"F값": "2.4", "ISO값": "25", "셔터스피드": "1/744", "화각": "69mm"},
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
            --record-panel-width: min(330px, calc(100vw - 24px));
            --record-panel-left: calc(100vw - 360px);
            --record-panel-top: 18px;
            --panel-black: rgba(2, 6, 15, 0.94);
            --panel-line: rgba(148, 163, 184, 0.26);
            --neon-cyan: #22d3ee;
            --neon-blue: #38bdf8;
            --neon-pink: #fb7185;
            --neon-violet: #a78bfa;
            --radius-sm: 6px;
            --radius-md: 8px;
            --radius-pill: 999px;
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
            border-radius: var(--radius-md);
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
            border-radius: var(--radius-md);
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
            border-radius: var(--radius-pill);
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
            background:
                linear-gradient(232deg, rgba(251, 113, 133, 0.13), transparent 20% 55%, rgba(34, 211, 238, 0.12)),
                repeating-linear-gradient(45deg, transparent 0 18px, rgba(148, 163, 184, 0.045) 18px 19px),
                var(--panel-black);
            border: 1px solid var(--panel-line);
            box-shadow: 0 22px 64px rgba(0, 0, 0, 0.56), inset 0 0 0 1px rgba(255,255,255,0.06);
            transform: translate3d(
                min(calc(100vw - var(--record-panel-width) - 16px), max(16px, var(--record-panel-left))),
                min(calc(100vh - 78px), max(12px, var(--record-panel-top))),
                0
            );
            transition: opacity 160ms ease, box-shadow 180ms ease;
            will-change: transform, opacity;
            contain: layout paint style;
            z-index: 72;
            border-radius: var(--radius-md);
        }

        .st-key-right_drawer_panel::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: calc(100% - 18px);
            border-radius: 999px;
            margin-top: 9px;
            background:
                linear-gradient(180deg, #fb7185, #a78bfa 38%, #22d3ee 70%, #34d399);
            opacity: 0.82;
        }

        .st-key-right_drawer_panel .glass-panel {
            margin-bottom: 0;
            padding: 0;
            border: 0;
            background: transparent;
            box-shadow: none;
            backdrop-filter: none;
        }

        .record-head {
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 0.55rem;
            align-items: center;
            margin-bottom: 0.35rem;
        }

        .record-title {
            color: var(--glass-text);
            font-size: 1rem;
            font-weight: 900;
            line-height: 1.15;
        }

        .record-coord {
            display: inline-flex;
            align-items: center;
            max-width: 100%;
            min-height: 24px;
            padding: 0.18rem 0.46rem;
            border-radius: var(--radius-pill);
            border: 1px solid rgba(34, 211, 238, 0.34);
            color: #67e8f9;
            background: rgba(3, 7, 18, 0.68);
            font: 800 0.72rem/1.2 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }

        .st-key-right_drawer_panel [data-testid="stVerticalBlock"] {
            gap: 0.35rem;
        }

        .st-key-right_drawer_panel [data-testid="stHorizontalBlock"] {
            gap: 0.45rem;
        }

        .st-key-right_drawer_panel label {
            font-size: 0.74rem !important;
            line-height: 1.2 !important;
            margin-bottom: 0.1rem !important;
        }

        .st-key-right_drawer_panel input,
        .st-key-right_drawer_panel [data-baseweb="select"] > div {
            min-height: 34px !important;
            font-size: 0.84rem !important;
        }

        .st-key-right_drawer_panel .stButton > button,
        .st-key-right_drawer_panel [data-testid="stBaseButton-secondary"],
        .st-key-right_drawer_panel [data-testid="stBaseButton-primary"] {
            min-height: 34px !important;
            padding: 0.25rem 0.55rem !important;
            font-size: 0.82rem !important;
        }

        .record-dial-caption {
            margin: -0.15rem 0 0;
            text-align: center;
            color: #67e8f9;
            font: 900 0.72rem/1.2 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }

        .record-time-row {
            margin-top: -0.1rem;
        }

        .record-advanced-note {
            margin: 0.1rem 0 0;
            color: var(--glass-muted);
            font-size: 0.74rem;
            line-height: 1.35;
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
            border-radius: var(--radius-md);
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
            border-radius: var(--radius-pill);
        }

        .filter-mini {
            border-top: 1px solid rgba(148, 163, 184, 0.18);
            padding-top: 0.62rem;
            color: #cbd5e1;
            font-size: 0.82rem;
            line-height: 1.45;
            border-radius: var(--radius-md);
        }

        .st-key-settings_floating_panel {
            position: fixed;
            top: 18px;
            right: 18px;
            width: min(230px, calc(100vw - 36px)) !important;
            z-index: 82;
            padding: 0.58rem;
            background:
                linear-gradient(132deg, rgba(251, 113, 133, 0.15), transparent 30% 64%, rgba(34, 211, 238, 0.13)),
                rgba(2, 6, 15, 0.92);
            border: 1px solid rgba(248, 250, 252, 0.24);
            box-shadow: 0 18px 48px rgba(0, 0, 0, 0.52), inset 0 0 0 1px rgba(255, 255, 255, 0.045);
            backdrop-filter: blur(18px) saturate(1.18);
            border-radius: var(--radius-md);
        }

        .st-key-settings_floating_panel [data-testid="stMarkdownContainer"] p {
            margin: 0;
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
            border-radius: var(--radius-md) !important;
            writing-mode: vertical-rl;
            text-orientation: mixed;
            letter-spacing: 0 !important;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            font-size: 0.72rem;
            font-weight: 900;
            color: #f8fafc !important;
            clip-path: none;
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
            clip-path: none;
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
            border-radius: var(--radius-md);
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
            border-radius: var(--radius-sm) !important;
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
            border-radius: var(--radius-md);
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
            border-radius: var(--radius-md);
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
    if st.session_state.get("theme_mode", "dark") == "light":
        st.markdown(
            """
            <style>
            :root {
                color-scheme: light;
                --glass-bg: rgba(255, 255, 255, 0.84);
                --glass-line: rgba(15, 23, 42, 0.16);
                --glass-text: #0f172a;
                --glass-muted: #64748b;
                --panel-black: rgba(255, 255, 255, 0.94);
                --panel-line: rgba(15, 23, 42, 0.14);
            }

            html, body, [data-testid="stAppViewContainer"], .stApp {
                background: #f4f7fb;
                color: #0f172a;
            }

            .stApp::before {
                background:
                    linear-gradient(116deg, transparent 0 18%, rgba(8, 145, 178, 0.12) 18% 18.5%, transparent 18.5% 43%, rgba(244, 63, 94, 0.10) 43% 43.45%, transparent 43.45% 71%, rgba(217, 119, 6, 0.10) 71% 71.5%, transparent 71.5%),
                    linear-gradient(38deg, rgba(5, 150, 105, 0.08) 0 10%, transparent 10% 36%, rgba(124, 58, 237, 0.08) 36% 36.45%, transparent 36.45% 66%, rgba(14, 165, 233, 0.08) 66% 66.4%, transparent 66.4%),
                    #f4f7fb;
                opacity: 0.95;
            }

            .stApp::after {
                background-image:
                    linear-gradient(90deg, rgba(15, 23, 42, 0.045) 1px, transparent 1px),
                    linear-gradient(0deg, rgba(15, 23, 42, 0.035) 1px, transparent 1px);
                mix-blend-mode: multiply;
                opacity: 0.28;
            }

            [data-testid="stSidebar"],
            .st-key-right_drawer_panel {
                background:
                    linear-gradient(128deg, rgba(8, 145, 178, 0.10), transparent 22% 56%, rgba(124, 58, 237, 0.08)),
                    rgba(255, 255, 255, 0.94);
                border-color: rgba(15, 23, 42, 0.14);
                box-shadow: 18px 0 54px rgba(15, 23, 42, 0.16), inset -1px 0 rgba(8, 145, 178, 0.16);
            }

            .st-key-right_drawer_panel {
                box-shadow: -18px 0 54px rgba(15, 23, 42, 0.16), inset 1px 0 rgba(244, 63, 94, 0.14);
            }

            .hero,
            .stat-tile,
            .glass-panel,
            .spot-card,
            .st-key-filter_floating_panel,
            .st-key-settings_floating_panel {
                background:
                    linear-gradient(132deg, rgba(8, 145, 178, 0.09), transparent 28% 62%, rgba(244, 63, 94, 0.07)),
                    rgba(255, 255, 255, 0.86);
                border-color: rgba(15, 23, 42, 0.14);
                box-shadow: 0 18px 42px rgba(15, 23, 42, 0.14), inset 0 0 0 1px rgba(255, 255, 255, 0.56);
            }

            .glass-panel::before {
                opacity: 0.34;
            }

            .hero-title,
            .stat-value,
            .spot-title,
            .filter-mini strong,
            [data-testid="stSidebar"] h3,
            .st-key-right_drawer_panel h3 {
                color: #0f172a;
            }

            .hero-sub,
            .muted,
            .filter-mini,
            [data-testid="stSidebar"] label,
            .st-key-right_drawer_panel label {
                color: #475569 !important;
            }

            .pill,
            .filter-count {
                color: #0f172a;
                background: rgba(255, 255, 255, 0.74);
                border-color: rgba(15, 23, 42, 0.16);
            }

            .drawer-handle button,
            .st-key-left_drawer_handle button,
            .st-key-right_drawer_handle button,
            .stButton > button,
            .stDownloadButton > button,
            [data-testid="stBaseButton-secondary"] {
                color: #0f172a !important;
                background:
                    linear-gradient(115deg, rgba(8, 145, 178, 0.10), transparent 42% 62%, rgba(244, 63, 94, 0.10)),
                    rgba(255, 255, 255, 0.86) !important;
                border-color: rgba(15, 23, 42, 0.18) !important;
            }

            [data-testid="stBaseButton-primary"] {
                color: #ffffff !important;
                background:
                    linear-gradient(90deg, rgba(8, 145, 178, 0.78), rgba(244, 63, 94, 0.70)),
                    #0891b2 !important;
            }

            input,
            textarea,
            [data-baseweb="select"] > div {
                color: #0f172a !important;
                background: rgba(255, 255, 255, 0.86) !important;
                border-color: rgba(15, 23, 42, 0.18) !important;
            }

            input:focus,
            textarea:focus {
                border-color: rgba(8, 145, 178, 0.72) !important;
                box-shadow: 0 0 0 1px rgba(8, 145, 178, 0.24) !important;
            }

            div[data-testid="stFileUploaderDropzone"] {
                background: rgba(255, 255, 255, 0.76);
                border-color: rgba(8, 145, 178, 0.34);
            }

            .leaflet-popup-content-wrapper,
            .leaflet-popup-tip {
                background:
                    linear-gradient(135deg, rgba(15,23,42,0.04), transparent 24% 72%, rgba(8,145,178,0.06)),
                    rgba(255, 255, 255, 0.98);
                color: #0f172a;
                border-color: rgba(15, 23, 42, 0.18);
                box-shadow: 0 20px 48px rgba(15, 23, 42, 0.16);
            }

            .leaflet-popup-close-button {
                color: #0f172a !important;
                text-shadow: none;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    left_open = bool(st.session_state.get("left_drawer_open", False))
    right_open = bool(st.session_state.get("right_drawer_open", False))
    record_left = int(st.session_state.get("record_panel_x", 24)) + 18
    record_top = int(st.session_state.get("record_panel_y", 24)) + 18
    st.markdown(
        f"""
        <style>
        :root {{
            --left-drawer-x: {"0" if left_open else "calc(-100% - 1px)"};
            --right-drawer-x: {"0" if right_open else "calc(100% + 1px)"};
            --left-handle-left: {"var(--drawer-width)" if left_open else "0px"};
            --right-handle-right: {"var(--drawer-width)" if right_open else "0px"};
            --record-panel-left: {record_left}px;
            --record-panel-top: {record_top}px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_layout_vars() -> None:
    left_open = bool(st.session_state.get("left_drawer_open", False))
    right_open = bool(st.session_state.get("right_drawer_open", False))
    record_left = int(st.session_state.get("record_panel_x", 24)) + 18
    record_top = int(st.session_state.get("record_panel_y", 24)) + 18
    st.markdown(
        f"""
        <style>
        :root {{
            --left-drawer-x: {"0" if left_open else "calc(-100% - 1px)"};
            --right-drawer-x: {"0" if right_open else "calc(100% + 1px)"};
            --left-handle-left: {"var(--drawer-width)" if left_open else "0px"};
            --right-handle-right: {"var(--drawer-width)" if right_open else "0px"};
            --record-panel-left: {record_left}px;
            --record-panel-top: {record_top}px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def ensure_state() -> None:
    now = datetime.now()
    defaults = {
        "spots": [spot.copy() for spot in SAMPLE_SPOTS],
        "selected_point": SEOUL_CENTER,
        "map_center": SEOUL_CENTER,
        "active_spot_id": 1,
        "weather_filter": WEATHER_OPTIONS.copy(),
        "time_filter": TIME_OPTIONS.copy(),
        "search_query": "",
        "map_zoom": 12,
        "left_drawer_open": False,
        "right_drawer_open": False,
        "form_lat": SEOUL_CENTER[0],
        "form_lng": SEOUL_CENTER[1],
        "record_panel_x": 24,
        "record_panel_y": 24,
        "record_long_exposure": False,
        "picking_location": False,
        "filter_open": False,
        "settings_open": False,
        "theme_mode": "dark",
        "last_context_click_nonce": None,
        "last_panel_close_nonce": None,
        "record_direction": 45,
        "record_advance_open": False,
        "record_date_text": now.strftime("%Y-%m-%d"),
        "record_time_text": now.strftime("%H:%M"),
        "record_iso_text": "100",
        "record_f_value": "",
        "record_focal": "",
        "record_shutter_seconds_text": "1",
        "record_shutter_denominator_text": "125",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    st.session_state.spots = [
        normalize_spot(spot, index + 1)
        for index, spot in enumerate(st.session_state.get("spots", []))
    ]
    current_weather_filter = st.session_state.get("weather_filter") or []
    current_time_filter = st.session_state.get("time_filter") or []
    if not set(current_weather_filter).issubset(set(WEATHER_OPTIONS)):
        st.session_state.weather_filter = WEATHER_OPTIONS.copy()
    if not set(current_time_filter).issubset(set(TIME_OPTIONS)):
        st.session_state.time_filter = TIME_OPTIONS.copy()


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
        "weather": weather,
        "time": normalize_time_value(str(time_value or "")),
        "date": normalize_date_value(str(date_value or "")) or "",
        "body": str(spot.get("body") or "").strip(),
        "lens": str(spot.get("lens") or spot.get("camera") or "").strip(),
        "comp": comp,
    }


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
    color = WEATHER_COLORS.get(spot.get("weather", WEATHER_OPTIONS[0]), "#38bdf8")
    img = data_uri(spot.get("photo_bytes"), spot.get("photo_mime"))
    image_html = ""
    if img:
        image_html = (
            f'<img src="{img}" style="width:100%;max-height:150px;object-fit:cover;'
            'margin-bottom:10px;border:1px solid rgba(148,163,184,0.24);" />'
        )
    link = link_html(spot_url(spot))
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
                <div style="font-size:12px;color:#f8fafc;font-weight:850;margin-top:4px;">{escape(spot.get("weather"))}</div>
                <div style="font-size:12px;color:#cbd5e1;font-weight:750;">{escape(spot.get("time"))}</div>
            </div>
        </div>
        <div style="font-size:12px;line-height:1.55;color:#cbd5e1;border-top:1px solid rgba(148,163,184,.18);padding-top:9px;">{escape(spot.get("body") or spot.get("lens") or "상세 정보 없음")}</div>
    </div>
    """


def record_popup_html(spot: dict[str, Any]) -> str:
    color = WEATHER_COLORS.get(spot.get("weather", WEATHER_OPTIONS[0]), "#38bdf8")
    link = link_html(spot_url(spot), "OPEN URL")
    shot_date = spot.get("date") or "-"
    shot_time = spot.get("time") or "-"
    advanced_html = ""
    items = advanced_items(spot)
    if items:
        advanced_html = (
            '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;'
            'font-size:12px;line-height:1.45;color:#cbd5e1;'
            'border-top:1px solid rgba(148,163,184,.18);padding-top:9px;">'
            + "".join(
                f'<div><span style="color:#94a3b8;font-weight:800;">{escape(label)}</span><br />{escape(value)}</div>'
                for label, value in items
            )
            + "</div>"
        )
    return f"""
    <div style="width:282px;font-family:Inter,Arial,sans-serif;color:#f8fafc;background:#020611;">
        <div style="border-left:3px solid {color};padding-left:10px;margin-bottom:10px;">
            <div style="font-size:12px;color:#94a3b8;font-weight:800;text-transform:uppercase;">SPOT NODE</div>
            <div style="font-size:16px;font-weight:900;line-height:1.25;color:#ffffff;">{escape(spot.get("title"))}</div>
            <div style="font-size:12px;color:{color};font-weight:900;margin-top:4px;">{compass_label(spot_drct(spot))}</div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;">
            <div style="border:1px solid rgba(148,163,184,.22);background:rgba(3,7,18,.88);padding:8px;">
                <div style="font-size:10px;color:#94a3b8;font-weight:800;">URL</div>
                <div style="font-size:12px;margin-top:8px;">{link}</div>
            </div>
            <div style="border:1px solid rgba(148,163,184,.22);background:rgba(3,7,18,.88);padding:8px;">
                <div style="font-size:10px;color:#94a3b8;font-weight:800;">SHOT</div>
                <div style="font-size:12px;color:#f8fafc;font-weight:850;margin-top:4px;">{escape(shot_date)}</div>
                <div style="font-size:12px;color:#cbd5e1;font-weight:750;">{escape(shot_time)}</div>
            </div>
        </div>
        {advanced_html}
    </div>
    """


def add_direction_vector(fmap: folium.Map, spot: dict[str, Any]) -> None:
    color = WEATHER_COLORS.get(spot.get("weather", WEATHER_OPTIONS[0]), "#38bdf8")
    end_lat, end_lng = destination_point(spot["lat"], spot["lng"], spot_drct(spot))
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


def add_selected_direction_preview(
    fmap: folium.Map,
    lat: float,
    lng: float,
    direction: int | float,
    *,
    light_mode: bool,
) -> None:
    color = "#dc2626" if light_mode else "#fb7185"
    label_bg = "rgba(255,255,255,0.94)" if light_mode else "rgba(2,6,15,0.92)"
    label_text = "#0f172a" if light_mode else "#f8fafc"
    end_lat, end_lng = destination_point(lat, lng, direction, distance_m=420)
    preview_line = folium.PolyLine(
        locations=[(lat, lng), (end_lat, end_lng)],
        color=color,
        weight=4,
        opacity=0.94,
        dash_array="10, 8",
    )
    preview_line.add_to(fmap)
    preview_end = folium.CircleMarker(
        location=(end_lat, end_lng),
        radius=5,
        color=color,
        weight=2,
        fill=True,
        fill_color=color,
        fill_opacity=0.92,
    )
    preview_end.add_to(fmap)
    preview_label = folium.Marker(
        location=(end_lat, end_lng),
        icon=folium.DivIcon(
            class_name="pgis-direction-label",
            html=(
                f'<span style="background:{label_bg};color:{label_text};'
                f'border:1px solid {color};box-shadow:0 12px 26px rgba(0,0,0,.24);">'
                f"{int(round(float(direction))) % 360:03d} {compass_label(direction)}</span>"
            ),
            icon_size=(96, 26),
            icon_anchor=(-8, 13),
        ),
    )
    preview_label.add_to(fmap)
    SelectedDirectionPreviewScript(
        preview_line.get_name(),
        preview_end.get_name(),
        preview_label.get_name(),
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
        end_lat, end_lng = destination_point(spot["lat"], spot["lng"], spot_drct(spot))
        self.map_name = fmap.get_name()
        self.marker_name = marker_name
        self.start_lat = f"{float(spot['lat']):.8f}"
        self.start_lng = f"{float(spot['lng']):.8f}"
        self.end_lat = f"{end_lat:.8f}"
        self.end_lng = f"{end_lng:.8f}"
        self.color = WEATHER_COLORS.get(spot.get("weather", WEATHER_OPTIONS[0]), "#38bdf8")


class SelectedPointMarkerScript(MacroElement):
    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var layers = [{{ this.outer_name }}, {{ this.inner_name }}];
            window.__pgisSelectedPointLayers = layers;
            layers.forEach(function(layer) {
                if (layer && layer.options) {
                    layer.options.pgisSelectedPoint = true;
                }
            });
        })();
        {% endmacro %}
        """
    )

    def __init__(self, outer_name: str, inner_name: str) -> None:
        super().__init__()
        self._name = "SelectedPointMarkerScript"
        self.outer_name = outer_name
        self.inner_name = inner_name


class SelectedDirectionPreviewScript(MacroElement):
    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var layers = [{{ this.line_name }}, {{ this.end_name }}, {{ this.label_name }}];
            window.__pgisSelectedDirectionLayers = layers;
            layers.forEach(function(layer) {
                if (layer && layer.options) {
                    layer.options.pgisSelectedDirection = true;
                }
            });
        })();
        {% endmacro %}
        """
    )

    def __init__(self, line_name: str, end_name: str, label_name: str) -> None:
        super().__init__()
        self._name = "SelectedDirectionPreviewScript"
        self.line_name = line_name
        self.end_name = end_name
        self.label_name = label_name


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
            function sendComponentValue(payload) {
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
            }
            function getHostDocument() {
                try {
                    return window.parent && window.parent.document ? window.parent.document : null;
                } catch (error) {
                    return null;
                }
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
                var panel = hostDocument.querySelector(".st-key-right_drawer_panel");
                if (panel) {
                    panel.style.opacity = "1";
                    panel.style.pointerEvents = "";
                }
            }
            function hideHostRecordPanel() {
                var hostDocument = getHostDocument();
                if (!hostDocument) {
                    return;
                }
                var panel = hostDocument.querySelector(".st-key-right_drawer_panel");
                if (panel) {
                    panel.style.opacity = "0";
                    panel.style.pointerEvents = "none";
                }
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
                var center = map.getCenter();
                sendComponentValue({
                    _pgis_event: "record_panel_out_of_bounds",
                    _pgis_nonce: String(Date.now()) + "-" + Math.random().toString(36).slice(2),
                    zoom: map.getZoom(),
                    center: {
                        lat: center.lat,
                        lng: center.lng
                    },
                    last_clicked: selectedLatLng ? {
                        lat: selectedLatLng.lat,
                        lng: selectedLatLng.lng
                    } : null
                });
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
            map.on("move zoom resize", requestRecordPanelSync);
            map.on("moveend zoomend", syncRecordPanelPosition);
            if (recordPanelOpen) {
                map.whenReady(requestRecordPanelSync);
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
                clearSelectedPointMarkers();
                window.__pgisSelectedPointLayer = L.layerGroup([
                    L.circleMarker(selectedLatLng, {
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
                    L.circleMarker(selectedLatLng, {
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
                drawDirectionPreview(selectedLatLng, {{ this.default_direction }});
                var nonce = String(Date.now()) + "-" + Math.random().toString(36).slice(2);
                var original = event.originalEvent || {};
                var point = map.latLngToContainerPoint(selectedLatLng);
                var center = map.getCenter();
                setHostRecordPanelPosition(point);
                var payload = {
                    _pgis_event: "contextmenu",
                    _pgis_nonce: nonce,
                    zoom: map.getZoom(),
                    center: {
                        lat: center.lat,
                        lng: center.lng
                    },
                    container_point: {
                        x: point.x,
                        y: point.y
                    },
                    client_point: {
                        x: original.clientX || point.x,
                        y: original.clientY || point.y
                    },
                    last_clicked: {
                        lat: selectedLatLng.lat,
                        lng: selectedLatLng.lng
                    }
                };
                sendComponentValue(payload);
            });
        })();
        {% endmacro %}
        """
    )

    def __init__(self, fmap: folium.Map) -> None:
        super().__init__()
        self._name = "RightClickSelectScript"
        self.map_name = fmap.get_name()
        light_mode = st.session_state.get("theme_mode", "dark") == "light"
        self.selected_ring = "#0f172a" if light_mode else "#f8fafc"
        self.selected_fill = "#0891b2" if light_mode else "#22d3ee"
        self.selected_inner_stroke = "#ffffff" if light_mode else "#020611"
        self.selected_inner_fill = "#0f172a" if light_mode else "#ffffff"
        self.direction_color = "#dc2626" if light_mode else "#fb7185"
        self.default_direction = int(st.session_state.get("record_direction", 45)) % 360
        selected_lat, selected_lng = st.session_state.get("selected_point", SEOUL_CENTER)
        self.selected_lat = f"{float(selected_lat):.8f}"
        self.selected_lng = f"{float(selected_lng):.8f}"
        self.panel_open = "true" if st.session_state.get("right_drawer_open", False) else "false"


def build_map(spots: list[dict[str, Any]]) -> folium.Map:
    center = st.session_state.get("map_center", st.session_state.selected_point)
    active_spot = None
    if st.session_state.active_spot_id:
        active_spot = next((spot for spot in st.session_state.spots if spot["id"] == st.session_state.active_spot_id), None)
        if active_spot:
            center = (active_spot["lat"], active_spot["lng"])
    light_mode = st.session_state.get("theme_mode", "dark") == "light"
    tile_url = (
        "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        if light_mode
        else "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    )
    tile_name = "Light Matter" if light_mode else "Dark Matter"
    map_bg = "#f4f7fb" if light_mode else "#060811"
    popup_surface = "rgba(255, 255, 255, 0.98)" if light_mode else "rgba(2, 6, 17, 0.98)"
    popup_text = "#0f172a" if light_mode else "#f8fafc"
    popup_border = "rgba(15, 23, 42, 0.18)" if light_mode else "rgba(248, 250, 252, 0.34)"
    popup_shadow = "0 20px 50px rgba(15, 23, 42, 0.18)" if light_mode else "0 22px 58px rgba(0, 0, 0, 0.62)"
    popup_inset = "rgba(15, 23, 42, 0.05)" if light_mode else "rgba(255,255,255,0.08)"
    popup_close_hover = "#020617" if light_mode else "#ffffff"
    selected_ring = "#0f172a" if light_mode else "#f8fafc"
    selected_fill = "#0891b2" if light_mode else "#22d3ee"
    selected_inner_stroke = "#ffffff" if light_mode else "#020611"
    selected_inner_fill = "#0f172a" if light_mode else "#ffffff"

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
            .leaflet-popup-content-wrapper,
            .leaflet-popup-tip {{
                background:
                    linear-gradient(135deg, rgba(255,255,255,0.08), transparent 24% 72%, rgba(34,211,238,0.08)),
                    {popup_surface} !important;
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
                color: {popup_text} !important;
                font-weight: 900 !important;
                text-shadow: 0 0 12px rgba(255,255,255,0.45);
            }}
            .leaflet-popup-close-button:hover {{
                background: transparent !important;
                color: {popup_close_hover} !important;
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

    lat, lng = st.session_state.selected_point
    selected_outer = folium.CircleMarker(
        location=(lat, lng),
        radius=12,
        color=selected_ring,
        fill=True,
        fill_color=selected_fill,
        fill_opacity=0.34,
        opacity=0.94,
        weight=2,
        tooltip="선택 지점",
    )
    selected_outer.add_to(fmap)

    selected_inner = folium.CircleMarker(
        location=(lat, lng),
        radius=4,
        color=selected_inner_stroke,
        fill=True,
        fill_color=selected_inner_fill,
        fill_opacity=0.96,
        weight=1,
        tooltip="selected point",
    )
    selected_inner.add_to(fmap)
    SelectedPointMarkerScript(selected_outer.get_name(), selected_inner.get_name()).add_to(fmap)

    if st.session_state.get("right_drawer_open", False):
        add_selected_direction_preview(
            fmap,
            float(lat),
            float(lng),
            int(st.session_state.get("record_direction", 45)) % 360,
            light_mode=light_mode,
        )

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
        time_value = str(spot.get("time", ""))
        meridiem = time_meridiem(time_value)
        comp = spot_comp(spot)
        haystack = " ".join(
            [
                spot.get("title", ""),
                weather,
                str(spot.get("date", "")),
                time_value,
                spot_url(spot),
                str(spot.get("body", "")),
                str(spot.get("lens", "")),
                comp.get("F값", ""),
                comp.get("ISO값", ""),
                comp.get("셔터스피드", ""),
                comp.get("화각", ""),
            ]
        ).lower()
        if weather not in weather_filter:
            continue
        if meridiem not in time_filter:
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
            "URL",
            "lat",
            "lng",
            "drct",
            "weather",
            "date",
            "time",
            "body",
            "lens",
            "comp",
        ],
    )
    writer.writeheader()
    for spot in spots:
        row = {key: spot.get(key, "") for key in writer.fieldnames}
        row["URL"] = spot_url(spot)
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


def render_sidebar(spots: list[dict[str, Any]]) -> None:
    with st.sidebar:
        st.markdown("### 필터")
        st.session_state.search_query = st.text_input("검색", value=st.session_state.search_query, placeholder="장소, 무드, 메모")
        st.session_state.weather_filter = st.multiselect("날씨", WEATHER_OPTIONS, default=st.session_state.weather_filter)
        st.session_state.time_filter = st.multiselect("오전/오후", TIME_OPTIONS, default=st.session_state.time_filter)

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
                    <span class="pill">{escape(spot.get("time", ""))}</span>
                    <span class="pill">{compass_label(spot_drct(spot))}</span>
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

        st.text_input("Search", key="search_query", placeholder="title, URL, body, lens")
        st.multiselect("Weather", WEATHER_OPTIONS, key="weather_filter")
        st.multiselect("AM/PM", TIME_OPTIONS, key="time_filter")

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
            secondary_meta = spot.get("lens") or spot.get("time", "")
            st.markdown(
                f"""
                <div class="pill-row" style="margin-top:-.45rem;margin-bottom:.6rem;">
                    <span class="pill" style="border-color:{color};">{escape(primary_meta)}</span>
                    <span class="pill">{escape(secondary_meta)}</span>
                    <span class="pill">{compass_label(spot_drct(spot))}</span>
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


def render_settings_floating() -> None:
    with st.container(key="settings_floating_panel"):
        if st.button("SETTINGS", key="settings_floating_toggle", use_container_width=True):
            st.session_state.settings_open = not st.session_state.settings_open
            st.rerun()

        if not st.session_state.settings_open:
            return

        light_mode = st.toggle(
            "Light mode",
            value=st.session_state.get("theme_mode", "dark") == "light",
            key="settings_light_mode",
        )
        next_theme = "light" if light_mode else "dark"
        if next_theme != st.session_state.get("theme_mode", "dark"):
            st.session_state.theme_mode = next_theme
            st.rerun()


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
    drct: int,
    weather: str | None = None,
    date_value: str = "",
    time_value: str = "",
    body: str = "",
    lens: str = "",
    comp: dict[str, str] | None = None,
    *,
    url: str = "",
) -> None:
    next_id = max([spot["id"] for spot in st.session_state.spots], default=0) + 1
    spot = {
        "id": next_id,
        "title": title.strip(),
        "URL": url.strip(),
        "lat": float(lat),
        "lng": float(lng),
        "drct": int(drct) % 360,
        "weather": weather or WEATHER_OPTIONS[0],
        "date": date_value.strip(),
        "body": body.strip(),
        "lens": lens.strip(),
        "time": time_value.strip(),
        "comp": comp or {"F값": "", "ISO값": "", "셔터스피드": "", "화각": ""},
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
            add_spot(
                title,
                lat,
                lng,
                direction,
                weather=weather,
                date_value=normalize_date_value(date_text) or "",
                time_value=normalize_time_value(time_text),
                lens=camera,
                url=memo,
            )
            st.success("스팟이 지도에 추가됐습니다.")
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_record_form() -> None:
    lat = float(st.session_state.form_lat)
    lng = float(st.session_state.form_lng)
    coord_label = f"{lat:.6f}, {lng:.6f}"
    head_col, close_col = st.columns([1, 0.32])
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
        close_clicked = st.button("닫기", key="close_record_panel", use_container_width=True)
    if close_clicked:
        st.session_state.right_drawer_open = False
        st.session_state.picking_location = False
        st.rerun()

    dial_col, main_col = st.columns([0.42, 1.0])
    with dial_col:
        direction = render_direction_dial()
    with main_col:
        title = st.text_input("제목", placeholder="촬영 지점 이름", key="record_title")
        url = st.text_input("URL", placeholder="https://instagram.com/...", key="record_url")

    weather_col, date_col, time_col = st.columns([0.72, 1.0, 0.82])
    with weather_col:
        weather = st.selectbox("날씨", WEATHER_OPTIONS, key="record_weather")
    with date_col:
        date_text = st.text_input("촬영 날짜", placeholder="YYYY-MM-DD", key="record_date_text")
    with time_col:
        time_text = st.text_input("시간", placeholder="17:30", key="record_time_text")

    advanced = st.toggle("ADVANCE", key="record_advance_open")

    body = ""
    lens = ""
    comp = {"F값": "", "ISO값": "", "셔터스피드": "", "화각": ""}
    shutter_speed = ""
    if advanced:
        st.markdown('<p class="record-advanced-note">Body, lens, comp</p>', unsafe_allow_html=True)
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

        long_exposure = st.toggle("장노출", key="record_long_exposure")
        shutter_col, focal_col = st.columns(2)
        with shutter_col:
            if long_exposure:
                shutter_raw = st.text_input("셔터 N초", placeholder="1", key="record_shutter_seconds_text")
                shutter_speed = f"{shutter_raw.strip()}s" if shutter_raw.strip() else ""
            else:
                shutter_raw = st.text_input("셔터 1/N", placeholder="125", key="record_shutter_denominator_text")
                shutter_speed = f"1/{shutter_raw.strip()}" if shutter_raw.strip() else ""
        with focal_col:
            focal = st.text_input("화각", placeholder="35mm", key="record_focal")

        comp = {
            "F값": f_value.strip(),
            "ISO값": iso_value.strip(),
            "셔터스피드": shutter_speed.strip(),
            "화각": focal.strip(),
        }

    submitted = st.button("마커 생성", type="primary", use_container_width=True, key="record_submit")

    if submitted:
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
        elif advanced and st.session_state.record_long_exposure and shutter_raw.strip() and not shutter_raw.strip().isdigit():
            st.error("장노출 셔터스피드는 초 단위 숫자로 입력하세요.")
        elif advanced and not st.session_state.record_long_exposure and shutter_raw.strip() and not shutter_raw.strip().isdigit():
            st.error("셔터스피드 1/N은 숫자로 입력하세요.")
        else:
            add_spot(
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
            )
            st.success("마커를 추가했습니다.")
            st.rerun()


def render_active_detail() -> None:
    active = next((spot for spot in st.session_state.spots if spot["id"] == st.session_state.active_spot_id), None)
    st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
    st.markdown("### 선택 스팟")
    if not active:
        st.markdown('<p class="muted">지도나 목록에서 스팟을 선택하세요.</p>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    color = WEATHER_COLORS.get(active["weather"], "#38bdf8")
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
                <span class="pill" style="border-color:{TIME_COLORS.get(time_meridiem(active.get("time")), "#a78bfa")};">{escape(active.get("time"))}</span>
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
            st.session_state.spots = [spot for spot in st.session_state.spots if spot["id"] != active["id"]]
            st.session_state.active_spot_id = st.session_state.spots[0]["id"] if st.session_state.spots else None
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
    if event_type == "record_panel_out_of_bounds":
        nonce = map_data.get("_pgis_nonce")
        if nonce and nonce == st.session_state.get("last_panel_close_nonce"):
            return
        st.session_state.last_panel_close_nonce = nonce
        store_map_view(map_data)
        st.session_state.right_drawer_open = False
        st.session_state.picking_location = False
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
    spots = filtered_spots()

    render_map(spots)
    inject_layout_vars()
    render_filter_floating(spots)
    render_settings_floating()
    if st.session_state.right_drawer_open:
        with st.container(key="right_drawer_panel"):
            render_record_form()


if __name__ == "__main__":
    main()
