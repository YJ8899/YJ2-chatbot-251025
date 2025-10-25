import streamlit as st
from openai import OpenAI
import requests

# ---------------------------
# 유틸: 지오코딩/날씨/아이콘
# ---------------------------
def geocode_city(name: str):
    """Open-Meteo 지오코딩 API로 도시명을 위/경도로 변환"""
    try:
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {"name": name, "count": 1, "language": "ko", "format": "json"}
        r = requests.get(url, params=params, timeout=7)
        r.raise_for_status()
        data = r.json()
        if data.get("results"):
            res = data["results"][0]
            return {
                "name": res.get("name"),
                "country": res.get("country"),
                "lat": res["latitude"],
                "lon": res["longitude"],
            }
    except Exception:
        pass
    return None

def fetch_current_weather(lat: float, lon: float):
    """Open-Meteo 현재 날씨 조회(날씨코드, 주/야, 기온)"""
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code,is_day",
            "timezone": "auto",
        }
        r = requests.get(url, params=params, timeout=7)
        r.raise_for_status()
        cur = r.json().get("current", {})
        return {
            "weather_code": cur.get("weather_code"),
            "is_day": cur.get("is_day"),  # 1 = day, 0 = night
            "temperature_2m": cur.get("temperature_2m"),
        }
    except Exception:
        return None

def weather_icon(code: int | None, is_day: int | None):
    """Open-Meteo WMO weather codes → 아이콘 맵핑"""
    if code is None:
        return "🌐"  # 알 수 없음
    day = (is_day == 1)
    if code == 0:  # Clear
        return "☀️" if day else "🌙"
    if code in (1, 2):  # Mainly clear, partly cloudy
        return "🌤️" if day else "🌙"
    if code == 3:  # Overcast
        return "☁️"
    if code in (45, 48):  # Fog
        return "🌫️"
    if code in (51, 53, 55, 61, 63, 65, 80, 81, 82):  # Drizzle/Rain
        return "🌧️"
    if code in (56, 57, 66, 67):  # Freezing drizzle/rain
        return "🌧️"
    if code in (71, 73, 75, 77, 85, 86):  # Snow
        return "❄️"
    if code in (95, 96, 99):  # Thunderstorm
        return "⛈️"
    return "🌦️"

# ---------------------------
# 유틸: IP 기반 위치 탐지 (공인 IP 포함)
# ---------------------------
@st.cache_data(show_spinner=False, ttl=60 * 30)
def detect_location_by_ip():
    """
    클라이언트 IP 기반 대략적인 위치 탐지 + 공인 IP/통신사 정보.
    배포 구조에 따라 서버 IP로 감지될 수 있음. 실패 시 None 반환.
    """
    # 1차: ipapi.co (빠르고 간단)
    try:
        r = requests.get("https://ipapi.co/json", timeout=6)
        if r.ok:
            j = r.json()
            city = j.get("city")
            country = j.get("country_name")
            lat = j.get("latitude")
            lon = j.get("longitude")
            ip = j.get("ip")
            org = j.get("org") or j.get("asn")
            if city and country and lat is not None and lon is not None:
                return {
                    "name": city,
                    "country": country,
                    "lat": float(lat),
                    "lon": float(lon),
                    "ip": ip,
                    "org": org,
                }
    except Exception:
        pass
    # 2차: ipwho.is (백업)
    try:
        r = requests.get("https://ipwho.is/", timeout=6)
        if r.ok:
            j = r.json()
            if j.get("success"):
                city = j.get("city")
                country = j.get("country")
                lat = j.get("latitude")
                lon = j.get("longitude")
                ip = j.get("ip")
                org = j.get("connection", {}).get("isp")
                if city and country and lat is not None and lon is not None:
                    return {
                        "name": city,
                        "country": country,
                        "lat": float(lat),
                        "lon": float(lon),
                        "ip": ip,
                        "org": org,
                    }
    except Exception:
        pass
    return None

# ---------------------------
# 페이지 설정
# ---------------------------
st.set_page_config(page_title="Chatbot for YJ", page_icon="💬", layout="centered")

# ---------------------------
# 상단: 위치(공인 IP 표시) + 위치 입력 + API 키 입력
# ---------------------------
top = st.container()
with top:
    c1, c2 = st.columns([3, 2])

    with c1:
        st.caption("현재 위치(추정)")
        # 최초/새로고침 시 IP 기반 위치 탐지
        refresh_loc = st.button("위치 새로고침", help="IP 기준 위치 재탐지")
        if "geo" not in st.session_state or refresh_loc:
            st.session_state.geo = detect_location_by_ip()

        # 추정 위치 표시 + 공인 IP
        if st.session_state.get("geo"):
            geo = st.session_state["geo"]
            line1 = f"**{geo['name']}, {geo['country']}**"
            ip = geo.get("ip")
            org = geo.get("org")
            if ip:
                line1 += f" &nbsp; · &nbsp; 공인 IP: `{ip}`"
            if org:
                line1 += f" &nbsp; · &nbsp; 통신사: {org}"
            st.markdown(line1, unsafe_allow_html=True)
        else:
            # 기본값(서울)로 세팅
            st.session_state.geo = {
                "name": "서울",
                "country": "대한민국",
                "lat": 37.5665,
                "lon": 126.9780,
                "ip": None,
                "org": None,
            }
            st.markdown("**서울, 대한민국** *(기본값)*")

        # 위치 직접 입력 → 적용
        manual_loc = st.text_input(
            "위치 직접 입력 (예: 서울, Busan, Tokyo, New York)",
            value=st.session_state.geo.get("name", "서울"),
        )
        apply_manual = st.button("위치 적용")
        if apply_manual and manual_loc.strip():
            g = geocode_city(manual_loc.strip())
            if g:
                # 기존 IP/통신사 정보는 유지
                st.session_state.geo.update(
                    {"name": g["name"], "country": g["country"], "lat": g["lat"], "lon": g["lon"]}
                )
                st.success(f"위치를 '{g['name']}, {g['country']}'(으)로 적용했어요.")
            else:
                st.warning("위치를 찾지 못했습니다. 철자나 도시명을 다시 확인해 주세요.")

    with c2:
        st.caption("OpenAI API Key")
        openai_api_key = st.text_input("🔑 API 키 입력", type="password", label_visibility="collapsed")
        if not openai_api_key:
            st.info("OpenAI API 키를 상단 입력란에 입력해 주세요.", icon="🗝️")

# ---------------------------
# 위치 → 날씨 아이콘 계산
# ---------------------------
geo = st.session_state.get("geo")
icon = "💬"
if geo:
    wx = fetch_current_weather(geo["lat"], geo["lon"])
    if wx:
        icon = weather_icon(wx["weather_code"], wx["is_day"])

# ---------------------------
# 제목 (설명 문구 없이 제목만)
# ---------------------------
st.title(f"{icon} Chatbot for YJ")

# ---------------------------
# API 키 확인
# ---------------------------
if not openai_api_key:
    st.stop()

# ---------------------------
# OpenAI 클라이언트 생성 및 채팅 본문
# ---------------------------
client = OpenAI(api_key=openai_api_key)

# 세션 상태로 대화 이력 유지
if "messages" not in st.session_state:
    st.session_state.messages = []

# 기존 대화 출력
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 채팅 입력
if prompt := st.chat_input("무엇이 궁금하세요?"):
    # 사용자 메시지 저장/표시
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # OpenAI 응답 스트리밍
    stream = client.chat.completions.create(
        model="gpt-3.5-turbo",  # 필요시 최신 모델명으로 교체 가능 (예: "gpt-4o-mini")
        messages=[
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages
        ],
        stream=True,
    )

    # 스트리밍 출력 및 세션 저장
    with st.chat_message("assistant"):
        response = st.write_stream(stream)
    st.session_state.messages.append({"role": "assistant", "content": response})
