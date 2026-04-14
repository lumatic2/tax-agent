"""strategy_engine end-to-end 통합 시나리오.

main.py 가 조립하는 raw profile 구조를 그대로 입력으로 던져,
orchestrator → profile_builder → gap_detector/generator → simulator → risk_flags
전 파이프라인이 깨지지 않고 기대 전략을 발동시키는지 검증한다.

시나리오: 근로+금융 겸업자 (총급여 6,000만 + 이자 800만 + 배당 700만)
- 월세 50만/월, 무주택
- IRP 150만 + 연금저축 50만 납입 (한도 900만 대비 200만 소진)
- 의료비 300만
"""

from __future__ import annotations

import tax_calculator
from strategy_engine import run
from strategy_engine.simulator import (
    financial_separation_savings,
    monthly_rent_credit_savings,
    pension_account_savings,
    medical_expense_timing_savings,
)


def build_raw_profile_composite():
    """main.py 의 tax_store.save_user_profile 에 들어가는 raw profile 형태."""
    return {
        "name": "E2E_복합소득자",
        "tax_year": 2026,
        "income_type": ["복합소득자"],
        "flags": {
            "월세지출": True,
            "월세지출_금액": 500_000,
            "무주택세대주": True,
            "중소기업취업": False,
            "교육비지출": False,
            "의료비지출": True,
            "중도퇴사": False,
            "혼인": False,
            "기부금이월": False,
            "종교단체기부": False,
            "inputs": {
                "type": "복합소득자",
                "composite": {
                    "wage": {
                        "gross_salary": 60_000_000,
                        "pay_items": [],
                        "insurance": {
                            "national_pension": 2_640_000,
                            "health_insurance": 2_100_000,
                            "employment_insurance": 480_000,
                        },
                        "expenses": {
                            "medical_expense": 3_000_000,
                            "education_expense": 0,
                            "donation": 0,
                        },
                        "housing_fund": 0,
                        "irp_pension": 1_500_000,
                        "pension_savings": 500_000,
                        "dependents": [],
                        "prepaid_tax": 0,
                    },
                    "business": {},
                    "financial": {
                        "interest": 8_000_000,
                        "dividend": 7_000_000,
                        "gross_up_eligible_dividend": 0,
                    },
                    "other_income_items": [],
                },
            },
        },
    }


def compute_tax_result_for_wage(gross_salary: int) -> dict:
    """근로분 세액만 대표로 반영한 tax_result (적용세율 파악용)."""
    return tax_calculator.calculate_wage_income_tax(
        gross_salary,
        extra_deductions={"국민연금": 2_640_000, "건강보험": 2_100_000, "고용보험": 480_000},
    )


# --- tests -----------------------------------------------------------------

def test_profile_builder_flattens_composite():
    from strategy_engine.profile_builder import build_profile

    raw = build_raw_profile_composite()
    tax_result = compute_tax_result_for_wage(60_000_000)
    profile = build_profile(raw, tax_result)

    assert profile["gross_salary"] == 60_000_000
    assert profile["interest_income"] == 8_000_000
    assert profile["dividend_income"] == 7_000_000
    assert profile["financial_income_total"] == 15_000_000
    assert profile["irp_pension"] == 1_500_000
    assert profile["pension_savings"] == 500_000
    assert profile["pension_account_total"] == 2_000_000
    assert profile["medical_expense"] == 3_000_000
    assert profile["monthly_rent"] == 500_000
    assert profile["is_homeless_household"] is True
    assert profile["has_earned_income"] is True
    # 복합 소득자지만 사업소득 0
    assert profile["has_business_income"] is False
    assert profile["marginal_rate"] == tax_result["적용세율"]


def test_e2e_pipeline_returns_expected_strategies():
    raw = build_raw_profile_composite()
    tax_result = compute_tax_result_for_wage(60_000_000)
    result = run(raw, tax_result)

    ids = {c["rule"].id for c in result["candidates"]}
    # 근로 + 금융 2천만 이하 + 월세 무주택 + 연금 한도 미소진 + 의료비 → 4개 전부 발동
    assert "FIN_SEPARATION_2000" in ids
    assert "CRED_MONTHLY_RENT" in ids
    assert "DED_PENSION_IRP_700" in ids
    assert "TIMING_MEDICAL_EXPENSE" in ids
    # 사업소득 0 → 복식부기 규칙 미발동
    assert "BOOK_DOUBLE_ENTRY_4800" not in ids


def test_e2e_savings_match_formulas():
    raw = build_raw_profile_composite()
    tax_result = compute_tax_result_for_wage(60_000_000)
    result = run(raw, tax_result)
    saving_by_id = {c["rule"].id: c["saving"] for c in result["candidates"]}

    marginal = tax_result["적용세율"]

    assert saving_by_id["FIN_SEPARATION_2000"] == financial_separation_savings(
        8_000_000, 7_000_000, marginal
    )
    assert saving_by_id["CRED_MONTHLY_RENT"] == monthly_rent_credit_savings(
        500_000, 60_000_000
    )
    assert saving_by_id["DED_PENSION_IRP_700"] == pension_account_savings(
        2_000_000, 60_000_000
    )
    assert saving_by_id["TIMING_MEDICAL_EXPENSE"] == medical_expense_timing_savings(
        3_000_000, 60_000_000
    )


def test_e2e_priority_ordering():
    """결과는 priority high 먼저, 동률 내 절세액 내림차순."""
    raw = build_raw_profile_composite()
    tax_result = compute_tax_result_for_wage(60_000_000)
    result = run(raw, tax_result)
    cands = result["candidates"]

    # priority rank: high=0, medium=1
    ranks = [c["rule"].priority for c in cands]
    rank_num = {"high": 0, "medium": 1, "low": 2}
    for i in range(len(ranks) - 1):
        assert rank_num[ranks[i]] <= rank_num[ranks[i + 1]], f"priority 역순: {ranks}"

    # high 끼리는 saving 내림차순
    high_savings = [c["saving"] for c in cands if c["rule"].priority == "high"]
    assert high_savings == sorted(high_savings, reverse=True), f"high 절세액 정렬 오류: {high_savings}"


def test_e2e_risk_fields_present():
    raw = build_raw_profile_composite()
    result = run(raw, compute_tax_result_for_wage(60_000_000))
    for c in result["candidates"]:
        risk = c.get("risk")
        assert isinstance(risk, dict)
        assert "level" in risk and risk["level"] in {"low", "medium", "high"}
        assert "flags" in risk and isinstance(risk["flags"], list)


def test_e2e_legacy_format_compatible_with_main_py():
    """main.py 가 기대하는 generate_strategy() 반환 스키마 유지."""
    from strategy_engine import generate_strategy

    raw = build_raw_profile_composite()
    strategies = generate_strategy(raw, compute_tax_result_for_wage(60_000_000))
    assert len(strategies) >= 4
    for s in strategies:
        assert "항목" in s
        assert "예상절세액" in s and isinstance(s["예상절세액"], int)
        assert "법령조항" in s
        assert "조건" in s
        assert "rule_id" in s
        assert "리스크" in s


def test_e2e_financial_over_20m_blocks_separation_rule():
    """금융소득 2,500만 케이스 → 분리과세 규칙 비발동, 다른 규칙은 정상."""
    raw = build_raw_profile_composite()
    raw["flags"]["inputs"]["composite"]["financial"]["interest"] = 15_000_000
    raw["flags"]["inputs"]["composite"]["financial"]["dividend"] = 10_000_000
    result = run(raw, compute_tax_result_for_wage(60_000_000))
    ids = {c["rule"].id for c in result["candidates"]}
    assert "FIN_SEPARATION_2000" not in ids
    # 다른 규칙 여전히 발동
    assert "CRED_MONTHLY_RENT" in ids
    assert "DED_PENSION_IRP_700" in ids


if __name__ == "__main__":
    tests = [
        ("profile_builder flatten", test_profile_builder_flattens_composite),
        ("e2e strategies", test_e2e_pipeline_returns_expected_strategies),
        ("e2e savings", test_e2e_savings_match_formulas),
        ("e2e priority", test_e2e_priority_ordering),
        ("e2e risk", test_e2e_risk_fields_present),
        ("e2e legacy fmt", test_e2e_legacy_format_compatible_with_main_py),
        ("e2e over-20m", test_e2e_financial_over_20m_blocks_separation_rule),
    ]
    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"[PASS] {name}")
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {name}: {e}")
        except Exception as e:
            import traceback
            print(f"[ERR ] {name}: {e!r}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} passed")
    if passed != len(tests):
        raise SystemExit(1)
