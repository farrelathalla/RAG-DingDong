# backend/page_index.py
import json
from pathlib import Path
from typing import List, Optional
from rank_bm25 import BM25Okapi
from backend.document_processor import PageEntry


def _tokenize(text: str) -> List[str]:
    """Simple whitespace + lowercase tokenizer."""
    return text.lower().split()


class PageIndex:
    """BM25-based page-level index. No vectors, no embeddings."""

    def __init__(self):
        self._pages: List[PageEntry] = []
        self._bm25: Optional[BM25Okapi] = None

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
            {"doc_id": p.doc_id, "doc_name": p.doc_name, "page_num": p.page_num, "text": p.text}
            for p in self._pages
        ]
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, path: str) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        pages = [
            PageEntry(doc_id=d["doc_id"], doc_name=d["doc_name"], page_num=d["page_num"], text=d["text"])
            for d in data
        ]
        self.build(pages)
