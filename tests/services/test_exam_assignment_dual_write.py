import copy
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from services import admin_service


def exam(exam_id, evaluation_type="official", assigned=None, set_id=None):
    return {
        "exam_id": exam_id,
        "exam_set_id": set_id or f"set-{exam_id}",
        "name": exam_id,
        "team_code": "T1",
        "question_ids": ["Q1"],
        "assigned_users": list(assigned or []),
        "evaluation_type": evaluation_type,
        "status": "active",
    }


class FakeExamSets:
    def __init__(self, events):
        self.events = events
        self.rows = []
        self.fail_assign = False
        self.fail_unassign = False

    def list_exam_sets(self):
        return self.rows

    def get_exam(self, exam_id):
        return self.by_id(exam_id)

    def by_id(self, exam_id):
        return next((row for row in self.rows if row["exam_id"] == exam_id), None)

    def assign_user(self, exam_id, employee_id):
        self.events.append(f"legacy-assign:{exam_id}")
        if self.fail_assign:
            raise RuntimeError("legacy assign failed")
        row = self.by_id(exam_id)
        if not row:
            return False
        if employee_id not in row["assigned_users"]:
            row["assigned_users"].append(employee_id)
        return True

    def unassign_user(self, exam_id, employee_id):
        self.events.append(f"legacy-unassign:{exam_id}")
        if self.fail_unassign:
            raise RuntimeError("legacy unassign failed")
        row = self.by_id(exam_id)
        if not row:
            return False
        if employee_id in row["assigned_users"]:
            row["assigned_users"].remove(employee_id)
        return True


class FakeUsers:
    def __init__(self):
        self.users = {
            "E1": {"employee_id": "E1", "approved": True},
            "E2": {"employee_id": "E2", "approved": False},
        }

    def find_user(self, employee_id):
        return self.users.get(employee_id)


class TeamAwareFakeUsers(FakeUsers):
    def __init__(self):
        super().__init__()
        self.users["E1"]["team"] = "T2"


class FakeExamV2:
    def __init__(self, events):
        self.events = events
        self.versions = {}
        self.assignments = {}
        self.fail_upsert = False

    def add_version(self, exam_row):
        self.versions[exam_row["exam_set_id"]] = {
            "exam_version_id": f"version-{exam_row['exam_set_id']}",
            "exam_set_id": exam_row["exam_set_id"],
            "version_no": "1",
        }

    def find_current_version(self, exam_set_id):
        return self.versions.get(exam_set_id)

    def find_assignment(self, exam_id, employee_id):
        return self.assignments.get((exam_id, employee_id))

    def list_active_assignments(self, employee_id):
        return [
            copy.deepcopy(row)
            for (_, assigned_employee), row in self.assignments.items()
            if assigned_employee == employee_id and row["status"] == "assigned"
        ]

    def upsert_assignment(self, row):
        self.events.append(f"v2-{row['status']}:{row['exam_id']}")
        if self.fail_upsert:
            raise RuntimeError("normalized assignment failed")
        self.assignments[(row["exam_id"], row["employee_id"])] = copy.deepcopy(row)


class ExamAssignmentDualWriteTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.legacy = FakeExamSets(self.events)
        self.users = FakeUsers()
        self.v2 = FakeExamV2(self.events)
        self.repo_patches = [
            patch("repositories.exam_set_repo", self.legacy),
            patch("repositories.user_repo", self.users),
            patch("repositories.exam_v2_repo", self.v2),
        ]
        for repo_patch in self.repo_patches:
            repo_patch.start()
            self.addCleanup(repo_patch.stop)

    def flags(self, mode="dual", frozen="true", assignments="true"):
        return patch.dict("os.environ", {
            "OJT_SHEETS_SCHEMA_MODE": mode,
            "OJT_USE_FROZEN_EXAM": frozen,
            "OJT_USE_ASSIGNMENTS_TAB": assignments,
        }, clear=False)

    def prepare(self, *rows):
        self.legacy.rows = list(rows)
        for row in rows:
            self.v2.add_version(row)

    def seed_assignment(self, exam_id, employee_id="E1", status="assigned"):
        self.v2.assignments[(exam_id, employee_id)] = {
            "assignment_id": f"assignment-{exam_id}-{employee_id}",
            "exam_id": exam_id,
            "exam_version_id": f"version-set-{exam_id}",
            "employee_id": employee_id,
            "status": status,
            "assigned_by": "admin-old",
            "assigned_at": "2026-07-14T00:00:00+00:00",
            "row_version": "1",
        }

    def test_missing_or_unapproved_user_is_409(self):
        target = exam("official-new")
        self.prepare(target)
        for employee_id in ("missing", "E2"):
            with self.subTest(employee_id=employee_id), self.flags():
                with self.assertRaises(HTTPException) as raised:
                    admin_service.assign_user_to_exam_set(
                        employee_id,
                        target["exam_id"],
                        actor={"sub": "admin-1"},
                    )
            self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(self.events, [])

    def test_different_team_user_is_read_only_for_assignment(self):
        target = exam("official-new")
        self.prepare(target)
        with patch("repositories.user_repo", TeamAwareFakeUsers()), self.flags():
            with self.assertRaises(HTTPException) as raised:
                admin_service.assign_user_to_exam_set(
                    "E1", target["exam_id"], actor={"sub": "admin-1"}
                )
        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(self.events, [])

    def test_official_assignment_cancels_only_other_official(self):
        official_old = exam("official-old", "official", ["E1"])
        practice_old = exam("practice-old", "practice", ["E1"])
        official_new = exam("official-new", "official")
        self.prepare(official_old, practice_old, official_new)
        self.seed_assignment("official-old")
        self.seed_assignment("practice-old")

        with self.flags():
            result = admin_service.assign_user_to_exam_set(
                "E1", "official-new", actor={"sub": "admin-1"}
            )

        self.assertTrue(result["success"])
        self.assertEqual(self.events, [
            "v2-cancelled:official-old",
            "v2-assigned:official-new",
            "legacy-unassign:official-old",
            "legacy-assign:official-new",
        ])
        self.assertNotIn("E1", official_old["assigned_users"])
        self.assertIn("E1", practice_old["assigned_users"])
        self.assertIn("E1", official_new["assigned_users"])
        cancelled = self.v2.find_assignment("official-old", "E1")
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(cancelled["cancelled_by"], "admin-1")

    def test_multiple_practice_and_official_assignments_coexist(self):
        official = exam("official", "official", ["E1"])
        practice_one = exam("practice-1", "practice", ["E1"])
        practice_two = exam("practice-2", "practice")
        self.prepare(official, practice_one, practice_two)
        self.seed_assignment("official")
        self.seed_assignment("practice-1")

        with self.flags():
            admin_service.assign_user_to_exam_set(
                "E1", "practice-2", actor={"sub": "admin-1"}
            )

        self.assertEqual(self.events, [
            "v2-assigned:practice-2",
            "legacy-assign:practice-2",
        ])
        self.assertTrue(all(
            "E1" in row["assigned_users"]
            for row in (official, practice_one, practice_two)
        ))

    def test_legacy_mode_also_preserves_multiple_practice_assignments(self):
        practice_one = exam("practice-1", "practice", ["E1"])
        practice_two = exam("practice-2", "practice")
        self.prepare(practice_one, practice_two)
        with self.flags(mode="legacy", frozen="false", assignments="false"):
            admin_service.assign_user_to_exam_set(
                "E1", "practice-2", actor={"sub": "admin-1"}
            )
        self.assertEqual(self.events, ["legacy-assign:practice-2"])
        self.assertIn("E1", practice_one["assigned_users"])

    def test_same_exam_assignment_retry_keeps_one_v2_primary_key(self):
        target = exam("practice-1", "practice")
        self.prepare(target)
        with self.flags():
            admin_service.assign_user_to_exam_set(
                "E1", "practice-1", actor={"sub": "admin-1"}
            )
            admin_service.assign_user_to_exam_set(
                "E1", "practice-1", actor={"sub": "admin-1"}
            )
        self.assertEqual(len(self.v2.assignments), 1)
        self.assertEqual(len(target["assigned_users"]), 1)

    def test_cancelled_assignment_can_be_reassigned_by_new_actor(self):
        target = exam("practice-1", "practice")
        self.prepare(target)
        self.seed_assignment("practice-1", status="cancelled")
        with self.flags():
            admin_service.assign_user_to_exam_set(
                "E1", "practice-1", actor={"sub": "admin-new"}
            )
        reassigned = self.v2.find_assignment("practice-1", "E1")
        self.assertEqual(reassigned["status"], "assigned")
        self.assertEqual(reassigned["assigned_by"], "admin-new")
        self.assertEqual(reassigned["cancelled_by"], "")

    def test_assignment_requires_frozen_version_when_flag_is_on(self):
        target = exam("official-new")
        self.legacy.rows = [target]
        with self.flags():
            with self.assertRaises(HTTPException) as raised:
                admin_service.assign_user_to_exam_set(
                    "E1", "official-new", actor={"sub": "admin-1"}
                )
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            raised.exception.detail["code"],
            "EXAM_VERSION_NOT_CONFIRMED",
        )

    def test_normalized_failure_prevents_legacy_mutation(self):
        target = exam("official-new")
        self.prepare(target)
        self.v2.fail_upsert = True
        before = copy.deepcopy(self.legacy.rows)
        with self.flags():
            with self.assertRaises(HTTPException) as raised:
                admin_service.assign_user_to_exam_set(
                    "E1", "official-new", actor={"sub": "admin-1"}
                )
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(self.legacy.rows, before)

    def test_legacy_failure_after_normalized_assignment_returns_503(self):
        target = exam("official-new")
        self.prepare(target)
        self.legacy.fail_assign = True
        with self.flags():
            with self.assertRaises(HTTPException) as raised:
                admin_service.assign_user_to_exam_set(
                    "E1", "official-new", actor={"sub": "admin-1"}
                )
        self.assertEqual(raised.exception.status_code, 503)
        self.assertIsNotNone(self.v2.find_assignment("official-new", "E1"))

    def test_unassign_marks_v2_cancelled_before_legacy_removal(self):
        target = exam("practice-1", "practice", ["E1"])
        self.prepare(target)
        self.seed_assignment("practice-1")
        with self.flags():
            result = admin_service.unassign_user_from_exam_set(
                "E1", "practice-1", actor={"sub": "admin-2"}
            )
        self.assertTrue(result["success"])
        self.assertEqual(self.events, [
            "v2-cancelled:practice-1",
            "legacy-unassign:practice-1",
        ])
        cancelled = self.v2.find_assignment("practice-1", "E1")
        self.assertEqual(cancelled["cancelled_by"], "admin-2")
        self.assertNotIn("E1", target["assigned_users"])


if __name__ == "__main__":
    unittest.main()
