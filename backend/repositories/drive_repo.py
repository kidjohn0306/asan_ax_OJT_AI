import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from repositories.base import QuestionRepository, ResultRepository, SnapshotRepository

_MOCK_DIR = Path(__file__).parent.parent / "mock_data"
_QUESTIONS_FILENAME = "questions.json"

_RESULTS_FILENAME = "results.jsonl"


def _build_drive_service():
    from services.drive_service import DriveService
    return DriveService().service


class DriveQuestionRepository(QuestionRepository):
    """Google Drive JSON 기반 QuestionRepository.

    DRIVE_RESULTS_FOLDER_ID 폴더에 questions.json을 저장.
    Drive 파일이 없으면 mock_data/questions.json을 시드로 사용.
    """

    def __init__(self):
        self._folder_id = os.getenv("DRIVE_RESULTS_FOLDER_ID", "")

    def _service(self):
        return _build_drive_service()

    def _find_file_id(self, service) -> str | None:
        if not self._folder_id:
            return None
        query = (
            f"name='{_QUESTIONS_FILENAME}' and "
            f"'{self._folder_id}' in parents and trashed=false"
        )
        resp = service.files().list(
            q=query, fields="files(id)",
            includeItemsFromAllDrives=True, supportsAllDrives=True,
        ).execute()
        files = resp.get("files", [])
        return files[0]["id"] if files else None

    def _download(self, service, file_id: str) -> dict:
        request = service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        dl = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = dl.next_chunk()
        buf.seek(0)
        return json.loads(buf.read().decode("utf-8"))

    def _upload(self, service, data: dict, file_id: str | None) -> None:
        content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype="application/json", resumable=False)
        if file_id:
            service.files().update(
                fileId=file_id, media_body=media, supportsAllDrives=True,
            ).execute()
        else:
            meta = {"name": _QUESTIONS_FILENAME, "parents": [self._folder_id]}
            service.files().create(
                body=meta, media_body=media, fields="id", supportsAllDrives=True,
            ).execute()

    def _load(self) -> tuple[dict, any, str | None]:
        """(data, service, file_id) 반환. Drive 파일 없으면 mock_data를 시드로."""
        if not self._folder_id:
            with open(_MOCK_DIR / _QUESTIONS_FILENAME, encoding="utf-8") as f:
                return json.load(f), None, None
        svc = self._service()
        fid = self._find_file_id(svc)
        if fid:
            return self._download(svc, fid), svc, fid
        with open(_MOCK_DIR / _QUESTIONS_FILENAME, encoding="utf-8") as f:
            return json.load(f), svc, None

    def _all_flat(self, data: dict) -> list:
        result = []
        for pool in data.values():
            result.extend(pool)
        return result

    def get_all_questions(self) -> dict:
        data, _, _ = self._load()
        return data

    def get_approved_questions(self, team_key: str = None, category: str = None) -> list:
        data, _, _ = self._load()
        if team_key:
            pools = [data.get(team_key, []), data.get("common", []),
                     data.get("safety", []), data.get("general", [])]
            flat = [q for pool in pools for q in pool]
        else:
            flat = self._all_flat(data)
        flat = [q for q in flat if q.get("status") == "approved"]
        if category:
            flat = [q for q in flat if q.get("category") == category]
        return flat

    def list_by_status(self, status: str) -> list:
        data, _, _ = self._load()
        return [q for q in self._all_flat(data) if q.get("status") == status]

    def get_question(self, question_id: str) -> dict | None:
        data, _, _ = self._load()
        for q in self._all_flat(data):
            if q["question_id"] == question_id:
                return q
        return None

    def add_question(self, pool_key: str, question: dict) -> None:
        if not self._folder_id:
            raise RuntimeError("DRIVE_RESULTS_FOLDER_ID 환경변수가 설정되지 않았습니다.")
        data, svc, fid = self._load()
        if pool_key not in data:
            data[pool_key] = []
        data[pool_key].append(question)
        self._upload(svc, data, fid)

    _CONTENT_FIELDS = {"question", "option_a", "option_b", "option_c", "option_d", "answer", "explanation"}

    def update_question(self, question_id: str, fields: dict) -> None:
        if not self._folder_id:
            raise RuntimeError("DRIVE_RESULTS_FOLDER_ID 환경변수가 설정되지 않았습니다.")
        data, svc, fid = self._load()
        for pool in data.values():
            for q in pool:
                if q["question_id"] == question_id:
                    q.update(fields)
                    if any(k in self._CONTENT_FIELDS for k in fields):
                        q["version"] = q.get("version", 1) + 1
                    self._upload(svc, data, fid)
                    return

    def count_by_status(self, status: str) -> int:
        return len(self.list_by_status(status))


class DriveResultRepository(ResultRepository):
    """Google Drive JSONL 기반 ResultRepository.

    환경변수 DRIVE_RESULTS_FOLDER_ID에 Drive 폴더 ID를 설정해야 동작.
    results.jsonl 파일을 append-only로 유지한다.
    """

    def __init__(self):
        self._folder_id = os.getenv("DRIVE_RESULTS_FOLDER_ID", "")

    def _service(self):
        return _build_drive_service()

    def _find_file_id(self, service) -> str | None:
        query = (
            f"name='{_RESULTS_FILENAME}' and "
            f"'{self._folder_id}' in parents and trashed=false"
        )
        resp = service.files().list(
            q=query, fields="files(id)",
            includeItemsFromAllDrives=True, supportsAllDrives=True,
        ).execute()
        files = resp.get("files", [])
        return files[0]["id"] if files else None

    def _download_lines(self, service, file_id: str) -> list[str]:
        request = service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        dl = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = dl.next_chunk()
        buf.seek(0)
        return [line for line in buf.read().decode("utf-8").splitlines() if line.strip()]

    def _upload(self, service, lines: list[str], file_id: str | None) -> str:
        content = "\n".join(lines) + "\n"
        media = MediaIoBaseUpload(
            io.BytesIO(content.encode("utf-8")),
            mimetype="text/plain",
            resumable=False,
        )
        if file_id:
            service.files().update(
                fileId=file_id, media_body=media, supportsAllDrives=True,
            ).execute()
            return file_id
        meta = {"name": _RESULTS_FILENAME, "parents": [self._folder_id]}
        created = service.files().create(
            body=meta, media_body=media, fields="id", supportsAllDrives=True,
        ).execute()
        return created["id"]

    def append_result(self, result: dict) -> None:
        if not self._folder_id:
            raise RuntimeError("DRIVE_RESULTS_FOLDER_ID 환경변수가 설정되지 않았습니다.")
        result.setdefault("saved_at", datetime.now(timezone.utc).isoformat())
        svc = self._service()
        fid = self._find_file_id(svc)
        lines = self._download_lines(svc, fid) if fid else []
        lines.append(json.dumps(result, ensure_ascii=False))
        self._upload(svc, lines, fid)

    def get_result(self, exam_id: str) -> dict | None:
        if not self._folder_id:
            return None
        svc = self._service()
        fid = self._find_file_id(svc)
        if not fid:
            return None
        for line in self._download_lines(svc, fid):
            r = json.loads(line)
            if r.get("exam_id") == exam_id:
                return r
        return None

    def get_all_results(self) -> dict:
        if not self._folder_id:
            return {}
        svc = self._service()
        fid = self._find_file_id(svc)
        if not fid:
            return {}
        results = {}
        for line in self._download_lines(svc, fid):
            r = json.loads(line)
            results[r["exam_id"]] = r
        return results

    def count(self) -> int:
        if not self._folder_id:
            return 0
        svc = self._service()
        fid = self._find_file_id(svc)
        if not fid:
            return 0
        return len(self._download_lines(svc, fid))


class DriveSnapshotRepository(SnapshotRepository):
    """시험 스냅샷을 Google Drive에 저장 — 서버리스 콜드스타트 대응."""

    def __init__(self):
        self._folder_id = os.getenv("DRIVE_RESULTS_FOLDER_ID", "")
        self._snapshots_fid_cache: str | None = None  # 인스턴스당 폴더 ID 캐싱

    def _service(self):
        return _build_drive_service()

    def _get_snapshots_folder_id(self, service) -> str:
        if self._snapshots_fid_cache:
            return self._snapshots_fid_cache
        query = (
            f"name='snapshots' and '{self._folder_id}' in parents "
            f"and mimeType='application/vnd.google-apps.folder' and trashed=false"
        )
        resp = service.files().list(
            q=query, fields="files(id)",
            includeItemsFromAllDrives=True, supportsAllDrives=True,
        ).execute()
        files = resp.get("files", [])
        if files:
            self._snapshots_fid_cache = files[0]["id"]
        else:
            meta = {
                "name": "snapshots",
                "parents": [self._folder_id],
                "mimeType": "application/vnd.google-apps.folder",
            }
            created = service.files().create(
                body=meta, fields="id", supportsAllDrives=True,
            ).execute()
            self._snapshots_fid_cache = created["id"]
        return self._snapshots_fid_cache

    def save_snapshot(self, exam_id: str, snapshot: dict) -> None:
        if not self._folder_id:
            return
        svc = self._service()
        folder_id = self._get_snapshots_folder_id(svc)
        content = json.dumps(snapshot, ensure_ascii=False).encode("utf-8")
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype="application/json", resumable=False)
        svc.files().create(
            body={"name": f"{exam_id}.json", "parents": [folder_id]},
            media_body=media,
            fields="id",
            supportsAllDrives=True,
        ).execute()

    def get_snapshot(self, exam_id: str) -> dict | None:
        if not self._folder_id:
            return None
        svc = self._service()
        folder_id = self._get_snapshots_folder_id(svc)
        # exam_id는 서버 생성 uuid4이므로 쿼리 인젝션 위험 없음
        query = f"name='{exam_id}.json' and '{folder_id}' in parents and trashed=false"
        resp = svc.files().list(
            q=query, fields="files(id)",
            includeItemsFromAllDrives=True, supportsAllDrives=True,
        ).execute()
        files = resp.get("files", [])
        if not files:
            return None
        buf = io.BytesIO()
        dl = MediaIoBaseDownload(buf, svc.files().get_media(fileId=files[0]["id"]))
        done = False
        while not done:
            _, done = dl.next_chunk()
        buf.seek(0)
        return json.loads(buf.read().decode("utf-8"))
