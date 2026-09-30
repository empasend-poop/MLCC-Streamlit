MLCC Excel Chatbot 추가 파일

교체:
- app.py

추가:
- pages/chatbot.py
- utils/chatbot_engine.py

선택 교체:
- utils/__init__.py

기존 최신 utils/data_loader.py는 그대로 유지하세요.

특징:
- API Key 불필요
- 수명/Aging/BDV Excel 직접 조회
- Excel에 없는 결과를 생성하지 않음
- 부품사/자재코드 검색
- 전체 평가결과/개별 평가결과/보유현황 질문 가능

Excel이 GitHub에서 변경되면 앱이 재실행될 때 최신 파일을 읽습니다.
실행 중 즉시 다시 읽고 싶으면 Chatbot 페이지의 '챗봇 데이터 새로고침' 버튼을 누르세요.
