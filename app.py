#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 페이지 설정
st.set_page_config(page_title="MLCC 수명 평가 대시보드", layout="wide")

# ---------------------------------------------------------
# 0. 데이터 로드 함수 (요구사항 4: 자동 반영 및 캐싱)
# ---------------------------------------------------------
@st.cache_data(ttl=5)  # 5초마다 엑셀 변경사항 자동 감지/갱신
def load_data(file_path):
    # 엑셀 파일의 Header 위치 처리 (Row 5: 그룹 헤더, Row 6: 상세 컬럼)
    raw_df = pd.read_excel(file_path, sheet_name='수명', header=None)
    
    # 실제 컬럼명 추출 (Row 5의 데이터)
    columns = raw_df.iloc[5].values
    df = raw_df.iloc[6:].copy()
    df.columns = columns
    
    # 데이터 타입 정제
    df = df.dropna(subset=['부품사', '자재코드', '사용전압(V)'])
    
    # 수치형 컬럼 변환
    numeric_cols = ['정격전압(V)', '정격용량(uF)', '사용전압(V)', 'Ea', 'n', '형상모수', '척도모수']
    # 온도시험 결과 컬럼 (65℃ ~ 125℃)
    temp_cols = [c for c in df.columns if '℃' in str(c)]
    
    for col in numeric_cols + temp_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
    df['사용전압(V)'] = df['사용전압(V)'].astype(str) + "V"
    return df, temp_cols

# 엑셀 데이터 불러오기
EXCEL_FILE = 'test_수명.xlsx'
try:
    df, temp_cols = load_data(EXCEL_FILE)
except Exception as e:
    st.error(f"엑셀 파일을 읽는 중 오류가 발생했습니다: {e}")
    st.stop()

st.title("🔬 MLCC 가속평가 및 수명 산출 대시보드")
st.markdown("---")

# ---------------------------------------------------------
# 1. 캐스케이딩 필터링 (요구사항 1: 부품사 -> 자재코드 -> 사용전압 계층 선택)
# ---------------------------------------------------------
st.sidebar.header("📌 데이터 선택 (필터)")

# 1-1. 부품사 선택
supplier_list = sorted(df['부품사'].unique().tolist())
selected_supplier = st.sidebar.selectbox("1. 부품사 선택", supplier_list)

# 1-2. 부품사 조건에 맞는 자재코드만 추출하여 선택
filtered_by_supplier = df[df['부품사'] == selected_supplier]
code_list = sorted(filtered_by_supplier['자재코드'].unique().tolist())
selected_code = st.sidebar.selectbox("2. 자재코드 선택", code_list)

# 1-3. 부품사 & 자재코드 조건에 존재하는 사용전압만 추출하여 선택 (없는 전압은 자동 제외)
filtered_by_code = filtered_by_supplier[filtered_by_supplier['자재코드'] == selected_code]
voltage_list = sorted(filtered_by_code['사용전압(V)'].unique().tolist())
selected_voltage = st.sidebar.selectbox("3. 사용전압(V) 선택", voltage_list)

# 최종 선택 데이터 추출
selected_row = filtered_by_code[filtered_by_code['사용전압(V)'] == selected_voltage].iloc[0]

# ---------------------------------------------------------
# 2. 정보 표현 (요구사항 2: 선택된 조건의 깔끔한 카드 및 상세 정보 표기)
# ---------------------------------------------------------
st.subheader(f"📋 [{selected_supplier}] {selected_code} ({selected_voltage}) 상세 정보")

# Key Metrics 표시
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("업데이트일자", str(selected_row['업데이트일자'])[:10])
m2.metric("부품사코드", selected_row['부품사코드'])
m3.metric("Grade / Size", f"{selected_row['Grade']} / {selected_row['Size']}")
m4.metric("정격전압 / 정격용량", f"{selected_row['정격전압(V)']}V / {selected_row['정격용량(uF)']}uF")
m5.metric("Bx수명", selected_row['Bx수명'])
m6.metric("Ea / n", f"{selected_row['Ea']} / {selected_row['n']}")

# 상세 파라미터 표
st.markdown("#### ⚙️ 신뢰성 파라미터 상세")
param_df = pd.DataFrame([{
    '형상모수(Beta)': selected_row['형상모수'],
    '척도모수(Eta)': selected_row['척도모수'],
    'Ea (활성화에너지)': selected_row['Ea'],
    'n (전압가속지수)': selected_row['n']
}])
st.dataframe(param_df, use_container_width=True, hide_index=True)

st.markdown("---")

# ---------------------------------------------------------
# 3. 그래프 표현 (요구사항 3: 온도별 수명 산출결과 + 부품사 간 동 자재코드 수명 비교)
# ---------------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    st.subheader("🌡️ 가속평가 기반 온도별 수명산출결과")
    
    # 선택된 항목의 온도별 수명 데이터 구성
    temp_data = pd.DataFrame({
        '온도': temp_cols,
        '수명시간': [selected_row[col] for col in temp_cols]
    })
    
    fig_temp = px.line(
        temp_data, 
        x='온도', 
        y='수명시간', 
        markers=True,
        title=f"온도 상승에 따른 기대수명 변화 ({selected_supplier} - {selected_code})",
        labels={'수명시간': '수명 (시간)', '온도': '시험 온도'}
    )
    fig_temp.update_traces(line_color='#2E86C1', line_width=3, marker_size=8)
    fig_temp.update_layout(yaxis_type="log")  # Log Scale 적용으로 시각적 편의 제공
    st.plotly_chart(fig_temp, use_container_width=True)

with col2:
    st.subheader(f"🏢 부품사 간 동일 자재코드({selected_code}) 수명 비교")
    
    # 동일한 자재코드 및 사용전압을 가진 타 부품사 데이터 추출
    same_code_df = df[(df['자재코드'] == selected_code) & (df['사용전압(V)'] == selected_voltage)]
    
    # 비교를 위한 온도 선택 slider
    selected_temp_for_comp = st.select_slider(
        "비교할 온도를 선택하세요:", 
        options=temp_cols, 
        value='85℃' if '85℃' in temp_cols else temp_cols[0]
    )
    
    fig_comp = px.bar(
        same_code_df,
        x='부품사',
        y=selected_temp_for_comp,
        color='부품사',
        text_auto='.2f',
        title=f"자재코드[{selected_code}] @ {selected_voltage}, {selected_temp_for_comp} 조건 수명 비교",
        labels={selected_temp_for_comp: '수명 (시간)'}
    )
    fig_comp.update_layout(showlegend=False)
    st.plotly_chart(fig_comp, use_container_width=True)

st.sidebar.info("💡 엑셀 데이터가 수정되거나 추가되면 화면이 5초 이내에 자동 업데이트됩니다.")

