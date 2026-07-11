"""테스트 패키지 루트 — backend/ 디렉터리를 sys.path에 추가해 백엔드 절대 임포트(services.*, api.*, repositories.*)를 가능하게 한다.
저장소 루트는 `python -m unittest`가 cwd로 이미 sys.path에 넣어주므로 ai_engine 임포트는 별도 처리가 필요 없다."""
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
