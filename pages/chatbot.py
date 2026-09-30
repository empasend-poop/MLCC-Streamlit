import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from utils.chatbot_engine import ReliabilityChatbot

st.title("💬 Reliability Excel Chatbot")
st.caption("Excel 데이터를 비교 그래프 중심으로 조회합니다.")


def _clean_log_time_axis(fig):
    """Aging 시간축: 자동 2/5 보조눈금을 숨기고 의미 있는 시간만 표시."""
    fig.update_xaxes(
        type="log",
        tickmode="array",
        tickvals=[48, 72, 96, 200, 500, 1000, 8760, 43800, 87600],
        ticktext=["48", "72", "96", "200", "500", "1k", "8.76k", "43.8k", "87.6k"],
        minor=dict(ticks="", showgrid=False),
        title="경과시간 (hr)",
    )
    return fig

def get_chatbot():
    # 코드 교체 후 이전 클래스 객체가 남는 문제를 막기 위해 resource cache를 사용하지 않음
    return ReliabilityChatbot()


def render_lifetime(bot, material, supplier, temperature, voltage=None, key_prefix="life"):
    all_data = bot.lifetime_comparison(material, temperature)
    if all_data.empty:
        st.warning("해당 자재코드의 수명평가 데이터가 없습니다.")
        return

    # 같은 전압끼리만 비교. 전압 미지정 시 가장 많은 부품사가 존재하는 전압 선택.
    if voltage is None:
        counts = all_data.groupby("사용전압(V)")["부품사"].nunique()
        voltage = float(counts.sort_values(ascending=False).index[0])

    data = bot.lifetime_comparison(material, temperature, voltage)
    if supplier:
        data = data[data["부품사"] == supplier]

    if data.empty:
        st.warning(f"{voltage:g}V 조건에서 비교 가능한 수명 데이터가 없습니다.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("사용전압", f"{voltage:g} V")
    c2.metric("비교온도", f"{temperature} ℃")
    c3.metric("비교 부품사", f"{data['부품사'].nunique()}개")

    fig = px.bar(
        data, x="부품사", y="예측수명", color="부품사",
        text="예측수명",
        title=f"{material} · {voltage:g}V · {temperature}℃ 수명 비교",
    )
    fig.update_traces(texttemplate="%{text:,.1f}", textposition="outside")
    fig.update_layout(
        xaxis_title="부품사", yaxis_title="예측수명",
        legend_title_text="", height=450,
    )
    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_chart")

    detail = bot.lifetime_rows(material, supplier, temperature, voltage)
    if not detail.empty:
        temp_col = f"{temperature}℃"
        if temp_col in detail.columns:
            detail = detail.rename(columns={temp_col: f"{temperature}℃ 예측수명"})
        st.dataframe(detail, hide_index=True, use_container_width=True)


def render_aging(bot, material=None, supplier=None, voltage=None, key_prefix="aging"):
    # 전압별 비교를 원칙으로 함. 미지정 시 비교 가능한 전압을 UI에서 선택.
    voltages = bot.available_aging_voltages(material, supplier)
    if not voltages:
        st.warning("해당 조건의 Aging 데이터가 없습니다.")
        return

    if voltage not in voltages:
        voltage = voltages[0]

    if len(voltages) > 1:
        voltage = st.selectbox(
            "비교 시험전압",
            voltages,
            index=voltages.index(voltage),
            format_func=lambda x: f"{x:g} V",
            key=f"{key_prefix}_voltage",
        )

    data = bot.aging_comparison(material, supplier, voltage)
    if data.empty:
        st.warning("비교 가능한 Aging 데이터가 없습니다.")
        return

    # 같은 부품사 내 여러 자재, 또는 같은 자재의 여러 부품사가 모두 구분되도록 라벨 구성
    data["비교대상"] = (
        data["부품사"].astype(str)
        + " / "
        + data["자재코드"].astype(str)
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("시험전압", f"{voltage:g} V")
    c2.metric("비교 부품사", f"{data['부품사'].nunique()}개")
    c3.metric("비교 자재", f"{data['자재코드'].nunique()}개")

    fig = go.Figure()
    palette = px.colors.qualitative.Plotly

    for idx, label in enumerate(data["비교대상"].drop_duplicates()):
        part = data[data["비교대상"] == label].sort_values("시간(hr)")
        measured = part[part["구분"] == "실측"]
        predicted = part[part["구분"] == "회귀분석 예측"].copy()
        color = palette[idx % len(palette)]

        if not measured.empty:
            fig.add_trace(go.Scatter(
                x=measured["시간(hr)"], y=measured["잔여용량(uF)"],
                mode="lines+markers", name=f"{label} 실측",
                legendgroup=label,
                line=dict(width=3, color=color),
                marker=dict(size=8, color=color),
            ))

        if not predicted.empty:
            # 마지막 실측점에서 점선 예측을 연결
            if not measured.empty:
                last = measured.iloc[-1]
                bridge = predicted.iloc[[0]].copy()
                bridge["시간(hr)"] = last["시간(hr)"]
                bridge["잔여용량(uF)"] = last["잔여용량(uF)"]
                bridge["잔여율(%)"] = last["잔여율(%)"]
                bridge["구분"] = "회귀분석 예측"
                predicted = (
                    pd.concat([bridge, predicted], ignore_index=True)
                    .sort_values("시간(hr)")
                )
            fig.add_trace(go.Scatter(
                x=predicted["시간(hr)"], y=predicted["잔여용량(uF)"],
                mode="lines+markers", name=f"{label} 예측",
                legendgroup=label,
                line=dict(width=3, dash="dash", color=color),
                marker=dict(size=8, symbol="diamond", color=color),
            ))

    fig.update_xaxes(type="log")
    fig.update_layout(
        height=540, xaxis_title="경과시간 (hr)", yaxis_title="잔여용량 (µF)",
        legend_title="", title=f"Aging 비교 · {voltage:g}V",
    )
    _clean_log_time_axis(fig)
    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_capacity")

    # 잔여율도 실측 마지막 점에서 회귀분석 예측 점선이 정확히 이어지도록 직접 그림
    rate = data.dropna(subset=["잔여율(%)"]).copy()
    if not rate.empty:
        fig_rate = go.Figure()

        for idx, label in enumerate(rate["비교대상"].drop_duplicates()):
            part = rate[rate["비교대상"] == label].sort_values("시간(hr)")
            measured = part[part["구분"] == "실측"].copy()
            predicted = part[part["구분"] == "회귀분석 예측"].copy()
            color = palette[idx % len(palette)]

            if not measured.empty:
                fig_rate.add_trace(go.Scatter(
                    x=measured["시간(hr)"],
                    y=measured["잔여율(%)"],
                    mode="lines+markers",
                    name=f"{label} 실측",
                    legendgroup=label,
                    line=dict(width=3, color=color),
                    marker=dict(size=8, color=color),
                ))

            if not predicted.empty:
                if not measured.empty:
                    last = measured.iloc[-1]
                    bridge = predicted.iloc[[0]].copy()
                    bridge["시간(hr)"] = last["시간(hr)"]
                    bridge["잔여율(%)"] = last["잔여율(%)"]
                    bridge["구분"] = "회귀분석 예측"
                    predicted = (
                        pd.concat([bridge, predicted], ignore_index=True)
                        .sort_values("시간(hr)")
                    )

                fig_rate.add_trace(go.Scatter(
                    x=predicted["시간(hr)"],
                    y=predicted["잔여율(%)"],
                    mode="lines+markers",
                    name=f"{label} 회귀분석 예측",
                    legendgroup=label,
                    line=dict(width=3, dash="dash", color=color),
                    marker=dict(size=8, symbol="diamond", color=color),
                ))

        fig_rate.update_xaxes(type="log")
        fig_rate.update_layout(
            height=480,
            xaxis_title="경과시간 (hr)",
            yaxis_title="초기 대비 잔여율 (%)",
            legend_title="",
            title=f"Aging 잔여율 비교 · {voltage:g}V",
        )
        _clean_log_time_axis(fig_rate)
        st.plotly_chart(
            fig_rate,
            use_container_width=True,
            key=f"{key_prefix}_rate",
        )



def render_bdv(bot, material, supplier=None, key_prefix="bdv"):
    data = bot.bdv_comparison(material, supplier)
    if data.empty:
        st.warning("해당 조건의 BDV 평가 데이터가 없습니다.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("비교 부품사", f"{data['부품사'].nunique()}개")
    if "정격전압(V)" in data.columns:
        rated = data["정격전압(V)"].dropna()
        c2.metric("정격전압", f"{rated.iloc[0]:g} V" if not rated.empty else "-")
    else:
        c2.metric("정격전압", "-")
    if "1ppm Lower" in data.columns:
        lower = data["1ppm Lower"].dropna()
        c3.metric("1ppm Lower 범위", f"{lower.min():.1f} ~ {lower.max():.1f} V" if not lower.empty else "-")
    else:
        c3.metric("1ppm Lower 범위", "-")

    # 핵심 비교: 정격전압과 1ppm Lower를 같은 부품사 기준으로 비교
    fig = go.Figure()
    if "정격전압(V)" in data.columns:
        fig.add_trace(go.Bar(
            x=data["부품사"], y=data["정격전압(V)"],
            name="정격전압", text=data["정격전압(V)"],
            textposition="outside",
        ))
    if "1ppm Lower" in data.columns:
        fig.add_trace(go.Bar(
            x=data["부품사"], y=data["1ppm Lower"],
            name="BDV 1ppm Lower", text=data["1ppm Lower"],
            textposition="outside",
        ))
    if "10ppm Lower" in data.columns:
        fig.add_trace(go.Bar(
            x=data["부품사"], y=data["10ppm Lower"],
            name="BDV 10ppm Lower", text=data["10ppm Lower"],
            textposition="outside",
        ))

    fig.update_layout(
        barmode="group",
        height=470,
        title=f"{material} · 부품사별 BDV 비교",
        xaxis_title="부품사",
        yaxis_title="전압 (V)",
        legend_title="",
    )
    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_chart")

    display_cols = [c for c in [
        "부품사", "정격전압(V)", "BDV 결과 (Typ.)",
        "1ppm Lower", "1ppm Typ.", "10ppm Lower", "10ppm Typ.",
        "1ppm Lower / 정격전압 (배)"
    ] if c in data.columns]
    st.dataframe(data[display_cols], hide_index=True, use_container_width=True)


def render_overall(bot, material, supplier=None, temperature=85, voltage=None, key_prefix="overall"):
    availability = bot.evaluation_availability(material)

    c1, c2, c3 = st.columns(3)
    c1.metric("수명평가", "보유" if availability["수명"] else "없음")
    c2.metric("Aging평가", "보유" if availability["Aging"] else "없음")
    c3.metric("BDV평가", "보유" if availability["BDV"] else "없음")

    # 전체 평가에서는 데이터가 존재하는 평가만 순서대로 표시
    if availability["수명"]:
        st.markdown("### ⏱️ 수명 평가")
        render_lifetime(
            bot, material, supplier, temperature, voltage,
            key_prefix=f"{key_prefix}_life",
        )

    if availability["Aging"]:
        st.markdown("### 📉 Aging 평가")
        render_aging(
            bot, material, supplier, voltage,
            key_prefix=f"{key_prefix}_aging",
        )

    if availability["BDV"]:
        st.markdown("### ⚡ BDV 평가")
        render_bdv(
            bot, material, supplier,
            key_prefix=f"{key_prefix}_bdv",
        )


st.markdown("#### 💡 질문 예시")
examples = [
    "2203-008953 2.0V 85도 수명 비교해줘",
    "2203-010255 5.0V 100도 수명 비교해줘",
    "2203-008491 3.3V Aging 열화 추이 보여줄래?",
    "2203-010255 5.0V Aging 부품사 비교해줘",
    "2203-000699 BDV 부품사 비교해줘",
    "2203-008953 전체 평가결과 보여줘",
]
cols = st.columns(2)
for i, q in enumerate(examples):
    if cols[i % 2].button(q, key=f"example_{i}", use_container_width=True):
        st.session_state["pending_question"] = q

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

with st.sidebar:
    if st.button("챗봇 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.session_state.chat_history = []
        st.session_state.pop("last_result_context", None)
        st.rerun()

bot = get_chatbot()

with st.sidebar:
    try:
        from utils.llm_engine import groq_available
        if groq_available():
            st.success("🧠 Groq LLM: 사용 가능")
            st.caption("API 오류/무료 한도 초과 시 규칙 기반으로 자동 전환")
        else:
            st.info("🔧 규칙 기반 모드")
            st.caption("GROQ_API_KEY를 설정하면 LLM 질문 해석이 활성화됩니다.")
    except Exception:
        st.info("🔧 규칙 기반 모드")

for idx, item in enumerate(st.session_state.chat_history):
    with st.chat_message(item["role"]):
        st.markdown(item["text"])
        if item["role"] == "assistant" and item.get("answer_mode"):
            if item["answer_mode"] == "groq":
                st.caption("🧠 Groq 질문 해석 · Excel 데이터 조회")
            elif item["answer_mode"] == "groq_analysis":
                st.caption("🧠 Groq 후속 분석 · 직전 Excel 조회 결과 기반")
            else:
                st.caption("🔧 규칙 기반 자동 fallback · Excel 데이터 조회")
        if item.get("show_lifetime"):
            render_lifetime(
                bot, item["material"], item.get("supplier"),
                item.get("temperature", 85), item.get("voltage"),
                key_prefix=f"life_{idx}",
            )
        if item.get("show_aging"):
            render_aging(
                bot, item.get("material"), item.get("supplier"),
                item.get("voltage"), key_prefix=f"aging_{idx}",
            )
        if item.get("show_bdv"):
            render_bdv(
                bot, item.get("material"), item.get("supplier"),
                key_prefix=f"bdv_{idx}",
            )
        if item.get("show_overall"):
            render_overall(
                bot, item.get("material"), item.get("supplier"),
                item.get("temperature", 85), item.get("voltage"),
                key_prefix=f"overall_{idx}",
            )
        if item.get("ai_analysis"):
            st.markdown("### 🧠 AI 분석 요약")
            st.markdown(item["ai_analysis"])

typed = st.chat_input("예: 2203-007317 BDV 부품사 비교해줘")
clicked = st.session_state.pop("pending_question", None)
question = typed or clicked

if question:
    st.session_state.chat_history.append({"role": "user", "text": question})
    previous_context = st.session_state.get("last_result_context")
    result = bot.short_answer(question, previous_context=previous_context)
    if result.get("context"):
        st.session_state["last_result_context"] = result["context"]
    st.session_state.chat_history.append({"role": "assistant", **result})
    st.rerun()
