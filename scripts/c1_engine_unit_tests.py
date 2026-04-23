"""C-1 엔진 레벨 단위 테스트 — /tax 스킬 경로 검증 전에 엔진이 올바르게 작동하는지 확인.

S1: 소득세 strategy_engine.run()
S2: 법인세 strategy_engine.run()
S3: 회색지대 reasoning_engine.run()

이 테스트가 통과해야 /tax 스킬이 올바른 경로로 가도 의미 있는 결과를 낼 수 있다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def test_s1_income_tax():
    from strategy_engine import run as strategy_run

    profile = {
        "has_earned_income": True,
        "gross_salary": 80_000_000,
        "spouse_exists": True,
        "spouse_income": 30_000_000,  # 근로소득, 소득금액 약 0
        "children": [
            {"age": 8, "relation": "자녀"},
            {"age": 12, "relation": "자녀"},
        ],
        "num_children": 2,
        "children_under_20_count": 2,
        "pension_account_amount": 7_000_000,
        "medical_expense": 2_000_000,
        "housing_savings_monthly": 200_000,
        "housing_savings_annual": 2_400_000,
        "total_income": 65_000_000,  # 근로소득금액(공제 후 대략)
    }

    result = strategy_run(profile)
    fired = sorted(c["rule"].id for c in result["candidates"])

    expected_any_of = {
        "DED_PENSION_IRP_700",
        "CRED_CHILDREN",
        "TIMING_MEDICAL_EXPENSE",
        # Note: 주택청약 소득공제 규칙 미구현 — B-2 확장 대상
    }
    hit = set(fired) & expected_any_of
    return {
        "scenario": "S1_income_tax",
        "fired": fired,
        "expected_any_of": sorted(expected_any_of),
        "hit": sorted(hit),
        "coverage": f"{len(hit)}/{len(expected_any_of)}",
        "passed": len(hit) == len(expected_any_of),
    }


def test_s2_corporate_tax():
    from strategy_engine import run as strategy_run

    profile = {
        "is_corporation": True,
        "is_sme_corporation": True,
        "industry": "제조",
        "corp_revenue": 8_000_000_000,  # 80억
        "corp_operating_income": 800_000_000,  # 8억
        "corp_taxable_income": 800_000_000,
        "rd_expense": 300_000_000,  # 3억
        "rd_personnel_ratio": 1.0,
        "qualified_investment_amount": 500_000_000,  # 5억
        "investment_asset_type": "설비",
        "employment_increase_total": 0,
    }

    result = strategy_run(profile)
    fired = sorted(c["rule"].id for c in result["candidates"])

    expected_any_of = {
        "CORP_RD_TAX_CREDIT",
        "CORP_INTEGRATED_INVESTMENT_CREDIT",
    }
    hit = set(fired) & expected_any_of
    return {
        "scenario": "S2_corporate_tax",
        "fired": fired,
        "expected_any_of": sorted(expected_any_of),
        "hit": sorted(hit),
        "coverage": f"{len(hit)}/{len(expected_any_of)}",
        "passed": len(hit) >= 1,
    }


def test_s3_gray_gajigeupgeum():
    from reasoning_engine.orchestrator import run as reasoning_run

    profile = {
        "is_corporation": True,
        "is_sme_corporation": True,
        "related_party_loan_amount": 500_000_000,  # 5억
        "related_party_loan_rate": 0.02,
        "market_rate": 0.046,  # 당좌대출이자율
        "borrower": "대표이사",
        "loan_purpose": "개인 부동산 취득",
    }

    try:
        result = reasoning_run(
            issue_id="GRAY_CORP_GAJIGEUPGEUM_INTEREST",
            profile=profile,
        )
    except Exception as e:
        return {
            "scenario": "S3_gray_gajigeupgeum",
            "error": repr(e),
            "passed": False,
        }

    judgment = result.get("judgment", {}) if isinstance(result, dict) else {}
    ruling = judgment.get("ruling")
    retrieved = judgment.get("retrieved_legal") or result.get("retrieved_legal") or []
    decisive_in_ctx = any(
        "decisive" in str(x).lower() or "결정" in str(x) for x in retrieved
    )

    return {
        "scenario": "S3_gray_gajigeupgeum",
        "ruling": ruling,
        "num_retrieved": len(retrieved),
        "decisive_in_ctx": decisive_in_ctx,
        "confidence": judgment.get("confidence"),
        "passed": ruling is not None,
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["deterministic", "llm", "all"], default="all",
                    help="deterministic=S1+S2 strategy_engine / llm=S3 reasoning_engine / all")
    args = ap.parse_args()

    tests = []
    if args.only in ("deterministic", "all"):
        tests += [test_s1_income_tax, test_s2_corporate_tax]
    if args.only in ("llm", "all"):
        tests += [test_s3_gray_gajigeupgeum]

    results = []
    for fn in tests:
        print(f"\n--- {fn.__name__} ---", flush=True)
        r = fn()
        results.append(r)
        print(json.dumps(r, ensure_ascii=False, indent=2), flush=True)

    print("\n\n=== 요약 ===", flush=True)
    passed = sum(1 for r in results if r.get("passed"))
    print(f"{passed}/{len(results)} scenarios passed", flush=True)

    suffix = f"_{args.only}" if args.only != "all" else ""
    out = REPO / f"data/eval/tax_skill_runs/c1_engine_unit_results{suffix}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {out}", flush=True)


if __name__ == "__main__":
    main()
