# Vectorless RAG with PageIndex — Academic Drive Chatbot

> **For Claude:** REQUIRED SUB-SKILL: Use parallel-plan-execution to implement this plan task-by-task.

**Goal:** Build a web-based AI chatbot that searches the user's Google Drive academic folder using BM25-based PageIndex (no vector embeddings), shows relevant source pages, and generates answers via Google Gemini API (free tier).

**Architecture:** Google Drive files are downloaded and parsed page-by-page into a BM25 PageIndex (each page is a separate retrieval unit). On user query, BM25 retrieves the top-k most relevant pages; those pages plus the query are sent to Gemini to generate a grounded answer. No vector DB or embeddings required — pure keyword-based sparse retrieval.

**Tech Stack:** Python 3.11+, FastAPI, rank-bm25, PyMuPDF (fitz), python-docx, python-pptx, google-api-python-client, google-auth-oauthlib, google-generativeai SDK, Vanilla JS + HTML/CSS (no build step)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                      Web Browser                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Chat UI (HTML/CSS/JS)                            │  │
│  │  - Chatbot interface                              │  │
│  │  - Source document cards with page highlights    │  │
│  │  - Google OAuth login button                     │  │
│  └─────────────────┬─────────────────────────────────┘  │
└────────────────────┼────────────────────────────────────┘
                     │ HTTP/SSE
┌────────────────────▼────────────────────────────────────┐
│                  FastAPI Backend                          │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ DriveClient │  │  DocProcessor│  │   PageIndex    │  │
│  │             │  │              │  │                │  │
│  │ OAuth2 flow │  │ PDF → pages  │  │ BM25 index     │  │
│  │ List files  │  │ DOCX → pages │  │ per page       │  │
│  │ Download    │  │ PPTX → pages │  │ search(query)  │  │
│  └──────┬──────┘  └──────┬───────┘  └───────┬────────┘  │
│         │                │                   │           │
│  ┌──────▼────────────────▼───────────────────▼────────┐  │
│  │                  RAG Engine                         │  │
│  │  retrieve(query) → top-k pages → Gemini API        │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                     │
        ┌────────────▼───────────────┐
        │   Google Drive API         │
        │   (user's academic folder) │
        └────────────────────────────┘
```

## PageIndex Concept

Each page of every document becomes an independent "chunk" in the index:

```
PageEntry {
  doc_id:     "fileId_from_drive"
  doc_name:   "Calculus 101.pdf"
  page_num:   3
  text:       "The derivative of f(x)..."
  char_count: 842
}
```

BM25 scores all pages against the query. Top-k pages (from potentially different documents) are returned as context for Gemini.

---

## Project Structure

```
RAG-DingDong/
├── backend/
│   ├── main.py                  # FastAPI app + routes
│   ├── config.py                # Settings from env vars
│   ├── drive_client.py          # Google Drive OAuth2 + file ops
│   ├── document_processor.py   # Text extraction per page
│   ├── page_index.py            # BM25 PageIndex
│   ├── rag_engine.py            # Retrieve + generate pipeline
│   └── requirements.txt
├── frontend/
│   ├── index.html               # Main app shell
│   ├── style.css                # Styles
│   └── app.js                   # Chat logic + API calls
├── data/
│   ├── index/                   # Persisted index (JSON)
│   └── cache/                   # Downloaded Drive files
├── .env.example
└── docs/plans/
```

---

## Pre-Implementation: Google Cloud Setup (Manual Step)

Before coding, the user must:

1. Go to https://console.cloud.google.com
2. Create a new project (e.g. "RAG-DingDong")
3. Enable **Google Drive API**
4. Create **OAuth 2.0 credentials** (Web Application type)
   - Authorized redirect URI: `http://localhost:8000/auth/callback`
5. Download credentials as `client_secret.json` → place in `backend/`
6. Get a **Gemini API key** (free) from https://aistudio.google.com/apikey — same Google account, no credit card

---

## Session 1: Project Scaffold + Document Pipeline

**Exit criteria:** Can extract pages from PDFs/DOCX/PPTX, build BM25 index, search it, and save/load to disk. All unit tests green.

---

### Task 1: Project scaffold + requirements

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/config.py`
- Create: `.env.example`

**Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
python-multipart==0.0.9
rank-bm25==0.2.2
PyMuPDF==1.24.10
python-docx==1.1.2
python-pptx==1.0.2
google-api-python-client==2.143.0
google-auth-oauthlib==1.2.1
google-auth-httplib2==0.2.0
google-generativeai==0.8.3
python-dotenv==1.0.1
httpx==0.27.0
```

**Step 2: Create config.py**

```python
# backend/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
INDEX_DIR = DATA_DIR / "index"

# Create dirs on import
CACHE_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GOOGLE_CLIENT_SECRETS_FILE = Path(__file__).parent / "client_secret.json"
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "1R22isu0HXNka5aU3X9KYqDraW9esTeyW")

GEMINI_MODEL = "gemini-1.5-flash"   # free tier: 15 req/min, 1M tokens/day
TOP_K_PAGES = 8          # pages retrieved per query
MAX_PAGE_CHARS = 3000    # truncate very long pages
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
```

**Step 3: Create .env.example**

```env
GEMINI_API_KEY=your_gemini_api_key_here
DRIVE_FOLDER_ID=1R22isu0HXNka5aU3X9KYqDraW9esTeyW
```

**Step 4: Install dependencies**

```bash
cd backend
pip install -r requirements.txt
```

**Step 5: Commit**

```bash
git add backend/requirements.txt backend/config.py .env.example
git commit -m "feat: project scaffold and config"
```

---

### Task 2: Document Processor — page-level text extraction

**Files:**
- Create: `backend/document_processor.py`
- Create: `tests/test_document_processor.py`

**Step 1: Write tests**

```python
# tests/test_document_processor.py
import pytest
from pathlib import Path
from backend.document_processor import extract_pages, PageEntry

# We'll use a tiny synthetic PDF created in the fixture
def test_extract_pages_returns_list_of_page_entries(tmp_path):
    """Each returned item must be a PageEntry with required fields."""
    # Create a simple text file to test
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("Hello world\nThis is page content.")

    pages = extract_pages(str(txt_file), "test_doc_id", "test.txt")

    assert isinstance(pages, list)
    assert len(pages) == 1
    entry = pages[0]
    assert entry.doc_id == "test_doc_id"
    assert entry.doc_name == "test.txt"
    assert entry.page_num == 1
    assert "Hello world" in entry.text

def test_unsupported_format_returns_empty(tmp_path):
    f = tmp_path / "file.xyz"
    f.write_text("data")
    pages = extract_pages(str(f), "id1", "file.xyz")
    assert pages == []

def test_page_entry_text_truncated_to_max_chars():
    from backend.document_processor import PageEntry, MAX_PAGE_CHARS
    big_text = "x" * (MAX_PAGE_CHARS + 500)
    entry = PageEntry(doc_id="d", doc_name="f", page_num=1, text=big_text)
    assert len(entry.text) <= MAX_PAGE_CHARS
```

**Step 2: Run to verify failure**

```bash
cd backend && python -m pytest ../tests/test_document_processor.py -v
```
Expected: `ModuleNotFoundError: No module named 'backend.document_processor'`

**Step 3: Implement document_processor.py**

```python
# backend/document_processor.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import List
import fitz  # PyMuPDF
from backend.config import MAX_PAGE_CHARS

@dataclass
class PageEntry:
    doc_id: str
    doc_name: str
    page_num: int         # 1-based
    text: str

    def __post_init__(self):
        # Truncate to avoid sending huge pages to BM25/Claude
        self.text = self.text[:MAX_PAGE_CHARS]


def extract_pages(file_path: str, doc_id: str, doc_name: str) -> List[PageEntry]:
    """Extract text per page from a document. Returns [] for unsupported formats."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(file_path, doc_id, doc_name)
    elif suffix in (".docx",):
        return _extract_docx(file_path, doc_id, doc_name)
    elif suffix in (".pptx",):
        return _extract_pptx(file_path, doc_id, doc_name)
    elif suffix in (".txt", ".md"):
        return _extract_text(file_path, doc_id, doc_name)
    else:
        return []


def _extract_pdf(file_path: str, doc_id: str, doc_name: str) -> List[PageEntry]:
    pages = []
    doc = fitz.open(file_path)
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if text:
            pages.append(PageEntry(doc_id=doc_id, doc_name=doc_name, page_num=i, text=text))
    doc.close()
    return pages


def _extract_docx(file_path: str, doc_id: str, doc_name: str) -> List[PageEntry]:
    from docx import Document
    doc = Document(file_path)
    # DOCX has no hard pages; group every 30 paragraphs as a "page"
    PARAS_PER_PAGE = 30
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    pages = []
    for i in range(0, len(paragraphs), PARAS_PER_PAGE):
        chunk = "\n".join(paragraphs[i:i + PARAS_PER_PAGE])
        page_num = (i // PARAS_PER_PAGE) + 1
        pages.append(PageEntry(doc_id=doc_id, doc_name=doc_name, page_num=page_num, text=chunk))
    return pages


def _extract_pptx(file_path: str, doc_id: str, doc_name: str) -> List[PageEntry]:
    from pptx import Presentation
    prs = Presentation(file_path)
    pages = []
    for i, slide in enumerate(prs.slides, start=1):
        texts = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                texts.append(shape.text.strip())
        if texts:
            pages.append(PageEntry(
                doc_id=doc_id, doc_name=doc_name,
                page_num=i, text="\n".join(texts)
            ))
    return pages


def _extract_text(file_path: str, doc_id: str, doc_name: str) -> List[PageEntry]:
    text = Path(file_path).read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return []
    return [PageEntry(doc_id=doc_id, doc_name=doc_name, page_num=1, text=text)]
```

**Step 4: Run tests**

```bash
cd backend && python -m pytest ../tests/test_document_processor.py -v
```
Expected: 3 tests PASS

**Step 5: Commit**

```bash
git add backend/document_processor.py tests/test_document_processor.py
git commit -m "feat: document processor — page extraction for PDF/DOCX/PPTX/TXT"
```

---

### Task 3: BM25 PageIndex — build, search, persist

**Files:**
- Create: `backend/page_index.py`
- Create: `tests/test_page_index.py`

**Step 1: Write tests**

```python
# tests/test_page_index.py
import pytest
from backend.document_processor import PageEntry
from backend.page_index import PageIndex

SAMPLE_PAGES = [
    PageEntry("doc1", "Calculus.pdf", 1, "The derivative is the rate of change of a function"),
    PageEntry("doc1", "Calculus.pdf", 2, "Integrals compute the area under a curve"),
    PageEntry("doc2", "Algorithms.pdf", 1, "Binary search runs in O(log n) time"),
    PageEntry("doc2", "Algorithms.pdf", 2, "Sorting algorithms like quicksort use divide and conquer"),
    PageEntry("doc3", "Physics.pdf", 1, "Newton's second law: force equals mass times acceleration"),
]

def test_build_and_search_returns_relevant_results():
    idx = PageIndex()
    idx.build(SAMPLE_PAGES)
    results = idx.search("derivative calculus", top_k=2)
    assert len(results) > 0
    assert results[0].doc_name == "Calculus.pdf"

def test_search_returns_at_most_top_k():
    idx = PageIndex()
    idx.build(SAMPLE_PAGES)
    results = idx.search("algorithm sorting search", top_k=2)
    assert len(results) <= 2

def test_search_with_empty_index_returns_empty():
    idx = PageIndex()
    results = idx.search("anything")
    assert results == []

def test_save_and_load_roundtrip(tmp_path):
    idx = PageIndex()
    idx.build(SAMPLE_PAGES)
    save_path = tmp_path / "index.json"
    idx.save(str(save_path))

    idx2 = PageIndex()
    idx2.load(str(save_path))

    results = idx2.search("binary search algorithm", top_k=1)
    assert len(results) == 1
    assert results[0].doc_name == "Algorithms.pdf"

def test_page_count():
    idx = PageIndex()
    idx.build(SAMPLE_PAGES)
    assert idx.page_count == 5

def test_doc_list():
    idx = PageIndex()
    idx.build(SAMPLE_PAGES)
    docs = idx.doc_names
    assert "Calculus.pdf" in docs
    assert "Algorithms.pdf" in docs
```

**Step 2: Run to verify failure**

```bash
python -m pytest tests/test_page_index.py -v
```
Expected: `ModuleNotFoundError: No module named 'backend.page_index'`

**Step 3: Implement page_index.py**

```python
# backend/page_index.py
import json
from pathlib import Path
from typing import List
from dataclasses import asdict
from rank_bm25 import BM25Okapi
from backend.document_processor import PageEntry


def _tokenize(text: str) -> List[str]:
    """Simple whitespace + lowercase tokenizer."""
    return text.lower().split()


class PageIndex:
    """BM25-based page-level index. No vectors, no embeddings."""

    def __init__(self):
        self._pages: List[PageEntry] = []
        self._bm25: BM25Okapi | None = None

    def build(self, pages: List[PageEntry]) -> None:
        self._pages = pages
        corpus = [_tokenize(p.text) for p in pages]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def search(self, query: str, top_k: int = 8) -> List[PageEntry]:
        if not self._bm25 or not self._pages:
            return []
        tokens = _tokenize(query)
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [self._pages[i] for i in ranked[:top_k] if scores[i] > 0]

    @property
    def page_count(self) -> int:
        return len(self._pages)

    @property
    def doc_names(self) -> List[str]:
        return list({p.doc_name for p in self._pages})

    def save(self, path: str) -> None:
        data = [
            {
                "doc_id": p.doc_id,
                "doc_name": p.doc_name,
                "page_num": p.page_num,
                "text": p.text,
            }
            for p in self._pages
        ]
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, path: str) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        pages = [
            PageEntry(
                doc_id=d["doc_id"],
                doc_name=d["doc_name"],
                page_num=d["page_num"],
                text=d["text"],
            )
            for d in data
        ]
        self.build(pages)
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_page_index.py -v
```
Expected: 6 tests PASS

**Step 5: Commit**

```bash
git add backend/page_index.py tests/test_page_index.py
git commit -m "feat: BM25 PageIndex with save/load persistence"
```

---

### Task 4: Google Drive Client — OAuth2 + file listing + download

**Files:**
- Create: `backend/drive_client.py`
- Create: `tests/test_drive_client.py`

**Step 1: Write tests (mocked — no real Drive calls in tests)**

```python
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
```

**Step 2: Run to verify failure**

```bash
python -m pytest tests/test_drive_client.py -v
```

**Step 3: Implement drive_client.py**

```python
# backend/drive_client.py
import io
import os
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
    # Google Docs exported as PDF
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
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent",
        )
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
        """Recursively list all supported files in folder and subfolders."""
        return self._list_folder_files(folder_id, recursive=True)

    def _list_folder_files(
        self, folder_id: str, recursive: bool = False
    ) -> List[DriveFile]:
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
                    results.append(
                        DriveFile(
                            id=f["id"],
                            name=f["name"],
                            mime_type=mime,
                            size=int(f.get("size", 0)),
                        )
                    )
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return results

    def download_file(self, drive_file: DriveFile) -> Optional[Path]:
        """Download file to cache dir. Returns local path or None on failure."""
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
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_drive_client.py -v
```
Expected: 4 tests PASS

**Step 5: Commit**

```bash
git add backend/drive_client.py tests/test_drive_client.py
git commit -m "feat: Google Drive client with OAuth2, file listing and download"
```

---

## Session 2: RAG Engine + FastAPI Backend

**Exit criteria:** `/api/index` triggers Drive crawl + index build. `/api/chat` returns Claude answers with source citations. All API tests green.

---

### Task 5: RAG Engine — retrieve pages + generate answer

**Files:**
- Create: `backend/rag_engine.py`
- Create: `tests/test_rag_engine.py`

**Step 1: Write tests**

```python
# tests/test_rag_engine.py
import pytest
from unittest.mock import MagicMock, patch
from backend.document_processor import PageEntry
from backend.page_index import PageIndex
from backend.rag_engine import RAGEngine, ChatMessage, RAGResponse

SAMPLE_PAGES = [
    PageEntry("doc1", "Calculus.pdf", 3, "The chain rule states d/dx[f(g(x))] = f'(g(x))·g'(x)"),
    PageEntry("doc2", "Physics.pdf", 1, "Newton's second law F=ma describes force and acceleration"),
]

def make_index():
    idx = PageIndex()
    idx.build(SAMPLE_PAGES)
    return idx

def test_rag_response_has_required_fields():
    r = RAGResponse(answer="42", sources=SAMPLE_PAGES[:1], query="test")
    assert r.answer == "42"
    assert len(r.sources) == 1
    assert r.query == "test"

def test_retrieve_returns_relevant_pages():
    engine = RAGEngine(index=make_index(), api_key="fake")
    pages = engine._retrieve("chain rule derivative")
    assert len(pages) > 0
    assert any("chain rule" in p.text.lower() for p in pages)

def test_retrieve_empty_query_returns_empty():
    engine = RAGEngine(index=make_index(), api_key="fake")
    pages = engine._retrieve("   ")
    assert pages == []

def test_build_prompt_contains_query_and_pages():
    engine = RAGEngine(index=make_index(), api_key="fake")
    prompt = engine._build_prompt("What is the chain rule?", SAMPLE_PAGES)
    assert "chain rule" in prompt.lower()
    assert "Calculus.pdf" in prompt

@patch("backend.rag_engine.genai.GenerativeModel")
def test_chat_calls_gemini_and_returns_response(mock_model_cls):
    mock_model = MagicMock()
    mock_model_cls.return_value = mock_model
    mock_model.generate_content.return_value.text = (
        "The chain rule is used for composite functions."
    )

    engine = RAGEngine(index=make_index(), api_key="fake")
    response = engine.chat("What is the chain rule?")

    assert isinstance(response, RAGResponse)
    assert "chain rule" in response.answer.lower()
    assert len(response.sources) > 0
```

**Step 2: Run to verify failure**

```bash
python -m pytest tests/test_rag_engine.py -v
```

**Step 3: Implement rag_engine.py**

```python
# backend/rag_engine.py
from dataclasses import dataclass
from typing import List, Optional
import google.generativeai as genai
from backend.document_processor import PageEntry
from backend.page_index import PageIndex
from backend.config import GEMINI_MODEL, TOP_K_PAGES


@dataclass
class ChatMessage:
    role: str   # "user" | "model"  (Gemini uses "model" not "assistant")
    content: str


@dataclass
class RAGResponse:
    answer: str
    sources: List[PageEntry]
    query: str


SYSTEM_PROMPT = """You are an academic assistant helping a student search and understand their study materials.
You will be given excerpts from relevant pages of their documents, followed by their question.
Answer based ONLY on the provided excerpts. If the answer is not in the excerpts, say so clearly.
Cite the document name and page number when you reference information (e.g., [Calculus.pdf, p.3]).
Be concise, accurate, and helpful."""


class RAGEngine:
    def __init__(self, index: PageIndex, api_key: str):
        self._index = index
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
        )

    def chat(self, query: str, history: List[ChatMessage] | None = None) -> RAGResponse:
        sources = self._retrieve(query)
        if not sources:
            return RAGResponse(
                answer="I couldn't find relevant pages for your query. "
                       "Try re-indexing or rephrasing your question.",
                sources=[],
                query=query,
            )
        prompt = self._build_prompt(query, sources)

        # Build Gemini chat history format
        gemini_history = []
        for msg in (history or []):
            gemini_history.append({
                "role": msg.role,          # "user" or "model"
                "parts": [msg.content],
            })

        chat_session = self._model.start_chat(history=gemini_history)
        response = chat_session.send_message(prompt)
        answer = response.text
        return RAGResponse(answer=answer, sources=sources, query=query)

    def _retrieve(self, query: str) -> List[PageEntry]:
        if not query.strip():
            return []
        return self._index.search(query, top_k=TOP_K_PAGES)

    def _build_prompt(self, query: str, pages: List[PageEntry]) -> str:
        context_blocks = []
        for p in pages:
            context_blocks.append(
                f"[{p.doc_name}, page {p.page_num}]\n{p.text}"
            )
        context = "\n\n---\n\n".join(context_blocks)
        return f"Relevant excerpts from study materials:\n\n{context}\n\n---\n\nQuestion: {query}"
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_rag_engine.py -v
```
Expected: 5 tests PASS

**Step 5: Commit**

```bash
git add backend/rag_engine.py tests/test_rag_engine.py
git commit -m "feat: RAG engine — BM25 retrieval + Claude answer generation"
```

---

### Task 6: FastAPI backend — all routes

**Files:**
- Create: `backend/main.py`
- Create: `tests/test_api.py`

**Step 1: Write tests**

```python
# tests/test_api.py
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app, follow_redirects=False)

def test_health_check():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_status_returns_index_stats():
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert "indexed" in data
    assert "page_count" in data
    assert "doc_count" in data

def test_chat_without_index_returns_not_ready():
    # Before indexing, chat should return a not-ready message
    r = client.post("/api/chat", json={"query": "hello"})
    assert r.status_code in (200, 503)

def test_chat_empty_query_returns_400():
    r = client.post("/api/chat", json={"query": "   "})
    assert r.status_code == 400

def test_auth_login_redirects():
    r = client.get("/auth/login")
    # Redirects to Google OAuth or returns error if no client_secret.json
    assert r.status_code in (302, 500, 503)

def test_docs_list_before_index():
    r = client.get("/api/docs")
    assert r.status_code == 200
    assert "docs" in r.json()
```

**Step 2: Run to verify failure**

```bash
python -m pytest tests/test_api.py -v
```

**Step 3: Implement main.py**

```python
# backend/main.py
import os
import json
import threading
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import (
    GEMINI_API_KEY, DRIVE_FOLDER_ID, INDEX_DIR, BASE_DIR
)
from backend.drive_client import DriveClient
from backend.document_processor import extract_pages
from backend.page_index import PageIndex
from backend.rag_engine import RAGEngine, ChatMessage

app = FastAPI(title="RAG-DingDong Academic Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

# ── Global singletons ──────────────────────────────────────────────────────────
_drive_client = DriveClient()
_page_index = PageIndex()
_rag_engine: Optional[RAGEngine] = None
_index_file = INDEX_DIR / "page_index.json"
_index_status = {"indexed": False, "page_count": 0, "doc_count": 0, "indexing": False}

# Load persisted index on startup
if _index_file.exists():
    _page_index.load(str(_index_file))
    _index_status.update({
        "indexed": True,
        "page_count": _page_index.page_count,
        "doc_count": len(_page_index.doc_names),
    })
    _rag_engine = RAGEngine(index=_page_index, api_key=GEMINI_API_KEY)

REDIRECT_URI = "http://localhost:8000/auth/callback"


# ── Auth routes ────────────────────────────────────────────────────────────────

@app.get("/auth/login")
def login():
    try:
        url = _drive_client.get_auth_url(REDIRECT_URI)
        return RedirectResponse(url)
    except Exception as e:
        raise HTTPException(503, f"Google OAuth not configured: {e}")


@app.get("/auth/callback")
def auth_callback(code: str, request: Request):
    _drive_client.exchange_code(code, REDIRECT_URI)
    return RedirectResponse("/?auth=success")


@app.get("/auth/status")
def auth_status():
    return {"authenticated": _drive_client.is_authenticated}


# ── Index routes ────────────────────────────────────────────────────────────────

@app.post("/api/index")
async def trigger_index(background_tasks: BackgroundTasks):
    if not _drive_client.is_authenticated:
        raise HTTPException(401, "Not authenticated with Google Drive")
    if _index_status["indexing"]:
        return {"message": "Indexing already in progress"}
    background_tasks.add_task(_build_index)
    return {"message": "Indexing started"}


def _build_index():
    global _rag_engine
    _index_status["indexing"] = True
    all_pages = []
    try:
        files = _drive_client.list_all_files(DRIVE_FOLDER_ID)
        for f in files:
            local_path = _drive_client.download_file(f)
            if local_path:
                pages = extract_pages(str(local_path), f.id, f.name)
                all_pages.extend(pages)
        _page_index.build(all_pages)
        _page_index.save(str(_index_file))
        _rag_engine = RAGEngine(index=_page_index, api_key=GEMINI_API_KEY)
        _index_status.update({
            "indexed": True,
            "page_count": _page_index.page_count,
            "doc_count": len(_page_index.doc_names),
        })
    finally:
        _index_status["indexing"] = False


# ── Status & docs ──────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/status")
def status():
    return _index_status


@app.get("/api/docs")
def list_docs():
    return {"docs": _page_index.doc_names}


# ── Chat ────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str
    history: List[dict] = []


@app.post("/api/chat")
def chat(req: ChatRequest):
    if not req.query.strip():
        raise HTTPException(400, "Query cannot be empty")
    if _rag_engine is None:
        return JSONResponse(
            status_code=503,
            content={"answer": "Index not ready. Please authenticate and click 'Index Drive'.", "sources": []},
        )
    # Gemini uses "user"/"model" roles (frontend sends "user"/"assistant" — remap)
    history = [
        ChatMessage(role="model" if m["role"] == "assistant" else m["role"], content=m["content"])
        for m in req.history
    ]
    response = _rag_engine.chat(req.query, history)
    return {
        "answer": response.answer,
        "sources": [
            {
                "doc_name": p.doc_name,
                "page_num": p.page_num,
                "snippet": p.text[:300],
            }
            for p in response.sources
        ],
        "query": response.query,
    }


# ── Frontend fallback ──────────────────────────────────────────────────────────

@app.get("/")
def root():
    index_html = BASE_DIR / "frontend" / "index.html"
    if index_html.exists():
        from fastapi.responses import FileResponse
        return FileResponse(str(index_html))
    return {"message": "RAG-DingDong API running"}
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_api.py -v
```
Expected: 6 tests PASS

**Step 5: Commit**

```bash
git add backend/main.py tests/test_api.py
git commit -m "feat: FastAPI backend — auth, index, status, chat endpoints"
```

---

## Session 3: Frontend Chatbot UI

**Exit criteria:** Opening `http://localhost:8000` shows a working chat interface with Google login, index button, chat input, response display with source cards.

---

### Task 7: HTML shell + CSS

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/style.css`

**Step 1: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>RAG-DingDong — Academic Assistant</title>
  <link rel="stylesheet" href="/static/style.css" />
</head>
<body>
  <div class="app">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <h1 class="logo">📚 DingDong</h1>
        <p class="tagline">Academic Drive Search</p>
      </div>

      <!-- Auth section -->
      <div class="section" id="auth-section">
        <h3>Google Drive</h3>
        <div id="auth-status-msg" class="status-msg">Checking...</div>
        <a id="login-btn" href="/auth/login" class="btn btn-primary hidden">
          Login with Google
        </a>
        <div id="logged-in-info" class="hidden">
          <span class="badge badge-green">Connected</span>
        </div>
      </div>

      <!-- Index section -->
      <div class="section" id="index-section">
        <h3>Knowledge Index</h3>
        <div id="index-stats" class="stats-grid">
          <div class="stat"><span id="stat-pages">—</span><small>pages</small></div>
          <div class="stat"><span id="stat-docs">—</span><small>documents</small></div>
        </div>
        <button id="index-btn" class="btn btn-secondary" disabled>
          Build Index
        </button>
        <div id="index-progress" class="progress-bar hidden">
          <div class="progress-fill"></div>
        </div>
        <div id="index-msg" class="status-msg"></div>
      </div>

      <!-- Docs list -->
      <div class="section" id="docs-section">
        <h3>Indexed Documents</h3>
        <ul id="docs-list" class="docs-list"></ul>
      </div>
    </aside>

    <!-- Main chat area -->
    <main class="chat-area">
      <div class="chat-header">
        <h2>Ask about your study materials</h2>
      </div>

      <!-- Messages -->
      <div class="messages" id="messages">
        <div class="welcome-msg">
          <p>Login with Google Drive and build the index to get started.</p>
          <p>Then ask me anything about your academic materials!</p>
        </div>
      </div>

      <!-- Sources panel -->
      <div id="sources-panel" class="sources-panel hidden">
        <h4>Source Pages</h4>
        <div id="sources-list" class="sources-list"></div>
      </div>

      <!-- Input -->
      <div class="input-area">
        <textarea
          id="query-input"
          placeholder="Ask something about your study materials..."
          rows="2"
          disabled
        ></textarea>
        <button id="send-btn" class="btn btn-send" disabled>Send</button>
      </div>
    </main>
  </div>

  <script src="/static/app.js"></script>
</body>
</html>
```

**Step 2: Create style.css**

```css
/* frontend/style.css */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #0f1117;
  --surface: #1a1d2e;
  --surface2: #252840;
  --border: #2e3150;
  --accent: #6c63ff;
  --accent2: #4ade80;
  --text: #e2e8f0;
  --text-muted: #94a3b8;
  --user-bubble: #6c63ff22;
  --assistant-bubble: #1e2235;
  --danger: #f87171;
  --radius: 12px;
  --font: 'Segoe UI', system-ui, sans-serif;
}

body { background: var(--bg); color: var(--text); font-family: var(--font); height: 100vh; overflow: hidden; }

.app { display: flex; height: 100vh; }

/* Sidebar */
.sidebar {
  width: 280px; min-width: 240px;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
  padding: 20px 16px;
  overflow-y: auto; gap: 8px;
}
.sidebar-header { padding-bottom: 16px; border-bottom: 1px solid var(--border); margin-bottom: 8px; }
.logo { font-size: 1.4rem; font-weight: 700; color: var(--accent); }
.tagline { font-size: 0.75rem; color: var(--text-muted); margin-top: 2px; }

.section { padding: 12px 0; border-bottom: 1px solid var(--border); }
.section h3 { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-muted); margin-bottom: 10px; }

.btn {
  display: inline-block; padding: 8px 14px; border-radius: 8px;
  font-size: 0.85rem; font-weight: 600; cursor: pointer;
  border: none; transition: opacity 0.15s, transform 0.1s;
  text-decoration: none; text-align: center; width: 100%;
}
.btn:hover:not(:disabled) { opacity: 0.85; transform: translateY(-1px); }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-primary { background: var(--accent); color: white; }
.btn-secondary { background: var(--surface2); color: var(--text); border: 1px solid var(--border); }
.btn-send {
  background: var(--accent); color: white;
  padding: 10px 20px; border-radius: 10px; width: auto;
  align-self: flex-end;
}

.hidden { display: none !important; }
.badge { font-size: 0.75rem; padding: 2px 8px; border-radius: 999px; font-weight: 600; }
.badge-green { background: #166534; color: var(--accent2); }

.stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
.stat {
  background: var(--surface2); border-radius: 8px; padding: 10px;
  text-align: center; display: flex; flex-direction: column; gap: 2px;
}
.stat span { font-size: 1.4rem; font-weight: 700; color: var(--accent); }
.stat small { font-size: 0.7rem; color: var(--text-muted); }

.status-msg { font-size: 0.8rem; color: var(--text-muted); margin-bottom: 8px; min-height: 18px; }

.progress-bar { height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; margin: 8px 0; }
.progress-fill { height: 100%; width: 60%; background: var(--accent); border-radius: 2px; animation: progress-anim 1.5s ease-in-out infinite; }
@keyframes progress-anim { 0% { transform: translateX(-100%); } 100% { transform: translateX(200%); } }

.docs-list { list-style: none; display: flex; flex-direction: column; gap: 4px; }
.docs-list li {
  font-size: 0.78rem; color: var(--text-muted); padding: 6px 8px;
  background: var(--surface2); border-radius: 6px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* Chat */
.chat-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.chat-header {
  padding: 16px 24px; border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.chat-header h2 { font-size: 1rem; color: var(--text-muted); font-weight: 500; }

.messages {
  flex: 1; overflow-y: auto; padding: 24px;
  display: flex; flex-direction: column; gap: 16px;
}
.welcome-msg { text-align: center; color: var(--text-muted); padding: 40px 20px; line-height: 1.8; }

.message { display: flex; flex-direction: column; gap: 4px; max-width: 85%; }
.message.user { align-self: flex-end; align-items: flex-end; }
.message.assistant { align-self: flex-start; align-items: flex-start; }
.message-label { font-size: 0.7rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; padding: 0 4px; }
.bubble {
  padding: 12px 16px; border-radius: var(--radius);
  font-size: 0.9rem; line-height: 1.6;
  white-space: pre-wrap; word-break: break-word;
}
.message.user .bubble { background: var(--user-bubble); border: 1px solid var(--accent); color: var(--text); border-bottom-right-radius: 4px; }
.message.assistant .bubble { background: var(--assistant-bubble); border: 1px solid var(--border); border-bottom-left-radius: 4px; }
.message.thinking .bubble { color: var(--text-muted); font-style: italic; animation: pulse 1.5s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: 0.6; } 50% { opacity: 1; } }

/* Sources */
.sources-panel {
  border-top: 1px solid var(--border);
  background: var(--surface); padding: 12px 24px;
  max-height: 220px;
}
.sources-panel h4 { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); margin-bottom: 10px; }
.sources-list { display: flex; gap: 12px; overflow-x: auto; padding-bottom: 4px; }
.source-card {
  min-width: 220px; max-width: 260px; background: var(--surface2);
  border: 1px solid var(--border); border-radius: 10px; padding: 12px;
  flex-shrink: 0;
}
.source-card .doc-name { font-size: 0.78rem; font-weight: 700; color: var(--accent); margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.source-card .page-num { font-size: 0.7rem; color: var(--text-muted); margin-bottom: 6px; }
.source-card .snippet { font-size: 0.75rem; color: var(--text-muted); line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }

/* Input */
.input-area {
  display: flex; gap: 12px; padding: 16px 24px;
  border-top: 1px solid var(--border); background: var(--surface);
  align-items: flex-end;
}
#query-input {
  flex: 1; background: var(--surface2); border: 1px solid var(--border);
  border-radius: 10px; color: var(--text); font-family: var(--font);
  font-size: 0.9rem; padding: 12px 16px; resize: none; outline: none;
  transition: border-color 0.2s;
}
#query-input:focus { border-color: var(--accent); }
#query-input:disabled { opacity: 0.5; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
```

**Step 3: Commit**

```bash
git add frontend/index.html frontend/style.css
git commit -m "feat: frontend HTML shell and dark-mode CSS"
```

---

### Task 8: Frontend JavaScript — chat logic + API integration

**Files:**
- Create: `frontend/app.js`

**Step 1: Implement app.js**

```javascript
// frontend/app.js
const API = "";  // same origin

// ── State ──────────────────────────────────────────────────────────────────────
let chatHistory = [];
let isIndexed = false;
let isAuthenticated = false;

// ── DOM refs ───────────────────────────────────────────────────────────────────
const messagesEl = document.getElementById("messages");
const queryInput = document.getElementById("query-input");
const sendBtn = document.getElementById("send-btn");
const indexBtn = document.getElementById("index-btn");
const loginBtn = document.getElementById("login-btn");
const loggedInInfo = document.getElementById("logged-in-info");
const authStatusMsg = document.getElementById("auth-status-msg");
const indexMsg = document.getElementById("index-msg");
const indexProgress = document.getElementById("index-progress");
const statPages = document.getElementById("stat-pages");
const statDocs = document.getElementById("stat-docs");
const docsList = document.getElementById("docs-list");
const sourcesPanel = document.getElementById("sources-panel");
const sourcesList = document.getElementById("sources-list");

// ── Init ───────────────────────────────────────────────────────────────────────
async function init() {
  // Check if redirected after auth
  const params = new URLSearchParams(window.location.search);
  if (params.get("auth") === "success") {
    window.history.replaceState({}, "", "/");
  }
  await checkAuth();
  await loadStatus();
}

// ── Auth ────────────────────────────────────────────────────────────────────────
async function checkAuth() {
  try {
    const r = await fetch(`${API}/auth/status`);
    const data = await r.json();
    isAuthenticated = data.authenticated;
    if (isAuthenticated) {
      loginBtn.classList.add("hidden");
      loggedInInfo.classList.remove("hidden");
      authStatusMsg.textContent = "Connected to Google Drive";
      indexBtn.disabled = false;
    } else {
      loginBtn.classList.remove("hidden");
      loggedInInfo.classList.add("hidden");
      authStatusMsg.textContent = "Not connected";
    }
  } catch {
    authStatusMsg.textContent = "Could not reach API";
  }
}

// ── Status & docs ──────────────────────────────────────────────────────────────
async function loadStatus() {
  try {
    const [statusR, docsR] = await Promise.all([
      fetch(`${API}/api/status`),
      fetch(`${API}/api/docs`),
    ]);
    const status = await statusR.json();
    const docsData = await docsR.json();

    isIndexed = status.indexed;
    statPages.textContent = status.page_count || "—";
    statDocs.textContent = status.doc_count || "—";

    if (status.indexing) {
      indexMsg.textContent = "Indexing in progress...";
      indexProgress.classList.remove("hidden");
      indexBtn.disabled = true;
      setTimeout(loadStatus, 3000);
    } else {
      indexProgress.classList.add("hidden");
    }

    docsList.innerHTML = "";
    for (const name of (docsData.docs || [])) {
      const li = document.createElement("li");
      li.title = name;
      li.textContent = name;
      docsList.appendChild(li);
    }

    if (isIndexed) {
      enableChat();
      indexMsg.textContent = `Index ready · ${status.page_count} pages`;
    }
  } catch (e) {
    indexMsg.textContent = "Could not load status";
  }
}

// ── Index trigger ──────────────────────────────────────────────────────────────
indexBtn.addEventListener("click", async () => {
  indexBtn.disabled = true;
  indexMsg.textContent = "Starting index...";
  indexProgress.classList.remove("hidden");
  try {
    const r = await fetch(`${API}/api/index`, { method: "POST" });
    const data = await r.json();
    if (r.ok) {
      indexMsg.textContent = "Indexing started — this may take a few minutes...";
      setTimeout(pollIndexStatus, 3000);
    } else {
      indexMsg.textContent = data.detail || "Failed to start indexing";
      indexBtn.disabled = false;
      indexProgress.classList.add("hidden");
    }
  } catch {
    indexMsg.textContent = "Request failed";
    indexBtn.disabled = false;
    indexProgress.classList.add("hidden");
  }
});

async function pollIndexStatus() {
  await loadStatus();
  const r = await fetch(`${API}/api/status`);
  const data = await r.json();
  if (data.indexing) {
    setTimeout(pollIndexStatus, 3000);
  } else {
    indexBtn.disabled = false;
    indexProgress.classList.add("hidden");
    if (data.indexed) {
      indexMsg.textContent = `Done! ${data.page_count} pages indexed.`;
      enableChat();
    }
  }
}

// ── Chat ────────────────────────────────────────────────────────────────────────
function enableChat() {
  queryInput.disabled = false;
  sendBtn.disabled = false;
  queryInput.placeholder = "Ask something about your study materials...";
}

sendBtn.addEventListener("click", sendMessage);
queryInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

async function sendMessage() {
  const query = queryInput.value.trim();
  if (!query) return;

  // Clear welcome message on first message
  const welcome = messagesEl.querySelector(".welcome-msg");
  if (welcome) welcome.remove();

  queryInput.value = "";
  sendBtn.disabled = true;
  queryInput.disabled = true;
  sourcesPanel.classList.add("hidden");

  appendMessage("user", query);

  const thinkingId = appendMessage("assistant", "Searching your materials...", true);
  chatHistory.push({ role: "user", content: query });

  try {
    const r = await fetch(`${API}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, history: chatHistory.slice(-10) }),
    });
    const data = await r.json();
    removeMessage(thinkingId);

    const answer = data.answer || "No answer returned.";
    appendMessage("assistant", answer);
    chatHistory.push({ role: "assistant", content: answer });

    if (data.sources && data.sources.length > 0) {
      renderSources(data.sources);
    }
  } catch (e) {
    removeMessage(thinkingId);
    appendMessage("assistant", "Error: Could not reach the API. Is the server running?");
  } finally {
    sendBtn.disabled = false;
    queryInput.disabled = false;
    queryInput.focus();
  }
}

// ── Message rendering ──────────────────────────────────────────────────────────
let msgCounter = 0;

function appendMessage(role, text, isThinking = false) {
  const id = `msg-${++msgCounter}`;
  const div = document.createElement("div");
  div.id = id;
  div.className = `message ${role}${isThinking ? " thinking" : ""}`;
  div.innerHTML = `
    <div class="message-label">${role === "user" ? "You" : "DingDong"}</div>
    <div class="bubble">${escapeHtml(text)}</div>
  `;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return id;
}

function removeMessage(id) {
  document.getElementById(id)?.remove();
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br/>");
}

// ── Sources rendering ──────────────────────────────────────────────────────────
function renderSources(sources) {
  sourcesList.innerHTML = "";
  for (const s of sources) {
    const card = document.createElement("div");
    card.className = "source-card";
    card.innerHTML = `
      <div class="doc-name" title="${escapeHtml(s.doc_name)}">${escapeHtml(s.doc_name)}</div>
      <div class="page-num">Page ${s.page_num}</div>
      <div class="snippet">${escapeHtml(s.snippet)}</div>
    `;
    sourcesList.appendChild(card);
  }
  sourcesPanel.classList.remove("hidden");
}

// ── Start ──────────────────────────────────────────────────────────────────────
init();
```

**Step 2: Commit**

```bash
git add frontend/app.js
git commit -m "feat: frontend chat UI with Google auth, index trigger, and source cards"
```

---

## Session 4: Integration + Launch Setup

**Exit criteria:** `python -m uvicorn backend.main:app` starts the server. Visiting `http://localhost:8000`, logging in with Google, clicking Index Drive, and chatting all work end-to-end.

---

### Task 9: Run script + startup instructions

**Files:**
- Create: `run.sh` (Unix) / `run.bat` (Windows)
- Create: `.env.example`

**Step 1: Create run.bat (Windows)**

```bat
@echo off
cd /d "%~dp0"
if not exist .env (
  echo Copying .env.example to .env
  copy .env.example .env
  echo Please edit .env and add your GEMINI_API_KEY, then re-run this script.
  pause
  exit /b 1
)
pip install -r backend/requirements.txt
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Step 2: Create run.sh (Linux/Mac)**

```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Edit .env with your GEMINI_API_KEY, then re-run."
  exit 1
fi
pip install -r backend/requirements.txt
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Step 3: Final integration test**

Manually verify:
1. `python -m uvicorn backend.main:app --port 8000` starts without error
2. `http://localhost:8000` shows the chat UI
3. Click "Login with Google" → authenticates
4. Click "Build Index" → shows progress → completes
5. Ask "What is [topic from your materials]?" → returns answer + source cards

**Step 4: Final commit**

```bash
git add run.bat run.sh
git commit -m "feat: launch scripts for Windows and Unix"
```

---

## Quick-Start Checklist

Before running for the first time:

- [ ] Create Google Cloud project at https://console.cloud.google.com
- [ ] Enable Google Drive API
- [ ] Create OAuth2 credentials (Web Application)
  - Authorized redirect URI: `http://localhost:8000/auth/callback`
- [ ] Download `client_secret.json` → place in `backend/client_secret.json`
- [ ] Get Gemini API key (free) → https://aistudio.google.com/apikey (same Google account)
- [ ] Copy `.env.example` to `.env` and fill in `GEMINI_API_KEY`
- [ ] `pip install -r backend/requirements.txt`
- [ ] `cd backend && python -m uvicorn main:app --port 8000`
- [ ] Open http://localhost:8000
- [ ] Login → Index → Chat!

---

## Session Summary

| Session | Tasks | Outcome |
|---------|-------|---------|
| 1 | 1–4 | Scaffold + Drive client + Doc processor + PageIndex |
| 2 | 5–6 | RAG engine + FastAPI routes |
| 3 | 7–8 | Full chatbot frontend |
| 4 | 9   | Launch scripts + integration test |
