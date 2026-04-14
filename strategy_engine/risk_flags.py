"""전략 후보에 리스크 플래그를 주입.

v0: rule.risk 사본을 그대로 전달. 향후 profile 특성
(현금매출 비율 등)과 교차해 세무조사 트리거를 동적으로 추가한다.
"""

from __future__ import annotations


def annotate(candidate: dict, profile: dict) -> dict:
    rule = candidate["rule"]
    risk = dict(rule.risk or {})
    risk.setdefault("level", "low")
    risk.setdefault("flags", [])
    risk.setdefault("caveat", "")
    candidate["risk"] = risk
    return candidate
