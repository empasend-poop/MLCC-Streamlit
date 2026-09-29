```python
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.data_loader import get_aging_data


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_text(value):
    """문자열 데이터 정리"""
    if pd.isna(value):
        return ""
    return str(value).strip()


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
    Excel 값이
    0.95 -> 95%
    95   -> 95%
    어느 형태든 대응
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


def percent_value(value):
    """
    Plotly용 percentage 숫자 변환.
    0.95 -> 95
    95   -> 95
    """
    if pd.isna(value):
        return np.nan

    value = float(value)

    if abs(value) <= 1:
        value *= 100

    return value


def latest_rows(data, subset):
    """업데이트일자가 있을 경우 조건별 최신 데이터만 유지"""

    result = data.copy()

    if "업데이트일자" not in result.columns:
        return result.drop_duplicates(
            subset=subset,
            keep="last",
        )

    result["_sort_date"] = pd.to_datetime(
        result["업데이트일자"],
        errors="coerce",
    )

    result = (
        result
        .sort_values("_sort_date")
        .drop_duplicates(
            subset=subset,
            keep="last",
        )
        .drop(
            columns="_sort_date",
            errors="ignore",
        )
    )

    return result


# ============================================================
# DATA LOAD
# ============================================================

try:
    df = get_aging_data().copy()

except Exception as e:

    st.error(
        "Aging Excel 데이터를 불러오는 중 오류가 발생했습니다."
    )

    st.exception(e)

    st.stop()


# ============================================================
# COLUMN CLEANING
# ============================================================

df.columns = [
    str(col)
    .replace("\n", " ")
    .strip()
    for col in df.columns
]


required_columns = [
    "부품사",
    "자재코드",
    "시험전압",
]


missing_columns = [
    col
    for col in required_columns
    if col not in df.columns
]


if missing_columns:

    st.error(
        "Aging Excel에 필요한 컬럼이 없습니다: "
        + ", ".join(missing_columns)
    )

    st.stop()


# ============================================================
# STRING COLUMNS
# ============================================================

string_columns = [
    "자재코드",
    "부품사",
    "부품사코드",
    "Grade",
]


for col in string_columns:

    if col in df.columns:

        df[col] = (
            df[col]
            .apply(clean_text)
        )


# ============================================================
# NUMERIC COLUMNS
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

    "24hr",
    "48hr",
    "72hr",
    "96hr",
    "200hr",
    "500hr",
    "1,000hr",

    "8,760hr",
    "43,800hr",
    "61,320hr",
    "87,600hr",

    "7년 (-20%반영)",
    "10년 (-20%반영)",

    "7년 잔여율",
    "7년 감소율",

    "10년 잔여율",
    "10년 감소율",

    "결정계수 (R^2)",
]


for col in numeric_columns:

    if col in df.columns:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )


# ============================================================
# PAGE TITLE
# ============================================================

st.title("📉 MLCC Aging 분석")

st.caption(
    "Aging 실측 데이터와 Excel 장기 산출결과를 기반으로 "
    "MLCC의 시간 경과에 따른 용량 변화를 분석합니다."
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("Aging 분석 조건")

    if st.button(
        "Aging 데이터 새로고침",
        use_container_width=True,
    ):

        st.cache_data.clear()
        st.rerun()

    st.divider()

    # --------------------------------------------------------
    # Supplier
    # --------------------------------------------------------

    supplier_list = sorted(
        df["부품사"]
        .dropna()
        .loc[
            lambda x: x != ""
        ]
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
    # Material
    # --------------------------------------------------------

    supplier_df = df[
        df["부품사"]
        == selected_supplier
    ].copy()


    material_list = sorted(
        supplier_df["자재코드"]
        .dropna()
        .loc[
            lambda x: x != ""
        ]
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
    # Test Voltage
    # --------------------------------------------------------

    material_df = supplier_df[
        supplier_df["자재코드"]
        == selected_material
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
        format_func=lambda x: f"{x:g} V",
        key="aging_voltage",
    )


# ============================================================
# SELECTED DATA
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


selected_df = latest_rows(
    selected_df,
    subset=[
        "부품사",
        "자재코드",
        "시험전압",
    ],
)


selected_row = selected_df.iloc[-1]


# ============================================================
# SUMMARY
# ============================================================

st.subheader("선택 조건")


c1, c2, c3, c4 = st.columns(4)


c1.metric(
    "부품사",
    selected_supplier,
)


c2.metric(
    "자재코드",
    selected_material,
)


c3.metric(
    "시험전압",
    f"{selected_voltage:g} V",
)


test_temperature = selected_row.get(
    "시험온도",
    np.nan,
)


c4.metric(
    "시험온도",
    (
        f"{test_temperature:g} ℃"
        if pd.notna(test_temperature)
        else "-"
    ),
)


# ============================================================
# BASIC INFORMATION
# ============================================================

st.subheader("MLCC 기본 정보")


i1, i2, i3, i4 = st.columns(4)


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


i1.metric(
    "정격전압",
    (
        f"{rated_voltage:g} V"
        if pd.notna(rated_voltage)
        else "-"
    ),
)


i2.metric(
    "정격용량",
    (
        f"{rated_capacity:g} µF"
        if pd.notna(rated_capacity)
        else "-"
    ),
)


i3.metric(
    "Grade",
    grade if grade else "-",
)


i4.metric(
    "Size",
    format_number(size),
)


# ============================================================
# INITIAL AGING RESULT
# ============================================================

st.subheader("초기 Aging 평가결과")


initial_cap = selected_row.get(
    "① 25℃, 0V",
    np.nan,
)

no_bias = selected_row.get(
    "②고온+No Bias",
    np.nan,
)

dc_bias = selected_row.get(
    "③ 고온+DC Bias",
    np.nan,
)

delta_c = selected_row.get(
    "△C (①-③)/①",
    np.nan,
)


m1, m2, m3, m4 = st.columns(4)


m1.metric(
    "25℃ / 0V",
    (
        f"{initial_cap:.4f} µF"
        if pd.notna(initial_cap)
        else "-"
    ),
)


m2.metric(
    "고온 / No Bias",
    (
        f"{no_bias:.4f} µF"
        if pd.notna(no_bias)
        else "-"
    ),
)


m3.metric(
    "고온 / DC Bias",
    (
        f"{dc_bias:.4f} µF"
        if pd.notna(dc_bias)
        else "-"
    ),
)


m4.metric(
    "초기 대비 ΔC",
    format_percent(delta_c),
)


# ============================================================
# AGING DATA DEFINITIONS
# ============================================================

measured_time_map = {
    "24hr": 24,
    "48hr": 48,
    "72hr": 72,
    "96hr": 96,
    "200hr": 200,
    "500hr": 500,
    "1,000hr": 1000,
}


long_term_map = {
    "8,760hr": 8760,
    "43,800hr": 43800,
    "61,320hr": 61320,
    "87,600hr": 87600,
}


# ============================================================
# MEASURED DATAFRAME
# ============================================================

measured_rows = []


for column, hour in measured_time_map.items():

    if column not in selected_row.index:
        continue

    value = selected_row[column]

    if pd.notna(value):

        measured_rows.append(
            {
                "시간(hr)": hour,
                "잔여용량(uF)": float(value),
                "구분": "실측",
            }
        )


measured_df = pd.DataFrame(
    measured_rows
)


# ============================================================
# LONG TERM DATAFRAME
# ============================================================

long_term_rows = []


for column, hour in long_term_map.items():

    if column not in selected_row.index:
        continue

    value = selected_row[column]

    if pd.notna(value):

        long_term_rows.append(
            {
                "시간(hr)": hour,
                "잔여용량(uF)": float(value),
                "구분": "장기 산출",
            }
        )


long_term_df = pd.DataFrame(
    long_term_rows
)


# ============================================================
# TAB STRUCTURE
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
# TAB 1 : CAPACITY
# ============================================================

with tab1:

    st.subheader(
        "시간경과에 따른 Aging 특성"
    )

    fig = go.Figure()


    # --------------------------------------------------------
    # Measured data
    # --------------------------------------------------------

    if not measured_df.empty:

        fig.add_trace(
            go.Scatter(
                x=measured_df["시간(hr)"],
                y=measured_df["잔여용량(uF)"],

                mode="lines+markers",

                name="Aging 실측",

                marker=dict(
                    size=9,
                ),

                line=dict(
                    width=3,
                ),

                hovertemplate=(
                    "시간: %{x:,.0f} hr"
                    "<br>잔여용량: %{y:.5f} µF"
                    "<extra></extra>"
                ),
            )
        )


    # --------------------------------------------------------
    # Long term Excel result
    # --------------------------------------------------------

    if not long_term_df.empty:

        fig.add_trace(
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


    fig.update_layout(
        height=520,

        xaxis_title="경과시간 (hr)",

        yaxis_title="잔여용량 (µF)",

        hovermode="closest",

        legend_title="",

        margin=dict(
            l=20,
            r=20,
            t=30,
            b=20,
        ),
    )


    fig.update_xaxes(
        type="log",
    )


    st.plotly_chart(
        fig,
        use_container_width=True,
    )


    st.caption(
        "실선은 Aging 실측값이며, Diamond는 Excel에 저장된 "
        "장기 Aging 산출값입니다. Python에서 별도의 장기 회귀를 "
        "수행하지 않습니다."
    )


    # --------------------------------------------------------
    # Data table
    # --------------------------------------------------------

    chart_table_parts = []


    if not measured_df.empty:
        chart_table_parts.append(
            measured_df
        )


    if not long_term_df.empty:
        chart_table_parts.append(
            long_term_df
        )


    if chart_table_parts:

        chart_table = pd.concat(
            chart_table_parts,
            ignore_index=True,
        ).sort_values(
            "시간(hr)"
        )


        with st.expander(
            "그래프 원본 데이터"
        ):

            st.dataframe(
                chart_table,
                hide_index=True,
                use_container_width=True,
            )


# ============================================================
# TAB 2 : REMAINING RATE
# ============================================================

with tab2:

    st.subheader(
        "초기 대비 Aging 잔여율"
    )


    remaining_rows = []


    if pd.notna(initial_cap) and initial_cap != 0:

        # Initial reference
        remaining_rows.append(
            {
                "시간(hr)": 0,
                "잔여율(%)": 100.0,
                "구분": "초기",
            }
        )


        # Measured
        for _, row in measured_df.iterrows():

            remaining_rows.append(
                {
                    "시간(hr)":
                        row["시간(hr)"],

                    "잔여율(%)":
                        (
                            row["잔여용량(uF)"]
                            / initial_cap
                            * 100
                        ),

                    "구분":
                        "실측",
                }
            )


        # Long term
        for _, row in long_term_df.iterrows():

            remaining_rows.append(
                {
                    "시간(hr)":
                        row["시간(hr)"],

                    "잔여율(%)":
                        (
                            row["잔여용량(uF)"]
                            / initial_cap
                            * 100
                        ),

                    "구분":
                        "장기 산출",
                }
            )


    remaining_df = pd.DataFrame(
        remaining_rows
    )


    if not remaining_df.empty:

        # log 축에서는 0 표시 불가하므로
        # 실제 그래프에서는 초기점을 제외
        graph_remaining_df = remaining_df[
            remaining_df["시간(hr)"] > 0
        ].copy()


        fig_remaining = go.Figure()


        measured_remaining = graph_remaining_df[
            graph_remaining_df["구분"]
            == "실측"
        ]


        long_remaining = graph_remaining_df[
            graph_remaining_df["구분"]
            == "장기 산출"
        ]


        if not measured_remaining.empty:

            fig_remaining.add_trace(
                go.Scatter(
                    x=measured_remaining[
                        "시간(hr)"
                    ],

                    y=measured_remaining[
                        "잔여율(%)"
                    ],

                    mode="lines+markers",

                    name="Aging 실측",

                    marker=dict(
                        size=9,
                    ),

                    line=dict(
                        width=3,
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
                    x=long_remaining[
                        "시간(hr)"
                    ],

                    y=long_remaining[
                        "잔여율(%)"
                    ],

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


        display_remaining = (
            remaining_df
            .copy()
        )


        display_remaining[
            "잔여율(%)"
        ] = display_remaining[
            "잔여율(%)"
        ].round(4)


        st.dataframe(
            display_remaining,
            hide_index=True,
            use_container_width=True,
        )


    else:

        st.info(
            "초기용량 데이터가 없어 잔여율을 계산할 수 없습니다."
        )


# ============================================================
# TAB 3 : LONG TERM RESULT
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


    s1, s2, s3 = st.columns(3)


    s1.metric(
        "7년 잔여용량",
        (
            f"{seven_capacity:.5f} µF"
            if pd.notna(seven_capacity)
            else "-"
        ),
    )


    s2.metric(
        "7년 잔여율",
        format_percent(
            seven_remaining
        ),
    )


    s3.metric(
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


    t1, t2, t3 = st.columns(3)


    t1.metric(
        "10년 잔여용량",
        (
            f"{ten_capacity:.5f} µF"
            if pd.notna(ten_capacity)
            else "-"
        ),
    )


    t2.metric(
        "10년 잔여율",
        format_percent(
            ten_remaining
        ),
    )


    t3.metric(
        "10년 감소율",
        format_percent(
            ten_decrease
        ),
    )


    # --------------------------------------------------------
    # Long-term table
    # --------------------------------------------------------

    if not long_term_df.empty:

        st.markdown(
            "#### 시간별 장기 산출값"
        )


        long_display = (
            long_term_df[
                [
                    "시간(hr)",
                    "잔여용량(uF)",
                ]
            ]
            .copy()
        )


        def hour_to_period(hour):

            mapping = {
                8760: "1년",
                43800: "5년",
                61320: "7년",
                87600: "10년",
            }

            return mapping.get(
                int(hour),
                f"{hour:,.0f} hr",
            )


        long_display.insert(
            0,
            "기간",
            long_display[
                "시간(hr)"
            ].apply(
                hour_to_period
            ),
        )


        if (
            pd.notna(initial_cap)
            and initial_cap != 0
        ):

            long_display[
                "초기 대비 잔여율(%)"
            ] = (
                long_display[
                    "잔여용량(uF)"
                ]
                / initial_cap
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


        st.dataframe(
            long_display,
            hide_index=True,
            use_container_width=True,
        )


# ============================================================
# TAB 4 : SUPPLIER COMPARISON
# ============================================================

with tab4:

    st.subheader(
        "동일 자재코드 부품사 Aging 비교"
    )


    st.caption(
        f"자재코드 {selected_material}의 "
        "부품사별 Aging 특성을 비교합니다."
    )


    same_voltage_only = st.checkbox(
        "동일 시험전압 조건만 비교",
        value=True,
        key="aging_same_voltage",
    )


    comparison_source = df[
        df["자재코드"]
        == selected_material
    ].copy()


    if same_voltage_only:

        comparison_source = comparison_source[
            comparison_source["시험전압"]
            == selected_voltage
        ].copy()


    comparison_source = latest_rows(
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


        for column, hour in measured_time_map.items():

            if column not in row.index:
                continue


            value = row[column]


            if pd.notna(value):

                comparison_rows.append(
                    {
                        "부품사":
                            supplier,

                        "시험전압":
                            voltage,

                        "시간(hr)":
                            hour,

                        "잔여용량(uF)":
                            float(value),

                        "구분":
                            (
                                f"{supplier} / "
                                f"{voltage:g}V"
                            ),
                    }
                )


    comparison_df = pd.DataFrame(
        comparison_rows
    )


    if not comparison_df.empty:

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

            xaxis_title=
                "경과시간 (hr)",

            yaxis_title=
                "잔여용량 (µF)",

            legend_title="",

            hovermode="closest",
        )


        st.plotly_chart(
            fig_compare,
            use_container_width=True,
        )


    else:

        st.info(
            "현재 조건에서 비교 가능한 Aging 데이터가 없습니다."
        )


    # ========================================================
    # LONG TERM SUPPLIER COMPARISON
    # ========================================================

    st.markdown(
        "#### 부품사별 7년 / 10년 잔여율"
    )


    supplier_long_rows = []


    for _, row in comparison_source.iterrows():

        supplier = row["부품사"]
        voltage = row["시험전압"]


        seven = percent_value(
            row.get(
                "7년 잔여율",
                np.nan,
            )
        )


        ten = percent_value(
            row.get(
                "10년 잔여율",
                np.nan,
            )
        )


        label = (
            f"{supplier} / "
            f"{voltage:g}V"
        )


        if pd.notna(seven):

            supplier_long_rows.append(
                {
                    "부품사 / 시험전압":
                        label,

                    "기간":
                        "7년",

                    "잔여율(%)":
                        seven,
                }
            )


        if pd.notna(ten):

            supplier_long_rows.append(
                {
                    "부품사 / 시험전압":
                        label,

                    "기간":
                        "10년",

                    "잔여율(%)":
                        ten,
                }
            )


    supplier_long_df = pd.DataFrame(
        supplier_long_rows
    )


    if not supplier_long_df.empty:

        fig_supplier_long = px.bar(
            supplier_long_df,

            x="부품사 / 시험전압",

            y="잔여율(%)",

            color="기간",

            barmode="group",

            text_auto=".2f",
        )


        fig_supplier_long.update_layout(
            height=480,

            xaxis_title="",

            yaxis_title="잔여율 (%)",

            legend_title="",
        )


        st.plotly_chart(
            fig_supplier_long,
            use_container_width=True,
        )


# ============================================================
# RAW DATA
# ============================================================

st.divider()


with st.expander(
    "선택 데이터 전체 보기"
):

    st.dataframe(
        selected_df,
        hide_index=True,
        use_container_width=True,
    )


with st.expander(
    "전체 Aging 데이터"
):

    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()


f1, f2, f3 = st.columns(3)


f1.caption(
    f"Aging 데이터: {len(df):,}건"
)


f2.caption(
    f"부품사: {df['부품사'].nunique():,}개"
)


f3.caption(
    f"자재코드: {df['자재코드'].nunique():,}개"
)
```
