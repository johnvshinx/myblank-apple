#import streamlit as st

#st.title("🎈 My new app")
#st.write(
#    "Let's start building! For help and inspiration, head over to [docs.streamlit.io](https://docs.streamlit.io/)."
#)

#streamlit run streamlit_app.py

import pandas as pd
import streamlit as st
import altair as alt

st.set_page_config(
    page_title="UGV Mission Dashboard",
    layout="wide"          # ← 핵심 옵션
)

## (선택) 위·양옆 여백 조금 줄이기
#st.markdown(
#    """
#    <style>
#        /* 기본 패딩 제거/축소 */
#        .block-container {
#            padding-top: 1rem;
#            padding-bottom: 1rem;
#            padding-left: 2rem;
#            padding-right: 2rem;
#        }
#    </style>
#    """,
#    unsafe_allow_html=True
#)

# =========================
# 데이터 로딩
# =========================
@st.cache_data
def load_data(path: str):
    df = pd.read_csv(path)
    return df

# CSV 경로는 필요하면 수정하세요.
DATA_PATH = "ugv_mission_dataset_220rows.csv"
df = load_data(DATA_PATH)

# 숫자형 → 범주형(지형 타입 라벨) 예시
# 필요하면 아래 dict를 실제 의미에 맞게 수정해서 쓰세요.
terrain_labels = {
    0: "Type 0",
    1: "Type 1",
    2: "Type 2",
    3: "Type 3",
}
df["TerrainLabel"] = df["TerrainType"].map(terrain_labels).fillna(df["TerrainType"].astype(str))

# =========================
# 사이드바 (앱 제목 + 입력 위젯)
# =========================
st.sidebar.title("UGV Mission Dashboard")

st.sidebar.markdown("### 필터")

# 지형 타입 선택
terrain_options = sorted(df["TerrainLabel"].unique().tolist())
selected_terrains = st.sidebar.multiselect(
    "Terrain Type 선택",
    options=terrain_options,
    default=terrain_options,
)

# 배터리 레벨 범위
min_batt, max_batt = int(df["BatteryLevel"].min()), int(df["BatteryLevel"].max())
battery_range = st.sidebar.slider(
    "Battery Level 범위",
    min_value=min_batt,
    max_value=max_batt,
    value=(min_batt, max_batt),
)

# 미션 성공 여부 필터
success_filter = st.sidebar.selectbox(
    "Mission Success 필터",
    ("All", "Success only", "Failure only"),
)

# 컬러 테마 (Altair color scheme 이름 사용)
color_theme = st.sidebar.selectbox(
    "Color Theme (차트용)",
    ("blues", "viridis", "magma", "plasma", "redblue", "greens"),
)

# =========================
# 필터 적용
# =========================
filtered = df[
    df["TerrainLabel"].isin(selected_terrains)
    & (df["BatteryLevel"].between(battery_range[0], battery_range[1]))
]

if success_filter == "Success only":
    filtered = filtered[filtered["MissionSuccess"] == 1]
elif success_filter == "Failure only":
    filtered = filtered[filtered["MissionSuccess"] == 0]

# 전체 대비 비교를 위해 원본도 보관
base = df.copy()

# =========================
# 레이아웃 구성: 3개 컬럼
# =========================
col1, col2, col3 = st.columns([1.2, 2.0, 1.2])

# -------------------------------------------------
# 📊 컬럼 1: 미션 개요 / 핵심 지표
# -------------------------------------------------
with col1:
    st.subheader("Mission Overview")

    total_missions = len(filtered)
    total_missions_all = len(base)

    success_rate = filtered["MissionSuccess"].mean() if len(filtered) > 0 else 0
    success_rate_all = base["MissionSuccess"].mean()

    avg_time = filtered["MissionTime"].mean() if len(filtered) > 0 else 0
    avg_time_all = base["MissionTime"].mean()

    avg_speed = filtered["Speed"].mean() if len(filtered) > 0 else 0
    avg_speed_all = base["Speed"].mean()

    # 상단 3개 metric (Gains/Losses 느낌)
    st.metric(
        "Missions (filtered)",
        f"{total_missions}",
        delta=f"{total_missions - total_missions_all} vs all",
    )
    st.metric(
        "Success Rate",
        f"{success_rate*100:,.1f} %",
        delta=f"{(success_rate - success_rate_all)*100:,.1f} % vs all",
    )
    st.metric(
        "Avg Mission Time",
        f"{avg_time:,.1f} min",
        delta=f"{avg_time - avg_time_all:,.1f} vs all",
    )

    st.markdown("---")

    # States Migration 자리에 미션 난이도 느낌의 비율 2개 표시 예시
    # 장애물 밀도 기준으로 high / low 비율
    if len(filtered) > 0:
        # threshold는 임의 값, 필요시 수정
        obstacle_threshold = filtered["ObstacleDensity"].median()
        high_obstacle = (filtered["ObstacleDensity"] > obstacle_threshold).mean()
        low_obstacle = 1 - high_obstacle

        st.markdown("#### Obstacle Profile")
        st.progress(int(high_obstacle * 100))
        st.caption(f"High obstacle missions: {high_obstacle*100:,.1f} %")

        st.progress(int(low_obstacle * 100))
        st.caption(f"Low/medium obstacle missions: {low_obstacle*100:,.1f} %")
    else:
        st.info("선택된 조건에 해당하는 미션이 없습니다.")

# -------------------------------------------------
# 🗺️ 컬럼 2: 메인 시각화 (히트맵 & 산점도)
# -------------------------------------------------
with col2:
    st.subheader("Mission Performance")

    if len(filtered) > 0:
        # 히트맵: Terrain × ObstacleDensity 에 대한 평균 성공률
        heat_data = (
            filtered.assign(
                ObstacleBin=pd.cut(
                    filtered["ObstacleDensity"], bins=6, include_lowest=True
                ).astype(str)
            )
            .groupby(["TerrainLabel", "ObstacleBin"], as_index=False)
            .agg(SuccessRate=("MissionSuccess", "mean"))
        )

        heatmap = (
            alt.Chart(heat_data)
            .mark_rect()
            .encode(
                x=alt.X("TerrainLabel:N", title="Terrain Type"),
                y=alt.Y("ObstacleBin:N", title="Obstacle Density (binned)"),
                color=alt.Color(
                    "SuccessRate:Q",
                    scale=alt.Scale(scheme=color_theme),
                    title="Success Rate",
                ),
                tooltip=[
                    alt.Tooltip("TerrainLabel:N", title="Terrain"),
                    alt.Tooltip("ObstacleBin:N", title="Obstacle range"),
                    alt.Tooltip("SuccessRate:Q", title="Success rate", format=".2f"),
                ],
            )
            .properties(height=260)
        )

        st.markdown("##### Success Rate Heatmap")
        st.altair_chart(heatmap, use_container_width=True)

        # 산점도: Speed vs MissionTime, 색 = MissionSuccess
        # 산점도: Speed vs Battery Level, 색 = MissionSuccess
        scatter = (
            alt.Chart(filtered)
            .mark_circle(size=60, opacity=0.8)
            .encode(
                x=alt.X("Speed:Q", title="Speed"),
                #y=alt.Y("MissionTime:Q", title="Mission Time"),
                y=alt.Y("BatteryLevel:Q", title="Battery Level"),
                color=alt.Color(
                    "MissionSuccess:N",
                    title="Success",
                    scale=alt.Scale(scheme="set1"),
                ),
                tooltip=[
                    "TerrainLabel",
                    "BatteryLevel",
                    "PayloadWeight",
                    "CommQuality",
                    "SensorHealth",
                    "ObstacleDensity",
                    "Speed",
                    "MissionTime",
                    "MissionSuccess",
                ],
            )
            .interactive()
            .properties(height=260)
        )

        #st.markdown("##### Speed vs Mission Time")
        st.markdown("##### Speed vs Battery Level")
        st.altair_chart(scatter, use_container_width=True)
    else:
        st.info("선택된 조건에 해당하는 미션이 없어 그래프를 그릴 수 없습니다.")

# -------------------------------------------------
# 📈 컬럼 3: Top 조건 & About
# -------------------------------------------------
with col3:
    st.subheader("Top Terrain Types")

    if len(filtered) > 0:
        terrain_stats = (
            filtered.groupby("TerrainLabel")
            .agg(
                SuccessRate=("MissionSuccess", "mean"),
                Missions=("MissionSuccess", "size"),
            )
            .reset_index()
        )

        top_terrain = terrain_stats.sort_values(
            by=["SuccessRate", "Missions"], ascending=False
        ).head(5)

        bar = (
            alt.Chart(top_terrain)
            .mark_bar()
            .encode(
                x=alt.X("SuccessRate:Q", title="Success Rate"),
                y=alt.Y("TerrainLabel:N", sort="-x", title="Terrain Type"),
                tooltip=[
                    alt.Tooltip("TerrainLabel:N", title="Terrain"),
                    alt.Tooltip("Missions:Q", title="# Missions"),
                    alt.Tooltip("SuccessRate:Q", title="Success rate", format=".2f"),
                ],
                color=alt.Color("SuccessRate:Q", scale=alt.Scale(scheme=color_theme)),
            )
            .properties(height=260)
        )

        st.altair_chart(bar, use_container_width=True)

    else:
        st.info("Top Terrain을 계산할 데이터가 없습니다.")

    st.markdown("---")

    with st.expander("About this dashboard"):
        st.markdown(
            """
            - **Data**: UGV(무인 지상 차량) 미션 로그 220건  
            - **MissionSuccess**: 1은 성공, 0은 실패를 의미합니다.  
            - **Heatmap**: 지형 타입과 장애물 밀도 구간에 따른 평균 성공률을 보여줍니다.  
            - **Scatter Plot**: 속도와 미션 시간 사이 관계를 시각화하고, 성공/실패를 색으로 구분합니다.  
            - **Top Terrain Types**: 필터된 조건에서 성공률이 높은 지형 타입 상위 5개입니다.  
            - 사이드바 필터를 바꾸면서 조건별 성능 변화를 살펴보세요.
            """
        )

