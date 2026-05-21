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
from folium.features import DivIcon
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
        }

        html, body, [data-testid="stAppViewContainer"], .stApp {
            background: #060811;
            color: var(--glass-text);
        }

        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            background:
                linear-gradient(115deg, transparent 0 12%, rgba(34, 211, 238, 0.12) 12% 13%, transparent 13% 31%, rgba(251, 113, 133, 0.11) 31% 32%, transparent 32% 54%, rgba(245, 158, 11, 0.10) 54% 55%, transparent 55%),
                linear-gradient(42deg, rgba(52, 211, 153, 0.08) 0 11%, transparent 11% 28%, rgba(167, 139, 250, 0.10) 28% 29%, transparent 29% 61%, rgba(56, 189, 248, 0.08) 61% 62%, transparent 62%),
                #060811;
            opacity: 0.95;
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
            background: rgba(6, 8, 17, 0.66);
            backdrop-filter: blur(18px);
        }

        [data-testid="stSidebar"] {
            background: rgba(5, 8, 15, 0.90);
            border-right: 1px solid rgba(226, 232, 240, 0.10);
        }

        .block-container {
            padding-top: 1.8rem;
            padding-bottom: 2rem;
            max-width: 1480px;
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
            border: 1px solid rgba(226, 232, 240, 0.14);
            background: var(--glass-bg);
            backdrop-filter: blur(20px);
            border-radius: 8px;
            box-shadow: 0 16px 40px rgba(0, 0, 0, 0.24);
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
            border-radius: 999px;
            border: 1px solid rgba(226, 232, 240, 0.16);
            color: #e2e8f0;
            background: rgba(15, 23, 42, 0.76);
            font-size: 0.78rem;
        }

        .muted {
            color: #94a3b8;
            font-size: 0.88rem;
            line-height: 1.6;
        }

        .map-wrap {
            border: 1px solid rgba(226, 232, 240, 0.16);
            background: rgba(2, 6, 23, 0.82);
            border-radius: 8px;
            padding: 0.55rem;
            overflow: hidden;
        }

        .map-wrap iframe {
            border-radius: 6px;
        }

        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stBaseButton-secondary"],
        [data-testid="stBaseButton-primary"] {
            border-radius: 8px;
            border: 1px solid rgba(226, 232, 240, 0.18);
            background: rgba(15, 23, 42, 0.78);
            color: #f8fafc;
            min-height: 42px;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            border-color: rgba(34, 211, 238, 0.7);
            color: #ffffff;
        }

        [data-testid="stBaseButton-primary"] {
            background: linear-gradient(90deg, rgba(34, 211, 238, 0.92), rgba(251, 113, 133, 0.88));
            color: #06111e;
            font-weight: 850;
        }

        input, textarea, [data-baseweb="select"] > div {
            border-radius: 8px !important;
        }

        div[data-testid="stFileUploaderDropzone"] {
            border-radius: 8px;
            border-color: rgba(34, 211, 238, 0.36);
            background: rgba(15, 23, 42, 0.55);
        }

        .leaflet-popup-content-wrapper,
        .leaflet-popup-tip {
            background: rgba(8, 13, 24, 0.96);
            color: #f8fafc;
            border: 1px solid rgba(226, 232, 240, 0.16);
            box-shadow: 0 18px 42px rgba(0, 0, 0, 0.44);
        }

        .leaflet-popup-content {
            margin: 12px;
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


def ensure_state() -> None:
    defaults = {
        "spots": [spot.copy() for spot in SAMPLE_SPOTS],
        "selected_point": SEOUL_CENTER,
        "active_spot_id": 1,
        "weather_filter": WEATHER_OPTIONS.copy(),
        "time_filter": TIME_OPTIONS.copy(),
        "search_query": "",
        "map_zoom": 12,
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


def destination_point(lat: float, lng: float, bearing: float, distance_m: float = 260) -> tuple[float, float]:
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


def marker_icon(spot: dict[str, Any]) -> DivIcon:
    color = WEATHER_COLORS.get(spot["weather"], "#38bdf8")
    direction = int(spot["direction"])
    marker_html = f"""
    <div style="
        width: 34px;
        height: 34px;
        position: relative;
        transform: rotate({direction}deg);
        border-radius: 50%;
        border: 1px solid rgba(255, 255, 255, 0.78);
        background: radial-gradient(circle at 50% 58%, rgba(8, 13, 24, 0.92), rgba(8, 13, 24, 0.42));
        box-shadow: 0 0 22px {color}, 0 0 0 3px rgba(255, 255, 255, 0.08);
    ">
        <div style="
            position: absolute;
            left: 11px;
            top: 3px;
            width: 0;
            height: 0;
            border-left: 6px solid transparent;
            border-right: 6px solid transparent;
            border-bottom: 15px solid {color};
            filter: drop-shadow(0 0 5px {color});
        "></div>
        <div style="
            position: absolute;
            left: 14px;
            top: 18px;
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #ffffff;
        "></div>
    </div>
    """
    return DivIcon(html=marker_html, icon_size=(34, 34), icon_anchor=(17, 17), class_name="glass-marker")


def popup_html(spot: dict[str, Any]) -> str:
    color = WEATHER_COLORS.get(spot["weather"], "#38bdf8")
    img = data_uri(spot.get("photo_bytes"), spot.get("photo_mime"))
    image_html = ""
    if img:
        image_html = (
            f'<img src="{img}" style="width:100%;max-height:150px;object-fit:cover;'
            'border-radius:8px;margin-bottom:10px;border:1px solid rgba(226,232,240,0.18);" />'
        )
    return f"""
    <div style="width:260px;font-family:Inter,Arial,sans-serif;color:#f8fafc;">
        {image_html}
        <div style="font-size:15px;font-weight:800;margin-bottom:6px;">{escape(spot["title"])}</div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px;">
            <span style="border:1px solid rgba(226,232,240,.18);border-radius:999px;padding:3px 8px;background:rgba(15,23,42,.8);">{escape(spot["weather"])}</span>
            <span style="border:1px solid rgba(226,232,240,.18);border-radius:999px;padding:3px 8px;background:rgba(15,23,42,.8);">{escape(spot["time_band"])}</span>
            <span style="border:1px solid {color};border-radius:999px;padding:3px 8px;background:rgba(15,23,42,.8);">{int(spot["direction"])}° {compass_label(spot["direction"])}</span>
        </div>
        <div style="font-size:12px;line-height:1.5;color:#cbd5e1;">{escape(spot.get("memo"))}</div>
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
    )
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr="&copy; OpenStreetMap contributors &copy; CARTO",
        name="Dark Matter",
        control=False,
    ).add_to(fmap)

    lat, lng = st.session_state.selected_point
    folium.CircleMarker(
        location=(lat, lng),
        radius=8,
        color="#22d3ee",
        fill=True,
        fill_color="#22d3ee",
        fill_opacity=0.82,
        weight=2,
        tooltip="선택 지점",
    ).add_to(fmap)

    for spot in spots:
        color = WEATHER_COLORS.get(spot["weather"], "#38bdf8")
        end_lat, end_lng = destination_point(spot["lat"], spot["lng"], spot["direction"])
        folium.PolyLine(
            locations=[(spot["lat"], spot["lng"]), (end_lat, end_lng)],
            color=color,
            weight=3,
            opacity=0.78,
            dash_array="6, 8",
        ).add_to(fmap)
        folium.CircleMarker(
            location=(spot["lat"], spot["lng"]),
            radius=12,
            color=color,
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.18,
        ).add_to(fmap)
        folium.Marker(
            location=(spot["lat"], spot["lng"]),
            icon=marker_icon(spot),
            tooltip=f"{spot['id']} · {spot['title']}",
            popup=folium.Popup(popup_html(spot), max_width=310),
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
        border-radius: 8px;
        background: rgba(8, 13, 24, 0.86);
        border: 1px solid rgba(226, 232, 240, 0.18);
        color: #f8fafc;
        font-size: 12px;
        box-shadow: 0 14px 34px rgba(0,0,0,.36);
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

    center = map_data.get("center")
    if center and "lat" in center and "lng" in center:
        st.session_state.map_zoom = map_data.get("zoom", st.session_state.map_zoom)

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
        height=675,
        use_container_width=True,
        returned_objects=["last_clicked", "last_object_clicked_tooltip", "center", "zoom"],
        key="photo_spot_map",
    )
    st.markdown("</div>", unsafe_allow_html=True)
    handle_map_return(map_data)


def main() -> None:
    inject_css()
    ensure_state()
    spots = filtered_spots()
    render_sidebar(spots)
    render_header(spots)

    map_col, tool_col = st.columns([1.72, 1], gap="large")
    with map_col:
        render_map(spots)
    with tool_col:
        render_form()
        render_active_detail()


if __name__ == "__main__":
    main()
