from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# ============================================================
# 1. 기본 설정
# ============================================================

st.set_page_config(
    page_title="MLCC 수명 Dashboard",
    page_icon="📊",
    layout="wide",
)


# Excel 파일 위치
BASE_DIR = Path(__file__).resolve().parent
EXCEL_FILE = BASE_DIR / "test_수명.xlsx"

# Excel 원본 시트명
SHEET_NAME = "수명"

# Excel에서 실제 데이터 헤더가 위치한 행
# 원본 파일 기준:
# 6행 = MLCC 정보 / 가속평가 기반...
# 7행 = 실제 컬럼명
#
# pandas는 0부터 세므로 header=6
HEADER_ROW = 6


# ============================================================
# 2. 디자인
# ============================================================

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1600px;
        }

        h1 {
            color: #17365D;
        }

        div[data-testid="stMetric"] {
            background-color: #F7F9FC;
            border: 1px solid #E2E8F0;
            padding: 15px;
            border-radius: 10px;
        }

        div[data-testid="stMetricLabel"] {
            font-weight: 600;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 3. Excel 데이터 읽기
# ============================================================

@st.cache_data
def load_data(file_path: str, modified_time: float):
    """
    Excel 데이터를 읽는 함수.

    modified_time을 인자로 받는 이유:
    Excel 파일이 수정되면 수정 시간이 달라지므로
    Streamlit cache가 자동으로 무효화되어 최신 데이터를 읽게 된다.
    """

    df = pd.read_excel(
        file_path,
        sheet_name=SHEET_NAME,
        header=HEADER_ROW,
        engine="openpyxl",
    )

    # 완전히 비어있는 행 제거
    df = df.dropna(how="all")

    # 컬럼명 공백 제거
    df.columns = [str(col).strip() for col in df.columns]

    # 핵심 필드가 없는 행 제거
    required_columns = [
        "자재코드",
        "부품사",
        "사용전압(V)",
    ]

    df = df.dropna(
        subset=[
            col
            for col in required_columns
            if col in df.columns
        ]
    )

    # 문자열 데이터 정리
    for col in ["자재코드", "부품사", "부품사코드", "Grade", "Bx수명"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # 사용전압 숫자로 변환
    if "사용전압(V)" in df.columns:
        df["사용전압(V)"] = pd.to_numeric(
            df["사용전압(V)"],
            errors="coerce",
        )

    # 온도별 수명 컬럼 숫자 변환
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

    return df


# ============================================================
# 4. Excel 파일 확인
# ============================================================

if not EXCEL_FILE.exists():

    st.error(
        f"""
        Excel 파일을 찾을 수 없습니다.

        아래 위치에 파일이 있어야 합니다.

        {EXCEL_FILE}
        """
    )

    st.stop()


# Excel 파일의 마지막 수정 시간
modified_time = EXCEL_FILE.stat().st_mtime


try:

    df = load_data(
        str(EXCEL_FILE),
        modified_time,
    )

except Exception as e:

    st.error("Excel 파일을 읽는 중 오류가 발생했습니다.")

    st.exception(e)

    st.stop()


# ============================================================
# 5. 필요한 컬럼 확인
# ============================================================

required_columns = [
    "업데이트일자",
    "자재코드",
    "부품사",
    "부품사코드",
    "Grade",
    "정격전압(V)",
    "정격용량(uF)",
    "Size",
    "사용전압(V)",
    "Bx수명",
    "Ea",
    "n",
    "형상모수",
    "척도모수",
]


missing_columns = [
    col
    for col in required_columns
    if col not in df.columns
]


if missing_columns:

    st.error(
        "Excel에서 필요한 컬럼을 찾을 수 없습니다."
    )

    st.write("없는 컬럼:")

    st.write(missing_columns)

    st.write("현재 Excel 컬럼:")

    st.write(list(df.columns))

    st.stop()


# ============================================================
# 6. 제목
# ============================================================

st.title("MLCC 수명 Dashboard")

st.caption(
    "부품사 → 자재코드 → 사용전압(V)을 선택하면 "
    "해당 조건의 MLCC 정보와 가속평가 기반 수명산출결과를 표시합니다."
)


# ============================================================
# 7. 사이드바
# ============================================================

with st.sidebar:

    st.header("조회 조건")

    if st.button(
        "데이터 새로고침",
        use_container_width=True,
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


    selected_supplier = st.selectbox(
        "부품사",
        supplier_list,
    )


    # --------------------------------------------------------
    # 자재코드
    # --------------------------------------------------------

    supplier_df = df[
        df["부품사"] == selected_supplier
    ]


    material_list = sorted(
        supplier_df["자재코드"]
        .dropna()
        .unique()
        .tolist()
    )


    selected_material = st.selectbox(
        "자재코드",
        material_list,
    )


    # --------------------------------------------------------
    # 사용전압
    # --------------------------------------------------------

    material_df = supplier_df[
        supplier_df["자재코드"]
        == selected_material
    ]


    voltage_list = sorted(
        material_df["사용전압(V)"]
        .dropna()
        .unique()
        .tolist()
    )


    selected_voltage = st.selectbox(
        "사용전압(V)",
        voltage_list,
        format_func=lambda x: f"{x:g} V",
    )


# ============================================================
# 8. 최종 선택 데이터
# ============================================================

selected_df = df[
    (df["부품사"] == selected_supplier)
    & (df["자재코드"] == selected_material)
    & (df["사용전압(V)"] == selected_voltage)
].copy()


if selected_df.empty:

    st.warning(
        "선택한 조건에 해당하는 데이터가 없습니다."
    )

    st.stop()


# 같은 조건의 데이터가 여러 개 있을 경우
# 가장 마지막 행 사용
selected_row = selected_df.iloc[-1]


# ============================================================
# 9. 선택 조건 표시
# ============================================================

st.subheader("선택 조건")


col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "부품사",
        selected_supplier,
    )


with col2:

    st.metric(
        "자재코드",
        selected_material,
    )


with col3:

    st.metric(
        "사용전압",
        f"{selected_voltage:g} V",
    )


# ============================================================
# 10. MLCC 기본 정보
# ============================================================

st.subheader("MLCC 정보")


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


info_df = pd.DataFrame(
    {
        "항목": info_columns,
        "값": [
            selected_row.get(col, "")
            for col in info_columns
        ],
    }
)


st.dataframe(
    info_df,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# 11. 수명 산출 Parameter
# ============================================================

st.subheader("가속평가 기반, 수명산출 Parameter")


parameter_columns = [
    "Bx수명",
    "Ea",
    "n",
    "형상모수",
    "척도모수",
]


parameter_cols = st.columns(
    len(parameter_columns)
)


for column, parameter in zip(
    parameter_cols,
    parameter_columns,
):

    value = selected_row.get(
        parameter,
        "",
    )

    column.metric(
        parameter,
        value,
    )


# ============================================================
# 12. 온도별 수명 데이터
# ============================================================

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


available_temperature_columns = [
    col
    for col in temperature_columns
    if col in df.columns
]


temperature_df = pd.DataFrame(
    {
        "온도": [
            int(
                col.replace(
                    "℃",
                    "",
                )
            )
            for col
            in available_temperature_columns
        ],

        "수명": [
            selected_row[col]
            for col
            in available_temperature_columns
        ],
    }
)


temperature_df = temperature_df.dropna(
    subset=["수명"]
)


# ============================================================
# 13. 선택 데이터 온도별 수명 그래프
# ============================================================

st.subheader("선택 부품 온도별 수명")


fig_selected = px.line(
    temperature_df,
    x="온도",
    y="수명",
    markers=True,
)


fig_selected.update_layout(
    xaxis_title="온도 (℃)",
    yaxis_title="수명",
    hovermode="x unified",
    height=450,
)


fig_selected.update_traces(
    line=dict(
        width=3,
    ),
    marker=dict(
        size=8,
    ),
)


st.plotly_chart(
    fig_selected,
    use_container_width=True,
)


# ============================================================
# 14. 온도별 수명 표
# ============================================================

with st.expander(
    "온도별 수명 데이터 보기",
    expanded=False,
):

    table_df = temperature_df.copy()

    table_df["온도"] = (
        table_df["온도"]
        .astype(str)
        + "℃"
    )

    st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# 15. 동일 자재코드 부품사 비교
# ============================================================

st.subheader(
    "동일 자재코드 수명 비교"
)


st.caption(
    f"자재코드 {selected_material} / "
    f"사용전압 {selected_voltage:g} V 기준"
)


comparison_source = df[
    (df["자재코드"] == selected_material)
    & (df["사용전압(V)"] == selected_voltage)
].copy()


comparison_rows = []


for _, row in comparison_source.iterrows():

    supplier = row["부품사"]

    for temp_col in available_temperature_columns:

        life = row[temp_col]

        if pd.notna(life):

            comparison_rows.append(
                {
                    "부품사": supplier,
                    "온도": int(
                        temp_col.replace(
                            "℃",
                            "",
                        )
                    ),
                    "수명": life,
                }
            )


comparison_df = pd.DataFrame(
    comparison_rows
)


# ============================================================
# 16. 부품사 비교 그래프
# ============================================================

if not comparison_df.empty:

    fig_compare = px.line(
        comparison_df,
        x="온도",
        y="수명",
        color="부품사",
        markers=True,
    )


    fig_compare.update_layout(
        xaxis_title="온도 (℃)",
        yaxis_title="수명",
        hovermode="x unified",
        height=550,
        legend_title="부품사",
    )


    fig_compare.update_traces(
        line=dict(
            width=3,
        ),
        marker=dict(
            size=8,
        ),
    )


    st.plotly_chart(
        fig_compare,
        use_container_width=True,
    )


else:

    st.info(
        "비교할 수명 데이터가 없습니다."
    )


# ============================================================
# 17. 부품사 비교 데이터 표
# ============================================================

with st.expander(
    "부품사 비교 원본 데이터 보기",
):

    display_columns = [
        "부품사",
        "자재코드",
        "사용전압(V)",
    ] + available_temperature_columns


    st.dataframe(
        comparison_source[
            display_columns
        ],
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# 18. 전체 Excel 데이터
# ============================================================

with st.expander(
    "전체 데이터 보기",
):

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# 19. 데이터 정보
# ============================================================

st.divider()


c1, c2, c3 = st.columns(3)


with c1:

    st.caption(
        f"전체 데이터: {len(df):,}건"
    )


with c2:

    st.caption(
        f"부품사: {df['부품사'].nunique():,}개"
    )


with c3:

    st.caption(
        f"자재코드: {df['자재코드'].nunique():,}개"
    )
