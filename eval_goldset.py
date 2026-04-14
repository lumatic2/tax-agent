"""PRD 목표 — 세무사 검토 결과 80% 일치 측정 프레임.

골드셋(`data/eval/goldset_v1.yaml`) 의 각 케이스에 대해
strategy_engine.run() 결과를 비교해 case-level pass/fail + 전체 accuracy 산출.

채점 규칙:
  - expected 모든 id 발동 → base hit
  - forbidden 발동 → 실패 (오탐)
  - optional 은 점수에 영향 없음
  - case.passed = (expected 전부 hit) AND (forbidden 0건)
  - accuracy = passed_cases / total_cases
  - PRD 목표 accuracy ≥ 0.80

사용:
  python eval_goldset.py                    # 기본 골드셋
  python eval_goldset.py --goldset path.yaml
  python eval_goldset.py --verbose          # miss/wrong 상세
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from strategy_engine import run as strategy_run

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


DEFAULT_GOLDSET = Path("data/eval/goldset_v1.yaml")
PRD_TARGET = 0.80


def _load_goldset(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        cases = yaml.safe_load(f) or []
    if not isinstance(cases, list):
        raise ValueError(f"{path}: top-level must be a list")
    return cases


def _score_case(case: dict) -> dict:
    profile = case.get("profile") or {}
    expected = set(case.get("expected") or [])
    forbidden = set(case.get("forbidden") or [])
    optional = set(case.get("optional") or [])

    res = strategy_run(profile)
    fired = {c["rule"].id for c in res["candidates"]}

    hit = fired & expected
    miss = expected - fired
    wrong = fired & forbidden
    bonus = fired & optional

    passed = len(miss) == 0 and len(wrong) == 0
    return {
        "id": case["id"],
        "passed": passed,
        "hit": sorted(hit),
        "miss": sorted(miss),
        "wrong": sorted(wrong),
        "bonus": sorted(bonus),
        "fired": sorted(fired),
    }


def _report(results: list[dict], verbose: bool) -> None:
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    acc = passed / total if total else 0.0

    print("=== 골드셋 채점 ===\n")
    for r in results:
        badge = "PASS" if r["passed"] else "FAIL"
        print(f"[{badge}] {r['id']}")
        if verbose or not r["passed"]:
            print(f"       hit:    {r['hit']}")
            if r["miss"]:
                print(f"       miss:   {r['miss']}")
            if r["wrong"]:
                print(f"       wrong:  {r['wrong']}")
            if verbose and r["bonus"]:
                print(f"       bonus:  {r['bonus']}")

    target_badge = "OK " if acc >= PRD_TARGET else "GAP"
    print(f"\n결과: {passed}/{total} = {acc:.1%} (PRD 목표 {PRD_TARGET:.0%}) [{target_badge}]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goldset", type=Path, default=DEFAULT_GOLDSET)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    cases = _load_goldset(args.goldset)
    results = [_score_case(c) for c in cases]
    _report(results, args.verbose)

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    acc = passed / total if total else 0.0
    return 0 if acc >= PRD_TARGET else 1


if __name__ == "__main__":
    raise SystemExit(main())
