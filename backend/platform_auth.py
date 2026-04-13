"""플랫폼 로그인 계정(JSON), 관리자 비밀번호, 감사 로그(JSONL)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import bcrypt
from fastapi import HTTPException, Request

_THIS = Path(__file__).resolve().parent
BASE_DIR = _THIS.parent
USERS_PATH = BASE_DIR / "data" / "platform_users.json"
AUDIT_PATH = BASE_DIR / "data" / "platform_audit.jsonl"


def platform_admin_username() -> str:
    """톱니바퀴·계정 관리 API에 쓰는 플랫폼 관리자 로그인 아이디."""
    return (os.environ.get("PLATFORM_ADMIN_USERNAME") or "admin").strip()


def session_secret() -> str:
    return (os.environ.get("SESSION_SECRET") or "dev-insecure-change-me").strip()


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host or ""
    return ""


def audit_write(request: Request, user: Optional[str], action: str, detail: str = "") -> None:
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "ip": client_ip(request),
            "user": user or "",
            "action": action,
            "detail": detail[:2000] if detail else "",
        },
        ensure_ascii=False,
    )
    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_users_data() -> dict[str, Any]:
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not USERS_PATH.exists():
        boot_u = (os.environ.get("PLATFORM_BOOTSTRAP_USER") or "admin").strip()
        boot_p = (os.environ.get("PLATFORM_BOOTSTRAP_PASSWORD") or "admin").strip()
        if not boot_u:
            boot_u = "admin"
        data: dict[str, Any] = {"users": [{"username": boot_u, "password_hash": _hash_password(boot_p)}]}
        USERS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data
    raw = USERS_PATH.read_text(encoding="utf-8")
    return json.loads(raw)


def save_users_data(data: dict[str, Any]) -> None:
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    USERS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def verify_user_credentials(username: str, password: str) -> bool:
    data = load_users_data()
    u = (username or "").strip()
    for row in data.get("users") or []:
        if isinstance(row, dict) and row.get("username") == u:
            h = row.get("password_hash") or ""
            if isinstance(h, str) and _verify_password(password, h):
                return True
    return False


def list_usernames() -> list[str]:
    data = load_users_data()
    out: list[str] = []
    for row in data.get("users") or []:
        if isinstance(row, dict) and row.get("username"):
            out.append(str(row["username"]))
    return sorted(out)


def add_user(username: str, password: str) -> None:
    u = (username or "").strip()
    if not u or not password:
        raise HTTPException(status_code=400, detail="아이디와 비밀번호가 필요합니다.")
    data = load_users_data()
    users: list[dict[str, Any]] = list(data.get("users") or [])
    if any(isinstance(x, dict) and x.get("username") == u for x in users):
        raise HTTPException(status_code=409, detail="이미 존재하는 아이디입니다.")
    users.append({"username": u, "password_hash": _hash_password(password)})
    data["users"] = users
    save_users_data(data)


def set_user_password(username: str, password: str) -> None:
    u = (username or "").strip()
    if not u or not password:
        raise HTTPException(status_code=400, detail="아이디와 비밀번호가 필요합니다.")
    data = load_users_data()
    users: list[dict[str, Any]] = list(data.get("users") or [])
    found = False
    for row in users:
        if isinstance(row, dict) and row.get("username") == u:
            row["password_hash"] = _hash_password(password)
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    data["users"] = users
    save_users_data(data)


def delete_user(username: str) -> None:
    u = (username or "").strip()
    data = load_users_data()
    users: list[dict[str, Any]] = [x for x in (data.get("users") or []) if isinstance(x, dict) and x.get("username") != u]
    if len(users) == len(data.get("users") or []):
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    if not users:
        raise HTTPException(status_code=400, detail="마지막 계정은 삭제할 수 없습니다.")
    data["users"] = users
    save_users_data(data)


def require_admin_header(request: Request) -> None:
    """헤더 비밀번호를 플랫폼 관리자(`platform_admin_username`) 로그인 비밀번호와 동일하게 검증."""
    got = (request.headers.get("x-platform-admin-password") or "").strip()
    if not got:
        raise HTTPException(status_code=403, detail="관리자 비밀번호가 필요합니다.")
    admin_u = platform_admin_username()
    if not verify_user_credentials(admin_u, got):
        raise HTTPException(status_code=403, detail="관리자 비밀번호가 올바르지 않습니다.")


def read_audit_tail(limit: int = 500) -> list[dict[str, Any]]:
    if not AUDIT_PATH.exists():
        return []
    lines = AUDIT_PATH.read_text(encoding="utf-8").splitlines()
    tail = lines[-limit:] if limit > 0 else lines
    out: list[dict[str, Any]] = []
    for ln in tail:
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out
