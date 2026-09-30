교체 파일
- pages/chatbot.py
- utils/chatbot_engine.py

수정 내용
1. Excel의 'Supplie A/B/C' 표기를 챗봇에서는 'Supplier A/B/C'로 정규화
2. 자재코드별 수명 결과를 부품사/사용전압으로 구분
3. 질문에서 '85도', '100도', '85℃' 등을 읽어 해당 온도 수명 비교
4. 텍스트 나열 대신 KPI + Plotly 막대그래프 + 간단 상세표 표시
5. Supplier를 질문에 넣으면 해당 부품사만 필터
6. Supplier를 생략하면 동일 자재코드의 전체 부품사 비교

실제 업로드된 test_수명.xlsx 검증
- 2203-007317: 4개 조건
- Supplier A / 3.15V / 85℃ 수명 = 43.75
- Supplier B / 3.15V 및 1.8V
- Supplier C / 3.15V
