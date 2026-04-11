from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import chromadb
import pandas as pd
from chromadb.config import Settings
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer


def _processed_dir(base_dir: Path) -> Path:
    p = base_dir / "data" / "processed"
    p.mkdir(parents=True, exist_ok=True)
    return p


def build_sqlite(coal_df: pd.DataFrame, nickel_df: pd.DataFrame, db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = __import__("sqlite3").connect(str(db_path))

    def _prep(df: pd.DataFrame, extra_cols: list[str]) -> pd.DataFrame:
        out = df.copy()
        for c in [
            "has_emergency_maintenance",
            "has_cargo_issue",
            "has_weather_delay",
        ]:
            if c in out.columns:
                out[c] = out[c].astype(int)
        for c in out.columns:
            if out[c].dtype == object:
                out[c] = out[c].apply(lambda x: x if x is not None else "")
        return out

    c_cols = list(coal_df.columns) if not coal_df.empty else []
    n_cols = list(nickel_df.columns) if not nickel_df.empty else []
    nickel_extra = [x for x in ["항차", "작업시간", "작업대기시간", "조업율", "TH"] if x in n_cols]

    if not coal_df.empty:
        _prep(coal_df, []).to_sql("coal_records", conn, index=False, if_exists="replace")
    else:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS coal_records (
            id INTEGER, 척수 INTEGER, 월 INTEGER, year INTEGER,
            선박명 TEXT, 품종 TEXT, 하역량_톤 REAL,
            착수 TEXT, 완료 TEXT, 소요일 REAL, 조정 REAL, 최종소요일 REAL,
            하역률 REAL, 현장교대 TEXT, raw_비고 TEXT,
            issue_categories TEXT, total_delay_hours REAL,
            has_emergency_maintenance INTEGER, has_cargo_issue INTEGER, has_weather_delay INTEGER,
            cargo_type TEXT)"""
        )

    if not nickel_df.empty:
        _prep(nickel_df, nickel_extra).to_sql("nickel_records", conn, index=False, if_exists="replace")
    else:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS nickel_records (
            id INTEGER, 척수 INTEGER, 월 INTEGER, year INTEGER,
            선박명 TEXT, 품종 TEXT, 하역량_톤 REAL,
            착수 TEXT, 완료 TEXT, 소요일 REAL, 조정 REAL, 최종소요일 REAL,
            하역률 REAL, 현장교대 TEXT, raw_비고 TEXT,
            issue_categories TEXT, total_delay_hours REAL,
            has_emergency_maintenance INTEGER, has_cargo_issue INTEGER, has_weather_delay INTEGER,
            cargo_type TEXT,
            항차 TEXT, 작업시간 REAL, 작업대기시간 REAL, 조업율 REAL, TH REAL)"""
        )
    conn.close()


def _tokenize_ko(text: str) -> list[str]:
    import re

    return re.findall(r"[\w가-힣]+", (text or "").lower())


def build_vector_db(
    documents: list[Document],
    persist_dir: Path,
    embedding_model_name: str,
    collection_name: str = "haeyang_records",
) -> tuple[chromadb.api.client.Client, Any, list[str]]:
    persist_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_dir), settings=Settings(anonymized_telemetry=False))
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    col = client.create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})
    model = SentenceTransformer(embedding_model_name)
    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict[str, Any]] = []
    embeddings_list: list[list[float]] = []
    for i, doc in enumerate(documents):
        doc_id = f"doc_{i}"
        ids.append(doc_id)
        texts.append(doc.page_content)
        md = {k: v for k, v in (doc.metadata or {}).items() if isinstance(v, (str, int, float, bool))}
        metadatas.append(md)
        emb = model.encode(doc.page_content, normalize_embeddings=True)
        embeddings_list.append(emb.tolist())
    col.add(ids=ids, embeddings=embeddings_list, documents=texts, metadatas=metadatas)
    return client, model, ids


def build_bm25_index(documents: list[Document]) -> tuple[BM25Okapi, list[str]]:
    corpus = [_tokenize_ko(d.page_content) for d in documents]
    ids = [f"doc_{i}" for i in range(len(documents))]
    bm25 = BM25Okapi(corpus)
    return bm25, ids


def save_bm25_artifact(bm25: BM25Okapi, doc_ids: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        pickle.dump({"bm25": bm25, "doc_ids": doc_ids}, f)


def load_bm25_artifact(path: Path) -> tuple[BM25Okapi, list[str]]:
    with path.open("rb") as f:
        data = pickle.load(f)
    return data["bm25"], data["doc_ids"]


def write_fingerprint(base_dir: Path, fingerprint: str) -> None:
    meta = _processed_dir(base_dir) / "index_meta.json"
    meta.write_text(json.dumps({"fingerprint": fingerprint}, ensure_ascii=False), encoding="utf-8")


def read_fingerprint(base_dir: Path) -> str | None:
    meta = _processed_dir(base_dir) / "index_meta.json"
    if not meta.exists():
        return None
    try:
        return str(json.loads(meta.read_text(encoding="utf-8")).get("fingerprint") or "")
    except json.JSONDecodeError:
        return None
