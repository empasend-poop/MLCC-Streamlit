import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_loader import get_lifetime_data

# ============================================================
# DASHBOARD COMMON STYLE
# ============================================================
st.markdown(
    """
    <style>
    :root {
        --section-blue: #178FCB;
        --section-blue-dark: #0F78AE;
        --section-border: #B9DCEB;
        --section-bg: #F7FCFF;
    }

    .mlcc-section-title {
        margin-top: 1.15rem;
        margin-bottom: 0.65rem;
        padding: 0.48rem 0.85rem;
        border-left: 6px solid var(--section-blue-dark);
        border-radius: 6px;
        background: linear-gradient(
            90deg,
            rgba(23,143,203,0.18) 0%,
            rgba(23,143,203,0.07) 55%,
            rgba(23,143,203,0.00) 100%
        );
        color: var(--section-blue-dark);
        font-size: 1.55rem;
        font-weight: 800;
        line-height: 1.35;
    }

    .mlcc-section-divider {
        height: 1px;
        margin: 0.15rem 0 0.85rem 0;
        background: linear-gradient(
            90deg,
            var(--section-border) 0%,
            rgba(185,220,235,0.35) 75%,
            transparent 100%
        );
    }

    div[data-testid="stMetric"] {
        padding: 0.30rem 0.15rem 0.50rem 0.15rem;
    }

    div[data-testid="stMetricLabel"] {
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def section_title(title):
    st.markdown(
        f'<div class="mlcc-section-title">{title}</div>'
        '<div class="mlcc-section-divider"></div>',
        unsafe_allow_html=True,
    )



# ============================================================
# DATA LOAD
# ============================================================

df = get_lifetime_data().copy()


# ============================================================
# DATA CLEANING
# ============================================================

df.columns = [
    str(col).replace("\n", " ").strip()
    for col in df.columns
]


# 문자열 컬럼 정리
string_columns = [
    "자재코드",
    "부품사",
    "부품사코드",
    "Grade",
    "Bx수명",
]

for col in string_columns:
    if col in df.columns:
        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
        )


# 숫자형 컬럼
numeric_columns = [
    "정격전압(V)",
    "정격용량(uF)",
    "Size",
    "사용전압(V)",
    "Ea",
    "n",
    "형상모수",
    "척도모수",
]

for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )


# 온도별 수명 컬럼
temperature_columns = [
    "65℃",
    "70℃",
    "75℃",
    "80℃",
    "85℃",
    "90℃",
    "95℃",
    "100℃",
    "105℃",
    "110℃",
    "115℃",
    "120℃",
    "125℃",
]

for col in temperature_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )


# ============================================================
# PAGE TITLE
# ============================================================

st.title("⏱️ MLCC 수명 분석")

st.caption(
    "부품사 → 자재코드 → 사용전압(V)을 선택하여 "
    "가속평가 기반 수명산출 결과와 부품사별 수명을 비교합니다."
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("수명 분석 조건")


    # --------------------------------------------------------
    # Refresh
    # --------------------------------------------------------

    if st.button(
        "수명 데이터 새로고침",
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
        .unique()
        .tolist()
    )


    if not supplier_list:

        st.error(
            "부품사 데이터가 없습니다."
        )

        st.stop()


    selected_supplier = st.selectbox(
        "부품사",
        supplier_list,
        key="life_supplier",
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
        key="life_material",
    )


    # --------------------------------------------------------
    # Voltage
    # --------------------------------------------------------

    material_df = supplier_df[
        supplier_df["자재코드"]
        == selected_material
    ].copy()


    voltage_list = sorted(
        material_df["사용전압(V)"]
        .dropna()
        .unique()
        .tolist()
    )


    if not voltage_list:

        st.warning(
            "선택한 자재코드에 사용전압 데이터가 없습니다."
        )

        st.stop()


    selected_voltage = st.selectbox(
        "사용전압(V)",
        voltage_list,
        format_func=lambda x: f"{x:g} V",
        key="life_voltage",
    )


# ============================================================
# SELECTED DATA
# ============================================================

selected_df = df[
    (df["부품사"] == selected_supplier)
    & (df["자재코드"] == selected_material)
    & (df["사용전압(V)"] == selected_voltage)
].copy()


if selected_df.empty:

    st.warning(
        "선택 조건에 해당하는 수명 데이터가 없습니다."
    )

    st.stop()


# 업데이트일자가 존재하면 최신 데이터 우선
if "업데이트일자" in selected_df.columns:

    selected_df["_date"] = pd.to_datetime(
        selected_df["업데이트일자"],
        errors="coerce",
    )

    selected_df = selected_df.sort_values(
        "_date"
    )


selected_row = selected_df.iloc[-1]


# ============================================================
# SELECTION SUMMARY
# ============================================================

section_title("선택 조건")


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
    "사용전압",
    f"{selected_voltage:g} V",
)


rated_voltage = selected_row.get(
    "정격전압(V)",
    None,
)


if pd.notna(rated_voltage):

    c4.metric(
        "정격전압",
        f"{rated_voltage:g} V",
    )

else:

    c4.metric(
        "정격전압",
        "-",
    )


# ============================================================
# MLCC INFORMATION
# ============================================================

section_title("MLCC 기본 정보")


info_columns = [
    "업데이트일자",
    "자재코드",
    "부품사",
    "부품사코드",
    "Grade",
    "정격전압(V)",
    "정격용량(uF)",
    "Size",
    "사용전압(V)",
]


info_rows = []


for col in info_columns:

    if col in selected_row.index:

        info_rows.append(
            {
                "항목": col,
                "값": selected_row[col],
            }
        )


info_df = pd.DataFrame(
    info_rows
)


st.dataframe(
    info_df,
    hide_index=True,
    use_container_width=True,
)


# ============================================================
# LIFETIME PARAMETERS
# ============================================================

section_title("가속평가 기반 수명산출 Parameter")


parameter_columns = [
    "Bx수명",
    "Ea",
    "n",
    "형상모수",
    "척도모수",
]


parameter_ui = st.columns(
    len(parameter_columns)
)


for ui, parameter in zip(
    parameter_ui,
    parameter_columns,
):

    value = selected_row.get(
        parameter,
        None,
    )


    if pd.isna(value):

        display_value = "-"

    elif isinstance(
        value,
        (float, int),
    ):

        display_value = f"{value:g}"

    else:

        display_value = str(value)


    ui.metric(
        parameter,
        display_value,
    )


# ============================================================
# TEMPERATURE DATA
# ============================================================

available_temperature_columns = [
    col
    for col in temperature_columns
    if col in df.columns
]


temperature_rows = []


for col in available_temperature_columns:

    value = selected_row[col]


    if pd.notna(value):

        temperature_rows.append(
            {
                "온도(℃)": int(
                    col.replace(
                        "℃",
                        "",
                    )
                ),

                "수명": value,
            }
        )


temperature_df = pd.DataFrame(
    temperature_rows
)


# ============================================================
# SELECTED LIFETIME CHART
# ============================================================

section_title("선택 부품 온도별 수명")


if not temperature_df.empty:

    log_scale = st.toggle(
        "수명 Y축 Log Scale",
        value=True,
        key="life_log_scale",
    )


    fig_selected = px.line(
        temperature_df,
        x="온도(℃)",
        y="수명",
        markers=True,
    )


    fig_selected.update_traces(
        line=dict(
            width=3,
        ),

        marker=dict(
            size=9,
        ),
    )


    fig_selected.update_layout(
        height=500,
        xaxis_title="온도 (℃)",
        yaxis_title="수명",
        hovermode="x unified",
    )


    if log_scale:

        fig_selected.update_yaxes(
            type="log"
        )


    st.plotly_chart(
        fig_selected,
        use_container_width=True,
    )


else:

    st.info(
        "온도별 수명 데이터가 없습니다."
    )


# ============================================================
# TEMPERATURE TABLE
# ============================================================

with st.expander(
    "온도별 수명 데이터 보기"
):

    st.dataframe(
        temperature_df,
        hide_index=True,
        use_container_width=True,
    )


# ============================================================
# SUPPLIER COMPARISON
# ============================================================

st.divider()


section_title("동일 자재코드 부품사별 수명 비교")


st.caption(
    f"자재코드 {selected_material} / "
    f"사용전압 {selected_voltage:g} V 조건"
)


comparison_source = df[
    (df["자재코드"] == selected_material)
    & (df["사용전압(V)"] == selected_voltage)
].copy()


# 같은 회사/자재/전압 데이터가 여러 개면
# 최신 데이터 하나만 사용
if "업데이트일자" in comparison_source.columns:

    comparison_source["_date"] = pd.to_datetime(
        comparison_source["업데이트일자"],
        errors="coerce",
    )


    comparison_source = (
        comparison_source
        .sort_values("_date")
        .drop_duplicates(
            subset=[
                "부품사",
                "자재코드",
                "사용전압(V)",
            ],
            keep="last",
        )
    )


comparison_rows = []


for _, row in comparison_source.iterrows():

    supplier = row["부품사"]


    for temp_col in available_temperature_columns:

        value = row[temp_col]


        if pd.notna(value):

            comparison_rows.append(
                {
                    "부품사": supplier,

                    "온도(℃)": int(
                        temp_col.replace(
                            "℃",
                            "",
                        )
                    ),

                    "수명": value,
                }
            )


comparison_df = pd.DataFrame(
    comparison_rows
)


# ============================================================
# COMPARISON CHART
# ============================================================

if not comparison_df.empty:

    fig_compare = px.line(
        comparison_df,
        x="온도(℃)",
        y="수명",
        color="부품사",
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


    fig_compare.update_layout(
        height=550,
        xaxis_title="온도 (℃)",
        yaxis_title="수명",
        legend_title="부품사",
        hovermode="x unified",
    )


    if log_scale:

        fig_compare.update_yaxes(
            type="log"
        )


    st.plotly_chart(
        fig_compare,
        use_container_width=True,
    )


else:

    st.info(
        "비교 가능한 부품사 데이터가 없습니다."
    )


# ============================================================
# COMPARISON TABLE
# ============================================================

with st.expander(
    "부품사별 수명 비교 데이터"
):

    comparison_table = comparison_source.drop(
        columns=["_date"],
        errors="ignore",
    )


    display_columns = [
        "부품사",
        "자재코드",
        "Grade",
        "정격전압(V)",
        "정격용량(uF)",
        "사용전압(V)",
    ] + available_temperature_columns


    display_columns = [
        col
        for col in display_columns
        if col in comparison_table.columns
    ]


    st.dataframe(
        comparison_table[
            display_columns
        ],
        hide_index=True,
        use_container_width=True,
    )


# ============================================================
# FULL DATA
# ============================================================

with st.expander(
    "전체 수명 데이터"
):

    full_df = df.drop(
        columns=["_date"],
        errors="ignore",
    )


    st.dataframe(
        full_df,
        hide_index=True,
        use_container_width=True,
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()


f1, f2, f3 = st.columns(3)


f1.caption(
    f"수명 데이터: {len(df):,}건"
)


f2.caption(
    f"부품사: {df['부품사'].nunique():,}개"
)


f3.caption(
    f"자재코드: {df['자재코드'].nunique():,}개"
)
