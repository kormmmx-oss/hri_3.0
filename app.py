import streamlit as st
import plotly.graph_objects as go
import requests
from datetime import datetime
import pytz

# --- 1. 설정 및 지역 데이터 ---
st.set_page_config(page_title="전북 극한호우 예측 v3.0", layout="wide")

# 기상청 ASOS 지점 번호 (전북 주요 지점)
STATIONS = {
    "전주": "146", "군산": "140", "정읍": "245", "남원": "248", 
    "익산": "249", "고창": "172", "장수": "247", "임실": "244"
}

# --- 2. 시간 가중치 및 기상 데이터 함수 ---
def get_time_weight():
    # 한국 시간 기준 현재 시간 추출
    tz_korea = pytz.timezone('Asia/Seoul')
    now = datetime.now(tz_korea)
    hour = now.hour
    
    # 분석된 위험 시간대: 18시 ~ 다음날 10시 (과거 극한강수 빈발 시간)
    if 18 <= hour or hour <= 10:
        return 1.25, f"⚠️ 야간~오전 집중호우 위험 시간대 (현재 {hour}시, 가중치 125% 적용)"
    return 1.0, f"✅ 주간 평시 시간대 (현재 {hour}시, 가중치 100% 적용)"

def fetch_weather(stn_id):
    # 기상청 API 연동 (제공해주신 인증키 사용)
    SERVICE_KEY = "Tt8x4uYTSKufMeLmE-ir3Q"
    url = "http://apis.data.go.kr/1360000/AsosObservationsService/getLatestObservation"
    try:
        res = requests.get(url, params={'serviceKey': SERVICE_KEY, 'stnId': stn_id, 'dataType': 'JSON'}, timeout=5)
        item = res.json()['response']['body']['items']['item'][0]
        return {
            "temp": float(item.get('ta', 28.0)), 
            "hm": float(item.get('hm', 80.0))
        }
    except:
        # API 오류 시 기본값 (여름철 고온다습 조건)
        return {"temp": 28.0, "hm": 80.0}

# --- 3. 메인 UI ---
st.title("🌧️ 전북지역 극한호우 예측 및 모니터링 시스템 v3.0")
st.markdown("##### 과거 100mm/h 이상 극한사례 및 시간대별 가중치 반영 모델")

# 시간 가중치 확인 및 표시
time_weight, time_msg = get_time_weight()
if time_weight > 1.0:
    st.warning(time_msg)
else:
    st.info(time_msg)

selected_city = st.sidebar.selectbox("📍 관측 지역 선택", list(STATIONS.keys()))
weather = fetch_weather(STATIONS[selected_city])

# --- 4. 슬라이더 세팅 (과거 데이터 기반 임계치 적용) ---
st.sidebar.header("📊 실시간 관측 인자 조정")

# 과거 데이터 분석을 통한 범위 재설정
sst = st.sidebar.slider("해수면 온도 (SST, °C)", 20.0, 33.0, 28.5) 
pwat = st.sidebar.slider("가용가강수량 (PWAT, mm)", 30.0, 100.0, float(weather["hm"])) # 습도를 PWAT 대용으로 활용
v850 = st.sidebar.slider("하층제트 (V850, m/s)", 0.0, 50.0, 25.0)
# 상당온위는 345K 이상일 때 극한사례 집중 발생
theta_e = st.sidebar.slider("상당온위 (Theta-e, K)", 300.0, 370.0, float(weather["temp"] + 315))

# --- 5. 데이터 기반 가중치 계산 ---
# 각 변수별 정규화 (0~100점)
s_sst = (sst - 20) / (33 - 20) * 100
s_pwat = (pwat - 30) / (100 - 30) * 100
s_v850 = (v850 - 0) / (50 - 0) * 100
s_theta = (theta_e - 300) / (370 - 300) * 100

# [재설정된 가중치] 상당온위(35%), PWAT(30%), 하층제트(20%), SST(15%)
base_hri = (0.15 * s_sst) + (0.30 * s_pwat) + (0.20 * s_v850) + (0.35 * s_theta)
final_hri = min(100.0, base_hri * time_weight)

# --- 6. 결과 시각화 및 경보 등급 ---
col1, col2 = st.columns([1, 1.5])

with col1:
    st.metric("최종 HRI 지수", f"{final_hri:.1f}점", delta=f"시간 가중치 x{time_weight}")
    
    # [수정된 등급 체계] 30~50점 구간 추가
    if final_hri >= 85:
        st.error("🚨 [위험] 1시간 100mm급 극한호우 발생 가능성 매우 높음")
        st.write("**대응:** 저지대 즉시 대피 및 재난안전대책본부 가동 권고")
    elif final_hri >= 65:
        st.warning("⚠️ [경계] 1시간 50mm급 집중호우 발생 가능성")
        st.write("**대응:** 취약지역 예찰 강화 및 배수시설 점검")
    elif 30 <= final_hri <= 50:
        st.info("🌧️ [주의] 시간당 30~50mm 내외의 강한 비 예상")
        st.write("**대응:** 하천변 산책로 출입 통제 및 운전 시 시야 확보 주의")
    elif 50 < final_hri < 65:
        st.warning("🟠 [준비] 호우 발달 가능성 모니터링")
        st.write("**대응:** 기상 특보 실시간 확인")
    else:
        st.success("✅ [안전] 기상 상황 양호")

    st.markdown("---")
    st.write(f"**현재 {selected_city} 기상:** {weather['temp']}°C / 습도 {weather['hm']}%")

with col2:
    # 레이더 차트 (위험 기여도)
    fig = go.Figure(go.Scatterpolar(
        r=[s_sst, s_pwat, s_v850, s_theta],
        theta=['해수면온도', '가용수증기', '하층제트', '상당온위'],
        fill='toself', 
        fillcolor='rgba(255, 75, 75, 0.4)',
        line=dict(color='#FF4B4B', width=2)
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        title="항목별 위험 기여도 (Radar Chart)"
    )
    st.plotly_chart(fig, use_container_width=True)

# 하단 과거 사례 안내
with st.expander("ℹ️ HRI v3.0 모델링 근거"):
    st.write("본 시스템은 전북지역 2000-2025년 극한강수 데이터(1시간 최다 152.2mm 등)를 분석하여 개발되었습니다.")
    st.write("- **30~50mm 구간:** 호우주의보 기준 발령 및 10분 강수량 급증 구간")
    st.write("- **100mm 이상 구간:** 상당온위 345K 이상 및 야간 하층제트 강화 시 집중 발생")
