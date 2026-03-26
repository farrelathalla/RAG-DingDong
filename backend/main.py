# backend/main.py
import os
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import (
    GROQ_API_KEY, DRIVE_FOLDER_ID, INDEX_DIR, BASE_DIR
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
    if GROQ_API_KEY:
        _rag_engine = RAGEngine(index=_page_index, api_key=GROQ_API_KEY)

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
        _rag_engine = RAGEngine(index=_page_index, api_key=GROQ_API_KEY)
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
    history = [
        ChatMessage(role=m["role"], content=m["content"])
        for m in req.history
    ]
    response = _rag_engine.chat(req.query, history)
    return {
        "answer": response.answer,
        "sources": [
            {
                "doc_id": p.doc_id,
                "doc_name": p.doc_name,
                "page_num": p.page_num,
                "snippet": p.text[:300],
            }
            for p in response.sources
        ],
        "query": response.query,
    }


# ── Document viewer endpoints ──────────────────────────────────────────────────

@app.get("/api/file/{doc_id}")
def serve_file(doc_id: str):
    """Serve a cached document file for in-browser viewing."""
    from backend.config import CACHE_DIR
    for f in CACHE_DIR.iterdir():
        if f.name.startswith(doc_id + "_"):
            return FileResponse(str(f), filename=f.name)
    raise HTTPException(404, "File not found in cache. Re-index to refresh.")


@app.get("/api/page-text/{doc_id}/{page_num}")
def get_page_text(doc_id: str, page_num: int):
    """Return the extracted text for a specific page (used for non-PDF viewer)."""
    matches = [
        p for p in _page_index._pages
        if p.doc_id == doc_id and p.page_num == page_num
    ]
    if not matches:
        raise HTTPException(404, "Page not found in index.")
    p = matches[0]
    return {"doc_name": p.doc_name, "page_num": p.page_num, "text": p.text}


@app.get("/api/doc-info/{doc_id}")
def get_doc_info(doc_id: str):
    """Return page count and file type for a document."""
    pages = [p for p in _page_index._pages if p.doc_id == doc_id]
    if not pages:
        raise HTTPException(404, "Document not in index.")
    from backend.config import CACHE_DIR
    file_path = next((f for f in CACHE_DIR.iterdir() if f.name.startswith(doc_id + "_")), None)
    ext = file_path.suffix.lower() if file_path else ""
    return {
        "doc_name": pages[0].doc_name,
        "page_count": max(p.page_num for p in pages),
        "ext": ext,
        "is_pdf": ext == ".pdf",
    }


# ── Frontend fallback ──────────────────────────────────────────────────────────

@app.get("/")
def root():
    index_html = BASE_DIR / "frontend" / "index.html"
    if index_html.exists():
        return FileResponse(str(index_html))
    return {"message": "RAG-DingDong API running"}
