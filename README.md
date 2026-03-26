# RAG-DingDong — Academic Drive Search

A vectorless RAG (Retrieval-Augmented Generation) chatbot that searches your Google Drive academic materials using BM25 PageIndex and answers questions with Groq LLM — completely free, no vector database, no embeddings.

## How It Works

```
Google Drive folder
       │
       ▼
  Download files  ──►  Extract text per page  ──►  BM25 PageIndex
  (PDF, DOCX,              (each page is an              (persisted to
   PPTX, TXT)               indexed unit)               data/index/)
                                                              │
  User asks question  ──►  BM25 search  ──►  Top-8 pages  ──►  Groq LLM
                           (keyword-based,    (from any          (generates
                            no embeddings)     documents)         answer with
                                                                  citations)
```

**Vectorless** means no embeddings, no vector database, no expensive API calls for indexing. BM25 (Best Match 25) is a classic sparse retrieval algorithm — fast, offline, and surprisingly effective for academic material.

**PageIndex** means each page of every document is a separate searchable unit. A 100-page PDF becomes 100 indexed entries. Answers cite the exact document and page number.

---

## Features

- **AI chatbot** — Ask questions in natural language, get cited answers
- **Source viewer** — Click any cited source card to open the document at that exact page
  - PDF files: rendered in-browser using PDF.js with prev/next navigation
  - DOCX/PPTX/TXT: shows the extracted text for that page
- **Google Drive integration** — OAuth2 login, recursive folder crawl, supports Google Docs/Slides export
- **Persistent index** — Index is saved to disk; survives server restarts
- **Dark-mode UI** — Clean chat interface with sidebar, source cards, and document viewer modal
- **Completely free** — Groq free tier (14,400 req/day), Google Drive API (no practical limit for personal use)

---

## Supported File Types

| Format | Extension | Notes |
|--------|-----------|-------|
| PDF | `.pdf` | Page-accurate extraction via PyMuPDF |
| Word | `.docx` | Grouped every 30 paragraphs as a "page" |
| PowerPoint | `.pptx` | One slide = one page |
| Plain text | `.txt`, `.md` | Entire file = one page |
| Google Docs | (Google format) | Exported as PDF |
| Google Slides | (Google format) | Exported as PDF |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Retrieval | rank-bm25 (BM25Okapi) |
| Document parsing | PyMuPDF, python-docx, python-pptx |
| LLM | Groq API (llama-3.1-8b-instant) — free tier |
| Drive access | google-api-python-client, google-auth-oauthlib |
| Frontend | Vanilla JS + HTML/CSS (no build step) |
| PDF viewer | PDF.js (CDN) |

---

## Setup

### Prerequisites

- Python 3.11 or higher
- A Google account with the academic Drive folder
- A free Groq API key

### 1. Google Cloud Setup

You need OAuth2 credentials to let the app access your Google Drive.

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project (e.g. `RAG-DingDong`)
3. Navigate to **APIs & Services → Library**, search for **Google Drive API**, click **Enable**
4. Navigate to **APIs & Services → Credentials**
5. Click **Create Credentials → OAuth 2.0 Client ID**
   - Application type: **Web application**
   - Authorized redirect URI: `http://127.0.0.1:8000/auth/callback`
6. Download the JSON → rename to `client_secret.json` → place in `backend/`

### 2. Groq API Key (Free)

1. Sign up at [console.groq.com](https://console.groq.com) with any personal email
2. Go to **API Keys → Create API Key**
3. Copy the key (starts with `gsk_`)

> **Important:** Use a personal email for Groq — institutional Google Workspace accounts (e.g. university emails) have their free tier quota set to 0 and cannot use Groq/Gemini free tiers.

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```env
GROQ_API_KEY=gsk_your_key_here
DRIVE_FOLDER_ID=your_drive_folder_id
```

To find your Drive folder ID: open the folder in Google Drive — the ID is the string after `/folders/` in the URL.

### 4. Run

**Windows:**
```powershell
.\run.bat
```

**Linux / Mac:**
```bash
chmod +x run.sh && ./run.sh
```

Then open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

> Use `127.0.0.1:8000` not `localhost:8000` — on Windows 11, `localhost` may resolve to IPv6 which won't match the server's IPv4 listener.

---

## Usage

### First Time

1. **Login with Google** — Click the button in the sidebar. You'll be redirected to Google's OAuth consent screen. Grant Drive read-only access.
2. **Build Index** — Click "Build Index". The app will:
   - Recursively list all files in your Drive folder and subfolders
   - Download each supported file to `data/cache/`
   - Extract text page by page
   - Build a BM25 index and save it to `data/index/page_index.json`
   - This may take a few minutes depending on folder size
3. **Chat** — Once indexed, the chat input activates. Ask anything about your materials.

### Subsequent Runs

The index persists on disk — the server loads it automatically on startup. You only need to re-index if your Drive contents change.

### Document Viewer

After getting an answer, source cards appear at the bottom. Click any card to open the document viewer:
- PDF files render at the exact cited page using PDF.js
- Use **Prev / Next** buttons or **← →** arrow keys to navigate pages
- Press **Escape** or click outside the modal to close

---

## Project Structure

```
RAG-DingDong/
├── backend/
│   ├── main.py                 # FastAPI app — all routes
│   ├── config.py               # Environment config, path constants
│   ├── drive_client.py         # Google Drive OAuth2 + file operations
│   ├── document_processor.py  # Text extraction per page (PDF/DOCX/PPTX/TXT)
│   ├── page_index.py           # BM25 PageIndex — build, search, save, load
│   ├── rag_engine.py           # Retrieve pages + generate answer via Groq
│   └── requirements.txt
├── frontend/
│   ├── index.html              # App shell with chat UI + document viewer modal
│   ├── style.css               # Dark-mode styles
│   └── app.js                  # Chat logic, API calls, PDF.js viewer
├── tests/
│   ├── test_document_processor.py
│   ├── test_drive_client.py
│   ├── test_page_index.py
│   ├── test_rag_engine.py
│   └── test_api.py
├── data/
│   ├── cache/                  # Downloaded Drive files (gitignored)
│   └── index/                  # Persisted BM25 index JSON (gitignored)
├── .env.example
├── run.bat                     # Windows launch script
└── run.sh                      # Linux/Mac launch script
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serves the frontend |
| `GET` | `/auth/login` | Redirects to Google OAuth |
| `GET` | `/auth/callback` | OAuth2 callback (redirect URI) |
| `GET` | `/auth/status` | `{"authenticated": bool}` |
| `POST` | `/api/index` | Trigger Drive crawl + index build (runs in background) |
| `GET` | `/api/status` | `{indexed, page_count, doc_count, indexing}` |
| `GET` | `/api/docs` | List of indexed document names |
| `POST` | `/api/chat` | `{query, history[]} → {answer, sources[], query}` |
| `GET` | `/api/file/{doc_id}` | Serve raw cached file for in-browser viewer |
| `GET` | `/api/page-text/{doc_id}/{page_num}` | Extracted text for one page |
| `GET` | `/api/doc-info/{doc_id}` | `{doc_name, page_count, ext, is_pdf}` |
| `GET` | `/api/health` | `{"status": "ok"}` |

---

## Running Tests

```bash
python -m pytest tests/ -v
```

25 tests covering document extraction, BM25 search, save/load roundtrip, Drive client mocks, and all API endpoints.

---

## Free Tier Limits

| Service | Limit |
|---------|-------|
| Groq (llama-3.1-8b-instant) | 30 req/min, 14,400 req/day, 131k token context |
| Google Drive API | No practical limit for personal use |
| Google OAuth | No limit |

---

## Known Limitations

- **DOCX page boundaries are approximate** — DOCX has no hard page markers; the processor groups every 30 paragraphs as one "page". Page numbers in citations are logical, not visual.
- **Index is not incremental** — Re-indexing rebuilds from scratch.
- **OAuth session is in-memory** — Restarting the server requires re-authenticating with Google Drive (the index itself persists).
- **Institutional email restriction** — University/corporate Google Workspace accounts may have LLM API free tiers blocked at zero quota. Use a personal email to sign up for Groq.
