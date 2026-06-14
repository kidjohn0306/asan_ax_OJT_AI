import json
from pathlib import Path
from fastapi import HTTPException

MOCK_DIR = Path(__file__).parent.parent / "mock_data"


def _load_users() -> dict:
    with open(MOCK_DIR / "users.json", encoding="utf-8") as f:
        return json.load(f)


def authenticate_user(employee_id: str, password: str) -> dict:
    # TODO: 실제 사내 인사 DB 연동 + bcrypt 검증
    data = _load_users()
    all_users = data["approved_users"] + data["admins"]

    user = next((u for u in all_users if u["employee_id"] == employee_id), None)
    if not user:
        raise HTTPException(status_code=403, detail="승인되지 않은 계정입니다.")
    if not user.get("approved"):
        raise HTTPException(status_code=403, detail="응시 승인이 완료되지 않았습니다.")

    # mock: 비밀번호 검증 생략
    token = f"mock_jwt_{employee_id}"  # TODO: 실제 JWT 발급

    return {
        "token": token,
        "name": user["name"],
        "team": user.get("team"),
        "role": user["role"],
        "approved": user["approved"],
    }
