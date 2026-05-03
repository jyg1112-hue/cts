from __future__ import annotations

import re
from typing import Any

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer


def _tokenize_ko(text: str) -> list[str]:
    return re.findall(r"[\w가-힣]+", (text or "").lower())


def _metadata_match(meta: dict[str, Any], filt: dict[str, Any] | None) -> bool:
    if not filt:
        return True
    for k, v in filt.items():
        if v is None:
            continue
        if k == "year":
            meta_year = meta.get("year")
            if meta_year is None:
                continue  # year 없는 문서는 필터 통과 (제거하지 않음)
            if int(meta_year) != int(v):
                return False
        elif k == "month":
            try:
                if int(meta.get("month") or -1) != int(float(v)):  # float 변환 후 int
                    return False
            except (ValueError, TypeError):
                return False
        elif k == "cargo_type" and str(meta.get("cargo_type")) != str(v):
            return False
        elif k == "ship_name":
            if v and str(v).lower() not in str(meta.get("ship_name") or "").lower():
                return False
        elif k == "품종" and v:
            if str(v).lower() not in str(meta.get("품종") or "").lower():
                return False
        elif k in ("has_cargo_issue", "has_emergency_maintenance", "has_weather_delay"):
            try:
                if int(meta.get(k, 0)) != int(v):
                    return False
            except (ValueError, TypeError):
                return False
        elif k == "issue_keyword" and v:
            # raw_비고 또는 issue_categories에 키워드가 포함된 문서만 통과
            haystack = (
                str(meta.get("raw_비고") or "") + " " + str(meta.get("issue_categories") or "")
            ).lower()
            if str(v).lower() not in haystack:
                return False
    return True


class HybridRetriever:
    """
    BM25 + 벡터(Chroma) 결합, RRF 병합 후 메타데이터 필터.
    """

    def __init__(
        self,
        bm25: BM25Okapi,
        bm25_doc_ids: list[str],
        chroma_collection: Any,
        embedder: SentenceTransformer,
        documents: list[Document],
    ):
        self.bm25 = bm25
        self.bm25_doc_ids = bm25_doc_ids
        self.collection = chroma_collection
        self.embedder = embedder
        self.documents = documents
        self._id_to_idx = {did: i for i, did in enumerate(bm25_doc_ids)}

    def _rrf_fusion(
        self,
        ranked_ids: list[str],
        ranked_ids_sem: list[str],
        k: int = 60,
        bm25_weight: float = 0.3,
        semantic_weight: float = 0.7,
    ) -> list[tuple[str, float]]:
        scores: dict[str, float] = {}
        for rank, doc_id in enumerate(ranked_ids, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + bm25_weight / (k + rank)
        for rank, doc_id in enumerate(ranked_ids_sem, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + semantic_weight / (k + rank)
        return sorted(scores.items(), key=lambda x: -x[1])

    def retrieve(
        self,
        query: str,
        top_k: int = 8,
        filter_metadata: dict[str, Any] | None = None,
        bm25_k: int = 30,
        sem_k: int = 30,
        bm25_weight: float = 0.3,
        semantic_weight: float = 0.7,
    ) -> list[Document]:
        tokens = _tokenize_ko(query)
        bm25_scores = self.bm25.get_scores(tokens) if tokens else [0.0] * len(self.bm25_doc_ids)
        ranked_bm = sorted(range(len(bm25_scores)), key=lambda i: -bm25_scores[i])[:bm25_k]
        ranked_ids_bm = [self.bm25_doc_ids[i] for i in ranked_bm]

        q_emb = self.embedder.encode(query, normalize_embeddings=True).tolist()
        sem = self.collection.query(query_embeddings=[q_emb], n_results=min(sem_k, len(self.bm25_doc_ids)))
        ranked_ids_sem = []
        if sem.get("ids") and sem["ids"][0]:
            ranked_ids_sem = list(sem["ids"][0])

        fused = self._rrf_fusion(ranked_ids_bm, ranked_ids_sem, bm25_weight=bm25_weight, semantic_weight=semantic_weight)
        out: list[Document] = []
        for doc_id, _ in fused:
            idx = self._id_to_idx.get(doc_id)
            if idx is None:
                continue
            doc = self.documents[idx]
            if _metadata_match(doc.metadata or {}, filter_metadata):
                out.append(doc)
            if len(out) >= top_k:
                break
        return out
