"""
로컬 mock_data/questions.json의 문제 데이터를 Google Sheets 문제은행(question_bank) 탭으로 일괄 이관.

실행: cd backend && python scripts/migrate_questions_to_sheets.py

사전 조건:
- GOOGLE_SHEETS_ID (또는 GOOGLE_EXAM_SETS_SHEET_ID) 환경변수로 대상 시트 지정
- credentials/service_account.json 또는 GOOGLE_SERVICE_ACCOUNT_JSON 환경변수로 인증
- 서비스 계정에 해당 시트 편집자 권한 부여
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repositories.local_json import LocalQuestionRepository
from repositories.sheets_repo import SheetsQuestionRepository, QUESTIONS_TAB


def main():
    local = LocalQuestionRepository()
    data = local.get_all_questions()

    sheets = SheetsQuestionRepository()
    sheets._maybe_ensure_tab()

    rows = [
        SheetsQuestionRepository._dict_to_row(pool_key, q)
        for pool_key, questions in data.items()
        for q in questions
    ]
    if not rows:
        print("이관할 문제가 없습니다.")
        return

    sheets._values().append(
        spreadsheetId=sheets._spreadsheet_id,
        range=f"{QUESTIONS_TAB}!A:R",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()
    print(f"{len(rows)}개 문제를 Sheets 문제은행({QUESTIONS_TAB})으로 이관했습니다.")


if __name__ == "__main__":
    main()
