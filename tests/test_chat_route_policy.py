from __future__ import annotations

import pytest

from backend.main import _should_force_hybrid_question


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("수분 이슈가 있었던 선박의 평균 하역률은?", True),
        ("돌발정비 선박들의 평균 소요일은?", True),
        ("기상불량 지연 선박의 총 지연시간은?", True),
        ("철편 검출 이슈 선박의 하역률 하위 5척은?", True),
        ("SNNC 트러블 선박 평균 하역률 알려줘", True),
        ("점성 이슈 선박의 월별 평균 하역률은?", True),
        ("화물이슈 선박의 합계 물량은?", True),
        ("수분 문제 선박의 최저 하역률은?", True),
        ("우천 지연 선박 평균 하역률", True),
        ("대형괴광 이슈 선박 순위 알려줘", True),
        ("2025년 니켈 평균 하역률은?", False),
        ("3월 석탄 총 하역량은?", False),
        ("하역률 상위 5개 선박은?", False),
        ("돌발정비 발생 선박 목록은?", False),
        ("기상불량이 있었던 월은?", False),
        ("수분, 죽광 이슈가 있었던 니켈 품종은?", False),
        ("CSU2호 관련 정비 이슈 정리해줘", False),
        ("수분이 높은 화물로 인한 문제 사례는?", False),
        ("철편검출이 많았던 사례 설명해줘", False),
        ("돌발정비 발생 경위를 알려줘", False),
        ("하역률이 낮았던 선박의 원인은?", False),
        ("3월에 돌발정비가 발생한 선박의 하역률은?", True),
        ("기상불량으로 지연된 선박의 실적은?", True),
        ("니켈 선박 평균 하역률은?", False),
        ("수분 이슈 평균", True),
        ("문제 있었던 선박 얼마나 지연됐어?", True),
        ("정비 이슈 총 몇 건?", True),
        ("SNNC 사례 보여줘", False),
        ("기상 이슈와 하역률 관계 알려줘", True),
        ("돌발정비 이유 알려줘", False),
    ],
)
def test_should_force_hybrid_question(question: str, expected: bool) -> None:
    assert _should_force_hybrid_question(question) is expected
