"""strategy_engine — 규칙 카탈로그 기반 절세 전략 엔진.

기존 모듈(`strategy_engine.py`)의 공개 API 를 그대로 유지하되,
하드코딩 체크리스트 대신 YAML 규칙 카탈로그로 전환.
레거시 세부 함수는 `strategy_engine_legacy` 에 보존.
"""

from __future__ import annotations

from .orchestrator import (
    generate_strategy_legacy_format as generate_strategy,
    simulate_savings_legacy_format as simulate_savings,
    run,
)


def check_missing_deductions(user_data, tax_result=None):
    """기존 시그니처 유지. category 가 deduction/credit 인 항목을 필터해 반환."""
    candidates = run(user_data, tax_result or {})["candidates"]
    result = []
    for c in candidates:
        rule = c["rule"]
        if rule.category not in ("deduction", "credit"):
            continue
        legal_ref_parts = [
            f"{lb.get('law','')} {lb.get('article','')}".strip()
            for lb in (rule.legal_basis or [])
        ]
        result.append(
            {
                "name": rule.name,
                "condition": rule.diagnosis,
                "expected_saving": int(c.get("saving", 0)),
                "legal_ref": " / ".join(p for p in legal_ref_parts if p),
            }
        )
    return result


__all__ = [
    "generate_strategy",
    "simulate_savings",
    "check_missing_deductions",
    "run",
]
