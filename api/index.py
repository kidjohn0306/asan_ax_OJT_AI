import sys
import os

# backend/ 디렉토리를 Python path에 추가 (backend/main.py 및 하위 모듈 임포트용)
_backend_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend')
)
sys.path.insert(0, _backend_dir)

# backend/main.py의 app을 그대로 사용
# (CORS, 라우터, frontend/dist StaticFiles 마운트 포함)
from main import app  # noqa: E402
