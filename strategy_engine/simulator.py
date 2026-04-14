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
    business_revenue: int = 0,
) -> int:
    """복식부기 전환 시 기장세액공제(산출세액 20%, 상한 100만).
    business_income 누락 시 business_revenue × 0.30 으로 근사.
    """
    bi = int(business_income or 0)
    if bi <= 0:
        bi = int(int(business_revenue or 0) * 0.30)
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
    marginal_rate: float = 0.24,
) -> int:
    """기타소득 300만 이하 분리과세(20%) vs 종합과세.
    marginal_rate 기본 0.24(중간 구간 추정) — 회사원 기준 분리과세가 통상 유리.
    종합과세가 유리한 저소득자에도 정보 제공용 최소 saving 반환.
    """
    n = int(other_income_net or 0)
    if n <= 0:
        return 0
    mr = float(marginal_rate) if marginal_rate else 0.24
    sep_tax = int(n * 0.20)
    comp_tax = int(n * mr)
    saving = comp_tax - sep_tax
    # 종합과세가 유리한 케이스(낮은 소득)도 선택권 안내 목적으로 상징 saving
    return max(saving, max(int(n * 0.01), 1))


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


def corp_company_vehicle_savings(
    expense: int = 0,
    corp_tax_rate: float = 0.19,
) -> int:
    """업무용승용차 연 1,500만 초과분에 대한 손금불산입 익스포저."""
    excess = max(int(expense or 0) - 15_000_000, 0)
    return int(excess * float(corp_tax_rate or 0.19))


def corp_deemed_dividend_withholding(amount: int = 0) -> int:
    """의제배당 원천징수 14% (지방소득세 별도)."""
    return int(max(int(amount or 0), 0) * 0.14)


def corp_rd_tax_credit_savings(
    expense: int = 0,
    is_sme: bool = False,
    is_new_growth: bool = False,
) -> int:
    """R&D 세액공제 (조특 §10).

    보수적 단순화: SME 일반 25% / 중견·대 15% / 신성장 SME 30% / 신성장 중견 20%.
    """
    e = int(expense or 0)
    if e <= 0:
        return 0
    if is_new_growth and is_sme:
        rate = 0.30
    elif is_new_growth:
        rate = 0.20
    elif is_sme:
        rate = 0.25
    else:
        rate = 0.15
    return int(e * rate)


def corp_integrated_investment_credit_savings(
    investment: int = 0,
    is_sme: bool = False,
    tech_type: str = "general",
    prior_3yr_avg: int = 0,
) -> int:
    """통합투자세액공제 (조특 §24).

    tech_type: "general" | "new_growth" | "national_strategic"
    기본공제 + 증가분 3% 추가.
    """
    inv = int(investment or 0)
    if inv <= 0:
        return 0
    tt = str(tech_type or "general").lower()
    if tt == "national_strategic":
        base_rate = 0.25 if is_sme else 0.15
    elif tt == "new_growth":
        base_rate = 0.12 if is_sme else 0.03
    else:
        base_rate = 0.10 if is_sme else 0.01
    base = int(inv * base_rate)
    increment = max(inv - int(prior_3yr_avg or 0), 0)
    extra = int(increment * 0.03)
    return base + extra


def corp_employment_increase_credit_savings(
    youth_increase: int = 0,
    regular_increase: int = 0,
    is_sme: bool = False,
    is_non_metro: bool = False,
) -> int:
    """통합고용세액공제 (조특 §29의8).

    최대 3년 누적 (2년차 동일 + 3년차 50%).
    중소 수도권: 청년 1,450만/일반 850만.
    중소 비수도권: 청년 1,550만/일반 950만.
    중견·대 단순화: 청년 600만/일반 300만.
    """
    y = max(int(youth_increase or 0), 0)
    r = max(int(regular_increase or 0), 0)
    if y + r <= 0:
        return 0
    if is_sme and is_non_metro:
        per_year = y * 15_500_000 + r * 9_500_000
    elif is_sme:
        per_year = y * 14_500_000 + r * 8_500_000
    else:
        per_year = y * 6_000_000 + r * 3_000_000
    # 1년차 + 2년차 + 3년차×0.5 = 2.5× 단년공제
    return int(per_year * 2.5)


def corp_loss_carryback_refund(
    loss: int = 0,
    prior_tax_paid: int = 0,
    prior_taxable_income: int = 0,
) -> int:
    """중소기업 결손금 소급공제 환급세액.

    환급세액 = 직전 납부세액 × min(당기결손 / 직전과세표준, 1.0)
    직전과세표준 정보가 없으면 직전 납부세액 전액으로 보수적 추정.
    """
    loss_i = int(loss or 0)
    prior_tax = int(prior_tax_paid or 0)
    prior_ti = int(prior_taxable_income or 0)
    if loss_i <= 0 or prior_tax <= 0:
        return 0
    ratio = min(loss_i / prior_ti, 1.0) if prior_ti > 0 else 1.0
    return int(prior_tax * ratio)


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


def inh_family_business_deduction_savings(
    asset_value: int = 0,
    operating_years: int = 0,
) -> int:
    """가업상속공제 절세 — 경영기간별 한도 × 상속세 평균세율 40%.

    한도: 10년 이상 300억 / 20년 이상 400억 / 30년 이상 600억.
    """
    v = int(asset_value or 0)
    y = int(operating_years or 0)
    if v <= 0 or y < 10:
        return 0
    if y >= 30:
        cap = 60_000_000_000
    elif y >= 20:
        cap = 40_000_000_000
    else:
        cap = 30_000_000_000
    deductible = min(v, cap)
    return int(deductible * 0.40)


def inh_installment_cashflow_benefit(
    tax_payable: int = 0,
    inheritance_total: int = 0,
) -> int:
    """연부연납 현금흐름 이익 (10년 × 시장금리-가산금 스프레드 3% 가정).
    tax_payable 누락 시 inheritance_total × 0.20 으로 근사.
    """
    t = int(tax_payable or 0)
    if t <= 0:
        t = int(int(inheritance_total or 0) * 0.20)
    if t <= 20_000_000:
        return 0
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


# --- 증여세 v2 확장 (Phase 6) ---------------------------------------------

GIFT_AVG_RATE = 0.20  # 증여세 평균 유효세율 가정 (10~50% 누진의 중간값)


def gift_low_price_transfer_savings(
    market: int = 0,
    actual: int = 0,
) -> int:
    """저가양수 증여이익 = max(0, 차액 − min(시가×30%, 3억)) × 평균세율.

    상증법 §35 ①: 특수관계자 간 시가 대비 30% 또는 3억 이상 저가·고가 거래.
    """
    m = int(market or 0)
    a = int(actual or 0)
    gap = max(m - a, 0)
    threshold = min(int(m * 0.30), 300_000_000)
    gift_value = max(gap - threshold, 0)
    return int(gift_value * GIFT_AVG_RATE)


def gift_free_loan_savings(
    principal: int = 0,
    actual_rate: float = 0.0,
) -> int:
    """금전 무상·저리 대여 연간 증여이익 × 평균세율.

    상증법 §41의4: 1억 초과 대여. 적정이자율 4.6%. 연 1천만 미만 이익은 과세 제외.
    """
    p = int(principal or 0)
    if p <= 100_000_000:
        return 0
    rate_gap = max(0.046 - float(actual_rate or 0.0), 0.0)
    annual_benefit = int(p * rate_gap)
    if annual_benefit < 10_000_000:
        return 0
    return int(annual_benefit * GIFT_AVG_RATE)


def gift_free_real_estate_use_savings(property_value: int = 0) -> int:
    """부동산 무상사용 증여의제 = 부동산가액 × 2% × 3.7908 × 평균세율.

    상증법 §37: 5년간 무상사용이익 현재가치 1억 초과 시 과세.
    """
    pv = int(property_value or 0)
    if pv <= 0:
        return 0
    gift_value = int(pv * 0.02 * 3.7908)
    if gift_value < 100_000_000:
        return 0
    return int(gift_value * GIFT_AVG_RATE)


def gift_family_business_succession_savings(gift_value: int = 0) -> int:
    """가업승계 증여세 과세특례 — 일반 증여세율 대비 절감액.

    일반 누진세율 평균 30% vs 특례 10%(120억 한도) + 20%(600억까지).
    10억 공제 후 계산.
    """
    v = int(gift_value or 0)
    if v <= 0:
        return 0
    taxable = max(v - 1_000_000_000, 0)  # 10억 공제
    if taxable <= 0:
        return 0
    within_cap = min(taxable, 60_000_000_000)  # 600억 한도
    low_band = min(within_cap, 12_000_000_000)  # 120억 10%
    high_band = max(within_cap - 12_000_000_000, 0)
    special_tax = int(low_band * 0.10 + high_band * 0.20)
    normal_tax = int(within_cap * 0.30)  # 일반 증여세 평균
    return max(normal_tax - special_tax, 0)


def gift_insurance_savings(
    proceed: int = 0,
    other_ratio: float | None = None,
) -> int:
    """보험금 증여재산가액 × 평균세율. 보험료 납부자 ≠ 수익자.
    other_ratio None(필드 누락) → 1.0 가정 / 명시적 0.0 → 본인 납부로 skip.
    """
    p = int(proceed or 0)
    if p <= 0:
        return 0
    r = 1.0 if other_ratio is None else float(other_ratio)
    r = max(min(r, 1.0), 0.0)
    if r <= 0:
        return 0
    gift_value = int(p * r)
    return int(gift_value * GIFT_AVG_RATE)


# --- 양도소득 v1 확장 (Phase 7) --------------------------------------------

TRANSFER_AVG_RATE = 0.20  # 양도세 평균 유효세율 가정 (기본세율 6~45% 중간값)


def transfer_basic_savings(
    base: int = 0,
    rate: float = TRANSFER_AVG_RATE,
    fallback_base: int = 0,
    fallback_rate: float = 0.05,
) -> int:
    """양도차익 감소분 × 평균세율. base 누락/0 시 fallback_base × fallback_rate."""
    b = int(base or 0)
    if b <= 0:
        fb = int(fallback_base or 0)
        if fb <= 0:
            return 0
        return int(fb * float(fallback_rate or 0.05))
    return int(b * float(rate or TRANSFER_AVG_RATE))


def _ltcg1_rate(years: int) -> float:
    y = int(years or 0)
    if y < 3:
        return 0.0
    return min(y * 0.02, 0.30)


def transfer_ltcg_table1_savings(
    gain: int = 0,
    current_years: int = 0,
    target_years: int = 15,
) -> int:
    """보유기간 연장으로 얻는 장특공제 표1 추가 공제액 × 평균세율."""
    g = int(gain or 0)
    if g <= 0:
        return 0
    target = max(int(target_years or 15), int(current_years or 0))
    gap = _ltcg1_rate(target) - _ltcg1_rate(current_years)
    return int(g * max(gap, 0.0) * TRANSFER_AVG_RATE)


def _ltcg2_rate(holding_years: int, residence_years: int) -> float:
    h = max(int(holding_years or 0), 0)
    r = max(int(residence_years or 0), 0)
    if h < 3:
        return 0.0
    h_rate = min(h * 0.04, 0.40)
    r_rate = min(r * 0.04, 0.40)
    return min(h_rate + r_rate, 0.80)


def transfer_ltcg_table2_savings(
    gain: int = 0,
    holding_years: int = 0,
    residence_years: int = 0,
) -> int:
    """1세대 1주택 장특공제 표2 — 거주 10년 추가 달성 시 얻는 추가 공제."""
    g = int(gain or 0)
    if g <= 0:
        return 0
    current = _ltcg2_rate(holding_years, residence_years)
    target = _ltcg2_rate(max(int(holding_years or 0), 10), 10)
    gap = max(target - current, 0.0)
    return int(g * gap * TRANSFER_AVG_RATE)


def transfer_high_value_excess_savings(
    gain: int = 0,
    price: int = 0,
    holding_years: int = 0,
    residence_years: int = 0,
) -> int:
    """12억 초과 1세대 1주택 — 과세분 장특공제 표2 극대화로 얻는 절세액."""
    g = int(gain or 0)
    p = int(price or 0)
    if g <= 0 or p <= 1_200_000_000:
        return 0
    taxable = int(g * (p - 1_200_000_000) / p)
    current_rate = _ltcg2_rate(holding_years, residence_years)
    target_rate = _ltcg2_rate(max(int(holding_years or 0), 10), 10)
    gap = max(target_rate - current_rate, 0.0)
    return int(taxable * gap * TRANSFER_AVG_RATE)


def transfer_short_term_savings(
    gain: int = 0,
    current_months: int = 0,
) -> int:
    """단기양도 세율 회피 — 현재 보유기간 기준 단기세율과 기본세율(20%) 차액."""
    g = int(gain or 0)
    if g <= 0:
        return 0
    m = int(current_months or 0)
    if m < 12:
        diff = 0.50
    elif m < 24:
        diff = 0.40
    else:
        return 0
    return int(g * diff)


def transfer_unregistered_savings(gain: int = 0) -> int:
    """미등기 양도 70% → 기본세율 20%. 장특공제 배제 감안으로 50%p 차액."""
    g = int(gain or 0)
    if g <= 0:
        return 0
    return int(g * 0.50)


def transfer_multi_house_savings(
    gain: int = 0,
    surcharge: float = 0.20,
) -> int:
    """다주택 중과 유예기간 활용. 중과 가산율(20~30%p) × 양도차익.
    surcharge 누락/0 시 기본 0.20(조정지역 2주택 가산율) 사용.
    """
    g = int(gain or 0)
    if g <= 0:
        return 0
    s = float(surcharge) if surcharge else 0.20
    s = max(s, 0.0)
    return int(g * s)


def transfer_farmland_savings(gain: int = 0) -> int:
    """8년 자경농지 — 양도세 100% 감면, 1과세기간 1억 한도."""
    g = int(gain or 0)
    if g <= 0:
        return 0
    tax = int(g * TRANSFER_AVG_RATE)
    return min(tax, 100_000_000)


def transfer_expropriation_savings(
    gain: int = 0,
    compensation_type: str = "cash",
) -> int:
    """공익사업 수용 감면. 현금 10% / 3년채 15% / 5년채 30% / 7년채 40%."""
    g = int(gain or 0)
    if g <= 0:
        return 0
    t = str(compensation_type or "cash").lower()
    rate_map = {
        "cash": 0.10,
        "bond_3y": 0.15,
        "bond_5y": 0.30,
        "bond_7y": 0.40,
    }
    reduction_rate = rate_map.get(t, 0.10)
    tax = int(g * TRANSFER_AVG_RATE)
    saved = int(tax * reduction_rate)
    return min(saved, 100_000_000)


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
    "corp_company_vehicle_savings": corp_company_vehicle_savings,
    "corp_deemed_dividend_withholding": corp_deemed_dividend_withholding,
    "corp_loss_carryback_refund": corp_loss_carryback_refund,
    "corp_rd_tax_credit_savings": corp_rd_tax_credit_savings,
    "corp_integrated_investment_credit_savings": corp_integrated_investment_credit_savings,
    "corp_employment_increase_credit_savings": corp_employment_increase_credit_savings,
    "inh_spouse_deduction_savings": inh_spouse_deduction_savings,
    "inh_installment_cashflow_benefit": inh_installment_cashflow_benefit,
    "inh_family_business_deduction_savings": inh_family_business_deduction_savings,
    "gift_family_business_succession_savings": gift_family_business_succession_savings,
    "gift_split_savings": gift_split_savings,
    "gift_low_valuation_savings": gift_low_valuation_savings,
    "gift_low_price_transfer_savings": gift_low_price_transfer_savings,
    "gift_free_loan_savings": gift_free_loan_savings,
    "gift_free_real_estate_use_savings": gift_free_real_estate_use_savings,
    "gift_insurance_savings": gift_insurance_savings,
    "transfer_basic_savings": transfer_basic_savings,
    "transfer_ltcg_table1_savings": transfer_ltcg_table1_savings,
    "transfer_ltcg_table2_savings": transfer_ltcg_table2_savings,
    "transfer_high_value_excess_savings": transfer_high_value_excess_savings,
    "transfer_short_term_savings": transfer_short_term_savings,
    "transfer_unregistered_savings": transfer_unregistered_savings,
    "transfer_multi_house_savings": transfer_multi_house_savings,
    "transfer_farmland_savings": transfer_farmland_savings,
    "transfer_expropriation_savings": transfer_expropriation_savings,
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
