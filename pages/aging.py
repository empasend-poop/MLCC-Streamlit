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
                    size=9,
                ),
                hovertemplate=(
                    "시간: %{x:,.0f} hr"
                    "<br>잔여용량: %{y:.5f} µF"
                    "<extra></extra>"
                ),
            )
        )

    if not long_term_df.empty:
        fig_aging.add_trace(
            go.Scatter(
                x=long_term_df["시간(hr)"],
                y=long_term_df["잔여용량(uF)"],
                mode="markers",
                name="Excel 장기 산출값",
                marker=dict(
                    size=12,
                    symbol="diamond",
                ),
                hovertemplate=(
                    "시간: %{x:,.0f} hr"
                    "<br>잔여용량: %{y:.5f} µF"
                    "<extra></extra>"
                ),
            )
        )

    fig_aging.update_layout(
        height=520,
        xaxis_title="경과시간 (hr)",
        yaxis_title="잔여용량 (µF)",
        hovermode="closest",
        legend_title="",
    )

    fig_aging.update_xaxes(
        type="log",
    )

    st.plotly_chart(
        fig_aging,
        use_container_width=True,
    )

    st.caption(
        "실선은 1,000시간 이하 Aging 데이터, "
        "Diamond는 Excel의 1,000시간 초과 장기 산출값입니다."
    )

    chart_parts = []

    if not measured_df.empty:
        measured_table = measured_df.copy()
        measured_table["구분"] = "실측"
        chart_parts.append(
            measured_table
        )

    if not long_term_df.empty:
        long_table = long_term_df.copy()
        long_table["구분"] = "장기 산출"
        chart_parts.append(
            long_table
        )

    if chart_parts:
        chart_table = pd.concat(
            chart_parts,
            ignore_index=True,
        ).sort_values(
            "시간(hr)"
        )

        with st.expander(
            "Aging 그래프 데이터 보기"
        ):
            st.dataframe(
                chart_table,
                hide_index=True,
                use_container_width=True,
            )


# ============================================================
# 19. TAB 2 - 잔여율
# ============================================================

with tab2:
    st.subheader(
        "초기 대비 Aging 잔여율"
    )

    remaining_rows = []

    if (
        pd.notna(initial_capacity)
        and float(initial_capacity) != 0
    ):
        for _, row in measured_df.iterrows():
            remaining_rate = (
                row["잔여용량(uF)"]
                / float(initial_capacity)
                * 100
            )

            remaining_rows.append(
                {
                    "시간(hr)": row["시간(hr)"],
                    "잔여율(%)": remaining_rate,
                    "구분": "실측",
                }
            )

        for _, row in long_term_df.iterrows():
            remaining_rate = (
                row["잔여용량(uF)"]
                / float(initial_capacity)
                * 100
            )

            remaining_rows.append(
                {
                    "시간(hr)": row["시간(hr)"],
                    "잔여율(%)": remaining_rate,
                    "구분": "장기 산출",
                }
            )

    remaining_df = pd.DataFrame(
        remaining_rows
    )

    if remaining_df.empty:
        st.info(
            "초기용량 데이터가 없어 잔여율을 계산할 수 없습니다."
        )

    else:
        measured_remaining = remaining_df[
            remaining_df["구분"] == "실측"
        ].copy()

        long_remaining = remaining_df[
            remaining_df["구분"] == "장기 산출"
        ].copy()

        fig_remaining = go.Figure()

        if not measured_remaining.empty:
            fig_remaining.add_trace(
                go.Scatter(
                    x=measured_remaining["시간(hr)"],
                    y=measured_remaining["잔여율(%)"],
                    mode="lines+markers",
                    name="Aging 실측",
                    line=dict(
                        width=3,
                    ),
                    marker=dict(
                        size=9,
                    ),
                    hovertemplate=(
                        "시간: %{x:,.0f} hr"
                        "<br>잔여율: %{y:.4f}%"
                        "<extra></extra>"
                    ),
                )
            )

        if not long_remaining.empty:
            fig_remaining.add_trace(
                go.Scatter(
                    x=long_remaining["시간(hr)"],
                    y=long_remaining["잔여율(%)"],
                    mode="markers",
                    name="장기 산출",
                    marker=dict(
                        size=12,
                        symbol="diamond",
                    ),
                    hovertemplate=(
                        "시간: %{x:,.0f} hr"
                        "<br>잔여율: %{y:.4f}%"
                        "<extra></extra>"
                    ),
                )
            )

        fig_remaining.update_layout(
            height=500,
            xaxis_title="경과시간 (hr)",
            yaxis_title="초기 대비 잔여율 (%)",
            hovermode="closest",
            legend_title="",
        )

        fig_remaining.update_xaxes(
            type="log",
        )

        st.plotly_chart(
            fig_remaining,
            use_container_width=True,
        )

        st.caption(
            "잔여율 = 해당 시간의 잔여용량 ÷ 25℃/0V 초기용량 × 100"
        )

        remaining_table = remaining_df.copy()

        remaining_table["잔여율(%)"] = (
            remaining_table["잔여율(%)"]
            .round(4)
        )

        st.dataframe(
            remaining_table,
            hide_index=True,
            use_container_width=True,
        )


# ============================================================
# 20. TAB 3 - 장기 결과
# ============================================================

with tab3:
    st.subheader(
        "장기 Aging 산출결과"
    )

    excel_r2 = selected_row.get(
        "결정계수 (R^2)",
        np.nan,
    )

    st.metric(
        "Excel 결정계수 R²",
        (
            f"{excel_r2:.4f}"
            if pd.notna(excel_r2)
            else "-"
        ),
    )

    st.markdown("#### 7년")

    seven_capacity = selected_row.get(
        "7년 (-20%반영)",
        np.nan,
    )

    seven_remaining = selected_row.get(
        "7년 잔여율",
        np.nan,
    )

    seven_decrease = selected_row.get(
        "7년 감소율",
        np.nan,
    )

    seven1, seven2, seven3 = st.columns(3)

    seven1.metric(
        "7년 잔여용량",
        (
            f"{seven_capacity:.5f} µF"
            if pd.notna(seven_capacity)
            else "-"
        ),
    )

    seven2.metric(
        "7년 잔여율",
        format_percent(
            seven_remaining
        ),
    )

    seven3.metric(
        "7년 감소율",
        format_percent(
            seven_decrease
        ),
    )

    st.markdown("#### 10년")

    ten_capacity = selected_row.get(
        "10년 (-20%반영)",
        np.nan,
    )

    ten_remaining = selected_row.get(
        "10년 잔여율",
        np.nan,
    )

    ten_decrease = selected_row.get(
        "10년 감소율",
        np.nan,
    )

    ten1, ten2, ten3 = st.columns(3)

    ten1.metric(
        "10년 잔여용량",
        (
            f"{ten_capacity:.5f} µF"
            if pd.notna(ten_capacity)
            else "-"
        ),
    )

    ten2.metric(
        "10년 잔여율",
        format_percent(
            ten_remaining
        ),
    )

    ten3.metric(
        "10년 감소율",
        format_percent(
            ten_decrease
        ),
    )

    if not long_term_df.empty:
        st.markdown(
            "#### Excel 장기 시간별 산출값"
        )

        long_display = long_term_df.copy()

        long_display["기간"] = long_display[
            "시간(hr)"
        ].map(
            {
                8760: "1년",
                43800: "5년",
                61320: "7년",
                87600: "10년",
            }
        )

        long_display["기간"] = (
            long_display["기간"]
            .fillna(
                long_display["시간(hr)"]
                .map(
                    lambda value: f"{value:,.0f} hr"
                )
            )
        )

        if (
            pd.notna(initial_capacity)
            and float(initial_capacity) != 0
        ):
            long_display[
                "초기 대비 잔여율(%)"
            ] = (
                long_display["잔여용량(uF)"]
                / float(initial_capacity)
                * 100
            ).round(4)

            long_display[
                "초기 대비 감소율(%)"
            ] = (
                100
                - long_display[
                    "초기 대비 잔여율(%)"
                ]
            ).round(4)

        display_order = [
            "기간",
            "시간(hr)",
            "잔여용량(uF)",
            "초기 대비 잔여율(%)",
            "초기 대비 감소율(%)",
        ]

        display_order = [
            column
            for column in display_order
            if column in long_display.columns
        ]

        st.dataframe(
            long_display[
                display_order
            ],
            hide_index=True,
            use_container_width=True,
        )


# ============================================================
# 21. TAB 4 - 부품사 비교
# ============================================================

with tab4:
    st.subheader(
        "동일 자재코드 부품사 Aging 비교"
    )

    st.caption(
        f"자재코드 {selected_material} 기준"
    )

    same_voltage_only = st.checkbox(
        "동일 시험전압 조건만 비교",
        value=True,
        key="aging_same_voltage",
    )

    comparison_source = df[
        df["자재코드"] == selected_material
    ].copy()

    if same_voltage_only:
        comparison_source = comparison_source[
            comparison_source["시험전압"]
            == selected_voltage
        ].copy()

    comparison_source = get_latest_rows(
        comparison_source,
        subset=[
            "부품사",
            "자재코드",
            "시험전압",
        ],
    )

    comparison_rows = []

    for _, row in comparison_source.iterrows():
        supplier = row["부품사"]
        voltage = row["시험전압"]

        for column, hour in measured_hour_columns:
            value = row.get(
                column,
                np.nan,
            )

            if pd.isna(value):
                continue

            comparison_rows.append(
                {
                    "부품사": supplier,
                    "시험전압": voltage,
                    "시간(hr)": hour,
                    "잔여용량(uF)": float(value),
                    "구분": (
                        f"{supplier} / "
                        f"{voltage:g}V"
                    ),
                }
            )

    comparison_df = pd.DataFrame(
        comparison_rows
    )

    if comparison_df.empty:
        st.info(
            "현재 조건에서 비교 가능한 Aging 데이터가 없습니다."
        )

    else:
        fig_compare = px.line(
            comparison_df,
            x="시간(hr)",
            y="잔여용량(uF)",
            color="구분",
            markers=True,
        )

        fig_compare.update_traces(
            line=dict(
                width=3,
            ),
            marker=dict(
                size=8,
            ),
        )

        fig_compare.update_xaxes(
            type="log",
        )

        fig_compare.update_layout(
            height=520,
            xaxis_title="경과시간 (hr)",
            yaxis_title="잔여용량 (µF)",
            legend_title="",
            hovermode="closest",
        )

        st.plotly_chart(
            fig_compare,
            use_container_width=True,
        )

    # --------------------------------------------------------
    # 7년 / 10년 비교
    # --------------------------------------------------------

    st.markdown(
        "#### 부품사별 7년 / 10년 잔여율 비교"
    )

    supplier_long_rows = []

    for _, row in comparison_source.iterrows():
        supplier = row["부품사"]
        voltage = row["시험전압"]

        seven_rate = percent_to_number(
            row.get(
                "7년 잔여율",
                np.nan,
            )
        )

        ten_rate = percent_to_number(
            row.get(
                "10년 잔여율",
                np.nan,
            )
        )

        label = (
            f"{supplier} / "
            f"{voltage:g}V"
        )

        if pd.notna(seven_rate):
            supplier_long_rows.append(
                {
                    "부품사 / 시험전압": label,
                    "기간": "7년",
                    "잔여율(%)": seven_rate,
                }
            )

        if pd.notna(ten_rate):
            supplier_long_rows.append(
                {
                    "부품사 / 시험전압": label,
                    "기간": "10년",
                    "잔여율(%)": ten_rate,
                }
            )

    supplier_long_df = pd.DataFrame(
        supplier_long_rows
    )

    if not supplier_long_df.empty:
        fig_long = px.bar(
            supplier_long_df,
            x="부품사 / 시험전압",
            y="잔여율(%)",
            color="기간",
            barmode="group",
            text_auto=".2f",
        )

        fig_long.update_layout(
            height=480,
            xaxis_title="",
            yaxis_title="잔여율 (%)",
            legend_title="",
        )

        st.plotly_chart(
            fig_long,
            use_container_width=True,
        )

    with st.expander(
        "부품사 비교 원본 데이터"
    ):
        st.dataframe(
            comparison_source,
            hide_index=True,
            use_container_width=True,
        )


# ============================================================
# 22. 원본 데이터
# ============================================================

st.divider()

with st.expander(
    "현재 선택 데이터 전체 보기"
):
    st.dataframe(
        selected_df,
        hide_index=True,
        use_container_width=True,
    )


with st.expander(
    "전체 Aging 데이터 보기"
):
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
    )


# ============================================================
# 23. Footer
# ============================================================

st.divider()

footer1, footer2, footer3 = st.columns(3)

footer1.caption(
    f"Aging 데이터: {len(df):,}건"
)

footer2.caption(
    f"부품사: {df['부품사'].nunique():,}개"
)

footer3.caption(
    f"자재코드: {df['자재코드'].nunique():,}개"
)
