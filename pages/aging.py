```python
import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.data_loader import get_aging_data


# ============================================================
# 1. 공통 함수
# ============================================================

def format_number(value, digits=4):
    """일반 숫자 표시"""
    if pd.isna(value):
        return "-"

    try:
        return f"{float(value):.{digits}g}"
    except (TypeError, ValueError):
        return str(value)


def format_percent(value):
    """
    Excel 값이 0.95이면 95.00%
    Excel 값이 95이면 95.00%
    """
    if pd.isna(value):
        return "-"

    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)

    if abs(value) <= 1:
        value *= 100

    return f"{value:.2f}%"


def percent_to_number(value):
    """
    그래프용 백분율 숫자 변환
    0.95 -> 95
    95   -> 95
    """
    if pd.isna(value):
        return np.nan

    try:
        value = float(value)
    except (TypeError, ValueError):
        return np.nan

    if abs(value) <= 1:
        value *= 100

    return value


def get_latest_rows(data, subset):
    """동일 조건 데이터가 여러 개이면 최신 행 사용"""

    result = data.copy()

    if result.empty:
        return result

    if "업데이트일자" in result.columns:
        result["_update_date"] = pd.to_datetime(
            result["업데이트일자"],
            errors="coerce",
        )

        result = result.sort_values(
            "_update_date"
        )

    result = result.drop_duplicates(
        subset=subset,
        keep="last",
    )

    result = result.drop(
        columns=["_update_date"],
        errors="ignore",
    )

    return result


def find_hour_columns(columns):
    """
    Excel에 있는 시간 컬럼을 자동 탐색.

    예:
    24hr
    48hr
    1,000hr
    2000hr

    새로운 시간 컬럼이 추가되어도 자동 인식.
    """

    result = []

    pattern = re.compile(
        r"^\s*([\d,]+)\s*hr\s*$",
        re.IGNORECASE,
    )

    for column in columns:
        match = pattern.match(str(column))

        if not match:
            continue

        hour_text = match.group(1).replace(",", "")

        try:
            hour = int(hour_text)
        except ValueError:
            continue

        result.append(
            (column, hour)
        )

    result.sort(
        key=lambda item: item[1]
    )

    return result


# ============================================================
# 2. 데이터 로드
# ============================================================

try:
    df = get_aging_data().copy()

except Exception as error:
    st.error(
        "Aging Excel 데이터를 불러오는 중 오류가 발생했습니다."
    )
    st.exception(error)
    st.stop()


# ============================================================
# 3. 컬럼명 정리
# ============================================================

df.columns = [
    str(column)
    .replace("\n", " ")
    .strip()
    for column in df.columns
]


# ============================================================
# 4. 필수 컬럼 확인
# ============================================================

required_columns = [
    "부품사",
    "자재코드",
    "시험전압",
]

missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing_columns:
    st.error(
        "Aging Excel에서 필요한 컬럼을 찾을 수 없습니다."
    )

    st.write(
        "없는 컬럼:",
        missing_columns,
    )

    st.write(
        "현재 Excel 컬럼:",
        list(df.columns),
    )

    st.stop()


# ============================================================
# 5. 빈 행 제거
# ============================================================

df = df.dropna(
    subset=[
        "부품사",
        "자재코드",
        "시험전압",
    ]
).copy()


# ============================================================
# 6. 문자열 데이터 정리
# ============================================================

string_columns = [
    "부품사",
    "자재코드",
    "부품사코드",
    "Grade",
]

for column in string_columns:
    if column in df.columns:
        df[column] = (
            df[column]
            .astype(str)
            .str.strip()
        )


# ============================================================
# 7. 숫자형 데이터 정리
# ============================================================

numeric_columns = [
    "정격전압(V)",
    "정격용량(uF)",
    "Size",
    "시험전압",
    "시험온도",
    "① 25℃, 0V",
    "②고온+No Bias",
    "③ 고온+DC Bias",
    "△C (①-③)/①",
    "7년 (-20%반영)",
    "10년 (-20%반영)",
    "7년 잔여율",
    "7년 감소율",
    "10년 잔여율",
    "10년 감소율",
    "결정계수 (R^2)",
]

# 시간 컬럼 자동 탐색
hour_columns = find_hour_columns(
    df.columns
)

for column, _ in hour_columns:
    numeric_columns.append(column)


for column in numeric_columns:
    if column in df.columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )


# ============================================================
# 8. 페이지 제목
# ============================================================

st.title("📉 MLCC Aging 분석")

st.caption(
    "Aging 실측 데이터와 Excel 장기 산출결과를 기반으로 "
    "시간 경과에 따른 MLCC 용량 변화를 분석합니다."
)


# ============================================================
# 9. Sidebar
# ============================================================

with st.sidebar:
    st.header("Aging 분석 조건")

    if st.button(
        "Aging 데이터 새로고침",
        use_container_width=True,
        key="aging_refresh",
    ):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    # --------------------------------------------------------
    # 부품사
    # --------------------------------------------------------

    supplier_list = sorted(
        df["부품사"]
        .dropna()
        .unique()
        .tolist()
    )

    if not supplier_list:
        st.error("부품사 데이터가 없습니다.")
        st.stop()

    selected_supplier = st.selectbox(
        "부품사",
        supplier_list,
        key="aging_supplier",
    )

    # --------------------------------------------------------
    # 자재코드
    # --------------------------------------------------------

    supplier_df = df[
        df["부품사"] == selected_supplier
    ].copy()

    material_list = sorted(
        supplier_df["자재코드"]
        .dropna()
        .unique()
        .tolist()
    )

    if not material_list:
        st.warning(
            "선택한 부품사에 자재코드가 없습니다."
        )
        st.stop()

    selected_material = st.selectbox(
        "자재코드",
        material_list,
        key="aging_material",
    )

    # --------------------------------------------------------
    # 시험전압
    # --------------------------------------------------------

    material_df = supplier_df[
        supplier_df["자재코드"] == selected_material
    ].copy()

    voltage_list = sorted(
        material_df["시험전압"]
        .dropna()
        .unique()
        .tolist()
    )

    if not voltage_list:
        st.warning(
            "선택한 자재코드에 시험전압 데이터가 없습니다."
        )
        st.stop()

    selected_voltage = st.selectbox(
        "시험전압(V)",
        voltage_list,
        format_func=lambda value: f"{value:g} V",
        key="aging_voltage",
    )


# ============================================================
# 10. 선택 데이터
# ============================================================

selected_df = df[
    (df["부품사"] == selected_supplier)
    & (df["자재코드"] == selected_material)
    & (df["시험전압"] == selected_voltage)
].copy()

if selected_df.empty:
    st.warning(
        "선택 조건에 해당하는 Aging 데이터가 없습니다."
    )
    st.stop()


selected_df = get_latest_rows(
    selected_df,
    subset=[
        "부품사",
        "자재코드",
        "시험전압",
    ],
)

selected_row = selected_df.iloc[-1]


# ============================================================
# 11. 선택 조건
# ============================================================

st.subheader("선택 조건")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "부품사",
    selected_supplier,
)

col2.metric(
    "자재코드",
    selected_material,
)

col3.metric(
    "시험전압",
    f"{selected_voltage:g} V",
)

test_temperature = selected_row.get(
    "시험온도",
    np.nan,
)

col4.metric(
    "시험온도",
    (
        f"{test_temperature:g} ℃"
        if pd.notna(test_temperature)
        else "-"
    ),
)


# ============================================================
# 12. MLCC 기본 정보
# ============================================================

st.subheader("MLCC 기본 정보")

info1, info2, info3, info4 = st.columns(4)

rated_voltage = selected_row.get(
    "정격전압(V)",
    np.nan,
)

rated_capacity = selected_row.get(
    "정격용량(uF)",
    np.nan,
)

grade = selected_row.get(
    "Grade",
    "-",
)

size = selected_row.get(
    "Size",
    np.nan,
)

info1.metric(
    "정격전압",
    (
        f"{rated_voltage:g} V"
        if pd.notna(rated_voltage)
        else "-"
    ),
)

info2.metric(
    "정격용량",
    (
        f"{rated_capacity:g} µF"
        if pd.notna(rated_capacity)
        else "-"
    ),
)

info3.metric(
    "Grade",
    grade if grade else "-",
)

info4.metric(
    "Size",
    format_number(size),
)


# ============================================================
# 13. 초기 Aging 평가
# ============================================================

st.subheader("초기 Aging 평가결과")

initial_capacity = selected_row.get(
    "① 25℃, 0V",
    np.nan,
)

no_bias_capacity = selected_row.get(
    "②고온+No Bias",
    np.nan,
)

dc_bias_capacity = selected_row.get(
    "③ 고온+DC Bias",
    np.nan,
)

delta_capacity = selected_row.get(
    "△C (①-③)/①",
    np.nan,
)

metric1, metric2, metric3, metric4 = st.columns(4)

metric1.metric(
    "25℃ / 0V",
    (
        f"{initial_capacity:.4f} µF"
        if pd.notna(initial_capacity)
        else "-"
    ),
)

metric2.metric(
    "고온 / No Bias",
    (
        f"{no_bias_capacity:.4f} µF"
        if pd.notna(no_bias_capacity)
        else "-"
    ),
)

metric3.metric(
    "고온 / DC Bias",
    (
        f"{dc_bias_capacity:.4f} µF"
        if pd.notna(dc_bias_capacity)
        else "-"
    ),
)

metric4.metric(
    "초기 대비 ΔC",
    format_percent(delta_capacity),
)


# ============================================================
# 14. 시간 데이터 분리
# ============================================================

# 1,000시간 이하 = 실측 영역
# 그보다 큰 시간 = 장기 산출 영역
#
# 필요하면 기준값만 변경하면 됨.
MEASURED_MAX_HOUR = 1000

measured_hour_columns = [
    (column, hour)
    for column, hour in hour_columns
    if hour <= MEASURED_MAX_HOUR
]

long_term_hour_columns = [
    (column, hour)
    for column, hour in hour_columns
    if hour > MEASURED_MAX_HOUR
]


# ============================================================
# 15. 실측 Aging DataFrame
# ============================================================

measured_rows = []

for column, hour in measured_hour_columns:
    value = selected_row.get(
        column,
        np.nan,
    )

    if pd.notna(value):
        measured_rows.append(
            {
                "시간(hr)": hour,
                "잔여용량(uF)": float(value),
            }
        )

measured_df = pd.DataFrame(
    measured_rows
)


# ============================================================
# 16. 장기 Aging DataFrame
# ============================================================

long_term_rows = []

for column, hour in long_term_hour_columns:
    value = selected_row.get(
        column,
        np.nan,
    )

    if pd.notna(value):
        long_term_rows.append(
            {
                "시간(hr)": hour,
                "잔여용량(uF)": float(value),
            }
        )

long_term_df = pd.DataFrame(
    long_term_rows
)


# ============================================================
# 17. Tabs
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "📈 Aging 추이",
        "📊 잔여율",
        "🗓 장기 결과",
        "🏭 부품사 비교",
    ]
)


# ============================================================
# 18. TAB 1 - Aging 추이
# ============================================================

with tab1:
    st.subheader(
        "시간경과에 따른 Aging 특성"
    )

    fig_aging = go.Figure()

    if not measured_df.empty:
        fig_aging.add_trace(
            go.Scatter(
                x=measured_df["시간(hr)"],
                y=measured_df["잔여용량(uF)"],
                mode="lines+markers",
                name="Aging 실측",
                line=dict(
                    width=3,
                ),
                marker=dict(
                    size=
