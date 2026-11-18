from fastapi import FastAPI

app = FastAPI(title="specbox")


@app.get("/health")
def health():
    return {"status": "ok"}

# TODO 1: .env 설정 읽기 (python-dotenv) — DB 접속 정보, STORAGE_MODE
# TODO 2: DB 연결 함수 (pymysql) — 요청마다 커넥션을 열고 닫는 방식부터
# TODO 3: GET /  — 추천 공고 목록 화면 (Jinja2 템플릿)  [A]
# TODO 4: GET /postings/{id} — 공고 상세 + 체크리스트
#          * "채용정보 제공사이트로 이동" 버튼, 고용24 출처 문구 필수
# TODO 5: GET/POST /vault — 서류 금고 목록·업로드  [B]