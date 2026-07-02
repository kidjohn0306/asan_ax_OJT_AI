import io
import json
import os
from datetime import datetime, timezone

from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from repositories.base import ResultRepository, SnapshotRepository

_RESULTS_FILENAME = "results.jsonl"


def _build_drive_service():
    from services.drive_service import DriveService
    return DriveService().service


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
