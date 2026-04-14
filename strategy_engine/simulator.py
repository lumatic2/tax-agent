"""전략 절세액 추정기.

규칙 YAML의 `estimator` 섹션을 받아 절세액(원)을 계산한다.
estimator.type:
- `formula`: 명명된 순수 함수 호출. 금액 추정에 사용
- `fixed`:  상수 추정치 반환 (스텁용)
- `simulate`: tax_calculator 함수 직접 호출로 baseline vs alternative 세액 비교 (v1에서 확장)
"""

from __future__ import annotations

import tax_calculator


def _resolve_param(value, profile: dict):
    if isinstance(value, str) and value.startswith("profile."):
        parts = value.split(".")[1:]
        cur = profile
        for key in parts:
            if isinstance(cur, dict):
                cur = cur.get(key)
            else:
                return None
        return cur
    return value


def _resolve_params(params: dict, profile: dict) -> dict:
    """`*_ref` 접미사 필드를 profile에서 해석, 그 외는 리터럴."""
    resolved = {}
    for k, v in (params or {}).items():
        key = k[:-4] if k.endswith("_ref") else k
        resolved[key] = _resolve_param(v, profile) if k.endswith("_ref") else v
    return resolved


def _pension_credit_rate(gross_salary: int) -> float:
    return 0.165 if (gross_salary or 0) <= 55_000_000 else 0.132


def _rent_credit_rate(gross_salary: int) -> float:
    return 0.17 if (gross_salary or 0) <= 55_000_000 else 0.15


# --- Named formulas -----------------------------------------------------------

def financial_separation_savings(
    interest: int = 0,
    dividend: int = 0,
    marginal_rate: float = 0.15,
) -> int:
    """분리과세 14% 유지 vs 종합과세 합산의 절세액.

    합산 시 한계세율 적용 - 14% 원천징수를 비교. 한계세율 <= 14%면 절세액 0.
    """
    fin = int((interest or 0) + (dividend or 0))
    if fin <= 0:
        return 0
    comprehensive = int(fin * float(marginal_rate or 0.15))
    separation = int(fin * 0.14)
    return max(comprehensive - separation, 0)


def double_entry_savings(
    business_income: int = 0,
    marginal_rate: float = 0.15,
) -> int:
    """복식부기 전환 시 기장세액공제(산출세액 20%, 상한 100만)."""
    bi = int(business_income or 0)
    if bi <= 0:
        return 0
    approx_tax = tax_calculator.calculate_tax(bi)
    income_tax = int(approx_tax.get("산출세액", 0) or 0)
    credit = min(int(income_tax * 0.20), 1_000_000)
    return max(credit, 0)


def monthly_rent_credit_savings(
    monthly_rent: int = 0,
    gross_salary: int = 0,
) -> int:
    """월세 세액공제. 연 1,000만 한도 × 15~17%."""
    annual = int((monthly_rent or 0) * 12)
    claimable = min(annual, 10_000_000)
    rate = _rent_credit_rate(gross_salary)
    return int(claimable * rate)


def pension_account_savings(
    pension_account_total: int = 0,
    gross_salary: int = 0,
) -> int:
    """연금계좌 한도 미소진분 × 세액공제율."""
    remaining = max(9_000_000 - int(pension_account_total or 0), 0)
    rate = _pension_credit_rate(gross_salary)
    return int(remaining * rate)


def medical_expense_timing_savings(
    medical_expense: int = 0,
    gross_salary: int = 0,
) -> int:
    """의료비 몰아주기로 3% 문턱 낮아질 때 추가 공제.

    보수적 추정: 저소득 배우자(총급여의 절반 가정) 기준 문턱 감소분 × 15%.
    """
    me = int(medical_expense or 0)
    gs = int(gross_salary or 0)
    if me <= 0 or gs <= 0:
        return 0
    threshold_now = int(gs * 0.03)
    threshold_spouse = int((gs / 2) * 0.03)
    extra_base = max(threshold_now - threshold_spouse, 0)
    extra_base = min(extra_base, max(me - threshold_spouse, 0))
    return int(extra_base * 0.15)


def corp_rate_exposure(
    base_amount: int = 0,
    corp_tax_rate: float = 0.19,
) -> int:
    """법인세 추징 예상액 = 부인될 손금 × 법인세율.

    리스크 규칙(부당행위·임원상여 한도초과 등)이 자진 시정 시 회피 가능한
    추징 세액을 "절세액"으로 표현하기 위한 보수적 공식.
    """
    base = int(base_amount or 0)
    if base <= 0:
        return 0
    return int(base * float(corp_tax_rate or 0.19))


# --- 소득세 v1 확장 --------------------------------------------------------

def children_credit_savings(count: int = 0) -> int:
    """자녀 세액공제: 1명 15만, 2명 35만, 3명 이상 35만+1명당 30만."""
    n = int(count or 0)
    if n <= 0:
        return 0
    if n == 1:
        return 150_000
    if n == 2:
        return 350_000
    return 350_000 + (n - 2) * 300_000


def education_credit_savings(expense: int = 0) -> int:
    """교육비 세액공제 15%. 한도 단순화(실무 한도는 부양가족 유형별)."""
    return int(max(int(expense or 0), 0) * 0.15)


def donation_credit_savings(amount: int = 0) -> int:
    """기부금 세액공제: 1천만 이하 15%, 초과분 30%."""
    a = int(amount or 0)
    if a <= 0:
        return 0
    if a <= 10_000_000:
        return int(a * 0.15)
    return int(10_000_000 * 0.15 + (a - 10_000_000) * 0.30)


def credit_card_deduction_savings(
    gross_salary: int = 0,
    card_usage_total: int = 0,
    traditional_market: int = 0,
    public_transit: int = 0,
    marginal_rate: float = 0.15,
) -> int:
    """신용카드 소득공제 한도 내 절세액 ≈ 공제가능액 × 한계세율."""
    gs = int(gross_salary or 0)
    total = int(card_usage_total or 0)
    threshold = int(gs * 0.25)
    excess = max(total - threshold, 0)
    if excess <= 0:
        return 0
    # 보수적 가정: 전체 초과분을 신용카드(15%)로 간주, 전통시장·대중교통 40% 가산
    base = int(excess * 0.15)
    extra = int((int(traditional_market or 0) + int(public_transit or 0)) * 0.25)
    deduction = min(base + extra, 3_000_000)
    return int(deduction * float(marginal_rate or 0.15))


def sme_employment_reduction_savings(
    worker_type: str = "general",
    years_employed: float = 0.0,
    gross_salary: int = 0,
) -> int:
    """중소기업취업자 감면. 청년 90%/일반 70% 가정한 보수적 추정."""
    ratio = 0.90 if str(worker_type or "").lower() in ("youth", "청년") else 0.70
    years = float(years_employed or 0)
    if years > 5.0:
        return 0
    # 대략적인 산출세액 추정: 총급여 × 0.1 → 감면액
    approx_tax = int(int(gross_salary or 0) * 0.1)
    cap = 2_000_000
    return min(int(approx_tax * ratio), cap)


def yellow_umbrella_savings(paid: int = 0, marginal_rate: float = 0.15) -> int:
    """노란우산 추가 납입 가능액 × 한계세율 (한도 500만 가정)."""
    remaining = max(5_000_000 - int(paid or 0), 0)
    return int(remaining * float(marginal_rate or 0.15))


def housing_rental_separation_savings(
    rental_income: int = 0,
    marginal_rate: float = 0.15,
    is_registered: bool = False,
) -> int:
    """주택임대 분리과세 vs 종합과세 차액."""
    ri = int(rental_income or 0)
    if ri <= 0:
        return 0
    expense_ratio = 0.60 if is_registered else 0.50
    basic_deduction = 4_000_000 if is_registered else 2_000_000
    sep_base = max(int(ri * (1 - expense_ratio)) - basic_deduction, 0)
    sep_tax = int(sep_base * 0.14)
    comp_tax = int(ri * float(marginal_rate or 0.15))
    return max(comp_tax - sep_tax, 0)


def other_income_separation_savings(
    other_income_net: int = 0,
    marginal_rate: float = 0.15,
) -> int:
    """기타소득 300만 이하 분리과세(20%) vs 종합과세."""
    n = int(other_income_net or 0)
    if n <= 0:
        return 0
    sep_tax = int(n * 0.20)
    comp_tax = int(n * float(marginal_rate or 0.15))
    return max(comp_tax - sep_tax, 0)


# --- 법인세 v1 확장 --------------------------------------------------------

def corp_loss_carryforward_savings(
    available: int = 0,
    taxable_income: int = 0,
    is_sme: bool = False,
    corp_tax_rate: float = 0.19,
) -> int:
    """이월결손금 공제 가능액 × 법인세율."""
    cap_ratio = 1.0 if is_sme else 0.80
    usable = min(int(available or 0), int(int(taxable_income or 0) * cap_ratio))
    if usable <= 0:
        return 0
    return int(usable * float(corp_tax_rate or 0.19))


# --- 상속세 v1 확장 --------------------------------------------------------

def inh_spouse_deduction_savings(
    total: int = 0,
    spouse_share: int = 0,
    spouse_legal_share: int = 0,
) -> int:
    """배우자 공제 극대화: 현 상속가액을 법정상속분 한도까지 끌어올릴 때 추가공제 × 20%(평균 상속세율 가정)."""
    max_deduction = min(int(spouse_legal_share or 0), 3_000_000_000)
    current = int(spouse_share or 0)
    additional = max(max_deduction - current, 0)
    return int(additional * 0.20)


def inh_installment_cashflow_benefit(tax_payable: int = 0) -> int:
    """연부연납 현금흐름 이익 (10년 × 시장금리-가산금 스프레드 3% 가정)."""
    t = int(tax_payable or 0)
    if t <= 20_000_000:
        return 0
    # 절반 평균잔액 × 3% × 10년 ≈ 15%
    return int(t * 0.15)


# --- 증여세 v1 확장 --------------------------------------------------------

def gift_split_savings(
    planned_amount: int = 0,
    prior_amount: int = 0,
    exemption: int = 0,
) -> int:
    """10년 합산 초과분을 분할로 회피 시 증여세율(10~50%) 평균 20% 가정."""
    total = int(planned_amount or 0) + int(prior_amount or 0)
    excess = max(total - int(exemption or 0), 0)
    return int(excess * 0.20)


def gift_low_valuation_savings(
    fair_price: int = 0,
    expected_price: int = 0,
) -> int:
    """저평가 시점 증여 시 평가차익에 대한 증여세 회피분 (평균 20%)."""
    diff = max(int(expected_price or 0) - int(fair_price or 0), 0)
    return int(diff * 0.20)


FORMULAS = {
    "financial_separation_savings": financial_separation_savings,
    "double_entry_savings": double_entry_savings,
    "monthly_rent_credit_savings": monthly_rent_credit_savings,
    "pension_account_savings": pension_account_savings,
    "medical_expense_timing_savings": medical_expense_timing_savings,
    "corp_rate_exposure": corp_rate_exposure,
    "children_credit_savings": children_credit_savings,
    "education_credit_savings": education_credit_savings,
    "donation_credit_savings": donation_credit_savings,
    "credit_card_deduction_savings": credit_card_deduction_savings,
    "sme_employment_reduction_savings": sme_employment_reduction_savings,
    "yellow_umbrella_savings": yellow_umbrella_savings,
    "housing_rental_separation_savings": housing_rental_separation_savings,
    "other_income_separation_savings": other_income_separation_savings,
    "corp_loss_carryforward_savings": corp_loss_carryforward_savings,
    "inh_spouse_deduction_savings": inh_spouse_deduction_savings,
    "inh_installment_cashflow_benefit": inh_installment_cashflow_benefit,
    "gift_split_savings": gift_split_savings,
    "gift_low_valuation_savings": gift_low_valuation_savings,
}


def estimate(estimator: dict, profile: dict) -> int:
    if not estimator:
        return 0
    etype = estimator.get("type")
    if etype == "fixed":
        return int(estimator.get("amount", 0) or 0)
    if etype == "formula":
        name = estimator.get("name")
        fn = FORMULAS.get(name)
        if fn is None:
            return 0
        kwargs = _resolve_params(estimator.get("params") or {}, profile)
        try:
            return int(fn(**kwargs) or 0)
        except TypeError:
            return 0
    if etype == "simulate":
        return 0
    return 0
