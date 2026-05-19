# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import html
import random
import time
from datetime import datetime, timedelta
from typing import Any

import folium
import streamlit as st
from folium.features import DivIcon
from streamlit_folium import st_folium

try:
    from streamlit_js_eval import get_geolocation
except Exception:  # pragma: no cover - keeps the app usable if optional JS fails.
    get_geolocation = None


st.set_page_config(
    page_title="우리 뭐하지?",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)


CATEGORIES: dict[str, dict[str, Any]] = {
    "pc": {
        "name": "PC/게임",
        "emoji": "🎮",
        "color": "#6366f1",
        "light": "#eef2ff",
        "subcategories": ["PC방", "플스방", "오락실"],
    },
    "sports": {
        "name": "스포츠",
        "emoji": "⚽",
        "color": "#10b981",
        "light": "#ecfdf5",
        "subcategories": ["당구장", "볼링장", "스크린야구", "스크린골프", "탁구장"],
    },
    "music": {
        "name": "음악/기타",
        "emoji": "🎵",
        "color": "#ec4899",
        "light": "#fdf2f8",
        "subcategories": ["코인노래방", "보드게임카페", "만화카페"],
    },
}

DEFAULT_PLACES: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "브로PC방",
        "type": "PC방",
        "category": "pc",
        "lat": 37.5547,
        "lng": 126.9707,
        "price": "1,000원/1h",
        "price_value": 1000,
        "distance": "250m",
        "distance_m": 250,
        "open": "24시간",
        "parking": True,
        "smoking": True,
        "external_food": False,
        "crowd_status": "여유",
        "updated_ago": "10분 전",
        "tips": ["키보드 상태 좋음", "사장님 친절", "콜라 무한리필"],
        "address": "서울역 인근",
        "created_by": "user123",
        "created_at": "2026-05-19T20:26:55",
    },
    {
        "id": 2,
        "name": "프렌즈 당구클럽",
        "type": "당구장",
        "category": "sports",
        "lat": 37.5557,
        "lng": 126.9717,
        "price": "1,500원/10분",
        "price_value": 9000,
        "distance": "450m",
        "distance_m": 450,
        "open": "12:00-02:00",
        "parking": False,
        "smoking": True,
        "external_food": True,
        "crowd_status": "대기 2팀",
        "updated_ago": "5분 전",
        "tips": ["당구대 관리 최상", "주말 대기 많음"],
        "address": "서울역 인근",
        "created_by": "user123",
        "created_at": "2026-05-19T20:26:55",
    },
    {
        "id": 3,
        "name": "노래방 코인",
        "type": "코인노래방",
        "category": "music",
        "lat": 37.5537,
        "lng": 126.9727,
        "price": "1,000원/5곡",
        "price_value": 200,
        "distance": "180m",
        "distance_m": 180,
        "open": "10:00-23:00",
        "parking": False,
        "smoking": False,
        "external_food": True,
        "crowd_status": "여유",
        "updated_ago": "30분 전",
        "tips": ["음질 좋음", "최신곡 업데이트 빠름", "혼자 와도 부담없음"],
        "address": "서울역 인근",
        "created_by": "user123",
        "created_at": "2026-05-19T20:26:55",
    },
    {
        "id": 4,
        "name": "스트라이크 볼링장",
        "type": "볼링장",
        "category": "sports",
        "lat": 37.5520,
        "lng": 126.9690,
        "price": "5,000원/게임",
        "price_value": 5000,
        "distance": "600m",
        "distance_m": 600,
        "open": "09:00-24:00",
        "parking": True,
        "smoking": False,
        "external_food": False,
        "crowd_status": "자리 많음",
        "updated_ago": "1시간 전",
        "tips": ["레인 상태 완벽", "신발 대여 무료", "단체 할인 있음"],
        "address": "서울역 인근",
        "created_by": "user123",
        "created_at": "2026-05-19T20:26:55",
    },
    {
        "id": 5,
        "name": "게임존 오락실",
        "type": "오락실",
        "category": "pc",
        "lat": 37.5565,
        "lng": 126.9695,
        "price": "500원/크레딧",
        "price_value": 500,
        "distance": "320m",
        "distance_m": 320,
        "open": "11:00-22:00",
        "parking": False,
        "smoking": False,
        "external_food": True,
        "crowd_status": "적당",
        "updated_ago": "2시간 전",
        "tips": ["레트로 게임 많음", "격투게임 고수 많음", "주말만 운영"],
        "address": "서울역 인근",
        "created_by": "user123",
        "created_at": "2026-05-19T20:26:55",
    },
]


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
          --primary: #6366f1;
          --secondary: #ec4899;
          --success: #10b981;
          --warning: #fbbf24;
          --ink: #111827;
          --muted: #6b7280;
          --line: #e5e7eb;
        }
        .stApp {
          background: linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
          color: var(--ink);
        }
        .block-container {
          max-width: 100%;
          padding: 1rem 1.35rem 1.5rem;
        }
        [data-testid="stSidebar"] {
          background: #ffffff;
          border-right: 1px solid var(--line);
          box-shadow: 12px 0 30px rgba(15, 23, 42, .08);
        }
        [data-testid="stSidebar"] .block-container {
          padding-top: 1.25rem;
        }
        h1, h2, h3, p {
          letter-spacing: 0;
        }
        .bro-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
          min-height: 64px;
          padding: 0 1.1rem;
          margin-bottom: .85rem;
          border-radius: 8px;
          color: white;
          background: linear-gradient(90deg, #4f46e5 0%, #ec4899 100%);
          box-shadow: 0 12px 28px rgba(79, 70, 229, .24);
        }
        .bro-title {
          display: flex;
          align-items: baseline;
          gap: .75rem;
          flex-wrap: wrap;
        }
        .bro-title strong {
          font-size: 1.5rem;
          line-height: 1.1;
        }
        .bro-title span {
          color: rgba(255,255,255,.82);
          font-size: .92rem;
        }
        .surface-card {
          background: #ffffff;
          border: 1px solid var(--line);
          border-radius: 8px;
          box-shadow: 0 16px 36px rgba(15, 23, 42, .09);
          padding: 1rem;
        }
        .place-card {
          background: #ffffff;
          border: 1px solid var(--line);
          border-radius: 8px;
          box-shadow: 0 20px 42px rgba(15, 23, 42, .12);
          padding: 1.15rem;
          margin-top: .8rem;
        }
        .place-heading {
          display: flex;
          align-items: start;
          justify-content: space-between;
          gap: 1rem;
          margin-bottom: 1rem;
        }
        .place-heading h2 {
          margin: 0 0 .25rem 0;
          font-size: 1.45rem;
        }
        .place-heading p {
          margin: 0;
          color: var(--muted);
        }
        .metric-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: .75rem;
          margin: .85rem 0;
        }
        .metric {
          border-radius: 8px;
          padding: .82rem;
          border: 1px solid rgba(99, 102, 241, .12);
        }
        .metric small {
          color: var(--muted);
          display: block;
          margin-bottom: .2rem;
        }
        .metric strong {
          font-size: 1.18rem;
        }
        .chip-row {
          display: flex;
          gap: .45rem;
          flex-wrap: wrap;
          margin: .7rem 0;
        }
        .chip {
          display: inline-flex;
          align-items: center;
          gap: .25rem;
          border-radius: 999px;
          font-size: .82rem;
          font-weight: 700;
          padding: .32rem .65rem;
          white-space: nowrap;
        }
        .tip-list {
          padding-left: 1.05rem;
          margin: .35rem 0 0;
        }
        .tip-list li {
          margin: .18rem 0;
          color: #4b5563;
          font-size: .92rem;
        }
        .sidebar-card {
          border-radius: 8px;
          border: 1px solid var(--line);
          padding: .85rem;
          margin-bottom: .65rem;
          background: #f9fafb;
        }
        .sidebar-card strong {
          display: block;
          margin-bottom: .2rem;
        }
        .sidebar-card span {
          color: var(--muted);
          font-size: .82rem;
        }
        .mini-result {
          text-align: center;
          padding: 1.15rem;
          border-radius: 8px;
          background: linear-gradient(135deg, #fef3c7 0%, #ffedd5 100%);
          border: 1px solid #fed7aa;
        }
        .mini-result small {
          display: block;
          color: var(--muted);
          margin-bottom: .35rem;
        }
        .mini-result strong {
          display: block;
          color: #ea580c;
          font-size: 1.55rem;
        }
        div[data-testid="stButton"] > button {
          border-radius: 8px;
          font-weight: 700;
        }
        div[data-testid="stMetric"] {
          background: white;
          border: 1px solid var(--line);
          border-radius: 8px;
          padding: .65rem .75rem;
        }
        iframe[title="streamlit_folium.st_folium"] {
          border-radius: 8px;
          border: 1px solid var(--line);
          box-shadow: 0 16px 36px rgba(15, 23, 42, .10);
        }
        @media (max-width: 900px) {
          .bro-header {
            align-items: flex-start;
            flex-direction: column;
            padding: .95rem;
          }
          .metric-grid {
            grid-template-columns: 1fr;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    defaults = {
        "places": copy.deepcopy(DEFAULT_PLACES),
        "active_categories": [],
        "selected_subcategories": {
            cid: list(meta["subcategories"]) for cid, meta in CATEGORIES.items()
        },
        "budget": 50000,
        "distance": 1000,
        "need_parking": False,
        "need_smoking": False,
        "allow_external_food": False,
        "selected_place_id": DEFAULT_PLACES[0]["id"],
        "candidate_places": [],
        "updates": [],
        "reviews": [],
        "favorites": [],
        "game_result": None,
        "show_register": False,
        "location_requested": False,
        "user_location": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def category_label(category_id: str) -> str:
    meta = CATEGORIES[category_id]
    return f"{meta['emoji']} {meta['name']}"


def format_distance(distance_m: int | float) -> str:
    if distance_m >= 1000:
        return f"{distance_m / 1000:.1f}km"
    return f"{int(distance_m)}m"


def clean_expired_updates() -> None:
    now = datetime.now()
    st.session_state.updates = [
        update for update in st.session_state.updates if update["expires_at"] > now
    ]


def relative_time(ts: datetime) -> str:
    seconds = max(0, int((datetime.now() - ts).total_seconds()))
    if seconds < 60:
        return "방금 전"
    if seconds < 3600:
        return f"{seconds // 60}분 전"
    return f"{seconds // 3600}시간 전"


def effective_place(place: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(place)
    for update in st.session_state.updates:
        if update["place_id"] != place["id"]:
            continue
        if update["type"] == "price":
            merged["price"] = update["data"]["price"]
            merged["price_value"] = update["data"]["price_value"]
        elif update["type"] == "crowd":
            merged["crowd_status"] = update["data"]["crowd_status"]
        elif update["type"] == "hours":
            merged["open"] = update["data"]["open"]
        merged["updated_ago"] = relative_time(update["timestamp"])
    return merged


def all_effective_places() -> list[dict[str, Any]]:
    clean_expired_updates()
    return [effective_place(place) for place in st.session_state.places]


def selected_place() -> dict[str, Any] | None:
    for place in all_effective_places():
        if place["id"] == st.session_state.selected_place_id:
            return place
    return None


def filter_places(places: list[dict[str, Any]]) -> list[dict[str, Any]]:
    active_categories = st.session_state.active_categories
    result: list[dict[str, Any]] = []

    for place in places:
        if active_categories and place["category"] not in active_categories:
            continue
        if active_categories:
            selected_types = st.session_state.selected_subcategories.get(place["category"], [])
            if selected_types and place["type"] not in selected_types:
                continue
        if place["price_value"] > st.session_state.budget:
            continue
        if place["distance_m"] > st.session_state.distance:
            continue
        if st.session_state.need_parking and not place["parking"]:
            continue
        if st.session_state.need_smoking and not place["smoking"]:
            continue
        if st.session_state.allow_external_food and not place["external_food"]:
            continue
        result.append(place)

    return result


def toggle_category(category_id: str) -> None:
    active = list(st.session_state.active_categories)
    if category_id in active:
        active.remove(category_id)
    else:
        active.append(category_id)
    st.session_state.active_categories = active


def reset_filters() -> None:
    st.session_state.active_categories = []
    st.session_state.selected_subcategories = {
        cid: list(meta["subcategories"]) for cid, meta in CATEGORIES.items()
    }
    st.session_state.budget = 50000
    st.session_state.distance = 1000
    st.session_state.need_parking = False
    st.session_state.need_smoking = False
    st.session_state.allow_external_food = False


def render_sidebar() -> None:
    with st.sidebar:
        st.subheader("필터 설정")
        st.caption("선택된 카테고리가 없으면 전체 장소를 보여줍니다.")

        st.markdown("##### 카테고리")
        for category_id, meta in CATEGORIES.items():
            selected = category_id in st.session_state.active_categories
            button_type = "primary" if selected else "secondary"
            if st.button(
                category_label(category_id),
                key=f"cat_{category_id}",
                use_container_width=True,
                type=button_type,
            ):
                toggle_category(category_id)
                st.rerun()

            if selected:
                current = st.session_state.selected_subcategories.get(category_id, [])
                chosen = st.multiselect(
                    "세부 카테고리",
                    meta["subcategories"],
                    default=current,
                    key=f"sub_{category_id}",
                    label_visibility="collapsed",
                )
                st.session_state.selected_subcategories[category_id] = chosen

        st.divider()
        st.markdown("##### 1인당 예산")
        st.session_state.budget = st.slider(
            "예산",
            5000,
            100000,
            st.session_state.budget,
            5000,
            format="%d원",
            label_visibility="collapsed",
        )
        st.markdown(
            f"<div style='text-align:right;font-weight:800;color:#6366f1;font-size:1.1rem;'>{st.session_state.budget:,}원 이하</div>",
            unsafe_allow_html=True,
        )

        st.markdown("##### 거리")
        st.session_state.distance = st.slider(
            "거리",
            100,
            5000,
            st.session_state.distance,
            100,
            format="%dm",
            label_visibility="collapsed",
        )
        st.markdown(
            f"<div style='text-align:right;font-weight:800;color:#ec4899;font-size:1.1rem;'>반경 {st.session_state.distance:,}m</div>",
            unsafe_allow_html=True,
        )

        st.divider()
        st.markdown("##### 시설 조건")
        st.session_state.need_parking = st.checkbox("🅿️ 주차 가능", value=st.session_state.need_parking)
        st.session_state.need_smoking = st.checkbox("🚬 흡연실 있음", value=st.session_state.need_smoking)
        st.session_state.allow_external_food = st.checkbox(
            "🍕 음식 반입 가능",
            value=st.session_state.allow_external_food,
        )

        col_apply, col_reset = st.columns(2)
        with col_apply:
            if st.button("필터 적용", use_container_width=True, type="primary"):
                st.toast("필터가 적용됐습니다.")
        with col_reset:
            if st.button("초기화", use_container_width=True):
                reset_filters()
                st.rerun()

        st.divider()
        st.markdown("##### 후보지")
        candidates = valid_candidates()
        if candidates:
            for candidate in candidates:
                st.markdown(
                    f"""
                    <div class="sidebar-card">
                      <strong>{html.escape(candidate)}</strong>
                      <span>결정 미니게임 후보</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.caption("장소 상세에서 후보지를 추가할 수 있습니다.")


def request_location() -> None:
    if get_geolocation is None:
        st.warning("브라우저 위치 기능을 쓰려면 requirements.txt 설치가 필요합니다.")
        return

    location = get_geolocation()
    if not location:
        st.info("브라우저 위치 권한을 허용하면 현재 위치가 지도에 표시됩니다.")
        return

    coords = location.get("coords", {})
    latitude = coords.get("latitude")
    longitude = coords.get("longitude")
    if latitude and longitude:
        st.session_state.user_location = (float(latitude), float(longitude))
        st.success(f"현재 위치: {float(latitude):.5f}, {float(longitude):.5f}")


def render_header() -> None:
    st.markdown(
        """
        <div class="bro-header">
          <div class="bro-title">
            <strong>🎮 우리 뭐하지?</strong>
            <span>동네 놀거리 가성비 가이드</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns([7, 1.15, 1.25, 1.2])
    with col2:
        if st.button("내 위치", use_container_width=True):
            st.session_state.location_requested = True
    with col3:
        if st.button("장소 등록", use_container_width=True, type="primary"):
            st.session_state.show_register = not st.session_state.show_register
    with col4:
        with st.popover("🎲 결정"):
            render_mini_games(in_popover=True)

    if st.session_state.location_requested:
        request_location()


def render_register_form() -> None:
    if not st.session_state.show_register:
        return

    st.markdown('<div class="surface-card">', unsafe_allow_html=True)
    st.subheader("숨은 아지트 등록")

    with st.form("place_register_form", clear_on_submit=True):
        col_a, col_b, col_c = st.columns([1.5, 1, 1])
        with col_a:
            name = st.text_input("장소명", placeholder="예: 브로 플스방")
        with col_b:
            category_name = st.selectbox(
                "카테고리",
                [category_label(cid) for cid in CATEGORIES],
            )
            category_id = list(CATEGORIES.keys())[
                [category_label(cid) for cid in CATEGORIES].index(category_name)
            ]
        with col_c:
            place_type = st.selectbox("세부 유형", CATEGORIES[category_id]["subcategories"])

        col_d, col_e, col_f = st.columns(3)
        with col_d:
            lat = st.number_input("위도", value=37.5547, format="%.6f")
        with col_e:
            lng = st.number_input("경도", value=126.9707, format="%.6f")
        with col_f:
            distance_m = st.number_input("거리(m)", min_value=0, value=300, step=50)

        col_g, col_h, col_i = st.columns(3)
        with col_g:
            price = st.text_input("가격 표시", value="1,000원/1h")
        with col_h:
            price_value = st.number_input("비교용 가격", min_value=0, value=1000, step=100)
        with col_i:
            open_hours = st.text_input("영업시간", value="24시간")

        col_j, col_k, col_l = st.columns(3)
        with col_j:
            parking = st.checkbox("주차", value=False)
        with col_k:
            smoking = st.checkbox("흡연실", value=False)
        with col_l:
            external_food = st.checkbox("음식 반입", value=True)

        crowd_status = st.text_input("혼잡도", value="여유")
        tips_text = st.text_area("유저 꿀팁", placeholder="줄바꿈으로 여러 개 입력")

        submitted = st.form_submit_button("등록하기", type="primary", use_container_width=True)
        if submitted:
            if not name.strip():
                st.error("장소명을 입력해주세요.")
            else:
                next_id = max(place["id"] for place in st.session_state.places) + 1
                st.session_state.places.append(
                    {
                        "id": next_id,
                        "name": name.strip(),
                        "type": place_type,
                        "category": category_id,
                        "lat": float(lat),
                        "lng": float(lng),
                        "price": price.strip() or f"{price_value:,}원",
                        "price_value": int(price_value),
                        "distance": format_distance(distance_m),
                        "distance_m": int(distance_m),
                        "open": open_hours.strip() or "미확인",
                        "parking": parking,
                        "smoking": smoking,
                        "external_food": external_food,
                        "crowd_status": crowd_status.strip() or "미확인",
                        "updated_ago": "방금 전",
                        "tips": [tip.strip() for tip in tips_text.splitlines() if tip.strip()],
                        "address": "사용자 등록 장소",
                        "created_by": "anonymous",
                        "created_at": datetime.now().isoformat(),
                    }
                )
                st.session_state.selected_place_id = next_id
                st.session_state.show_register = False
                st.success("장소가 등록됐습니다.")
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def price_marker_html(place: dict[str, Any]) -> str:
    category = CATEGORIES.get(place["category"], CATEGORIES["pc"])
    price = html.escape(str(place["price"]))
    return f"""
    <div style="
      background:{category['color']};
      color:white;
      padding:6px 12px;
      border-radius:20px;
      font-weight:800;
      font-size:13px;
      white-space:nowrap;
      box-shadow:0 2px 8px rgba(0,0,0,.30);
      border:2px solid white;
      transform:translate(-50%, -50%);
    ">{price}</div>
    """


def build_map(places: list[dict[str, Any]]) -> folium.Map:
    if st.session_state.user_location:
        center = st.session_state.user_location
        zoom = 15
    elif places:
        center = (places[0]["lat"], places[0]["lng"])
        zoom = 15
    else:
        center = (37.5547, 126.9707)
        zoom = 14

    fmap = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    if st.session_state.user_location:
        lat, lng = st.session_state.user_location
        folium.Circle(
            location=(lat, lng),
            radius=st.session_state.distance,
            color="#6366f1",
            fill=True,
            fill_color="#6366f1",
            fill_opacity=0.08,
            weight=2,
        ).add_to(fmap)
        folium.CircleMarker(
            location=(lat, lng),
            radius=8,
            color="#111827",
            fill=True,
            fill_color="#60a5fa",
            fill_opacity=1,
            popup="현재 위치",
        ).add_to(fmap)

    for place in places:
        popup = f"""
        <div style="font-family:Arial,sans-serif;font-size:13px;min-width:150px;">
          <strong style="font-size:15px;">{html.escape(place['name'])}</strong><br>
          <span style="color:#6b7280;">{html.escape(place['type'])}</span><br>
          <span>{html.escape(place['price'])}</span>
        </div>
        """
        folium.Marker(
            location=(place["lat"], place["lng"]),
            popup=folium.Popup(popup, max_width=240),
            tooltip=f"{place['name']} · {place['type']}",
            icon=DivIcon(
                icon_size=(90, 32),
                icon_anchor=(45, 16),
                html=price_marker_html(place),
            ),
        ).add_to(fmap)

    return fmap


def place_from_click(click: dict[str, Any] | None, places: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not click:
        return None

    lat = click.get("lat")
    lng = click.get("lng")
    if lat is None or lng is None:
        return None

    best_place = None
    best_distance = float("inf")
    for place in places:
        delta = abs(place["lat"] - lat) + abs(place["lng"] - lng)
        if delta < best_distance:
            best_distance = delta
            best_place = place

    if best_distance <= 0.0006:
        return best_place
    return None


def render_map(places: list[dict[str, Any]]) -> None:
    st.markdown("##### 가격 지도")
    map_data = st_folium(
        build_map(places),
        height=640,
        use_container_width=True,
        returned_objects=["last_object_clicked"],
        key="bromap",
    )
    clicked_place = place_from_click(map_data.get("last_object_clicked"), places)
    if clicked_place:
        st.session_state.selected_place_id = clicked_place["id"]

    count_cols = st.columns(4)
    count_cols[0].metric("표시 장소", f"{len(places)}곳")
    count_cols[1].metric("예산", f"{st.session_state.budget:,}원")
    count_cols[2].metric("거리", f"{st.session_state.distance:,}m")
    count_cols[3].metric("후보지", f"{len(valid_candidates())}곳")


def feature_chips(place: dict[str, Any]) -> str:
    chips = []
    if place["parking"]:
        chips.append('<span class="chip" style="background:#dcfce7;color:#15803d;">🅿️ 주차</span>')
    if place["smoking"]:
        chips.append('<span class="chip" style="background:#ffedd5;color:#c2410c;">🚬 흡연실</span>')
    if place["external_food"]:
        chips.append('<span class="chip" style="background:#dbeafe;color:#1d4ed8;">🍕 음식 반입</span>')
    if not chips:
        chips.append('<span class="chip" style="background:#f3f4f6;color:#4b5563;">시설 정보 없음</span>')
    return "".join(chips)


def render_place_card(place: dict[str, Any]) -> None:
    category = CATEGORIES[place["category"]]
    favorite = "⭐" if place["id"] in st.session_state.favorites else "☆"
    tips_html = "".join(f"<li>{html.escape(tip)}</li>" for tip in place["tips"])

    st.markdown(
        f"""
        <div class="place-card">
          <div class="place-heading">
            <div>
              <h2>{category['emoji']} {html.escape(place['name'])}</h2>
              <p>{html.escape(place['type'])} · {html.escape(place['distance'])}</p>
            </div>
            <div style="font-size:1.35rem;">{favorite}</div>
          </div>
          <div class="metric-grid">
            <div class="metric" style="background:{category['light']};">
              <small>가격</small>
              <strong style="color:{category['color']};">{html.escape(place['price'])}</strong>
            </div>
            <div class="metric" style="background:#fdf2f8;">
              <small>혼잡도</small>
              <strong style="color:#ec4899;">{html.escape(place['crowd_status'])}</strong>
              <small>{html.escape(place['updated_ago'])}</small>
            </div>
          </div>
          <p style="margin:.7rem 0 .25rem;color:#6b7280;font-size:.9rem;">영업시간</p>
          <p style="margin:0;font-weight:800;">{html.escape(place['open'])}</p>
          <div class="chip-row">{feature_chips(place)}</div>
          <p style="margin:.8rem 0 .25rem;font-weight:800;color:#374151;">💡 유저 꿀팁</p>
          <ul class="tip-list">{tips_html or '<li>아직 등록된 꿀팁이 없습니다.</li>'}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_a, col_b, col_c = st.columns([2, 1, 1])
    with col_a:
        if st.button("후보지에 추가", use_container_width=True, type="primary"):
            add_candidate(place["name"])
    with col_b:
        if st.button("📍", use_container_width=True, help="좌표 보기"):
            st.info(f"{place['lat']:.5f}, {place['lng']:.5f}")
    with col_c:
        if st.button(favorite, use_container_width=True, help="즐겨찾기"):
            toggle_favorite(place["id"])
            st.rerun()


def add_candidate(name: str) -> None:
    clean_name = name.strip()
    if clean_name and clean_name not in st.session_state.candidate_places:
        st.session_state.candidate_places.append(clean_name)
        st.toast("후보지에 추가했습니다.")


def toggle_favorite(place_id: int) -> None:
    favorites = list(st.session_state.favorites)
    if place_id in favorites:
        favorites.remove(place_id)
    else:
        favorites.append(place_id)
    st.session_state.favorites = favorites


def render_updates(place: dict[str, Any]) -> None:
    st.markdown("##### 실시간 업데이트")
    with st.form(f"update_form_{place['id']}", clear_on_submit=False):
        update_type = st.radio(
            "업데이트 유형",
            ["가격", "혼잡도", "영업시간"],
            horizontal=True,
            label_visibility="collapsed",
        )

        payload: dict[str, Any] = {}
        if update_type == "가격":
            col_a, col_b = st.columns([2, 1])
            with col_a:
                payload["price"] = st.text_input("가격 표시", value=place["price"])
            with col_b:
                payload["price_value"] = st.number_input(
                    "비교용 가격",
                    min_value=0,
                    value=int(place["price_value"]),
                    step=100,
                )
            update_key = "price"
        elif update_type == "혼잡도":
            payload["crowd_status"] = st.text_input("혼잡도", value=place["crowd_status"])
            update_key = "crowd"
        else:
            payload["open"] = st.text_input("영업시간", value=place["open"])
            update_key = "hours"

        if st.form_submit_button("제보하기", type="primary", use_container_width=True):
            st.session_state.updates.append(
                {
                    "id": len(st.session_state.updates) + 1,
                    "place_id": place["id"],
                    "type": update_key,
                    "data": payload,
                    "user_id": "anonymous",
                    "timestamp": datetime.now(),
                    "expires_at": datetime.now() + timedelta(hours=2),
                }
            )
            st.success("제보가 반영됐습니다. 2시간 뒤 자동 만료됩니다.")
            st.rerun()


def render_reviews(place: dict[str, Any]) -> None:
    st.markdown("##### 한줄평 & 꿀팁")
    place_reviews = [
        review for review in st.session_state.reviews if review["place_id"] == place["id"]
    ]

    with st.form(f"review_form_{place['id']}", clear_on_submit=True):
        review = st.text_area("한줄평", placeholder="날것의 리얼 리뷰를 남겨주세요.")
        if st.form_submit_button("등록", type="primary", use_container_width=True):
            if review.strip():
                st.session_state.reviews.append(
                    {
                        "id": len(st.session_state.reviews) + 1,
                        "place_id": place["id"],
                        "content": review.strip(),
                        "user_id": "anonymous",
                        "likes": 0,
                        "created_at": datetime.now(),
                    }
                )
                st.success("한줄평이 등록됐습니다.")
                st.rerun()

    if place_reviews:
        for review in reversed(place_reviews):
            st.markdown(
                f"""
                <div class="sidebar-card">
                  <strong>{html.escape(review['content'])}</strong>
                  <span>{relative_time(review['created_at'])} · 좋아요 {review['likes']}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.caption("아직 등록된 한줄평이 없습니다.")


def render_detail_panel() -> None:
    place = selected_place()
    if not place:
        st.info("지도에서 장소를 선택해주세요.")
        return

    render_place_card(place)
    tab_update, tab_review = st.tabs(["실시간 제보", "리뷰"])
    with tab_update:
        render_updates(place)
    with tab_review:
        render_reviews(place)


def valid_candidates() -> list[str]:
    return [candidate.strip() for candidate in st.session_state.candidate_places if candidate.strip()]


def run_roulette(candidates: list[str]) -> str:
    placeholder = st.empty()
    result = candidates[0]
    for _ in range(22):
        result = random.choice(candidates)
        placeholder.markdown(
            f"""
            <div class="mini-result">
              <small>결정 중...</small>
              <strong>🎰 {html.escape(result)}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
        time.sleep(0.05)
    return result


def run_ladder(candidates: list[str]) -> str:
    placeholder = st.empty()
    shuffled = candidates[:]
    random.shuffle(shuffled)
    for idx, name in enumerate(shuffled, 1):
        placeholder.markdown(
            f"""
            <div class="mini-result">
              <small>사다리 {idx}번 라인</small>
              <strong>🪜 {html.escape(name)}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
        time.sleep(0.35)
    return shuffled[0]


def render_mini_games(in_popover: bool = False) -> None:
    heading = "결정 미니게임" if not in_popover else "🎲 결정 미니게임"
    st.markdown(f"##### {heading}")

    candidates = valid_candidates()
    for idx, candidate in enumerate(list(st.session_state.candidate_places)):
        col_name, col_remove = st.columns([4, 1])
        with col_name:
            st.session_state.candidate_places[idx] = st.text_input(
                f"후보지 {idx + 1}",
                value=candidate,
                key=f"candidate_{'pop' if in_popover else 'side'}_{idx}",
                label_visibility="collapsed",
            )
        with col_remove:
            if st.button("✕", key=f"remove_{'pop' if in_popover else 'side'}_{idx}"):
                st.session_state.candidate_places.pop(idx)
                st.rerun()

    col_input, col_add = st.columns([3, 1])
    with col_input:
        new_candidate = st.text_input(
            "후보지 추가",
            placeholder="후보지 이름",
            key=f"new_candidate_{'pop' if in_popover else 'side'}",
            label_visibility="collapsed",
        )
    with col_add:
        if st.button("+", key=f"add_candidate_{'pop' if in_popover else 'side'}", use_container_width=True):
            add_candidate(new_candidate)
            st.rerun()

    game = st.radio(
        "방식",
        ["룰렛", "사다리"],
        horizontal=True,
        key=f"game_type_{'pop' if in_popover else 'side'}",
        label_visibility="collapsed",
    )

    if st.session_state.game_result:
        st.markdown(
            f"""
            <div class="mini-result">
              <small>결과</small>
              <strong>🎉 {html.escape(st.session_state.game_result)}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

    button_label = "🎰 룰렛 시작!" if game == "룰렛" else "🪜 사다리 타기!"
    if st.button(button_label, type="primary", use_container_width=True, key=f"run_{'pop' if in_popover else 'side'}"):
        candidates = valid_candidates()
        if len(candidates) < 2:
            st.warning("후보지를 2개 이상 넣어주세요.")
        else:
            st.session_state.game_result = (
                run_roulette(candidates) if game == "룰렛" else run_ladder(candidates)
            )
            st.rerun()

    if candidates:
        st.code(" · ".join(candidates), language=None)


def main() -> None:
    inject_css()
    init_state()

    render_sidebar()
    render_header()
    render_register_form()

    places = all_effective_places()
    filtered_places = filter_places(places)

    if filtered_places and st.session_state.selected_place_id not in {
        place["id"] for place in filtered_places
    }:
        st.session_state.selected_place_id = filtered_places[0]["id"]

    map_col, detail_col = st.columns([2.35, 1], gap="large")
    with map_col:
        if filtered_places:
            render_map(filtered_places)
        else:
            st.warning("조건에 맞는 장소가 없습니다.")
    with detail_col:
        render_detail_panel()


if __name__ == "__main__":
    main()
