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
    def update_exam_set(self, exam_set_id: str, fields: dict) -> bool: ...


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
