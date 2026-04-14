"""규칙 카탈로그 로더.

`strategy_engine/rules/**/*.yaml` 을 모두 읽어 Rule 객체 리스트로 반환.
각 YAML 파일은 규칙 객체의 리스트를 담는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

RULES_DIR = Path(__file__).parent / "rules"


@dataclass
class Rule:
    id: str
    name: str
    category: str
    tax_type: str
    priority: str
    applies_when: dict | None
    diagnosis: str
    recommendation: dict
    estimator: dict
    legal_basis: list[dict] = field(default_factory=list)
    risk: dict = field(default_factory=dict)
    source: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "Rule":
        return cls(
            id=data["id"],
            name=data["name"],
            category=data["category"],
            tax_type=data.get("tax_type", "소득세"),
            priority=data.get("priority", "medium"),
            applies_when=data.get("applies_when"),
            diagnosis=data.get("diagnosis", ""),
            recommendation=data.get("recommendation", {}),
            estimator=data.get("estimator", {}),
            legal_basis=data.get("legal_basis", []) or [],
            risk=data.get("risk", {}) or {},
            source=data.get("source", {}) or {},
        )


def load_all(rules_dir: Path | None = None) -> list[Rule]:
    base = Path(rules_dir) if rules_dir else RULES_DIR
    rules: list[Rule] = []
    for path in sorted(base.rglob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            items: Any = yaml.safe_load(f) or []
        if not isinstance(items, list):
            raise ValueError(f"{path}: top-level must be a list")
        for item in items:
            rules.append(Rule.from_dict(item))
    return rules


def load_by_category(category: str, rules_dir: Path | None = None) -> list[Rule]:
    return [r for r in load_all(rules_dir) if r.category == category]
