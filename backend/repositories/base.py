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


class SnapshotRepository(ABC):
    @abstractmethod
    def save_snapshot(self, exam_id: str, snapshot: dict) -> None: ...

    @abstractmethod
    def get_snapshot(self, exam_id: str) -> dict: ...


class FeedbackRepository(ABC):
    @abstractmethod
    def append_feedback(self, record: dict) -> None: ...
