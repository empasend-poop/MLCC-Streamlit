import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from utils.chatbot_engine import ReliabilityChatbot

st.title("💬 Reliability Excel Chatbot")
st.caption("Excel 데이터를 비교 그래프 중심으로 조회합니다.")

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
                predicted = (
                    __import__("pandas").concat([bridge, predicted], ignore_index=True)
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
    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_capacity")

    # 7년/10년 또는 장기 마지막 시점 비교 대신, 공통 시간축의 잔여율도 제공.
    rate = data.dropna(subset=["잔여율(%)"]).copy()
    if not rate.empty:
        fig_rate = px.line(
            rate, x="시간(hr)", y="잔여율(%)",
            color="비교대상", line_dash="구분",
            markers=True, log_x=True,
            title=f"Aging 잔여율 비교 · {voltage:g}V",
        )
        fig_rate.update_layout(height=480, legend_title="", yaxis_title="초기 대비 잔여율 (%)")
        st.plotly_chart(fig_rate, use_container_width=True, key=f"{key_prefix}_rate")


st.markdown("#### 💡 질문 예시")
examples = [
    "2203-007317 3.15V 85도 수명 비교해줘",
    "2203-007317 Aging 부품사 비교해줘",
    "Supplier A Aging 자재 비교해줘",
    "2203-007317 0.9V Aging 비교해줘",
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
        st.rerun()

bot = get_chatbot()

for idx, item in enumerate(st.session_state.chat_history):
    with st.chat_message(item["role"]):
        st.markdown(item["text"])
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

typed = st.chat_input("예: 2203-007317 Aging 부품사 비교해줘")
clicked = st.session_state.pop("pending_question", None)
question = typed or clicked

if question:
    st.session_state.chat_history.append({"role": "user", "text": question})
    result = bot.short_answer(question)
    st.session_state.chat_history.append({"role": "assistant", **result})
    st.rerun()
