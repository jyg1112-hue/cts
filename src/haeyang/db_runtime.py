"""하역 관계형 저장소: DATABASE_URL 있으면 PostgreSQL, 없으면 로컬 SQLite 파일."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


def haeyang_database_url() -> str | None:
    u = (os.environ.get("DATABASE_URL") or "").strip()
    return u or None


def sqlalchemy_url(url: str) -> str:
    """`postgres://` 호스트 URL → SQLAlchemy psycopg3 드라이버 URL."""
    u = url.strip()
    if u.startswith("postgres://"):
        u = "postgresql+psycopg://" + u[len("postgres://") :]
    elif u.startswith("postgresql://") and "+psycopg" not in u.split("://", 1)[0]:
        u = "postgresql+psycopg://" + u[len("postgresql://") :]
    return u


@lru_cache(maxsize=1)
def get_sqlalchemy_engine() -> Engine | None:
    from sqlalchemy import create_engine

    raw = haeyang_database_url()
    if not raw:
        return None
    return create_engine(sqlalchemy_url(raw), pool_pre_ping=True)
