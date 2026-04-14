"""category=gap 규칙을 탐색.

현재 v0에는 gap 전용 규칙이 없어 빈 리스트를 반환한다. 향후 누락
공제/경비 탐지 규칙이 추가될 때 이 모듈이 스캔한다.
"""

from __future__ import annotations

from .catalog import Rule, load_by_category
from .dsl import evaluate
from .simulator import estimate


def detect_gaps(profile: dict, rules: list[Rule] | None = None) -> list[dict]:
    if rules is None:
        rules = load_by_category("gap")
    results: list[dict] = []
    for rule in rules:
        applied, trace = evaluate(rule.applies_when, profile)
        if not applied:
            continue
        saving = estimate(rule.estimator, profile)
        results.append(
            {
                "rule": rule,
                "saving": saving,
                "trace": trace,
            }
        )
    return results
