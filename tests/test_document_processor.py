# tests/test_document_processor.py
import pytest
from pathlib import Path
from backend.document_processor import extract_pages, PageEntry

def test_extract_pages_returns_list_of_page_entries(tmp_path):
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
    from backend.document_processor import MAX_PAGE_CHARS
    big_text = "x" * (MAX_PAGE_CHARS + 500)
    entry = PageEntry(doc_id="d", doc_name="f", page_num=1, text=big_text)
    assert len(entry.text) <= MAX_PAGE_CHARS
