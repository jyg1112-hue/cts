from __future__ import annotations

from typing import Any

from langchain_core.documents import Document
from sentence_transformers import CrossEncoder


class Reranker:
    """Cross-Encoder로 (query, passage) 관련도 재정렬."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model: CrossEncoder | None = None

    @property
    def model(self) -> CrossEncoder:
        if self._model is None:
            self._model = CrossEncoder(self.model_name)
        return self._model

    def rerank(self, query: str, documents: list[Document], top_k: int = 5) -> list[Document]:
        if not documents:
            return []
        pairs: list[list[str]] = [[query, d.page_content] for d in documents]
        scores = self.model.predict(pairs)
        order = sorted(range(len(scores)), key=lambda i: float(scores[i]), reverse=True)
        return [documents[i] for i in order[:top_k]]


def lazy_reranker(model_name: str) -> Reranker:
    return Reranker(model_name=model_name)
