"""4단계 파이프라인 조립 + 결과 포맷.

main.py 와 eval 스크립트에서 호출하는 진입점은 `run()` 과
`generate_strategy_legacy_format()` 둘. 후자는 기존 출력 스키마를
유지해 main.py 를 깨지 않는다.
"""

from __future__ import annotations

from typing import Any

from . import gap_detector, generator, risk_flags
from .catalog import Rule
from .profile_builder import build_profile

PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def run(user_data: dict | None, tax_result: dict | None = None) -> dict:
    """파이프라인 전체 실행 → 구조화된 결과.

    Returns:
      {
        "profile": {...},
        "candidates": [{rule, saving, trace, risk}, ...],
      }
    """
    profile = build_profile(user_data or {}, tax_result or {})
    candidates: list[dict] = []
    candidates.extend(gap_detector.detect_gaps(profile))
    candidates.extend(generator.generate(profile))

    for c in candidates:
        risk_flags.annotate(c, profile)

    candidates.sort(
        key=lambda c: (
            PRIORITY_RANK.get(c["rule"].priority, 3),
            -int(c.get("saving", 0)),
        )
    )
    return {"profile": profile, "candidates": candidates}


def _rule_to_legacy_dict(c: dict) -> dict:
    rule: Rule = c["rule"]
    legal_ref = ""
    if rule.legal_basis:
        parts = []
        for lb in rule.legal_basis:
            parts.append(f"{lb.get('law','')} {lb.get('article','')}".strip())
        legal_ref = " / ".join(p for p in parts if p)
    return {
        "항목": rule.name,
        "예상절세액": int(c.get("saving", 0)),
        "조건": rule.diagnosis or rule.recommendation.get("detail", ""),
        "법령조항": legal_ref,
        "우선순위": rule.priority,
        "리스크": c.get("risk", {}),
        "rule_id": rule.id,
    }


def generate_strategy_legacy_format(
    user_data: dict | None, tax_result: dict | None = None
) -> list[dict]:
    """main.py 가 기대하는 기존 포맷(list[dict])."""
    res = run(user_data, tax_result)
    return [_rule_to_legacy_dict(c) for c in res["candidates"]]


def simulate_savings_legacy_format(
    user_data: dict | None, tax_result: dict | None = None
) -> list[dict]:
    """기존 simulate_savings 포맷(current/after/saving)."""
    current_tax = 0
    if isinstance(tax_result, dict):
        current_tax = int(
            tax_result.get("총결정세액", tax_result.get("산출세액", 0)) or 0
        )
    result = []
    for c in run(user_data, tax_result)["candidates"]:
        saving = int(c.get("saving", 0))
        if saving <= 0:
            continue
        result.append(
            {
                "항목": c["rule"].name,
                "현재세액": current_tax,
                "적용후세액": current_tax - saving,
                "절세액": saving,
            }
        )
    return result
