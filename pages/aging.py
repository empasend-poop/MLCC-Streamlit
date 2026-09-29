# ============================================================
# AGING REMAINING RATE
# ============================================================

st.subheader(
    "초기 대비 Aging 잔여율"
)


initial_reference = selected_row.get(
    "① 25℃, 0V",
    np.nan,
)


remaining_rows = []


if pd.notna(initial_reference) and initial_reference != 0:

    # 실측값
    for _, row in aging_df.iterrows():

        remaining_rows.append(
            {
                "시간(hr)": row["시간(hr)"],
                "잔여율(%)": (
                    row["잔여용량(uF)"]
                    / initial_reference
                    * 100
                ),
                "구분": "실측",
            }
        )


    # 장기 산출값
    for _, row in long_term_df.iterrows():

        remaining_rows.append(
            {
                "시간(hr)": row["시간(hr)"],
                "잔여율(%)": (
                    row["잔여용량(uF)"]
                    / initial_reference
                    * 100
                ),
                "구분": "장기 산출",
            }
        )


remaining_df = pd.DataFrame(
    remaining_rows
)


if not remaining_df.empty:

    fig_remaining = px.line(
        remaining_df,
        x="시간(hr)",
        y="잔여율(%)",
        color="구분",
        markers=True,
    )


    fig_remaining.update_xaxes(
        type="log",
    )


    fig_remaining.update_layout(
        height=480,
        xaxis_title="경과시간 (hr)",
        yaxis_title="초기 대비 잔여율 (%)",
        hovermode="closest",
        legend_title="",
    )


    st.plotly_chart(
        fig_remaining,
        use_container_width=True,
    )
