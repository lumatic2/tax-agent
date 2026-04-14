"""strategy_engine 골든 셋 회귀.

5개 규칙 × (적용/비적용) 케이스 exact-match 검증.
eval_scenarios.py 패턴을 따른다.
"""

from __future__ import annotations

from strategy_engine import generate_strategy, run
from strategy_engine.catalog import load_all
from strategy_engine.dsl import evaluate
from strategy_engine.simulator import (
    double_entry_savings,
    financial_separation_savings,
    medical_expense_timing_savings,
    monthly_rent_credit_savings,
    pension_account_savings,
)


def _rule_ids(strategies):
    return {s["rule_id"] for s in strategies}


def _by_id(strategies, rid):
    for s in strategies:
        if s["rule_id"] == rid:
            return s
    return None


def test_catalog_loads_five_rules():
    rules = load_all()
    ids = {r.id for r in rules}
    required = {
        "FIN_SEPARATION_2000",
        "BOOK_DOUBLE_ENTRY_4800",
        "CRED_MONTHLY_RENT",
        "DED_PENSION_IRP_700",
        "TIMING_MEDICAL_EXPENSE",
    }
    missing = required - ids
    assert not missing, f"소득세 골든 셋 규칙 누락: {missing}"


# --- FIN_SEPARATION_2000 ---------------------------------------------------

def test_fin_separation_applies_when_under_20m():
    profile = {
        "has_earned_income": True,
        "gross_salary": 60_000_000,
        "interest_income": 5_000_000,
        "dividend_income": 3_000_000,
        "financial_income_total": 8_000_000,
        "marginal_rate": 0.24,
    }
    strategies = generate_strategy(profile, {"적용세율": 0.24})
    s = _by_id(strategies, "FIN_SEPARATION_2000")
    assert s is not None, "금융 2천만 이하 → 분리과세 규칙 발동 필요"
    expected = financial_separation_savings(5_000_000, 3_000_000, 0.24)
    assert expected == 800_000, f"공식 검증: {expected}"
    assert s["예상절세액"] == expected


def test_fin_separation_not_applies_over_20m():
    profile = {
        "has_earned_income": True,
        "gross_salary": 60_000_000,
        "interest_income": 15_000_000,
        "dividend_income": 10_000_000,
        "financial_income_total": 25_000_000,
        "marginal_rate": 0.35,
    }
    strategies = generate_strategy(profile, {"적용세율": 0.35})
    assert "FIN_SEPARATION_2000" not in _rule_ids(strategies), "2천만 초과 시 비발동"


# --- BOOK_DOUBLE_ENTRY_4800 ------------------------------------------------

def test_bookkeeping_applies_when_revenue_over_4800():
    profile = {
        "has_earned_income": False,
        "has_business_income": True,
        "business_revenue": 80_000_000,
        "business_income": 50_000_000,
        "book_method": "단순",
        "marginal_rate": 0.24,
    }
    strategies = generate_strategy(profile, {"적용세율": 0.24})
    s = _by_id(strategies, "BOOK_DOUBLE_ENTRY_4800")
    assert s is not None
    expected = double_entry_savings(50_000_000, 0.24)
    assert s["예상절세액"] == expected
    assert expected > 0


def test_bookkeeping_not_applies_when_revenue_under_4800():
    profile = {
        "has_business_income": True,
        "business_revenue": 30_000_000,
        "business_income": 20_000_000,
        "book_method": "단순",
    }
    strategies = generate_strategy(profile, {})
    assert "BOOK_DOUBLE_ENTRY_4800" not in _rule_ids(strategies)


# --- CRED_MONTHLY_RENT -----------------------------------------------------

def test_monthly_rent_applies_when_homeless_under_80m():
    profile = {
        "has_earned_income": True,
        "gross_salary": 45_000_000,
        "monthly_rent": 500_000,
        "is_homeless_household": True,
    }
    strategies = generate_strategy(profile, {})
    s = _by_id(strategies, "CRED_MONTHLY_RENT")
    assert s is not None
    expected = monthly_rent_credit_savings(500_000, 45_000_000)
    # 500_000 × 12 = 6_000_000, < 한도 10_000_000, 17% (5500만 이하)
    assert expected == int(6_000_000 * 0.17) == 1_020_000
    assert s["예상절세액"] == expected


def test_monthly_rent_not_applies_when_salary_over_80m():
    profile = {
        "has_earned_income": True,
        "gross_salary": 90_000_000,
        "monthly_rent": 500_000,
        "is_homeless_household": True,
    }
    strategies = generate_strategy(profile, {})
    assert "CRED_MONTHLY_RENT" not in _rule_ids(strategies)


# --- DED_PENSION_IRP_700 ---------------------------------------------------

def test_pension_applies_when_under_limit():
    profile = {
        "has_earned_income": True,
        "gross_salary": 50_000_000,
        "irp_pension": 2_000_000,
        "pension_savings": 1_000_000,
        "pension_account_total": 3_000_000,
    }
    strategies = generate_strategy(profile, {})
    s = _by_id(strategies, "DED_PENSION_IRP_700")
    assert s is not None
    expected = pension_account_savings(3_000_000, 50_000_000)
    # (9_000_000 - 3_000_000) × 0.165 = 990_000
    assert expected == 990_000
    assert s["예상절세액"] == expected


def test_pension_not_applies_when_limit_reached():
    profile = {
        "has_earned_income": True,
        "gross_salary": 50_000_000,
        "irp_pension": 5_000_000,
        "pension_savings": 4_000_000,
        "pension_account_total": 9_000_000,
    }
    strategies = generate_strategy(profile, {})
    assert "DED_PENSION_IRP_700" not in _rule_ids(strategies)


# --- TIMING_MEDICAL_EXPENSE ------------------------------------------------

def test_medical_timing_applies_when_expense_exists():
    profile = {
        "has_earned_income": True,
        "gross_salary": 60_000_000,
        "medical_expense": 3_000_000,
    }
    strategies = generate_strategy(profile, {})
    s = _by_id(strategies, "TIMING_MEDICAL_EXPENSE")
    assert s is not None
    expected = medical_expense_timing_savings(3_000_000, 60_000_000)
    # threshold_now = 1_800_000, threshold_spouse = 900_000
    # extra_base = min(900_000, 3_000_000 - 900_000) = 900_000
    # saving = 900_000 × 0.15 = 135_000
    assert expected == 135_000
    assert s["예상절세액"] == expected


def test_medical_timing_not_applies_when_no_expense():
    profile = {
        "has_earned_income": True,
        "gross_salary": 60_000_000,
        "medical_expense": 0,
    }
    strategies = generate_strategy(profile, {})
    assert "TIMING_MEDICAL_EXPENSE" not in _rule_ids(strategies)


# --- DSL 트레이스 덤프 -----------------------------------------------------

def test_dsl_trace_dump_explains_nonapplicable():
    """DSL 트레이스는 어느 절이 false 였는지 설명 가능해야 한다."""
    rules = [r for r in load_all() if r.id == "FIN_SEPARATION_2000"]
    profile = {"financial_income_total": 25_000_000}
    _, trace = evaluate(rules[0].applies_when, profile)
    # and 노드의 자식 중 left_value=25000000이 right 20000000 초과로 false
    assert trace["op"] == "and"
    assert trace["result"] is False
    found_fail = any(
        t.get("left_value") == 25_000_000 and t.get("result") is False
        for t in trace["of"]
    )
    assert found_fail, f"25M 초과 노드 false 기록 누락: {trace}"


if __name__ == "__main__":
    tests = [
        ("catalog_loads", test_catalog_loads_five_rules),
        ("FIN apply", test_fin_separation_applies_when_under_20m),
        ("FIN skip", test_fin_separation_not_applies_over_20m),
        ("BOOK apply", test_bookkeeping_applies_when_revenue_over_4800),
        ("BOOK skip", test_bookkeeping_not_applies_when_revenue_under_4800),
        ("RENT apply", test_monthly_rent_applies_when_homeless_under_80m),
        ("RENT skip", test_monthly_rent_not_applies_when_salary_over_80m),
        ("PENSION apply", test_pension_applies_when_under_limit),
        ("PENSION skip", test_pension_not_applies_when_limit_reached),
        ("MEDICAL apply", test_medical_timing_applies_when_expense_exists),
        ("MEDICAL skip", test_medical_timing_not_applies_when_no_expense),
        ("DSL trace", test_dsl_trace_dump_explains_nonapplicable),
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
            print(f"[ERR ] {name}: {e!r}")
    print(f"\n{passed}/{len(tests)} passed")
    if passed != len(tests):
        raise SystemExit(1)
