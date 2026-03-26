# backend/rag_engine.py
from dataclasses import dataclass
from typing import List, Optional
from groq import Groq
from backend.document_processor import PageEntry
from backend.page_index import PageIndex
from backend.config import GROQ_MODEL, TOP_K_PAGES


@dataclass
class ChatMessage:
    role: str   # "user" | "assistant"
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
        self._client = Groq(api_key=api_key)

    def chat(self, query: str, history: Optional[List[ChatMessage]] = None) -> RAGResponse:
        sources = self._retrieve(query)
        if not sources:
            return RAGResponse(
                answer="I couldn't find relevant pages for your query. "
                       "Try re-indexing or rephrasing your question.",
                sources=[],
                query=query,
            )
        prompt = self._build_prompt(query, sources)

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in (history or []):
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                max_tokens=1024,
            )
            answer = response.choices[0].message.content
        except Exception as e:
            err = str(e)
            if "429" in err or "rate_limit" in err.lower() or "quota" in err.lower():
                answer = (
                    "⚠️ Groq rate limit hit. Wait a moment and try again.\n"
                    "Free tier: 30 req/min, 14,400 req/day."
                )
            else:
                answer = f"⚠️ Groq API error: {err}"

        return RAGResponse(answer=answer, sources=sources, query=query)

    def _retrieve(self, query: str) -> List[PageEntry]:
        if not query.strip():
            return []
        results = self._index.search(query, top_k=TOP_K_PAGES)
        if not results:
            tokens = set(query.lower().split())
            scored = [
                (sum(1 for t in tokens if t in p.text.lower()), p)
                for p in self._index._pages
            ]
            scored = [(s, p) for s, p in scored if s > 0]
            scored.sort(key=lambda x: x[0], reverse=True)
            results = [p for _, p in scored[:TOP_K_PAGES]]
        return results

    def _build_prompt(self, query: str, pages: List[PageEntry]) -> str:
        context_blocks = [
            f"[{p.doc_name}, page {p.page_num}]\n{p.text}"
            for p in pages
        ]
        context = "\n\n---\n\n".join(context_blocks)
        return f"Relevant excerpts from study materials:\n\n{context}\n\n---\n\nQuestion: {query}"
