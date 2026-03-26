# CLAUDE.md — RAG-DingDong

This file gives Claude Code full context on this codebase so it can assist effectively without re-reading every file.

---

## Project Overview

RAG-DingDong is a personal academic search chatbot. It indexes a Google Drive folder using BM25 (no vectors, no embeddings), retrieves the most relevant document pages for a query, and sends them to the Groq LLM (free tier) to generate a cited answer. A dark-mode web UI serves as the chat interface, with a document viewer modal (PDF.js for PDFs, text for others).

**Owner:** 13523118@std.stei.itb.ac.id (ITB student — institutional account cannot use LLM free tiers; Groq key must be from a personal email)

---

## Architecture

```
frontend/ (Vanilla JS, HTML, CSS)
    │  HTTP requests to same-origin API
    ▼
backend/main.py (FastAPI)
    ├── /auth/*          Google OAuth2 flow (drive_client.py)
    ├── /api/index       Background: download Drive files → extract pages → build BM25 index
    ├── /api/chat        BM25 search → Groq LLM → return answer + sources
    ├── /api/file/*      Serve cached file for PDF.js viewer
    ├── /api/page-text/* Return extracted page text (non-PDF viewer)
    └── /api/doc-info/*  Return page count + file type metadata
    │
    ├── drive_client.py   OAuth2 + recursive Drive folder listing + file download/export
    ├── document_processor.py  Per-page text extraction (PDF/DOCX/PPTX/TXT)
    ├── page_index.py     BM25Okapi index over PageEntry list; save/load as JSON
    └── rag_engine.py     Retrieve pages from index → build prompt → call Groq
```

### Data Flow

1. User clicks "Login with Google" → OAuth2 → `DriveClient` holds credentials in memory
2. User clicks "Build Index" → `POST /api/index` → background task:
   - `DriveClient.list_all_files()` recursively lists Drive folder
   - `DriveClient.download_file()` downloads to `data/cache/{doc_id}_{name}.ext`
   - `extract_pages()` returns `List[PageEntry]` (each page = one entry)
   - `PageIndex.build()` creates `BM25Okapi` over all page texts
   - `PageIndex.save()` writes `data/index/page_index.json`
3. User sends chat message → `POST /api/chat`:
   - `RAGEngine._retrieve()` runs BM25 search → top-8 pages
   - Falls back to keyword overlap if BM25 scores all zero (small corpus)
   - `RAGEngine._build_prompt()` formats pages as `[doc_name, page N]\ntext`
   - `Groq.chat.completions.create()` with system prompt + history + prompt
   - Returns `{answer, sources: [{doc_id, doc_name, page_num, snippet}]}`
4. User clicks a source card → viewer modal opens:
   - `GET /api/doc-info/{doc_id}` → determines if PDF or text
   - PDF: `GET /api/file/{doc_id}` → PDF.js renders to canvas
   - Non-PDF: `GET /api/page-text/{doc_id}/{page_num}` → text display

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/config.py` | All constants: `GROQ_API_KEY`, `GROQ_MODEL`, `TOP_K_PAGES=8`, `MAX_PAGE_CHARS=3000`, `DRIVE_FOLDER_ID`, paths |
| `backend/main.py` | FastAPI app, global singletons (`_drive_client`, `_page_index`, `_rag_engine`), all routes |
| `backend/drive_client.py` | `DriveClient` class — OAuth2 flow, `list_all_files()`, `download_file()`, `_export_google_doc()` |
| `backend/document_processor.py` | `PageEntry` dataclass, `extract_pages()` dispatcher, per-format extractors |
| `backend/page_index.py` | `PageIndex` class — `build()`, `search()`, `save()`, `load()`, `page_count`, `doc_names` |
| `backend/rag_engine.py` | `RAGEngine` class — `chat()`, `_retrieve()`, `_build_prompt()`. Uses `groq` SDK. |
| `frontend/app.js` | All JS: auth check, index polling, chat send/receive, PDF.js modal viewer |
| `frontend/index.html` | App shell — sidebar (auth, index stats, doc list) + chat area + viewer modal |
| `frontend/style.css` | Dark-mode CSS variables, layout, source cards, modal, PDF canvas |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq API key from console.groq.com (personal email) |
| `DRIVE_FOLDER_ID` | No | Google Drive folder ID (defaults to the owner's academic folder) |

Config is loaded via `python-dotenv` from `.env` at the project root. `config.py` uses `os.environ.get()` with empty-string defaults so tests work without a real `.env`.

---

## Running the App

```bash
# Windows
.\run.bat

# Linux/Mac
./run.sh

# Manual
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

**Always run from the project root.** The app uses `from backend.X import Y` — running from inside `backend/` will break all imports.

Open `http://127.0.0.1:8000` (not `localhost` — IPv6 resolution issue on Windows 11).

---

## Running Tests

```bash
python -m pytest tests/ -v
```

25 tests, all mocked — no real Drive or LLM calls needed. Tests live in `tests/` and import from `backend/` using the project root as the working directory.

Key mocking patterns:
- Drive tests: `DriveClient.__new__(DriveClient)` to bypass `__init__`, inject `mock_service`
- RAG engine tests: `@patch("backend.rag_engine.genai.GenerativeModel")` (now Groq but pattern is same)
- API tests: set `os.environ["GROQ_API_KEY"] = "test-key"` before importing `backend.main`

---

## PageIndex Details

`PageIndex` wraps `rank_bm25.BM25Okapi`. Each `PageEntry` has:
- `doc_id` — Google Drive file ID (used as cache filename prefix)
- `doc_name` — original filename
- `page_num` — 1-based page number
- `text` — extracted text, truncated to `MAX_PAGE_CHARS=3000`

`search()` filters out pages with score ≤ 0. BM25Okapi IDF collapses to 0 on very small corpora (< ~3 docs); `RAGEngine._retrieve()` has a keyword-overlap fallback for this case.

`save()/load()` serialize to plain JSON — no pickle, no binary format.

---

## LLM: Groq

Model: `llama-3.1-8b-instant` (fast, free, 131k context).

System prompt instructs the model to:
- Answer only from provided excerpts
- Cite `[doc_name, p.N]` inline
- Say "not in excerpts" if the answer isn't there

Chat history is passed as OpenAI-compatible messages (`role: "user"/"assistant"`). The frontend stores history as `[{role, content}]` and sends the last 10 turns.

**Do not switch to Gemini** — the owner's Google Workspace account has free tier quota locked to 0.

---

## Google Drive Integration

`DriveClient` uses the `google-auth-oauthlib` Flow. Credentials are held in memory — they're lost on server restart, requiring re-authentication (the index itself persists).

Supported MIME types: PDF, DOCX, PPTX, TXT, Markdown, Google Docs (exported as PDF), Google Slides (exported as PDF).

Cache files are named `{drive_file_id}_{safe_name}.ext`. The `doc_id` in the index is the Drive file ID, used as the prefix to look up cached files.

---

## Frontend

Pure vanilla JS — no framework, no build step. The JS file is ~340 lines covering:
- Auth check + Drive status polling
- Index trigger + progress polling (3s interval)
- Chat send/receive + history management
- Source card rendering (clickable → opens viewer)
- PDF.js viewer: `pdfjsLib.getDocument()` → `pdf.getPage()` → `page.render()` to canvas
- Text viewer: `GET /api/page-text/` → `<pre>` display
- Keyboard shortcuts: `←/→` page nav, `Escape` close modal

PDF.js is loaded from CDN (`cdnjs.cloudflare.com`, version 3.11.174). Worker URL is set to the matching CDN worker.

---

## Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError: No module named 'backend'` | Running uvicorn from inside `backend/` | Run from project root: `python -m uvicorn backend.main:app` |
| `localhost:8000` not reachable | Windows IPv6 resolution | Use `http://127.0.0.1:8000` |
| Port 8000 already in use (`WinError 10013`) | Previous server still running | `netstat -ano \| findstr :8000` then `taskkill /PID <pid> /F` |
| Groq 400 `invalid role` | Old Gemini role remapping (`"assistant"→"model"`) left in main.py | `ChatMessage(role=m["role"], ...)` — no remapping needed for Groq |
| Gemini `limit: 0` quota error | Institutional Google Workspace account | Use Groq instead (personal email signup) |
| BM25 returns no results | Very small corpus (< 3 docs) | Keyword-overlap fallback already in `rag_engine._retrieve()` |

---

## What NOT To Do

- **Do not run uvicorn from `backend/`** — imports break
- **Do not switch the LLM to Gemini** — institutional account blocks free tier
- **Do not add vector embeddings** — this is intentionally vectorless; BM25 is the design choice
- **Do not store OAuth credentials to disk** — current in-memory design is intentional for simplicity
- **Do not gitignore `data/index/`** selectively — the whole `data/` dir should be gitignored (contains user files)
