"""main.py user_data → DSL 평가용 flat profile 변환.

두 가지 입력 케이스 모두 처리:
1. main.py 의 원시 profile (income_type/flags.inputs 중첩 구조)
2. 간소화 user_data ({income, flags} 형태) — 기존 strategy_engine 테스트용
3. 이미 flat 한 profile — 테스트/eval에서 직접 주입
"""

from __future__ import annotations

from typing import Any

import tax_calculator


def _to_int(v, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return int(default)


def _to_float(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return float(default)


def _marginal_rate(total_income: int, tax_result: dict) -> float:
    if isinstance(tax_result, dict) and "적용세율" in tax_result:
        return _to_float(tax_result.get("적용세율", 0.15), 0.15)
    try:
        return _to_float(
            tax_calculator.calculate_tax(max(total_income, 0)).get("적용세율", 0.15),
            0.15,
        )
    except Exception:
        return 0.15


def build_profile(user_data: dict, tax_result: dict | None = None) -> dict:
    tax_result = tax_result or {}

    if _looks_flat(user_data):
        return _fill_defaults(dict(user_data), tax_result)

    if _looks_raw_main(user_data):
        return _from_main_profile(user_data, tax_result)

    return _from_simple_user_data(user_data, tax_result)


_FLAT_TRIGGERS = {
    "financial_income_total",
    "has_earned_income",
    "has_business_income",
    "gross_salary",
    "business_revenue",
    "is_corporation",
    "is_inheritance_case",
    "is_gift_case",
}


def _looks_flat(ud: dict) -> bool:
    return isinstance(ud, dict) and any(k in ud for k in _FLAT_TRIGGERS)


def _looks_raw_main(ud: dict) -> bool:
    return isinstance(ud, dict) and "income_type" in ud and "flags" in ud


def _fill_defaults(p: dict, tax_result: dict) -> dict:
    p.setdefault("gross_salary", 0)
    p.setdefault("business_revenue", 0)
    p.setdefault("business_income", 0)
    p.setdefault("interest_income", 0)
    p.setdefault("dividend_income", 0)
    p.setdefault("financial_income_total", p["interest_income"] + p["dividend_income"])
    p.setdefault("monthly_rent", 0)
    p.setdefault("irp_pension", 0)
    p.setdefault("pension_savings", 0)
    p.setdefault("pension_account_total", p["irp_pension"] + p["pension_savings"])
    p.setdefault("medical_expense", 0)
    p.setdefault("dependents_count", 0)
    p.setdefault("book_method", "")
    p.setdefault("is_homeless_household", False)
    p.setdefault("has_earned_income", p["gross_salary"] > 0)
    p.setdefault("has_business_income", p["business_income"] > 0 or p["business_revenue"] > 0)

    p.setdefault("is_corporation", False)
    p.setdefault("corp_tax_rate", 0.19)
    p.setdefault("executive_bonus_paid", 0)
    p.setdefault("executive_bonus_resolution_amount", 0)
    p.setdefault(
        "executive_bonus_excess",
        max(p["executive_bonus_paid"] - p["executive_bonus_resolution_amount"], 0),
    )
    p.setdefault("related_party_purchase_price", 0)
    p.setdefault("related_party_market_price", 0)
    market = p["related_party_market_price"]
    purchase = p["related_party_purchase_price"]
    p.setdefault(
        "high_price_purchase_excess_ratio",
        ((purchase - market) / market) if market > 0 else 0.0,
    )
    p.setdefault(
        "unfair_purchase_excess",
        max(purchase - market, 0) if market > 0 else 0,
    )

    # 소득세 v1 추가 필드
    p.setdefault("children_under_20_count", 0)
    p.setdefault("education_expense", 0)
    p.setdefault("donation_amount", 0)
    p.setdefault("card_usage_total", 0)
    p.setdefault("card_traditional_market", 0)
    p.setdefault("card_public_transit", 0)
    p.setdefault("is_sme_employee", False)
    p.setdefault("sme_years_employed", 0.0)
    p.setdefault("sme_worker_type", "general")
    p.setdefault("yellow_umbrella_paid", 0)
    p.setdefault("housing_rental_income", 0)
    p.setdefault("is_registered_rental", False)
    p.setdefault("other_income_net", 0)

    # 법인세 v1 추가 필드
    p.setdefault("entertainment_paid", 0)
    p.setdefault("entertainment_limit", 0)
    p.setdefault(
        "entertainment_excess",
        max(p["entertainment_paid"] - p["entertainment_limit"], 0),
    )
    p.setdefault("donation_paid", 0)
    p.setdefault("donation_limit", 0)
    p.setdefault(
        "donation_excess",
        max(p["donation_paid"] - p["donation_limit"], 0),
    )
    p.setdefault("loss_carryforward_available", 0)
    p.setdefault("corp_taxable_income", 0)
    p.setdefault("is_sme_corporation", False)

    # 법인세 v2 확장 (Phase 6 — 실증 근거 6규칙)
    p.setdefault("bad_debt_reserve_paid", 0)
    p.setdefault("bad_debt_reserve_limit", 0)
    p.setdefault(
        "bad_debt_reserve_excess",
        max(p["bad_debt_reserve_paid"] - p["bad_debt_reserve_limit"], 0),
    )
    p.setdefault("retirement_reserve_paid", 0)
    p.setdefault("retirement_reserve_limit", 0)
    p.setdefault(
        "retirement_reserve_excess",
        max(p["retirement_reserve_paid"] - p["retirement_reserve_limit"], 0),
    )
    p.setdefault("company_vehicle_expense", 0)
    p.setdefault("has_vehicle_log", False)
    p.setdefault("eso_exercise_cost", 0)
    p.setdefault("is_venture_or_sme", False)
    p.setdefault("deemed_dividend_amount", 0)
    p.setdefault("current_year_loss", 0)
    p.setdefault("prior_year_tax_paid", 0)
    p.setdefault("prior_year_taxable_income", 0)

    # 상속세 v1 추가 필드
    p.setdefault("is_inheritance_case", False)
    p.setdefault("spouse_exists", False)
    p.setdefault("inheritance_total", 0)
    p.setdefault("spouse_inherit_amount", 0)
    p.setdefault("spouse_legal_share", 0)
    p.setdefault("inheritance_tax_payable", 0)

    # 증여세 v1 추가 필드
    p.setdefault("is_gift_case", False)
    p.setdefault("gift_planned_amount", 0)
    p.setdefault("gift_prior_10yr_amount", 0)
    p.setdefault(
        "gift_total_with_prior_10yr",
        p["gift_planned_amount"] + p["gift_prior_10yr_amount"],
    )
    p.setdefault("gift_exemption_limit", 0)
    p.setdefault("low_value_asset_fair_price", 0)
    p.setdefault("low_value_asset_expected_price", 0)

    total = p["gross_salary"] + p["business_income"] + p["financial_income_total"]
    p.setdefault("marginal_rate", _marginal_rate(total, tax_result))
    p.setdefault("tax_result", tax_result)
    return p


def _from_main_profile(profile: dict, tax_result: dict) -> dict:
    flags = profile.get("flags", {}) or {}
    inputs = flags.get("inputs") or {}
    income_type = ((profile.get("income_type") or [""])[0]) or ""

    wage = inputs.get("wage") if income_type == "근로소득자" else (
        (inputs.get("composite") or {}).get("wage") or {}
    )
    biz_inputs = inputs.get("business") if income_type == "사업소득자" else (
        (inputs.get("composite") or {}).get("business") or {}
    )
    composite = inputs.get("composite") or {}
    financial = composite.get("financial") or {}

    wage = wage or {}
    biz_inputs = biz_inputs or {}

    gross_salary = _to_int(wage.get("gross_salary", 0))
    business_revenue = _to_int(biz_inputs.get("revenue", 0))
    prev_revenue = _to_int(biz_inputs.get("prev_year_revenue", 0))

    business_income = 0
    if business_revenue > 0:
        try:
            biz = tax_calculator.calculate_business_income(
                revenue=business_revenue,
                industry_code=str(biz_inputs.get("industry_code", "") or ""),
                method=str(biz_inputs.get("method", "단순") or "단순"),
                prev_year_revenue=prev_revenue,
                major_expenses=biz_inputs.get("major_expenses", {}) or {},
                actual_expenses=_to_int(biz_inputs.get("actual_expenses", 0)),
            )
            business_income = _to_int(biz.get("사업소득금액", 0))
        except Exception:
            business_income = 0

    interest = _to_int(financial.get("interest", 0))
    dividend = _to_int(financial.get("dividend", 0))

    irp = _to_int(wage.get("irp_pension", 0))
    pension = _to_int(wage.get("pension_savings", 0))

    expenses = wage.get("expenses", {}) or {}
    medical = _to_int(expenses.get("medical_expense", 0))

    dependents = wage.get("dependents", []) or []

    book_method = str(biz_inputs.get("method", "") or "")

    flat = {
        "income_type": income_type,
        "has_earned_income": gross_salary > 0,
        "has_business_income": business_revenue > 0 or business_income > 0,
        "gross_salary": gross_salary,
        "business_revenue": business_revenue,
        "business_income": business_income,
        "prev_year_business_revenue": prev_revenue,
        "interest_income": interest,
        "dividend_income": dividend,
        "financial_income_total": interest + dividend,
        "monthly_rent": _to_int(flags.get("월세지출_금액", wage.get("monthly_rent", 0))),
        "irp_pension": irp,
        "pension_savings": pension,
        "pension_account_total": irp + pension,
        "medical_expense": medical,
        "dependents_count": len(dependents),
        "book_method": book_method,
        "is_homeless_household": bool(flags.get("무주택세대주", flags.get("월세지출", False))),
        "flags": flags,
        "tax_result": tax_result,
    }
    total = flat["gross_salary"] + flat["business_income"] + flat["financial_income_total"]
    flat["marginal_rate"] = _marginal_rate(total, tax_result)
    return flat


def _from_simple_user_data(ud: dict, tax_result: dict) -> dict:
    income = ud.get("income", {}) if isinstance(ud, dict) else {}
    flags = ud.get("flags", {}) if isinstance(ud, dict) else {}
    gross_salary = _to_int(income.get("근로소득", 0))
    biz_income = _to_int(income.get("사업소득", 0))
    interest = _to_int(income.get("이자소득", 0))
    dividend = _to_int(income.get("배당소득", 0))

    flat = {
        "has_earned_income": gross_salary > 0,
        "has_business_income": biz_income > 0,
        "gross_salary": gross_salary,
        "business_revenue": _to_int(ud.get("business_revenue", 0)),
        "business_income": biz_income,
        "interest_income": interest,
        "dividend_income": dividend,
        "financial_income_total": interest + dividend,
        "monthly_rent": _to_int(ud.get("monthly_rent", 0)),
        "irp_pension": _to_int(ud.get("irp_pension", 0)),
        "pension_savings": _to_int(ud.get("pension_savings", 0)),
        "medical_expense": _to_int(ud.get("medical_expense", 0)),
        "dependents_count": _to_int(ud.get("dependents_total", 0)),
        "book_method": str(ud.get("book_method", "") or ""),
        "is_homeless_household": bool(flags.get("월세지출", False)) or _to_int(ud.get("monthly_rent", 0)) > 0,
        "flags": flags,
        "tax_result": tax_result,
    }
    flat["pension_account_total"] = flat["irp_pension"] + flat["pension_savings"]
    total = flat["gross_salary"] + flat["business_income"] + flat["financial_income_total"]
    flat["marginal_rate"] = _marginal_rate(total, tax_result)
    return flat
