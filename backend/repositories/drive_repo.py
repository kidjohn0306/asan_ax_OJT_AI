import io
import json
import os
from datetime import datetime, timezone

from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from repositories.base import ResultRepository

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
        resp = service.files().list(q=query, fields="files(id)").execute()
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
            service.files().update(fileId=file_id, media_body=media).execute()
            return file_id
        meta = {"name": _RESULTS_FILENAME, "parents": [self._folder_id]}
        created = service.files().create(body=meta, media_body=media, fields="id").execute()
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
