# backend/drive_client.py
import io
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from backend.config import (
    CACHE_DIR, DRIVE_FOLDER_ID, GOOGLE_CLIENT_SECRETS_FILE, SCOPES
)

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/markdown",
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.presentation",
}

GOOGLE_EXPORT_MIME = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
}

MIME_TO_EXT = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "text/plain": ".txt",
    "text/markdown": ".md",
}


@dataclass
class DriveFile:
    id: str
    name: str
    mime_type: str
    size: int


class DriveClient:
    def __init__(self):
        self._credentials: Optional[Credentials] = None
        self._service = None

    @property
    def is_authenticated(self) -> bool:
        return self._credentials is not None and self._credentials.valid

    def get_auth_url(self, redirect_uri: str) -> str:
        flow = Flow.from_client_secrets_file(
            str(GOOGLE_CLIENT_SECRETS_FILE),
            scopes=SCOPES,
            redirect_uri=redirect_uri,
        )
        auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
        self._flow = flow
        return auth_url

    def exchange_code(self, code: str, redirect_uri: str) -> None:
        flow = Flow.from_client_secrets_file(
            str(GOOGLE_CLIENT_SECRETS_FILE),
            scopes=SCOPES,
            redirect_uri=redirect_uri,
        )
        flow.fetch_token(code=code)
        self._credentials = flow.credentials
        self._service = build("drive", "v3", credentials=self._credentials)

    def list_all_files(self, folder_id: str = DRIVE_FOLDER_ID) -> List[DriveFile]:
        return self._list_folder_files(folder_id, recursive=True)

    def _list_folder_files(self, folder_id: str, recursive: bool = False) -> List[DriveFile]:
        results = []
        query = f"'{folder_id}' in parents and trashed = false"
        page_token = None

        while True:
            resp = (
                self._service.files()
                .list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType, size)",
                    pageToken=page_token,
                    pageSize=1000,
                )
                .execute()
            )
            for f in resp.get("files", []):
                mime = f.get("mimeType", "")
                if mime == "application/vnd.google-apps.folder" and recursive:
                    results.extend(self._list_folder_files(f["id"], recursive=True))
                elif mime in SUPPORTED_MIME_TYPES:
                    results.append(DriveFile(
                        id=f["id"],
                        name=f["name"],
                        mime_type=mime,
                        size=int(f.get("size", 0)),
                    ))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return results

    def download_file(self, drive_file: DriveFile) -> Optional[Path]:
        if drive_file.mime_type in GOOGLE_EXPORT_MIME:
            return self._export_google_doc(drive_file)
        ext = MIME_TO_EXT.get(drive_file.mime_type, "")
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in drive_file.name)
        local_path = CACHE_DIR / f"{drive_file.id}_{safe_name}{ext}"
        if local_path.exists():
            return local_path
        try:
            request = self._service.files().get_media(fileId=drive_file.id)
            with io.FileIO(str(local_path), "wb") as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            return local_path
        except Exception:
            return None

    def _export_google_doc(self, drive_file: DriveFile) -> Optional[Path]:
        export_mime, ext = GOOGLE_EXPORT_MIME[drive_file.mime_type]
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in drive_file.name)
        local_path = CACHE_DIR / f"{drive_file.id}_{safe_name}{ext}"
        if local_path.exists():
            return local_path
        try:
            content = (
                self._service.files()
                .export_media(fileId=drive_file.id, mimeType=export_mime)
                .execute()
            )
            local_path.write_bytes(content)
            return local_path
        except Exception:
            return None
