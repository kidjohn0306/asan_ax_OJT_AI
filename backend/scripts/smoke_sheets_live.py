"""Destructive-but-cleaning live smoke tests for the configured Google Sheet.

The script writes uniquely marked rows through the real repository classes and
removes every marked row in ``finally``. Run only against an explicitly
authorized test/copy spreadsheet.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env", override=True)

from repositories.exam_v2 import SheetsExamV2Repository  # noqa: E402
from repositories.generation_v2 import SheetsGenerationV2Repository  # noqa: E402
from repositories.result_v2 import SheetsResultV2Repository  # noqa: E402
from repositories.sheets_repo import (  # noqa: E402
    SheetsExamSetRepository,
    SheetsMaterialRepository,
    SheetsQuestionRepository,
    SheetsQuestionStatsRepository,
    SheetsResultRepository,
    SheetsSnapshotRepository,
    SheetsTeamRepository,
    SheetsUserRepository,
    _build_sheets_service,
)


EXPECTED_SPREADSHEET_ID = "1kNG1TCVcgCGE_Eee1nNxOgLf4ie9Iz75QfEdjK5ZK0Q"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def cleanup_marked_rows(service, spreadsheet_id: str, tabs: set[str], marker: str) -> int:
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_ids = {
        sheet["properties"]["title"]: sheet["properties"]["sheetId"]
        for sheet in metadata.get("sheets", [])
    }
    requests = []
    for tab in sorted(tabs):
        if tab not in sheet_ids:
            continue
        response = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{tab}'!A:AZ",
        ).execute()
        rows = response.get("values", [])
        marked = [
            row_number
            for row_number, row in enumerate(rows, start=1)
            if row_number > 1 and any(marker in str(cell) for cell in row)
        ]
        for row_number in sorted(marked, reverse=True):
            requests.append({
                "deleteDimension": {
                    "range": {
                        "sheetId": sheet_ids[tab],
                        "dimension": "ROWS",
                        "startIndex": row_number - 1,
                        "endIndex": row_number,
                    }
                }
            })
    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()
    return len(requests)


def assert_marker_absent(service, spreadsheet_id: str, tabs: set[str], marker: str) -> None:
    for tab in sorted(tabs):
        response = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{tab}'!A:AZ",
        ).execute()
        rows = response.get("values", [])
        require(
            not any(marker in str(cell) for row in rows for cell in row),
            f"cleanup failed in {tab}",
        )


def smoke_legacy_core(marker: str) -> tuple[list[str], set[str]]:
    checks: list[str] = []
    tabs = {"teams", "users", "exam_sets"}

    team_id = f"{marker}_TEAM"
    teams = SheetsTeamRepository()
    created_team = teams.create_team({
        "team_id": team_id,
        "team_name": f"{marker} team",
        "team_code": f"{marker}_TC",
    })
    require(created_team["team_id"] == team_id, "team create failed")
    require(teams.get_team(team_id)["team_code"] == f"{marker}_TC", "team read failed")
    require(teams.update_team(team_id, {"team_name": f"{marker} updated"})["team_name"].endswith("updated"), "team update failed")
    require(any(row["team_id"] == team_id for row in teams.list_teams()), "team list failed")
    require(teams.delete_team(team_id), "team delete failed")
    require(teams.get_team(team_id) is None, "team still exists after delete")
    checks.append("teams CRUD")

    employee_id = f"{marker}_USER"
    users = SheetsUserRepository()
    users.add_user({
        "employee_id": employee_id,
        "password_hash": "mock_hash",
        "name": f"{marker} user",
        "team": "T1",
        "role": "examinee",
        "exam_date": "",
        "approved": True,
    })
    require(users.find_user(employee_id)["approved"] is True, "user read failed")
    require(users.update_user(employee_id, {"team": "T2"}), "user update failed")
    require(users.find_user(employee_id)["team"] == "T2", "user update not persisted")
    require(any(row["employee_id"] == employee_id for row in users.list_users()), "user list failed")
    require(users.delete_user(employee_id), "user delete failed")
    require(users.find_user(employee_id) is None, "user still exists after delete")
    checks.append("users CRUD")

    exam_id = f"{marker}_EXAM"
    exam_set_id = f"{marker}_SET"
    exams = SheetsExamSetRepository()
    exams.create_exam_set({
        "exam_set_id": exam_set_id,
        "exam_id": exam_id,
        "name": f"{marker} exam",
        "team_code": "T1",
        "question_ids": [f"{marker}_Q"],
        "assigned_users": [],
        "pass_score": 70,
        "status": "active",
        "created_by": "admin001",
    })
    require(exams.get_exam(exam_id)["exam_set_id"] == exam_set_id, "exam create/read failed")
    require(exams.update_exam_set(exam_id, {"duration_min": 75}), "exam update failed")
    require(exams.get_exam(exam_id)["duration_min"] == 75, "exam duration update not persisted")
    require(exams.assign_user(exam_id, employee_id), "exam assignment failed")
    require(employee_id in exams.get_exam(exam_id)["assigned_users"], "assigned user missing")
    require(exams.unassign_user(exam_id, employee_id), "exam unassignment failed")
    require(employee_id not in exams.get_exam(exam_id)["assigned_users"], "unassigned user remains")
    require(any(row["exam_id"] == exam_id for row in exams.list_exam_sets()), "exam list failed")
    require(exams.delete_exam_set(exam_id), "exam delete failed")
    require(exams.get_exam(exam_id) is None, "exam still exists after delete")
    checks.append("exam_sets CRUD/assign")
    return checks, tabs


def smoke_legacy_content(marker: str) -> tuple[list[str], set[str]]:
    checks: list[str] = []
    tabs = {"question_bank", "question_stats", "material_cache", "snapshots", "results"}
    now = datetime.now(timezone.utc).isoformat()

    question_id = f"{marker}_Q"
    questions = SheetsQuestionRepository()
    questions.add_question("common", {
        "question_id": question_id,
        "category": "공통",
        "question": f"{marker} question?",
        "option_a": "A",
        "option_b": "B",
        "option_c": "C",
        "option_d": "D",
        "answer": "A",
        "difficulty_init": "하",
        "difficulty_ai": "하",
        "status": "reviewing",
        "version": 1,
        "explanation": marker,
    })
    require(questions.get_question(question_id)["status"] == "reviewing", "question read failed")
    questions.update_question(question_id, {"status": "approved", "question": f"{marker} updated?"})
    saved_question = questions.get_question(question_id)
    require(saved_question["status"] == "approved", "question status update failed")
    require(saved_question["version"] == 2, "question version was not incremented")
    require(any(row["question_id"] == question_id for row in questions.get_approved_questions()), "approved question list failed")
    require(questions.count_by_status("approved") >= 1, "question status count failed")
    checks.append("question_bank add/read/update/list")

    stats = SheetsQuestionStatsRepository()
    stats.increment_batch([question_id])
    require(stats.get_stats(question_id)["exam_count"] == 1, "question stats insert failed")
    stats.increment_batch([question_id])
    require(stats.get_stats(question_id)["exam_count"] == 2, "question stats update failed")
    require(question_id in stats.list_all_stats(), "question stats list failed")
    checks.append("question_stats insert/update/read")

    category = f"{marker}_MATERIAL"
    materials = SheetsMaterialRepository()
    materials.save_manifest(category, {"files": [{"id": marker}], "scanned_at": now})
    require(materials.get_manifest(category)["files"][0]["id"] == marker, "material manifest insert failed")
    materials.save_manifest(category, {"files": [{"id": marker, "updated": True}], "scanned_at": now})
    require(materials.get_manifest(category)["files"][0]["updated"] is True, "material manifest update failed")
    checks.append("material_cache upsert/read")

    result_id = f"{marker}_RESULT"
    snapshots = SheetsSnapshotRepository()
    snapshots.save_snapshot(result_id, {"marker": marker, "questions": []})
    require(snapshots.get_snapshot(result_id)["marker"] == marker, "snapshot round trip failed")
    checks.append("snapshots append/read")

    results = SheetsResultRepository()
    result = {
        "result_id": result_id,
        "exam_id": f"{marker}_EXAM",
        "employee_id": f"{marker}_USER",
        "name": marker,
        "score": 100,
        "pass": True,
        "team_code": "T1",
        "submitted_at": now,
        "difficulty_summary": {"하": 1},
        "results": [{"question_id": question_id}],
    }
    results.append_result(dict(result))
    results.append_result(dict(result))
    require(results.get_result(result_id)["score"] == 100, "result read failed")
    require(len(results.list_results_by_exam(result["exam_id"])) == 1, "result idempotency/list failed")
    require(result_id in results.get_all_results(), "result map read failed")
    require(results.count() >= 1, "result count failed")
    checks.append("results idempotent append/read/list")
    return checks, tabs


def smoke_v2(marker: str, service, spreadsheet_id: str) -> tuple[list[str], set[str]]:
    checks: list[str] = []
    tabs = {
        "generation_jobs", "question_candidates", "gate_results",
        "question_reviews", "question_history", "exam_versions",
        "exam_set_items", "assignments", "exam_attempts", "result_answers",
    }
    now = datetime.now(timezone.utc).isoformat()

    generation = SheetsGenerationV2Repository(service=service, spreadsheet_id=spreadsheet_id)
    job_id = f"{marker}_JOB"
    candidate_id = f"{marker}_CAND"
    question_id = f"{marker}_Q"
    generation.create_job({"generation_job_id": job_id, "status": "RUNNING", "requested_by": marker})
    generation.update_job(job_id, {"status": "COMPLETED", "completed_count": 1})
    generation.save_candidates([{
        "candidate_id": candidate_id,
        "generation_job_id": job_id,
        "question_text": f"{marker} candidate",
        "status": "reviewing",
        "payload_json": {"question_id": question_id},
    }])
    generation.update_candidate(candidate_id, {"status": "approved", "approved_question_id": question_id})
    generation.save_gate_results([{
        "gate_result_id": f"{marker}_GATE",
        "candidate_id": candidate_id,
        "gate_code": "V-01",
        "status": "PASS",
        "checked_at": now,
    }])
    generation.record_review(
        {"review_id": f"{marker}_REVIEW", "candidate_id": candidate_id, "question_id": question_id, "review_action": "APPROVE"},
        {"history_id": f"{marker}_HISTORY", "question_id": question_id, "version": 1, "action": "APPROVE"},
    )
    found_candidate = generation.find_candidate_by_question_id(question_id)
    require(found_candidate and found_candidate["candidate_id"] == candidate_id, "generation v2 round trip failed")
    require(found_candidate["status"] == "approved", "candidate update failed")
    checks.append("generation v2 job/candidate/gate/review/history")

    exams = SheetsExamV2Repository(service=service, spreadsheet_id=spreadsheet_id)
    exam_set_id = f"{marker}_SET"
    exam_id = f"{marker}_EXAM"
    version_id = f"{marker}_VER"
    item_id = f"{marker}_ITEM"
    employee_id = f"{marker}_USER"
    assignment_id = f"{marker}_ASSIGN"
    version = {
        "exam_version_id": version_id, "exam_set_id": exam_set_id,
        "version_no": 1, "status": "confirmed", "question_count": 1,
        "total_score": 100, "blueprint_json": "[]", "question_hash": marker,
        "confirmed_by": "admin001", "confirmed_at": now, "created_at": now,
        "row_version": 1,
    }
    item = {
        "exam_set_item_id": item_id, "exam_set_id": exam_set_id,
        "paper_version": 1, "order_no": 1, "question_id": question_id,
        "question_version": 1, "score": 100,
        "question_snapshot_json": {"marker": marker}, "created_at": now,
        "checksum": marker,
    }
    exams.save_frozen_exam(version, [item])
    require(exams.find_current_version(exam_set_id)["exam_version_id"] == version_id, "current exam version read failed")
    require(exams.find_version(version_id)["exam_set_id"] == exam_set_id, "exam version read failed")
    require(exams.list_version_items(exam_set_id, 1)[0]["exam_set_item_id"] == item_id, "exam items read failed")
    assignment = {
        "assignment_id": assignment_id, "exam_id": exam_id,
        "employee_id": employee_id, "status": "assigned",
        "assigned_by": "admin001", "assigned_at": now,
        "row_version": 1, "exam_version_id": version_id,
    }
    exams.upsert_assignment(assignment)
    require(exams.find_assignment(exam_id, employee_id)["assignment_id"] == assignment_id, "assignment read failed")
    require(exams.list_active_assignments(employee_id)[0]["assignment_id"] == assignment_id, "active assignment list failed")
    exams.upsert_assignment({**assignment, "status": "cancelled", "cancelled_by": "admin001", "cancelled_at": now, "row_version": 2})
    require(exams.find_assignment(exam_id, employee_id)["status"] == "cancelled", "assignment update failed")
    checks.append("exam v2 frozen version/items/assignment")

    result_repo = SheetsResultV2Repository(service=service, spreadsheet_id=spreadsheet_id)
    attempt_id = f"{marker}_ATTEMPT"
    result_id = f"{marker}_RESULT"
    attempt = {
        "attempt_id": attempt_id, "assignment_id": assignment_id,
        "exam_id": exam_id, "exam_version_id": version_id,
        "employee_id": employee_id, "status": "started",
        "entered_at": now, "started_at": now, "last_seen_at": now,
        "submitted_at": "", "closed_at": "", "client_session_id": marker,
        "submission_idempotency_key": marker, "error_code": "",
        "error_message": "", "row_version": 1,
    }
    result_repo.upsert_attempt(attempt)
    result_repo.upsert_attempt({**attempt, "status": "submitting", "row_version": 2})
    require(result_repo.find_attempt(attempt_id)["status"] == "submitting", "attempt upsert/read failed")
    require(result_repo.find_attempt_for_assignment(assignment_id, employee_id, {"submitting"})["attempt_id"] == attempt_id, "attempt assignment lookup failed")
    answer = {
        "result_answer_id": f"{marker}_ANSWER", "result_id": result_id,
        "exam_set_item_id": item_id, "question_id": question_id,
        "question_version": 1, "selected_choice": "A", "correct_choice": "A",
        "is_correct": True, "score": 100, "response_time_seconds": 1.5,
        "created_at": now,
    }
    result_repo.save_result_answers([answer])
    result_repo.save_result_answers([{**answer, "created_at": datetime.now(timezone.utc).isoformat()}])
    require(result_repo.list_result_answers(result_id)[0]["result_answer_id"] == answer["result_answer_id"], "result answers round trip failed")
    checks.append("result v2 attempt/answers/idempotency")
    return checks, tabs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("group", choices=("legacy-core", "legacy-content", "v2"))
    parser.add_argument("--spreadsheet-id", default=os.getenv("GOOGLE_SHEETS_ID"))
    parser.add_argument("--confirm-test-sheet", action="store_true")
    args = parser.parse_args()
    if not args.confirm_test_sheet:
        parser.error("--confirm-test-sheet is required because this test performs live writes")
    require(args.spreadsheet_id == EXPECTED_SPREADSHEET_ID, "refusing to write to an unexpected spreadsheet")

    marker = f"CODEX_SMOKE_{uuid4().hex[:10]}"
    service = _build_sheets_service()
    group_tabs = {
        "legacy-core": {"teams", "users", "exam_sets"},
        "legacy-content": {
            "question_bank", "question_stats", "material_cache",
            "snapshots", "results",
        },
        "v2": {
            "generation_jobs", "question_candidates", "gate_results",
            "question_reviews", "question_history", "exam_versions",
            "exam_set_items", "assignments", "exam_attempts",
            "result_answers",
        },
    }
    tabs = group_tabs[args.group]
    try:
        if args.group == "legacy-core":
            checks, tabs = smoke_legacy_core(marker)
        elif args.group == "legacy-content":
            checks, tabs = smoke_legacy_content(marker)
        else:
            checks, tabs = smoke_v2(marker, service, args.spreadsheet_id)
        print(f"group={args.group}")
        print(f"checks={len(checks)}")
        for check in checks:
            print(f"PASS {check}")
        return 0
    finally:
        deleted = cleanup_marked_rows(service, args.spreadsheet_id, tabs, marker)
        assert_marker_absent(service, args.spreadsheet_id, tabs, marker)
        print(f"cleanup_deleted_rows={deleted}")
        print("cleanup_verified=true")


if __name__ == "__main__":
    raise SystemExit(main())
