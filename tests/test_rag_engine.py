# tests/test_rag_engine.py
import pytest
from unittest.mock import MagicMock, patch
from backend.document_processor import PageEntry
from backend.page_index import PageIndex
from backend.rag_engine import RAGEngine, ChatMessage, RAGResponse

SAMPLE_PAGES = [
    PageEntry("doc1", "Calculus.pdf", 3, "The chain rule states d/dx[f(g(x))] = f'(g(x)) times g'(x)"),
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
    mock_chat = MagicMock()
    mock_model.start_chat.return_value = mock_chat
    mock_chat.send_message.return_value.text = "The chain rule is used for composite functions."

    engine = RAGEngine(index=make_index(), api_key="fake")
    response = engine.chat("What is the chain rule?")

    assert isinstance(response, RAGResponse)
    assert "chain rule" in response.answer.lower()
    assert len(response.sources) > 0
