from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import auth, exam, admin

app = FastAPI(title="OJT 평가 시스템 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 배포 시 사내 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["인증"])
app.include_router(exam.router, prefix="/api/exam", tags=["시험"])
app.include_router(admin.router, prefix="/api/admin", tags=["관리자"])


@app.get("/")
def root():
    return {"status": "ok", "message": "OJT 평가 시스템 API"}
