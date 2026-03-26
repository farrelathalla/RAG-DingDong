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
