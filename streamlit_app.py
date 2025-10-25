import streamlit as st
from openai import OpenAI
import requests

# ---------------------------
# 날씨 유틸 함수
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
    # 참고: https://open-meteo.com/en/docs
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
# 페이지/사이드바 구성
# ---------------------------
st.set_page_config(page_title="Chatbot", page_icon="💬", layout="centered")

with st.sidebar:
    st.header("🌍 위치 설정")
    city_input = st.text_input("도시 이름", value="서울", help="예: 서울, Busan, Tokyo, New York")
    st.caption("도시를 바꾸면 제목 아이콘이 현재 날씨에 맞게 변합니다.")

# 위치 → 날씨 조회
icon = "💬"  # 기본 아이콘(조회 실패 대비)
subtitle = ""
geo = geocode_city(city_input.strip()) if city_input.strip() else None
if geo:
    wx = fetch_current_weather(geo["lat"], geo["lon"])
    if wx:
        icon = weather_icon(wx["weather_code"], wx["is_day"])
        loc_label = f'{geo["name"]}, {geo["country"]}'
        temp = wx.get("temperature_2m")
        if temp is not None:
            subtitle = f"({loc_label} · 현재 {temp:.1f}°C)"
        else:
            subtitle = f"({loc_label})"

# ---------------------------
# 제목 + 설명 (날씨 아이콘 반영)
# ---------------------------
st.title(f"{icon} Chatbot")
st.write(
    "이 앱은 OpenAI의 GPT 모델을 사용한 간단한 챗봇입니다. "
    "사용하려면 OpenAI API 키가 필요합니다. "
    "키는 [여기](https://platform.openai.com/account/api-keys)에서 발급받을 수 있습니다. "
    "앱 만드는 방법은 [튜토리얼](https://docs.streamlit.io/develop/tutorials/llms/build-conversational-apps)을 참고하세요. "
    + (f"\n\n**오늘의 날씨** {subtitle}" if subtitle else "")
)

# ---------------------------
# OpenAI 키 입력 및 채팅 본문
# ---------------------------
openai_api_key = st.text_input("OpenAI API Key", type="password")
if not openai_api_key:
    st.info("계속하려면 OpenAI API 키를 입력해 주세요.", icon="🗝️")
else:
    # OpenAI 클라이언트 생성
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
            model="gpt-3.5-turbo",  # 필요시 최신 모델명으로 교체 가능
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
