"""전략 카테고리 규칙 실행기.

gap 이외 카테고리(separation_vs_comprehensive, deduction, credit,
bookkeeping, timing, reduction)를 일괄 평가한다.
"""

from __future__ import annotations

from .catalog import Rule, load_all
from .dsl import evaluate
from .simulator import estimate

STRATEGY_CATEGORIES = {
    "separation_vs_comprehensive",
    "deduction",
    "credit",
    "bookkeeping",
    "timing",
    "reduction",
}


def generate(profile: dict, rules: list[Rule] | None = None) -> list[dict]:
    if rules is None:
        rules = [r for r in load_all() if r.category in STRATEGY_CATEGORIES]
    results: list[dict] = []
    for rule in rules:
        applied, trace = evaluate(rule.applies_when, profile)
        if not applied:
            continue
        saving = estimate(rule.estimator, profile)
        if saving <= 0:
            continue
        results.append(
            {
                "rule": rule,
                "saving": saving,
                "trace": trace,
            }
        )
    return results
