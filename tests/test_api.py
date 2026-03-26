# tests/test_api.py
import pytest
import os
os.environ.setdefault("GEMINI_API_KEY", "test-key")

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Patch RAGEngine init so it doesn't call genai.configure with a fake key at import
with patch("backend.rag_engine.genai.configure"), patch("backend.rag_engine.genai.GenerativeModel"):
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

def test_chat_without_index_returns_503():
    r = client.post("/api/chat", json={"query": "hello"})
    assert r.status_code in (200, 503)

def test_chat_empty_query_returns_400():
    r = client.post("/api/chat", json={"query": "   "})
    assert r.status_code == 400

def test_auth_login_redirects_or_503():
    r = client.get("/auth/login")
    assert r.status_code in (302, 500, 503)

def test_docs_list_before_index():
    r = client.get("/api/docs")
    assert r.status_code == 200
    assert "docs" in r.json()

def test_auth_status_not_authenticated():
    r = client.get("/auth/status")
    assert r.status_code == 200
    assert r.json()["authenticated"] is False
