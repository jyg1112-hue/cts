"""Supply-chain news: Tavily Search (preferred) or Google News RSS; Korean via OpenAI."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

USER_AGENT = (
    "Mozilla/5.0 (compatible; PortOpsDashboard/1.0; +https://localhost) "
    "Python-urllib"
)
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
CACHE_TTL_SEC = 900
MAX_ITEMS_PER_QUERY = 15
MAX_ITEMS_TOTAL = 18
OPENAI_MODEL = os.environ.get("OPENAI_SUPPLY_NEWS_MODEL", "gpt-4o-mini")
TAVILY_DAYS = 30
TAVILY_INCLUDE_DOMAINS = [
    "reuters.com",
    "mining.com",
    "spglobal.com",
    "fastmarkets.com",
    "ft.com",
    "miningweekly.com",
]

_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_dotenv_loaded = False

# Tracking groups: human-readable reason + search queries
NICKEL_GROUPS: list[dict[str, Any]] = [
    {
        "id": "nickel_supply",
        "why_ko": "니켈 공급·광산·가격·지정학 리스크 동향",
        "queries": [
            "nickel supply New Caledonia Indonesia mine price 2026",
            "LME nickel ferronickel market outlook 2026",
            "New Caledonia unrest riot geopolitical risk nickel supply 2026",
        ],
    }
]

COAL_GROUPS: list[dict[str, Any]] = [
    {
        "id": "coal_supply",
        "why_ko": "석탄 수급 차질 및 아시아 가격 동향",
        "queries": [
            "thermal coal supply disruption price Asia 2026",
        ],
    }
]


def _load_local_dotenv() -> None:
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    try:
        from dotenv import load_dotenv

        root = Path(__file__).resolve().parent.parent
        load_dotenv(root / ".env")
    except ImportError:
        pass
    _dotenv_loaded = True


def _strip_html(text: str) -> str:
    if not text:
        return ""
    plain = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", plain).strip()


def _hostname(url: str) -> str:
    try:
        return urlparse(url).netloc or ""
    except ValueError:
        return ""


def _fetch_rss(query: str) -> bytes:
    params = urllib.parse.urlencode(
        {"q": query, "hl": "en", "gl": "US", "ceid": "US:en"}
    )
    url = f"{GOOGLE_NEWS_RSS}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read()


def _parse_rss(xml_bytes: bytes) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []
    channel = root.find("channel")
    if channel is None:
        return []
    out: list[dict[str, str]] = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        desc = _strip_html(item.findtext("description") or "")
        source_el = item.find("source")
        source_name = ""
        if source_el is not None and source_el.text:
            source_name = source_el.text.strip()
        if title and link:
            out.append(
                {
                    "title": title,
                    "link": link,
                    "pub_date": pub,
                    "snippet": desc[:800],
                    "source": source_name,
                }
            )
    return out


def _tavily_search(api_key: str, query: str, max_results: int) -> list[dict[str, str]]:
    body = json.dumps(
        {
            "api_key": api_key,
            "query": query,
            "topic": "news",
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": False,
            "days": TAVILY_DAYS,
            "include_domains": TAVILY_INCLUDE_DOMAINS,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        TAVILY_SEARCH_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError, TypeError):
        return []
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        return []
    out: list[dict[str, str]] = []
    for r in raw_results:
        if not isinstance(r, dict):
            continue
        title = (r.get("title") or "").strip()
        link = (r.get("url") or "").strip()
        content = _strip_html(str(r.get("content") or ""))
        pub = str(r.get("published_date") or "").strip()
        if title and link:
            out.append(
                {
                    "title": title,
                    "link": link,
                    "pub_date": pub,
                    "snippet": content[:1200],
                    "source": _hostname(link),
                    "score": float(r.get("score") or 0.0),
                }
            )
    return out


def _news_tag(title: str) -> str:
    t = (title or "").lower()
    if any(k in t for k in ("riot", "unrest", "geopolitical", "sanction", "protest", "폭동", "소요", "지정학")):
        return "지정학·리스크"
    if "coal" in t or "석탄" in t:
        return "석탄·에너지"
    if "mine" in t or "mining" in t:
        return "광산·운영"
    if "nickel" in t or "니켈" in t:
        return "공급·가격"
    return "시장 이슈"


def _is_relevant(item: dict[str, Any], cargo_type: str, min_score: float, strict_title: bool = True) -> bool:
    score = float(item.get("score") or 0.0)
    if score < min_score:
        return False
    text = f"{item.get('title','')} {item.get('snippet','')}".lower()
    common_keywords = (
        "nickel",
        "coal",
        "mine",
        "mining",
        "lme",
        "ferronickel",
        "new caledonia",
        "indonesia",
        "poya",
        "geminie",
        "ouaco",
        "riot",
        "unrest",
        "geopolitical",
        "sanction",
        "protest",
    )
    if not any(k in text for k in common_keywords):
        return False
    if cargo_type == "nickel":
        nickel_core = ("nickel", "lme", "ferronickel", "니켈")
        nickel_context = (
            "new caledonia",
            "indonesia",
            "poya",
            "ouaco",
            "geminie",
            "riot",
            "unrest",
            "geopolitical",
            "sanction",
            "protest",
            "mine",
            "mining",
            "supply",
            "price",
        )
        has_core = any(k in text for k in nickel_core)
        has_context = any(k in text for k in nickel_context)
        title_text = (item.get("title") or "").lower()
        title_has_core = any(k in title_text for k in (*nickel_core, "new caledonia", "ouaco", "poya"))
        if "copper" in title_text and not any(k in title_text for k in nickel_core):
            return False
        if strict_title and not title_has_core:
            nc_unrest_case = ("new caledonia" in text) and any(
                k in text for k in ("riot", "unrest", "protest", "geopolitical", "supply", "mine", "mining")
            )
            if not nc_unrest_case:
                return False
        # 니켈 피드는 니켈 핵심어가 반드시 있어야 하며, 맥락 키워드까지 맞출 때만 통과
        return has_core and has_context
    target = ("coal", "thermal coal", "asia", "indonesia", "newcastle")
    return any(k in text for k in target)


def _dedupe_sort_filter(items: list[dict[str, Any]], cargo_type: str) -> list[dict[str, Any]]:
    def boost(item: dict[str, Any]) -> int:
        text = f"{item.get('title','')} {item.get('snippet','')}".lower()
        score = 0
        if cargo_type == "nickel":
            if "new caledonia" in text or "ouaco" in text or "poya" in text:
                score += 3
            if any(k in text for k in ("riot", "unrest", "geopolitical", "sanction", "protest")):
                score += 2
            if any(k in text for k in ("nickel", "lme", "ferronickel")):
                score += 1
        return score

    def apply_threshold(min_score: float, strict_title: bool) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for it in items:
            key = (it.get("link") or it.get("title") or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            if _is_relevant(it, cargo_type, min_score, strict_title=strict_title):
                out.append(it)
        return sorted(out, key=lambda x: (boost(x), x.get("pub_date") or ""), reverse=True)

    filtered = apply_threshold(0.5, strict_title=True)
    if len(filtered) < 5:
        filtered = apply_threshold(0.35, strict_title=False)
    return filtered[:MAX_ITEMS_TOTAL]


def _collect_via_rss(cargo_type: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    groups = NICKEL_GROUPS if cargo_type == "nickel" else COAL_GROUPS
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    tracking_rows: list[dict[str, str]] = []

    for group in groups:
        why = group["why_ko"]
        gid = group["id"]
        tracking_rows.append(
            {"group_id": gid, "why_ko": why, "queries": " · ".join(group["queries"])}
        )
        for q in group["queries"]:
            if len(merged) >= MAX_ITEMS_TOTAL:
                break
            try:
                raw = _fetch_rss(q)
            except (urllib.error.URLError, OSError, TimeoutError):
                continue
            for row in _parse_rss(raw):
                if len(merged) >= MAX_ITEMS_TOTAL:
                    break
                key = row["link"] or row["title"]
                if key in seen:
                    continue
                seen.add(key)
                merged.append(
                    {
                        **row,
                        "group_id": gid,
                        "track_why_ko": why,
                        "search_query": q,
                        "tag": _news_tag(row.get("title", "")),
                    }
                )
                if sum(1 for x in merged if x.get("search_query") == q) >= MAX_ITEMS_PER_QUERY:
                    break
            if len(merged) >= MAX_ITEMS_TOTAL:
                break
        if len(merged) >= MAX_ITEMS_TOTAL:
            break

    merged.sort(key=lambda x: x.get("pub_date") or "", reverse=True)
    return merged[:MAX_ITEMS_TOTAL], tracking_rows


def _collect_via_tavily(
    cargo_type: str, api_key: str
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    groups = NICKEL_GROUPS if cargo_type == "nickel" else COAL_GROUPS
    merged_raw: list[dict[str, Any]] = []
    tracking_rows: list[dict[str, str]] = []

    for group in groups:
        why = group["why_ko"]
        gid = group["id"]
        tracking_rows.append(
            {"group_id": gid, "why_ko": why, "queries": " · ".join(group["queries"])}
        )
        futures = {}
        with ThreadPoolExecutor(max_workers=min(3, max(1, len(group["queries"])))) as pool:
            for q in group["queries"]:
                futures[pool.submit(_tavily_search, api_key, q, MAX_ITEMS_PER_QUERY)] = q
            for fut in as_completed(futures):
                q = futures[fut]
                try:
                    rows = fut.result()
                except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError, KeyError):
                    continue
                for row in rows:
                    merged_raw.append(
                        {
                            **row,
                            "group_id": gid,
                            "track_why_ko": why,
                            "search_query": q,
                            "tag": _news_tag(row.get("title", "")),
                        }
                    )

    merged = _dedupe_sort_filter(merged_raw, cargo_type)
    return merged, tracking_rows


def _collect_news(cargo_type: str) -> tuple[list[dict[str, Any]], list[dict[str, str]], str]:
    _load_local_dotenv()
    tavily_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
    if tavily_key:
        items, tracking = _collect_via_tavily(cargo_type, tavily_key)
        if items:
            return items, tracking, "tavily"
    items, tracking = _collect_via_rss(cargo_type)
    return items, tracking, "rss"


def _fallback_ko_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for it in items:
        snip = it.get("snippet") or ""
        out.append(
            {
                **it,
                "title_ko": it["title"],
                "summary_ko": (snip[:400] if snip else "요약 없음 (본문 미제공)"),
            }
        )
    return out


def _contains_korean(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r"[가-힣]", text))


def _extract_json_text(content: str) -> str:
    s = (content or "").strip()
    if not s:
        return "{}"
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    if s.startswith("{") and s.endswith("}"):
        return s
    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        return s[start : end + 1]
    return "{}"


def _request_openai_json(messages: list[dict[str, str]], api_key: str) -> tuple[dict[str, Any] | None, str | None]:
    body = json.dumps(
        {
            "model": OPENAI_MODEL,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": 2800,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        raw = payload["choices"][0]["message"]["content"]
        return json.loads(_extract_json_text(raw)), None
    except urllib.error.HTTPError as e:
        try:
            body_text = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body_text = ""
        if "invalid_api_key" in body_text:
            return None, "invalid_api_key"
        return None, f"http_{e.code}"
    except (urllib.error.URLError, OSError, KeyError, TypeError, json.JSONDecodeError):
        return None, "request_failed"


def _openai_enrich_ko(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key or not items:
        return _fallback_ko_items(items), "no_api_key"

    slim = [
        {
            "i": idx,
            "title": it["title"],
            "snippet": (it.get("snippet") or "")[:800],
            "context_ko": it.get("track_why_ko", ""),
        }
        for idx, it in enumerate(items)
    ]
    system = (
        "당신은 항만·원료 물류 담당자를 위한 뉴스 편집자입니다. "
        "각 항목은 웹에서 수집된 뉴스 제목과 본문 스니펫입니다. "
        "각 기사에 대해 한국어 제목(title_ko)과 공급망 관점 2문장 이내 요약(summary_ko)을 작성합니다. "
        "반드시 한국어 문장으로 작성하고(고유명사/기업명 제외), 영어 문장 복사를 금지합니다."
    )
    user = (
        "다음 뉴스 목록을 처리하세요. 응답 형식: "
        '{"results":[{"i":번호,"title_ko":"...","summary_ko":"..."},...]}\n\n'
        + json.dumps(slim, ensure_ascii=False)
    )
    parsed, first_error = _request_openai_json(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        api_key,
    )
    results = parsed.get("results") if isinstance(parsed, dict) else None
    by_i = {}
    if isinstance(results, list):
        by_i = {int(r["i"]): r for r in results if isinstance(r, dict) and "i" in r}

    out = []
    for idx, it in enumerate(items):
        r = by_i.get(idx)
        if r and r.get("title_ko") and r.get("summary_ko"):
            out.append({**it, "title_ko": r["title_ko"], "summary_ko": r["summary_ko"]})
        else:
            out.append(
                {
                    **it,
                    "title_ko": it["title"],
                    "summary_ko": (it.get("snippet") or "")[:400] or "요약을 생성하지 못했습니다.",
                }
            )

    # OpenAI 호출 성공이어도 간혹 영문 원문을 그대로 반환하는 경우가 있어 2차 번역 보정
    needs_fix = [
        {
            "i": i,
            "title_ko": x.get("title_ko", ""),
            "summary_ko": x.get("summary_ko", ""),
            "title_en": x.get("title", ""),
            "snippet_en": x.get("snippet", ""),
        }
        for i, x in enumerate(out)
        if (not _contains_korean(x.get("title_ko", ""))) or (not _contains_korean(x.get("summary_ko", "")))
    ]
    if not needs_fix:
        return out, None

    fix_user = (
        "다음 항목은 한국어가 충분하지 않습니다. 한국어 제목(title_ko)과 2문장 요약(summary_ko)로 다시 작성하세요. "
        "고유명사 외 영문 문장 금지. 형식: {\"results\":[{\"i\":번호,\"title_ko\":\"...\",\"summary_ko\":\"...\"}]}\n\n"
        + json.dumps(needs_fix, ensure_ascii=False)
    )
    fix_parsed, fix_error = _request_openai_json(
        [
            {"role": "system", "content": "당신은 번역/요약 편집자입니다. 반드시 한국어 JSON만 출력합니다."},
            {"role": "user", "content": fix_user},
        ],
        api_key,
    )
    fix_results = fix_parsed.get("results") if isinstance(fix_parsed, dict) else None
    if not isinstance(fix_results, list):
        return out, (fix_error or first_error or "openai_no_ko_output")
    fix_map = {int(r["i"]): r for r in fix_results if isinstance(r, dict) and "i" in r}
    for i, row in enumerate(out):
        rr = fix_map.get(i)
        if rr and rr.get("title_ko") and rr.get("summary_ko"):
            row["title_ko"] = rr["title_ko"]
            row["summary_ko"] = rr["summary_ko"]
    all_ko = all(_contains_korean(x.get("title_ko", "")) and _contains_korean(x.get("summary_ko", "")) for x in out)
    return out, (None if all_ko else (fix_error or first_error or "openai_partial_ko"))


def get_supply_news_payload(cargo_type: str) -> dict[str, Any]:
    _load_local_dotenv()
    now = time.time()
    ck = cargo_type
    if ck in _cache:
        ts, data = _cache[ck]
        if now - ts < CACHE_TTL_SEC:
            return data

    items_raw, tracking, news_source = _collect_news(cargo_type)
    openai_configured = bool((os.environ.get("OPENAI_API_KEY") or "").strip())
    if items_raw:
        items, ai_error = _openai_enrich_ko(items_raw)
    else:
        items, ai_error = ([], None)
    ai_effective = bool(items) and all(
        _contains_korean(it.get("title_ko", "")) and _contains_korean(it.get("summary_ko", ""))
        for it in items
    )

    payload = {
        "cargo_type": cargo_type,
        "news_source": news_source,
        "tavily_configured": bool((os.environ.get("TAVILY_API_KEY") or "").strip()),
        "ai_summaries_ko": ai_effective,
        "ai_configured": openai_configured,
        "ai_error": ai_error,
        "items": items,
        "tracking": tracking,
        "cached_until": int(now + CACHE_TTL_SEC),
    }
    _cache[ck] = (now, payload)
    return payload
