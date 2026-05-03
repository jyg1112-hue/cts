from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def chat_json_completion(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.1,
) -> dict[str, Any] | None:
    """OpenAI Chat Completions, response_format json_object."""
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    m = model or os.environ.get("OPENAI_CHAT_MODEL", "gpt-5-mini")
    body = json.dumps(
        {
            "model": m,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_completion_tokens": 2000,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        content = str(content).strip()
        if not content:
            return None
        return json.loads(content)
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError, TypeError, KeyError):
        return None


def chat_text_completion(system_prompt: str, user_prompt: str, model: str | None = None) -> str | None:
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    m = model or os.environ.get("OPENAI_CHAT_MODEL", "gpt-5-mini")
    body = json.dumps(
        {
            "model": m,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_completion_tokens": 1600,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return str(payload.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip() or None
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError, TypeError, KeyError):
        return None
