from abc import ABC, abstractmethod


class QuestionRepository(ABC):
    @abstractmethod
    def get_all_questions(self) -> dict: ...

    @abstractmethod
    def get_approved_questions(self, team_key: str = None, category: str = None) -> list: ...

    @abstractmethod
    def list_by_status(self, status: str) -> list: ...

    @abstractmethod
    def get_question(self, question_id: str) -> dict: ...

    @abstractmethod
    def add_question(self, pool_key: str, question: dict) -> None: ...

    @abstractmethod
    def update_question(self, question_id: str, fields: dict) -> None: ...

    @abstractmethod
    def count_by_status(self, status: str) -> int: ...


class ResultRepository(ABC):
    @abstractmethod
    def append_result(self, result: dict) -> None: ...

    @abstractmethod
    def get_result(self, exam_id: str) -> dict: ...

    @abstractmethod
    def get_all_results(self) -> dict: ...

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def list_results_by_set(self, exam_set_id: str) -> list: ...


class SnapshotRepository(ABC):
    @abstractmethod
    def save_snapshot(self, exam_id: str, snapshot: dict) -> None: ...

    @abstractmethod
    def get_snapshot(self, exam_id: str) -> dict: ...


class FeedbackRepository(ABC):
    @abstractmethod
    def append_feedback(self, record: dict) -> None: ...

    @abstractmethod
    def list_recent_feedback(self, limit: int = 20) -> list: ...


class ExamSetRepository(ABC):
    @abstractmethod
    def list_exam_sets(self) -> list: ...

    @abstractmethod
    def get_exam_set(self, exam_set_id: str) -> dict | None: ...

    @abstractmethod
    def create_exam_set(self, data: dict) -> dict: ...

    @abstractmethod
    def assign_user(self, exam_set_id: str, employee_id: str) -> bool: ...

    @abstractmethod
    def unassign_user(self, exam_set_id: str, employee_id: str) -> bool: ...

    @abstractmethod
    def delete_exam_set(self, exam_set_id: str) -> bool: ...


class TeamRepository(ABC):
    @abstractmethod
    def list_teams(self) -> list: ...

    @abstractmethod
    def get_team(self, team_id: str) -> dict | None: ...

    @abstractmethod
    def create_team(self, data: dict) -> dict: ...

    @abstractmethod
    def update_team(self, team_id: str, fields: dict) -> dict | None: ...

    @abstractmethod
    def delete_team(self, team_id: str) -> bool: ...


class QuestionStatsRepository(ABC):
    @abstractmethod
    def increment_batch(self, question_ids: list) -> None: ...

    @abstractmethod
    def get_stats(self, question_id: str) -> dict | None: ...

    @abstractmethod
    def list_all_stats(self) -> dict: ...

    @abstractmethod
    def list_flagged(self) -> list: ...


class UserRepository(ABC):
    """승인된 응시자(examinee) 계정 관리. 관리자 계정은 보안(비밀번호 해시 노출 방지)을
    위해 항상 로컬 파일에만 저장하며 이 Repository의 대상이 아니다."""

    @abstractmethod
    def list_users(self) -> list: ...

    @abstractmethod
    def find_user(self, employee_id: str) -> dict | None: ...

    @abstractmethod
    def add_user(self, user: dict) -> None: ...

    @abstractmethod
    def delete_user(self, employee_id: str) -> bool: ...

    @abstractmethod
    def update_user(self, employee_id: str, fields: dict) -> bool: ...


class MaterialRepository(ABC):
    """Drive 교육자료 스캔 결과 캐시. category(예: common/team1/team2/team3)별로
    스캔된 파일 매니페스트(id/name/modifiedTime)와 추출된 텍스트를 저장해
    변경되지 않은 파일은 재다운로드·재추출하지 않도록 한다."""

    @abstractmethod
    def get_manifest(self, category: str) -> dict | None: ...

    @abstractmethod
    def save_manifest(self, category: str, manifest: dict) -> None: ...
