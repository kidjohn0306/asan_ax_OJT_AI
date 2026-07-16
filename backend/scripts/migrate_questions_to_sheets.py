"""
로컬 mock_data/questions.json의 문제 데이터를 Google Sheets 문제은행(question_bank) 탭으로 일괄 이관.

실행: cd backend && python scripts/migrate_questions_to_sheets.py [--apply]

사전 조건:
- GOOGLE_SHEETS_ID (또는 GOOGLE_EXAM_SETS_SHEET_ID) 환경변수로 대상 시트 지정
- credentials/service_account.json 또는 GOOGLE_SERVICE_ACCOUNT_JSON 환경변수로 인증
- 서비스 계정에 해당 시트 편집자 권한 부여
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repositories.local_json import LocalQuestionRepository
from repositories.sheets_repo import SheetsQuestionRepository, QUESTIONS_TAB


def build_question_rows(local_data: dict, existing_ids: set[str]) -> list[list]:
    rows = []
    seen_ids = set(existing_ids)
    for pool_key, questions in local_data.items():
        for question in questions:
            question_id = question.get("question_id")
            if not question_id or question_id in seen_ids:
                continue
            rows.append(SheetsQuestionRepository._dict_to_row(pool_key, question))
            seen_ids.add(question_id)
    return rows


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="실제 Google Sheet에 변경을 적용합니다. 생략하면 Dry-run입니다.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    local = LocalQuestionRepository()
    data = local.get_all_questions()

    sheets = SheetsQuestionRepository()
    if args.apply:
        sheets._maybe_ensure_tab()

    existing_ids = {
        row[1]
        for row in sheets._read_all_rows()
        if len(row) > 1 and row[1]
    }
    rows = build_question_rows(data, existing_ids)
    if not rows:
        print("이관할 문제가 없습니다.")
        return

    print(f"대상 Spreadsheet ID: {sheets._spreadsheet_id}")
    print(f"신규 문제 이관 대상: {len(rows)}개 행 (기존 {len(existing_ids)}개 ID 제외)")
    if not args.apply:
        print("Dry-run 완료: 실제 변경은 적용하지 않았습니다. 적용하려면 --apply를 사용하세요.")
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
