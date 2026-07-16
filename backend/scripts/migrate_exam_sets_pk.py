"""
exam_sets 시트에 새로 추가된 exam_id(PK) 컬럼을 기존 행에 백필한다.

배경: exam_set_id가 더 이상 유일하지 않은 새 스키마로 바뀌면서, 각 회차를 유일하게
식별하는 exam_id 컬럼이 새로 생겼다. 이 스크립트 실행 전에 만들어진 행들은 exam_id가
비어있는데, 지금까지는 한 행 = 한 회차였으므로 exam_id = exam_set_id로 채워도 안전하다.

실행: cd backend && python scripts/migrate_exam_sets_pk.py [--apply]

사전 조건:
- GOOGLE_SHEETS_ID (또는 GOOGLE_EXAM_SETS_SHEET_ID) 환경변수로 대상 시트 지정
- credentials/service_account.json 또는 GOOGLE_SERVICE_ACCOUNT_JSON 환경변수로 인증
- 서비스 계정에 해당 시트 편집자 권한 부여
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repositories.sheets_repo import SheetsExamSetRepository, SHEET_TAB, _ensure_tab, HEADERS


def build_exam_id_updates(rows: list[list]) -> list[dict]:
    updates = []
    for row_no, row in enumerate(rows, start=2):
        data = SheetsExamSetRepository._row_to_dict(row)
        if data.get("exam_id") or not data.get("exam_set_id"):
            continue
        updates.append({
            "range": f"{SHEET_TAB}!K{row_no}",
            "values": [[data["exam_set_id"]]],
        })
    return updates


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
    repo = SheetsExamSetRepository()
    if args.apply:
        _ensure_tab(repo._svc, repo._spreadsheet_id, SHEET_TAB, HEADERS)

    rows = repo._read_all_rows()
    updates = build_exam_id_updates(rows)

    if not updates:
        print("백필할 행이 없습니다 (모든 행에 exam_id가 이미 있음).")
        return

    print(f"대상 Spreadsheet ID: {repo._spreadsheet_id}")
    print(f"exam_id 백필 대상: {len(updates)}개 행")
    if not args.apply:
        print("Dry-run 완료: 실제 변경은 적용하지 않았습니다. 적용하려면 --apply를 사용하세요.")
        return

    repo._values().batchUpdate(
        spreadsheetId=repo._spreadsheet_id,
        body={"valueInputOption": "RAW", "data": updates},
    ).execute()
    print(f"{len(updates)}개 행의 exam_id를 exam_set_id 값으로 백필했습니다.")


if __name__ == "__main__":
    main()
