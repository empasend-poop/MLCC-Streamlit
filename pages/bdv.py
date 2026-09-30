import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from utils.data_loader import get_bdv_data

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



def fmt(value, digits=1, suffix=""):
    if pd.isna(value): return "-"
    try: return f"{float(value):,.{digits}f}{suffix}"
    except (TypeError, ValueError): return str(value)


def latest_rows(data, subset):
    result = data.copy()
    if "업데이트일자" in result.columns:
        result["_date"] = pd.to_datetime(result["업데이트일자"], errors="coerce")
        result = result.sort_values("_date")
    result = result.drop_duplicates(subset=subset, keep="last")
    return result.drop(columns=["_date"], errors="ignore")


try:
    df = get_bdv_data().copy()
except Exception as error:
    st.error("BDV Excel 데이터를 불러오는 중 오류가 발생했습니다.")
    st.exception(error)
    st.stop()

required = ["부품사", "자재코드", "정격전압(V)", "BDV 결과 (Typ.)", "1ppm Lower"]
missing = [c for c in required if c not in df.columns]
if missing:
    st.error(f"BDV 필수 컬럼이 없습니다: {missing}")
    st.write("현재 컬럼:", list(df.columns))
    st.stop()

st.title("⚡ MLCC BDV 분석")
st.caption("BDV 평가결과와 1ppm/10ppm 전압을 확인하고 동일 자재코드의 부품사 결과를 비교합니다.")

with st.sidebar:
    st.header("BDV 분석 조건")
    if st.button("BDV 데이터 새로고침", use_container_width=True, key="bdv_refresh"):
        st.cache_data.clear(); st.rerun()
    st.divider()
    suppliers = sorted(df["부품사"].dropna().astype(str).unique().tolist())
    if not suppliers: st.error("부품사 데이터가 없습니다."); st.stop()
    supplier = st.selectbox("부품사", suppliers, key="bdv_supplier")
    supplier_df = df[df["부품사"].astype(str) == supplier]
    materials = sorted(supplier_df["자재코드"].dropna().astype(str).unique().tolist())
    if not materials: st.warning("선택한 부품사에 자재코드가 없습니다."); st.stop()
    material = st.selectbox("자재코드", materials, key="bdv_material")

selected = df[(df["부품사"].astype(str) == supplier) & (df["자재코드"].astype(str) == material)].copy()
selected = latest_rows(selected, ["부품사", "자재코드"])
if selected.empty: st.warning("선택 조건에 해당하는 BDV 데이터가 없습니다."); st.stop()
row = selected.iloc[-1]

section_title("선택 조건")
c1,c2,c3,c4 = st.columns(4)
c1.metric("부품사", supplier)
c2.metric("자재코드", material)
c3.metric("정격전압", fmt(row.get("정격전압(V)"),1," V"))
c4.metric("정격용량", fmt(row.get("정격용량(uF)"),1," µF"))

section_title("MLCC 기본 정보")
c1,c2,c3,c4 = st.columns(4)
c1.metric("Grade", str(row.get("Grade", "-")))
c2.metric("Size", fmt(row.get("Size", np.nan),0))
c3.metric("BDV 평가수량", fmt(row.get("BDV평가수량"),0," ea"))
c4.metric("BDV 평가온도", fmt(row.get("BDV평가온도"),0," ℃"))

section_title("BDV 평가결과")
c1,c2,c3,c4 = st.columns(4)
c1.metric("BDV 결과 (Typ.)", fmt(row.get("BDV 결과 (Typ.)"),1," V"))
c2.metric("정격 대비 BDV Typ.", fmt(row.get("정격대비수준"),1," 배"))
c3.metric("1ppm Lower / 정격전압", fmt(row.get("1ppm Lower / 정격전압 (배)"),1," 배"))
c4.metric("정격전압 / 1ppm Lower", fmt(row.get("정격전압 / 1ppm Lower (%)"),2,"%"))

result_table = pd.DataFrame({
    "구분":["1ppm","10ppm"],
    "Lower (V)":[row.get("1ppm Lower"),row.get("10ppm Lower")],
    "Typ. (V)":[row.get("1ppm Typ."),row.get("10ppm Typ.")],
    "Upper (V)":[row.get("1ppm Upper"),row.get("10ppm Upper")],
}).round(1)
section_title("1ppm / 10ppm 산출 전압")
st.dataframe(result_table, hide_index=True, use_container_width=True)

fig = go.Figure()
for label,prefix in [("1ppm","1ppm"),("10ppm","10ppm")]:
    fig.add_trace(go.Scatter(x=["Lower","Typ.","Upper"],
        y=[row.get(f"{prefix} Lower"),row.get(f"{prefix} Typ."),row.get(f"{prefix} Upper")],
        mode="lines+markers", name=label,
        hovertemplate="%{x}: %{y:,.1f} V<extra></extra>"))
fig.add_hline(y=float(row["정격전압(V)"]), line_dash="dash",
              annotation_text=f"정격전압 {float(row['정격전압(V)']):g} V")
fig.update_layout(height=440,xaxis_title="산출 구간",yaxis_title="BDV 전압 (V)",legend_title="")
st.plotly_chart(fig,use_container_width=True)

st.divider(); section_title("동일 자재코드 부품사 BDV 비교"); st.caption(f"자재코드 {material} 기준")
compare = latest_rows(df[df["자재코드"].astype(str)==material],["부품사","자재코드"]).sort_values("부품사")
fig2 = go.Figure()
fig2.add_trace(go.Bar(x=compare["부품사"],y=compare["BDV 결과 (Typ.)"],name="BDV 결과 (Typ.)"))
fig2.add_trace(go.Scatter(x=compare["부품사"],y=compare["1ppm Lower"],mode="lines+markers",name="1ppm Lower"))
fig2.add_trace(go.Scatter(x=compare["부품사"],y=compare["10ppm Lower"],mode="lines+markers",name="10ppm Lower"))
fig2.update_layout(height=520,xaxis_title="부품사",yaxis_title="전압 (V)",legend_title="",hovermode="x unified")
st.plotly_chart(fig2,use_container_width=True)

cols=["부품사","자재코드","정격전압(V)","BDV 결과 (Typ.)","1ppm Lower","1ppm Typ.","1ppm Upper","10ppm Lower","10ppm Typ.","10ppm Upper","1ppm Lower / 정격전압 (배)"]
cols=[c for c in cols if c in compare.columns]
st.dataframe(compare[cols].round(2),hide_index=True,use_container_width=True)
with st.expander("현재 선택 데이터 전체 보기"):
    st.dataframe(selected,hide_index=True,use_container_width=True)
with st.expander("전체 BDV 데이터 보기"):
    st.dataframe(df,hide_index=True,use_container_width=True)
