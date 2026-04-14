"""strategy_engine v1+v2 카탈로그 회귀 (28규칙).

각 신규 규칙(21개)을 적용/비적용 페어로 검증.
카운트·스코프 격리는 전체 셋 수준에서 확인.

v2 (Phase 6): 법인세 6규칙 추가 — 실증 근거 기반
  대손충당금·퇴직급여충당금·업무용승용차·주식매수선택권·의제배당·결손금소급공제
"""

from __future__ import annotations

from strategy_engine import run
from strategy_engine.catalog import load_all


def _ids(cands):
    return {c["rule"].id for c in cands}


def _saving(cands, rid):
    for c in cands:
        if c["rule"].id == rid:
            return c["saving"]
    return None


# --- 카탈로그 구성 ---------------------------------------------------------

def test_catalog_counts_by_tax_type():
    rules = load_all()
    counts = {}
    for r in rules:
        counts[r.tax_type] = counts.get(r.tax_type, 0) + 1
    assert len(rules) == 28, f"전체 28개 예상, 실제 {len(rules)}"
    assert counts.get("소득세") == 13
    assert counts.get("법인세") == 11
    assert counts.get("상속세") == 2
    assert counts.get("증여세") == 2


# --- 소득세 신규 규칙 ------------------------------------------------------

def test_children_credit_three_kids():
    r = run({"has_earned_income": True, "gross_salary": 50_000_000, "children_under_20_count": 3})
    assert _saving(r["candidates"], "CRED_CHILDREN") == 650_000  # 350k + 1×300k


def test_children_credit_no_kids_skips():
    r = run({"has_earned_income": True, "gross_salary": 50_000_000, "children_under_20_count": 0})
    assert "CRED_CHILDREN" not in _ids(r["candidates"])


def test_education_credit_applies():
    r = run({"has_earned_income": True, "gross_salary": 50_000_000, "education_expense": 4_000_000})
    assert _saving(r["candidates"], "CRED_EDUCATION") == 600_000


def test_donation_credit_tiered():
    r = run({"has_earned_income": True, "gross_salary": 50_000_000, "donation_amount": 12_000_000})
    # 10M × 15% + 2M × 30% = 1_500_000 + 600_000 = 2_100_000
    assert _saving(r["candidates"], "CRED_DONATION") == 2_100_000


def test_credit_card_over_threshold():
    r = run({
        "has_earned_income": True,
        "gross_salary": 40_000_000,
        "card_usage_total": 20_000_000,  # threshold 10M, excess 10M
        "card_traditional_market": 0,
        "card_public_transit": 0,
    })
    # excess 10M × 15% = 1.5M (한도 3M 내), × marginal_rate
    # 과세표준 대략 40M - 공제 → 15% 구간 추정 — 단순히 발동만 확인
    assert "DED_CREDIT_CARD" in _ids(r["candidates"])


def test_credit_card_below_threshold():
    r = run({
        "has_earned_income": True,
        "gross_salary": 40_000_000,
        "card_usage_total": 0,  # 사용액 0 → 규칙 자체 비발동
    })
    assert "DED_CREDIT_CARD" not in _ids(r["candidates"])


def test_sme_employment_applies_youth():
    r = run({
        "has_earned_income": True,
        "gross_salary": 30_000_000,
        "is_sme_employee": True,
        "sme_worker_type": "youth",
        "sme_years_employed": 2.0,
    })
    assert "RED_SME_EMPLOYMENT" in _ids(r["candidates"])
    # approx_tax = 3M × 90% = 2.7M → cap 2M
    assert _saving(r["candidates"], "RED_SME_EMPLOYMENT") == 2_000_000


def test_sme_employment_expired_after_5years():
    r = run({
        "has_earned_income": True,
        "gross_salary": 30_000_000,
        "is_sme_employee": True,
        "sme_years_employed": 6.0,
    })
    assert "RED_SME_EMPLOYMENT" not in _ids(r["candidates"])


def test_yellow_umbrella_applies_for_business():
    r = run({
        "has_business_income": True,
        "business_revenue": 50_000_000,
        "business_income": 30_000_000,
        "yellow_umbrella_paid": 1_000_000,
    })
    assert "RED_YELLOW_UMBRELLA" in _ids(r["candidates"])


def test_yellow_umbrella_skips_for_employee_only():
    r = run({"has_earned_income": True, "gross_salary": 50_000_000})
    assert "RED_YELLOW_UMBRELLA" not in _ids(r["candidates"])


def test_housing_rental_separation_under_20m():
    r = run({
        "has_earned_income": True,
        "gross_salary": 50_000_000,
        "housing_rental_income": 15_000_000,
    })
    assert "SEP_HOUSING_RENTAL_2000" in _ids(r["candidates"])


def test_housing_rental_separation_over_20m_skips():
    r = run({
        "has_earned_income": True,
        "gross_salary": 50_000_000,
        "housing_rental_income": 25_000_000,
    })
    assert "SEP_HOUSING_RENTAL_2000" not in _ids(r["candidates"])


def test_other_income_separation_under_300():
    r = run({
        "has_earned_income": True,
        "gross_salary": 80_000_000,
        "other_income_net": 2_500_000,
    })
    assert "SEP_OTHER_INCOME_300" in _ids(r["candidates"])


def test_other_income_separation_over_300_skips():
    r = run({
        "has_earned_income": True,
        "gross_salary": 80_000_000,
        "other_income_net": 4_000_000,
    })
    assert "SEP_OTHER_INCOME_300" not in _ids(r["candidates"])


# --- 법인세 신규 ----------------------------------------------------------

def test_corp_entertainment_limit_over():
    r = run({
        "is_corporation": True,
        "corp_tax_rate": 0.19,
        "entertainment_paid": 50_000_000,
        "entertainment_limit": 36_000_000,
    })
    assert "CORP_ENTERTAINMENT_LIMIT" in _ids(r["candidates"])
    # excess 14M × 19% = 2,660,000
    assert _saving(r["candidates"], "CORP_ENTERTAINMENT_LIMIT") == 2_660_000


def test_corp_entertainment_within_limit_skips():
    r = run({
        "is_corporation": True,
        "entertainment_paid": 30_000_000,
        "entertainment_limit": 36_000_000,
    })
    assert "CORP_ENTERTAINMENT_LIMIT" not in _ids(r["candidates"])


def test_corp_donation_limit_over():
    r = run({
        "is_corporation": True,
        "corp_tax_rate": 0.19,
        "donation_paid": 200_000_000,
        "donation_limit": 100_000_000,
    })
    assert "CORP_DONATION_LIMIT" in _ids(r["candidates"])
    assert _saving(r["candidates"], "CORP_DONATION_LIMIT") == 19_000_000


def test_corp_loss_carryforward_sme():
    r = run({
        "is_corporation": True,
        "corp_tax_rate": 0.19,
        "loss_carryforward_available": 50_000_000,
        "corp_taxable_income": 100_000_000,
        "is_sme_corporation": True,
    })
    # usable = min(50M, 100M × 100%) = 50M × 19% = 9,500,000
    assert _saving(r["candidates"], "CORP_LOSS_CARRYFORWARD") == 9_500_000


def test_corp_loss_carryforward_general_limited_to_80pct():
    r = run({
        "is_corporation": True,
        "corp_tax_rate": 0.19,
        "loss_carryforward_available": 100_000_000,
        "corp_taxable_income": 100_000_000,
        "is_sme_corporation": False,
    })
    # usable = min(100M, 100M × 80%) = 80M × 19% = 15,200,000
    assert _saving(r["candidates"], "CORP_LOSS_CARRYFORWARD") == 15_200_000


# --- 상속세 신규 ----------------------------------------------------------

def test_inh_spouse_deduction_maximize():
    r = run({
        "is_inheritance_case": True,
        "spouse_exists": True,
        "inheritance_total": 2_000_000_000,
        "spouse_inherit_amount": 500_000_000,
        "spouse_legal_share": 1_200_000_000,
    })
    assert "INH_SPOUSE_DEDUCTION" in _ids(r["candidates"])
    # additional 700M × 20% = 140M
    assert _saving(r["candidates"], "INH_SPOUSE_DEDUCTION") == 140_000_000


def test_inh_spouse_deduction_small_estate_skips():
    r = run({
        "is_inheritance_case": True,
        "spouse_exists": True,
        "inheritance_total": 300_000_000,
    })
    assert "INH_SPOUSE_DEDUCTION" not in _ids(r["candidates"])


def test_inh_installment_large_payable():
    r = run({
        "is_inheritance_case": True,
        "inheritance_tax_payable": 100_000_000,
    })
    assert "INH_INSTALLMENT_PAYMENT" in _ids(r["candidates"])


def test_inh_installment_under_20m_skips():
    r = run({
        "is_inheritance_case": True,
        "inheritance_tax_payable": 15_000_000,
    })
    assert "INH_INSTALLMENT_PAYMENT" not in _ids(r["candidates"])


# --- 증여세 신규 ----------------------------------------------------------

def test_gift_split_over_exemption():
    r = run({
        "is_gift_case": True,
        "gift_planned_amount": 100_000_000,
        "gift_prior_10yr_amount": 50_000_000,
        "gift_total_with_prior_10yr": 150_000_000,
        "gift_exemption_limit": 50_000_000,
    })
    assert "GIFT_SPLIT_10YEAR" in _ids(r["candidates"])
    # excess 100M × 20% = 20M
    assert _saving(r["candidates"], "GIFT_SPLIT_10YEAR") == 20_000_000


def test_gift_split_under_exemption_skips():
    r = run({
        "is_gift_case": True,
        "gift_planned_amount": 30_000_000,
        "gift_prior_10yr_amount": 10_000_000,
        "gift_total_with_prior_10yr": 40_000_000,
        "gift_exemption_limit": 50_000_000,
    })
    assert "GIFT_SPLIT_10YEAR" not in _ids(r["candidates"])


def test_gift_low_valuation_applies():
    r = run({
        "is_gift_case": True,
        "low_value_asset_fair_price": 500_000_000,
        "low_value_asset_expected_price": 700_000_000,
    })
    assert "GIFT_LOW_VALUATION" in _ids(r["candidates"])
    assert _saving(r["candidates"], "GIFT_LOW_VALUATION") == 40_000_000


def test_gift_low_valuation_equal_price_skips():
    r = run({
        "is_gift_case": True,
        "low_value_asset_fair_price": 500_000_000,
        "low_value_asset_expected_price": 500_000_000,
    })
    assert "GIFT_LOW_VALUATION" not in _ids(r["candidates"])


# --- 법인세 v2 (Phase 6) — 실증 근거 6규칙 ------------------------------

_CORP_BASE = {"is_corporation": True, "corp_tax_rate": 0.19}


def test_corp_bad_debt_reserve_excess():
    r = run({**_CORP_BASE, "bad_debt_reserve_paid": 100_000_000, "bad_debt_reserve_limit": 80_000_000})
    # excess 20M × 19% = 3.8M
    assert _saving(r["candidates"], "CORP_BAD_DEBT_RESERVE_EXCESS") == 3_800_000


def test_corp_bad_debt_within_limit_skips():
    r = run({**_CORP_BASE, "bad_debt_reserve_paid": 80_000_000, "bad_debt_reserve_limit": 100_000_000})
    assert "CORP_BAD_DEBT_RESERVE_EXCESS" not in _ids(r["candidates"])


def test_corp_retirement_reserve_excess():
    r = run({**_CORP_BASE, "retirement_reserve_paid": 50_000_000, "retirement_reserve_limit": 20_000_000})
    # excess 30M × 19% = 5.7M
    assert _saving(r["candidates"], "CORP_RETIREMENT_RESERVE_EXCESS") == 5_700_000


def test_corp_retirement_reserve_within_limit_skips():
    r = run({**_CORP_BASE, "retirement_reserve_paid": 10_000_000, "retirement_reserve_limit": 20_000_000})
    assert "CORP_RETIREMENT_RESERVE_EXCESS" not in _ids(r["candidates"])


def test_corp_company_vehicle_no_log_over_limit():
    r = run({**_CORP_BASE, "company_vehicle_expense": 25_000_000, "has_vehicle_log": False})
    # excess over 15M → 10M × 19% = 1.9M
    assert _saving(r["candidates"], "CORP_COMPANY_VEHICLE_EXCESS") == 1_900_000


def test_corp_company_vehicle_with_log_skips():
    r = run({**_CORP_BASE, "company_vehicle_expense": 25_000_000, "has_vehicle_log": True})
    assert "CORP_COMPANY_VEHICLE_EXCESS" not in _ids(r["candidates"])


def test_corp_eso_nondeductible_regular_corp():
    r = run({**_CORP_BASE, "eso_exercise_cost": 30_000_000, "is_venture_or_sme": False})
    # 30M × 19% = 5.7M
    assert _saving(r["candidates"], "CORP_ESO_NONDEDUCTIBLE") == 5_700_000


def test_corp_eso_venture_exemption_skips():
    r = run({**_CORP_BASE, "eso_exercise_cost": 30_000_000, "is_venture_or_sme": True})
    assert "CORP_ESO_NONDEDUCTIBLE" not in _ids(r["candidates"])


def test_corp_deemed_dividend_withholding_applies():
    r = run({**_CORP_BASE, "deemed_dividend_amount": 100_000_000})
    # 100M × 14% = 14M
    assert _saving(r["candidates"], "CORP_DEEMED_DIVIDEND_WITHHOLDING") == 14_000_000


def test_corp_deemed_dividend_zero_skips():
    r = run({**_CORP_BASE, "deemed_dividend_amount": 0})
    assert "CORP_DEEMED_DIVIDEND_WITHHOLDING" not in _ids(r["candidates"])


def test_corp_loss_carryback_sme_partial_ratio():
    r = run({
        **_CORP_BASE,
        "is_sme_corporation": True,
        "current_year_loss": 50_000_000,
        "prior_year_tax_paid": 30_000_000,
        "prior_year_taxable_income": 100_000_000,
    })
    # 30M × (50M/100M) = 15M
    assert _saving(r["candidates"], "CORP_LOSS_CARRYBACK") == 15_000_000


def test_corp_loss_carryback_non_sme_skips():
    r = run({
        **_CORP_BASE,
        "is_sme_corporation": False,
        "current_year_loss": 50_000_000,
        "prior_year_tax_paid": 30_000_000,
        "prior_year_taxable_income": 100_000_000,
    })
    assert "CORP_LOSS_CARRYBACK" not in _ids(r["candidates"])


# --- 스코프 격리 (크로스-세목 오발동 금지) ------------------------------

def test_income_profile_no_corp_or_estate_rules():
    r = run({"has_earned_income": True, "gross_salary": 60_000_000})
    ids = _ids(r["candidates"])
    for rid in (
        "CORP_EXECUTIVE_BONUS_EXCESS", "CORP_UNFAIR_HIGH_PRICE_PURCHASE",
        "CORP_ENTERTAINMENT_LIMIT", "CORP_DONATION_LIMIT", "CORP_LOSS_CARRYFORWARD",
        "CORP_BAD_DEBT_RESERVE_EXCESS", "CORP_RETIREMENT_RESERVE_EXCESS",
        "CORP_COMPANY_VEHICLE_EXCESS", "CORP_ESO_NONDEDUCTIBLE",
        "CORP_DEEMED_DIVIDEND_WITHHOLDING", "CORP_LOSS_CARRYBACK",
        "INH_SPOUSE_DEDUCTION", "INH_INSTALLMENT_PAYMENT",
        "GIFT_SPLIT_10YEAR", "GIFT_LOW_VALUATION",
    ):
        assert rid not in ids, f"{rid} 오발동 (개인 소득세 프로필)"


def test_inheritance_profile_no_income_or_corp_rules():
    r = run({
        "is_inheritance_case": True,
        "spouse_exists": True,
        "inheritance_total": 1_000_000_000,
        "spouse_inherit_amount": 300_000_000,
        "spouse_legal_share": 600_000_000,
    })
    ids = _ids(r["candidates"])
    assert "CRED_CHILDREN" not in ids
    assert "CORP_ENTERTAINMENT_LIMIT" not in ids
    assert "GIFT_SPLIT_10YEAR" not in ids


if __name__ == "__main__":
    tests = [
        ("catalog counts", test_catalog_counts_by_tax_type),
        ("children 3kids", test_children_credit_three_kids),
        ("children 0 skip", test_children_credit_no_kids_skips),
        ("education", test_education_credit_applies),
        ("donation tiered", test_donation_credit_tiered),
        ("card over", test_credit_card_over_threshold),
        ("card under skip", test_credit_card_below_threshold),
        ("sme youth", test_sme_employment_applies_youth),
        ("sme expired skip", test_sme_employment_expired_after_5years),
        ("yellow biz", test_yellow_umbrella_applies_for_business),
        ("yellow emp skip", test_yellow_umbrella_skips_for_employee_only),
        ("housing 20m", test_housing_rental_separation_under_20m),
        ("housing over skip", test_housing_rental_separation_over_20m_skips),
        ("other 300", test_other_income_separation_under_300),
        ("other over skip", test_other_income_separation_over_300_skips),
        ("corp ent over", test_corp_entertainment_limit_over),
        ("corp ent skip", test_corp_entertainment_within_limit_skips),
        ("corp donation", test_corp_donation_limit_over),
        ("corp loss sme", test_corp_loss_carryforward_sme),
        ("corp loss 80pct", test_corp_loss_carryforward_general_limited_to_80pct),
        ("corp bad debt", test_corp_bad_debt_reserve_excess),
        ("corp bad debt skip", test_corp_bad_debt_within_limit_skips),
        ("corp retire", test_corp_retirement_reserve_excess),
        ("corp retire skip", test_corp_retirement_reserve_within_limit_skips),
        ("corp vehicle", test_corp_company_vehicle_no_log_over_limit),
        ("corp vehicle log skip", test_corp_company_vehicle_with_log_skips),
        ("corp eso", test_corp_eso_nondeductible_regular_corp),
        ("corp eso venture skip", test_corp_eso_venture_exemption_skips),
        ("corp deemed div", test_corp_deemed_dividend_withholding_applies),
        ("corp deemed zero skip", test_corp_deemed_dividend_zero_skips),
        ("corp carryback", test_corp_loss_carryback_sme_partial_ratio),
        ("corp carryback non-sme skip", test_corp_loss_carryback_non_sme_skips),
        ("inh spouse", test_inh_spouse_deduction_maximize),
        ("inh spouse skip", test_inh_spouse_deduction_small_estate_skips),
        ("inh installment", test_inh_installment_large_payable),
        ("inh install skip", test_inh_installment_under_20m_skips),
        ("gift split", test_gift_split_over_exemption),
        ("gift split skip", test_gift_split_under_exemption_skips),
        ("gift low val", test_gift_low_valuation_applies),
        ("gift low eq skip", test_gift_low_valuation_equal_price_skips),
        ("scope income only", test_income_profile_no_corp_or_estate_rules),
        ("scope inh only", test_inheritance_profile_no_income_or_corp_rules),
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
