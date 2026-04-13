from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from haeyang.openai_json import chat_json_completion, chat_text_completion

SQL_SYSTEM_PROMPT = """
당신은 하역률 SQLite DB용 SELECT 쿼리만 생성한다.

테이블 스키마:
- coal_records: 석탄 하역 데이터
  컬럼: 척수, 월, year, 선박명, 품종, 하역량_톤, 착수, 완료, 소요일, 조정, 최종소요일,
        하역률, 현장교대, raw_비고, issue_categories, total_delay_hours,
        has_emergency_maintenance, has_cargo_issue, has_weather_delay, cargo_type
- nickel_records: 니켈 하역 데이터 (coal_records 컬럼 + 항차, 작업시간, 작업대기시간, 조업율, TH)

규칙:
1. 반드시 SELECT 한 문장만. 세미콜론 금지.
2. 하역률 단위는 톤/일 (컬럼명: "하역률").
3. 월은 1~12 정수 컬럼 `월`. 연도는 4자리 정수 컬럼 `year`.
4. 집계 결과는 round(..., 1)로 소수점 1자리 반올림.
5. 한글 컬럼명은 큰따옴표로 감싼다: "하역률", "선박명", "하역량_톤", "raw_비고" 등.
6. 이슈 여부는 has_emergency_maintenance, has_cargo_issue, has_weather_delay 컬럼(0/1)으로 필터링.
7. total_delay_hours: 해당 항차의 총 지연 시간 합계(시간 단위).
8. 니켈/석탄의 품종·광종별 하역률 순위·최저·최고·평균은 해당 테이블(nickel_records 또는 coal_records)에서
   year(및 필요 시 월) 조건 후 GROUP BY "품종", round(avg("하역률"),1) 등으로 집계한다.
   예: 연도·니켈만 주어지면 nickel_records WHERE year = ? … GROUP BY "품종" ORDER BY avg("하역률") ASC LIMIT 1

응답은 JSON만: {"sql": "SELECT ...", "explanation_hint": "한 줄 요약"}
"""


def _validate_sql(sql: str) -> bool:
    s = sql.strip().lower()
    if ";" in s:
        return False
    if not s.startswith("select"):
        return False
    forbidden = (
        "insert ",
        "update ",
        "delete ",
        "drop ",
        "attach ",
        "pragma ",
        "create ",
        "replace ",
        "alter ",
        "truncate ",
    )
    if any(x in s for x in forbidden):
        return False
    # 테이블 화이트리스트
    if "coal_records" not in s and "nickel_records" not in s:
        return False
    return True


def run_sql_chain(question: str, db_path: Path) -> str | None:
    if not db_path.exists():
        return None
    user = f"질문: {question}\n"
    parsed = chat_json_completion(SQL_SYSTEM_PROMPT, user, temperature=0.0)
    if not parsed or not isinstance(parsed.get("sql"), str):
        return None
    sql = parsed["sql"].strip()
    if not _validate_sql(sql):
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql)
        rows = cur.fetchmany(50)
        conn.close()
    except sqlite3.Error:
        return None
    if not rows:
        summary = "(SQL 결과 없음)"
    else:
        cols = rows[0].keys()
        lines = [", ".join(cols)]
        for r in rows[:20]:
            lines.append(", ".join(str(r[c]) for c in cols))
        summary = "\n".join(lines)
    explain = chat_text_completion(
        "SQL 결과를 한국어로 1~4문장으로만 설명한다. 수치는 그대로 인용한다.",
        f"질문: {question}\nSQL:\n{sql}\n결과:\n{summary}",
    )
    return explain or summary


