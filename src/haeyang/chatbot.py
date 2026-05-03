from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from haeyang.db_builder import (
    build_bm25_index,
    build_relational_tables,
    build_vector_db,
    load_bm25_artifact,
    read_stored_fingerprint,
    relational_db_ready,
    save_bm25_artifact,
    write_stored_fingerprint,
)
from haeyang.preprocess import build_all_documents, rows_to_dataframes
from haeyang.reranker import Reranker
from haeyang.retriever import HybridRetriever
from haeyang.router import build_router_graph

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cached: dict[str, Any] = {}


def _processed_paths(base_dir: Path) -> tuple[Path, Path, Path, Path]:
    proc = base_dir / "data" / "processed"
    return (
        proc / "haeyang.db",
        proc / "chroma",
        proc / "bm25.pkl",
        proc / "documents.jsonl",
    )


def _embedding_model() -> str:
    return os.environ.get(
        "HAEYANG_EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )


def _reranker_model() -> str:
    return os.environ.get("HAEYANG_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")


def rebuild_index(base_dir: Path, rows: list[dict[str, Any]], fingerprint: str) -> None:
    """관계형(PostgreSQL 또는 SQLite) + Chroma + BM25 재구축."""
    coal_df, nickel_df = rows_to_dataframes(rows)
    db_path, chroma_dir, bm25_path, _ = _processed_paths(base_dir)
    build_relational_tables(coal_df, nickel_df, db_path)
    documents = build_all_documents(coal_df, nickel_df)
    if not documents:
        return
    build_vector_db(documents, chroma_dir, _embedding_model())
    bm25, doc_ids = build_bm25_index(documents)
    save_bm25_artifact(bm25, doc_ids, bm25_path)
    # 문서 캐시(재시작 시 로드)
    doc_cache = base_dir / "data" / "processed" / "documents.jsonl"
    doc_cache.parent.mkdir(parents=True, exist_ok=True)
    with doc_cache.open("w", encoding="utf-8") as f:
        for d in documents:
            f.write(
                json.dumps(
                    {"page_content": d.page_content, "metadata": d.metadata or {}},
                    ensure_ascii=False,
                )
                + "\n"
            )
    write_stored_fingerprint(base_dir, fingerprint)
    _cached.clear()


def _load_documents_from_cache(base_dir: Path) -> list[Document]:
    path = base_dir / "data" / "processed" / "documents.jsonl"
    if not path.exists():
        return []
    out: list[Document] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            out.append(Document(page_content=o["page_content"], metadata=o.get("metadata") or {}))
    return out


def get_or_build_context(base_dir: Path, rows: list[dict[str, Any]], fingerprint: str) -> dict[str, Any] | None:
    if not rows:
        return None
    key = fingerprint
    with _lock:
        if _cached.get("fp") == key and _cached.get("ctx"):
            return _cached["ctx"]

        proc_fp = read_stored_fingerprint(base_dir)
        db_path, chroma_dir, bm25_path, _ = _processed_paths(base_dir)
        docs_cache = _load_documents_from_cache(base_dir)

        need_rebuild = (
            proc_fp != key
            or not relational_db_ready(db_path)
            or not chroma_dir.exists()
            or not bm25_path.exists()
            or len(docs_cache) == 0
        )
        if need_rebuild:
            try:
                rebuild_index(base_dir, rows, fingerprint=key)
            except Exception:
                logger.exception("haeyang index rebuild failed")
                return None

        documents = _load_documents_from_cache(base_dir)
        if not documents:
            return None

        try:
            bm25, doc_ids = load_bm25_artifact(bm25_path)
        except Exception:
            logger.exception("bm25 load failed")
            return None

        import chromadb
        from chromadb.config import Settings

        client = chromadb.PersistentClient(path=str(chroma_dir), settings=Settings(anonymized_telemetry=False))
        col = client.get_collection("haeyang_records")
        from sentence_transformers import SentenceTransformer

        embedder = SentenceTransformer(_embedding_model())
        retriever = HybridRetriever(bm25, doc_ids, col, embedder, documents)
        reranker = Reranker(_reranker_model())
        graph = build_router_graph(db_path, retriever, reranker)
        ctx = {"graph": graph, "db_path": db_path}
        _cached["fp"] = key
        _cached["ctx"] = ctx
        return ctx


def enhanced_chat_answer(
    question: str,
    history: list[dict[str, str]] | None,
    base_dir: Path,
    rows: list[dict[str, Any]],
    fingerprint: str,
) -> str | None:
    """
    하이브리드 챗봇 답변. 실패 시 None (호출측에서 기존 로직으로 폴백).
    """
    if os.environ.get("UNLOADING_CHAT_ENHANCED", "1") != "1":
        return None
    if not (os.environ.get("OPENAI_API_KEY") or "").strip():
        return None

    ctx = get_or_build_context(base_dir, rows, fingerprint)
    if not ctx:
        return None

    graph = ctx["graph"]
    try:
        out = graph.invoke({"query": question})
        ans = out.get("final_answer")
        if isinstance(ans, str) and ans.strip():
            return ans.strip()
    except Exception:
        logger.exception("haeyang graph invoke failed")
    return None
