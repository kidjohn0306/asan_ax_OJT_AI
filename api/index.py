import sys
import os

# backend/ 디렉토리를 Python path에 추가
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, 'backend')

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# mock_data 등 상대경로 파일 참조를 위해 backend를 작업 디렉토리로 설정
os.chdir(BACKEND_DIR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.auth import router as auth_router
from api.exam import router as exam_router
from api.admin import router as admin_router

app = FastAPI(title="OJT 평가 시스템 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["인증"])
app.include_router(exam_router, prefix="/api/exam", tags=["시험"])
app.include_router(admin_router, prefix="/api/admin", tags=["관리자"])
