# tests/test_drive_client.py
import pytest
from unittest.mock import MagicMock, patch
from backend.drive_client import DriveClient, DriveFile, SUPPORTED_MIME_TYPES

def test_drive_file_dataclass():
    f = DriveFile(id="123", name="notes.pdf", mime_type="application/pdf", size=1024)
    assert f.id == "123"
    assert f.name == "notes.pdf"

def test_supported_mime_types_not_empty():
    assert len(SUPPORTED_MIME_TYPES) > 0
    assert "application/pdf" in SUPPORTED_MIME_TYPES

def test_list_files_calls_drive_api(tmp_path):
    client = DriveClient.__new__(DriveClient)
    mock_service = MagicMock()
    mock_service.files().list().execute.return_value = {
        "files": [
            {"id": "abc", "name": "lecture.pdf", "mimeType": "application/pdf", "size": "2048"},
        ]
    }
    client._service = mock_service

    files = client._list_folder_files("folder123")
    assert len(files) == 1
    assert files[0].name == "lecture.pdf"
    assert files[0].id == "abc"

def test_is_authenticated_false_without_credentials():
    client = DriveClient.__new__(DriveClient)
    client._credentials = None
    assert client.is_authenticated is False
