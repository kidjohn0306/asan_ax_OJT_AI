import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from api import auth, exam, admin, drive

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
app.include_router(drive.router, prefix="/api/drive", tags=["드라이브"])


_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_frontend_dir):
    _assets_dir = os.path.join(_frontend_dir, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    # index.html은 해시 없는 파일이라 캐시되면 배포한 새 코드가 반영 안 된 것처럼 보임 —
    # 항상 재검증하도록 no-cache 지정. /assets의 해시된 JS/CSS는 파일명이 바뀌므로 캐시돼도 무방.
    _NO_CACHE_HEADERS = {"Cache-Control": "no-cache, no-store, must-revalidate"}

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        file_path = os.path.join(_frontend_dir, full_path)
        if os.path.isfile(file_path) and full_path != "index.html":
            return FileResponse(file_path)
        return FileResponse(os.path.join(_frontend_dir, "index.html"), headers=_NO_CACHE_HEADERS)
