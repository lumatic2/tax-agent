"""법인세 계산 엔진 — 법인세법 기준

Phase 4: Ch10(세율·과세표준) → Ch02~04(세무조정) → Ch07~08(감가상각·충당금)
         → Ch09,11~14(부당행위·세액공제·최저한세·신고납부)
"""

from typing import Optional


# ══════════════════════════════════════════════
# 공통: 세율표 (§55, 2023.1.1. 이후 개시 사업연도)
# ══════════════════════════════════════════════

CORPORATE_TAX_BRACKETS = [
    # (과세표준 상한, 세율, 누진공제)
    (200_000_000,         0.09, 0),
    (20_000_000_000,      0.19, 20_000_000),
    (300_000_000_000,     0.21, 420_000_000),
    (float('inf'),        0.24, 9_420_000_000),
]


# ══════════════════════════════════════════════
# Ch10. 과세표준·세율
# ══════════════════════════════════════════════

def apply_corporate_tax_rate(*, taxable_base: int) -> dict:
    """법인세 세율 적용 (§55).

    과세표준에 누진세율 적용하여 산출세액 계산.
    2억 이하 9%, 200억 이하 19%, 3,000억 이하 21%, 3,000억 초과 24%.

    Args:
        taxable_base: 과세표준 (원)

    Returns:
        dict: {과세표준, 적용세율, 누진공제, 산출세액}
    """
    if taxable_base <= 0:
        return {
            '과세표준': 0,
            '적용세율': 0,
            '누진공제': 0,
            '산출세액': 0,
        }

    for upper, rate, progressive in CORPORATE_TAX_BRACKETS:
        if taxable_base <= upper:
            tax = int(taxable_base * rate) - progressive
            return {
                '과세표준': taxable_base,
                '적용세율': rate,
                '누진공제': progressive,
                '산출세액': max(tax, 0),
            }

    # fallback (should not reach)
    rate = 0.24
    progressive = 9_420_000_000
    tax = int(taxable_base * rate) - progressive
    return {
        '과세표준': taxable_base,
        '적용세율': rate,
        '누진공제': progressive,
        '산출세액': max(tax, 0),
    }


def calculate_loss_carryforward(
    *,
    income_before_loss: int,
    carried_losses: list[dict],
    is_sme: bool = False,
) -> dict:
    """이월결손금 공제 (§13①1).

    각 사업연도 소득에서 이월결손금을 차감. 15년 이내 결손금만 공제 가능.
    - 일반법인: 소득의 80% 한도
    - 중소기업·회생법인: 소득의 100% 한도

    Args:
        income_before_loss: 이월결손금 공제 전 각사업연도소득
        carried_losses: [{사업연도, 결손금, 경과연수}] — 발생순 정렬
        is_sme: 중소기업 여부 (True면 100% 한도)

    Returns:
        dict: {공제전소득, 공제한도, 이월결손금공제, 공제후소득, 공제내역, 미공제잔액}
    """
    if income_before_loss <= 0 or not carried_losses:
        return {
            '공제전소득': income_before_loss,
            '공제한도': 0,
            '이월결손금공제': 0,
            '공제후소득': income_before_loss,
            '공제내역': [],
            '미공제잔액': sum(l.get('결손금', 0) for l in carried_losses),
        }

    limit_ratio = 1.0 if is_sme else 0.8
    deduction_limit = int(income_before_loss * limit_ratio)

    total_deducted = 0
    details = []
    remaining_losses = []

    for loss in carried_losses:
        years_elapsed = loss.get('경과연수', 0)
        loss_amount = loss.get('결손금', 0)
        biz_year = loss.get('사업연도', '')

        # 15년 초과 결손금은 공제 불가
        if years_elapsed > 15:
            remaining_losses.append({'사업연도': biz_year, '결손금': loss_amount, '사유': '15년 초과'})
            continue

        available = min(loss_amount, deduction_limit - total_deducted)
        if available <= 0:
            remaining_losses.append({'사업연도': biz_year, '결손금': loss_amount, '사유': '한도 소진'})
            continue

        total_deducted += available
        details.append({
            '사업연도': biz_year,
            '결손금': loss_amount,
            '공제액': available,
        })

        leftover = loss_amount - available
        if leftover > 0:
            remaining_losses.append({'사업연도': biz_year, '결손금': leftover, '사유': '한도 소진'})

    return {
        '공제전소득': income_before_loss,
        '공제한도': deduction_limit,
        '이월결손금공제': total_deducted,
        '공제후소득': income_before_loss - total_deducted,
        '공제내역': details,
        '미공제잔액': sum(r['결손금'] for r in remaining_losses),
    }


def calculate_corporate_tax_base(
    *,
    income_per_year: int,
    carried_losses: list[dict] | None = None,
    is_sme: bool = False,
    nontaxable_income: int = 0,
    income_deductions: int = 0,
) -> dict:
    """과세표준 계산 (§13).

    과세표준 = 각사업연도소득 - 이월결손금 - 비과세소득 - 소득공제액

    Args:
        income_per_year: 각사업연도소득
        carried_losses: [{사업연도, 결손금, 경과연수}]
        is_sme: 중소기업 여부
        nontaxable_income: 비과세소득
        income_deductions: 소득공제액

    Returns:
        dict: {각사업연도소득, 이월결손금공제, 비과세소득, 소득공제, 과세표준, 이월결손금내역}
    """
    # Step 1: 이월결손금 공제
    if carried_losses:
        loss_result = calculate_loss_carryforward(
            income_before_loss=income_per_year,
            carried_losses=carried_losses,
            is_sme=is_sme,
        )
        loss_deducted = loss_result['이월결손금공제']
        loss_details = loss_result
    else:
        loss_deducted = 0
        loss_details = None

    after_loss = income_per_year - loss_deducted

    # Step 2: 비과세소득 차감
    nontax = min(nontaxable_income, after_loss)
    after_nontax = after_loss - nontax

    # Step 3: 소득공제 차감
    deduction = min(income_deductions, after_nontax)
    taxable_base = after_nontax - deduction

    return {
        '각사업연도소득': income_per_year,
        '이월결손금공제': loss_deducted,
        '비과세소득': nontax,
        '소득공제': deduction,
        '과세표준': max(taxable_base, 0),
        '이월결손금내역': loss_details,
    }


def calculate_corporate_tax(
    *,
    income_per_year: int,
    carried_losses: list[dict] | None = None,
    is_sme: bool = False,
    nontaxable_income: int = 0,
    income_deductions: int = 0,
    tax_credits: int = 0,
    prepaid_tax: int = 0,
) -> dict:
    """법인세 종합계산 (§55, §13).

    각사업연도소득 → 과세표준 → 세율 → 산출세액 → 공제 → 납부세액

    Args:
        income_per_year: 각사업연도소득
        carried_losses: [{사업연도, 결손금, 경과연수}]
        is_sme: 중소기업 여부
        nontaxable_income: 비과세소득
        income_deductions: 소득공제액
        tax_credits: 세액공제·감면 합계
        prepaid_tax: 기납부세액 (중간예납 + 원천징수)

    Returns:
        dict: {각사업연도소득, 과세표준, 산출세액, 세액공제감면,
               결정세액, 기납부세액, 납부할세액, 과세표준내역, 세율내역}
    """
    # Step 1: 과세표준
    base_result = calculate_corporate_tax_base(
        income_per_year=income_per_year,
        carried_losses=carried_losses,
        is_sme=is_sme,
        nontaxable_income=nontaxable_income,
        income_deductions=income_deductions,
    )
    taxable_base = base_result['과세표준']

    # Step 2: 세율 적용
    rate_result = apply_corporate_tax_rate(taxable_base=taxable_base)
    computed_tax = rate_result['산출세액']

    # Step 3: 세액공제·감면
    credits = min(tax_credits, computed_tax)
    determined_tax = computed_tax - credits

    # Step 4: 기납부세액 차감
    tax_due = determined_tax - prepaid_tax

    return {
        '각사업연도소득': income_per_year,
        '과세표준': taxable_base,
        '산출세액': computed_tax,
        '세액공제감면': credits,
        '결정세액': determined_tax,
        '기납부세액': prepaid_tax,
        '납부할세액': tax_due,
        '과세표준내역': base_result,
        '세율내역': rate_result,
    }


# ══════════════════════════════════════════════
# Ch02. 세무조정 — 각사업연도소득
# ══════════════════════════════════════════════

def calculate_taxable_income(
    *,
    accounting_profit: int,
    additions: list[dict] | None = None,
    deductions: list[dict] | None = None,
) -> dict:
    """각사업연도소득 계산 (§14).

    각사업연도소득 = 회계이익 + 익금산입/손금불산입 - 손금산입/익금불산입

    세무조정 항목은 각각 {항목, 금액, 소득처분} 구조.
    소득처분: '유보', '사외유출', '기타', '△유보'

    Args:
        accounting_profit: 기업회계 당기순이익
        additions: 익금산입·손금불산입 목록 [{항목, 금액, 소득처분}]
        deductions: 손금산입·익금불산입 목록 [{항목, 금액, 소득처분}]

    Returns:
        dict: {당기순이익, 익금산입손금불산입, 손금산입익금불산입, 각사업연도소득, 세무조정내역}
    """
    adds = additions or []
    deds = deductions or []

    total_add = sum(a.get('금액', 0) for a in adds)
    total_ded = sum(d.get('금액', 0) for d in deds)

    taxable_income = accounting_profit + total_add - total_ded

    return {
        '당기순이익': accounting_profit,
        '익금산입손금불산입': total_add,
        '손금산입익금불산입': total_ded,
        '각사업연도소득': taxable_income,
        '세무조정내역': {
            '가산': adds,
            '차감': deds,
        },
    }


# ══════════════════════════════════════════════
# Ch03. 익금·익금불산입
# ══════════════════════════════════════════════

# 수입배당금 익금불산입률 (§18의2, 2023.1.1 이후, 일반법인 기준)
DIVIDEND_EXCLUSION_RATES = {
    # (지분율 하한, 익금불산입률)
    '완전자회사': (1.00, 1.00),   # 지분 100%
    '자회사':     (0.50, 1.00),   # 지분 50% 이상
    '관계기업':   (0.20, 0.80),   # 지분 20% 이상 50% 미만
    '기타법인':   (0.00, 0.30),   # 지분 20% 미만
}


def calculate_dividend_received_deduction(
    *,
    dividend_income: int,
    ownership_ratio: float,
    borrowing_interest_adjustment: int = 0,
) -> dict:
    """수입배당금 익금불산입 (§18의2).

    내국법인이 피출자법인에서 받은 배당금에 대해 지분율별 익금불산입.
    - 지분 100%: 100% 익금불산입
    - 지분 50% 이상: 100%
    - 지분 20% 이상: 80%
    - 지분 20% 미만: 30%

    차입금 이자 차감액 반영 가능 (§18의2①2호).

    Args:
        dividend_income: 수입배당금액
        ownership_ratio: 출자비율 (0.0~1.0)
        borrowing_interest_adjustment: 차입금 이자 차감액 (기본 0)

    Returns:
        dict: {수입배당금, 지분율, 익금불산입률, 익금불산입액, 차입금이자차감, 최종익금불산입}
    """
    ratio = max(0.0, min(1.0, ownership_ratio))

    if ratio >= 1.0:
        exclusion_rate = 1.00
        tier = '완전자회사'
    elif ratio >= 0.50:
        exclusion_rate = 1.00
        tier = '자회사'
    elif ratio >= 0.20:
        exclusion_rate = 0.80
        tier = '관계기업'
    else:
        exclusion_rate = 0.30
        tier = '기타법인'

    gross_exclusion = int(dividend_income * exclusion_rate)
    net_exclusion = max(gross_exclusion - borrowing_interest_adjustment, 0)

    return {
        '수입배당금': dividend_income,
        '지분율': ratio,
        '구분': tier,
        '익금불산입률': exclusion_rate,
        '익금불산입액': gross_exclusion,
        '차입금이자차감': borrowing_interest_adjustment,
        '최종익금불산입': net_exclusion,
    }


# ══════════════════════════════════════════════
# Ch04. 손금·손금불산입
# ══════════════════════════════════════════════

def calculate_entertainment_expense_limit_corp(
    *,
    revenue: int,
    actual_entertainment: int = 0,
    is_sme: bool = False,
    months: int = 12,
) -> dict:
    """기업업무추진비(접대비) 한도 (§25, 영§42).

    한도 = 기본한도 + 수입금액별 한도
    - 기본한도: 중소기업 3,600만 / 일반 1,200만 (연 기준, 월할)
    - 수입금액별:
      100억 이하: × 0.3% (3/1,000)
      100억 초과 500억 이하: × 0.2%
      500억 초과: × 0.03%

    Args:
        revenue: 수입금액 (매출액)
        actual_entertainment: 실지출 기업업무추진비
        is_sme: 중소기업 여부
        months: 사업연도 월수 (기본 12)

    Returns:
        dict: {기본한도, 수입금액한도, 총한도, 실지출액, 손금산입액, 손금불산입액}
    """
    months = max(1, min(12, months))
    rev = int(revenue)
    actual = int(actual_entertainment)

    base_annual = 36_000_000 if is_sme else 12_000_000
    base_limit = int(base_annual * months / 12)

    # 수입금액별 한도 (누적 구간)
    if rev <= 10_000_000_000:
        rev_limit = int(rev * 0.003)
    elif rev <= 50_000_000_000:
        rev_limit = 30_000_000 + int((rev - 10_000_000_000) * 0.002)
    else:
        rev_limit = 110_000_000 + int((rev - 50_000_000_000) * 0.0003)

    total_limit = base_limit + rev_limit
    deductible = min(actual, total_limit)
    excess = max(actual - total_limit, 0)

    return {
        '기본한도': base_limit,
        '수입금액한도': rev_limit,
        '총한도': total_limit,
        '실지출액': actual,
        '손금산입액': deductible,
        '손금불산입액': excess,
    }


def calculate_donation_limit(
    *,
    income_before_donation: int,
    statutory_donations: int = 0,
    designated_donations: int = 0,
    is_sme: bool = False,
) -> dict:
    """기부금 한도 (§24).

    특례기부금(법정): 소득금액의 50% 한도 (§24②)
    일반기부금(지정): (소득금액 - 특례기부금 손금산입액)의 10% 한도 (§24③)

    Args:
        income_before_donation: 기부금 한도 계산 기준소득 (각사업연도소득)
        statutory_donations: 특례기부금(법정기부금) 지출액
        designated_donations: 일반기부금(지정기부금) 지출액
        is_sme: 중소기업 여부 (현재 한도율 동일)

    Returns:
        dict: {기준소득, 특례기부금, 일반기부금, 특례한도, 일반한도,
               특례손금산입, 특례손금불산입, 일반손금산입, 일반손금불산입}
    """
    income = max(income_before_donation, 0)

    # Step 1: 특례기부금 (법정) — 소득의 50%
    stat_limit = int(income * 0.50)
    stat_deductible = min(statutory_donations, stat_limit)
    stat_excess = max(statutory_donations - stat_limit, 0)

    # Step 2: 일반기부금 (지정) — (소득 - 특례 손금산입)의 10%
    income_after_stat = income - stat_deductible
    desig_limit = int(income_after_stat * 0.10)
    desig_deductible = min(designated_donations, desig_limit)
    desig_excess = max(designated_donations - desig_limit, 0)

    return {
        '기준소득': income,
        '특례기부금': statutory_donations,
        '일반기부금': designated_donations,
        '특례한도': stat_limit,
        '일반한도': desig_limit,
        '특례손금산입': stat_deductible,
        '특례손금불산입': stat_excess,
        '일반손금산입': desig_deductible,
        '일반손금불산입': desig_excess,
    }


# 손금불산입 열거 항목 (§21)
NON_DEDUCTIBLE_ITEMS = {
    '법인세',
    '법인지방소득세',
    '가산세',
    '벌금',
    '과료',
    '과태료',
    '과징금',
    '가산금',
    '강제징수비',
    '체납처분비',
    '뇌물',
    '의무외공과금',       # 법령에 의하지 않는 공과금
    '의무위반공과금',     # 법령 의무위반으로 부과된 공과금
    '부가가치세매입세액',  # 원칙 (면세·불공제 제외)
}


def check_non_deductible_expenses(
    *,
    items: list[dict],
) -> dict:
    """손금불산입 항목 판정 (§21).

    벌금·과료·과태료·가산금·법인세 등 열거 항목을 판정.

    Args:
        items: [{유형, 금액}] 목록

    Returns:
        dict: {판정결과: [{유형, 금액, 손금불산입여부, 소득처분}], 총손금불산입액}
    """
    results = []
    total_non_deductible = 0

    for item in items:
        item_type = item.get('유형', '')
        amount = item.get('금액', 0)

        if item_type in NON_DEDUCTIBLE_ITEMS:
            results.append({
                '유형': item_type,
                '금액': amount,
                '손금불산입여부': True,
                '소득처분': '기타사외유출',
            })
            total_non_deductible += amount
        else:
            results.append({
                '유형': item_type,
                '금액': amount,
                '손금불산입여부': False,
                '소득처분': '-',
            })

    return {
        '판정결과': results,
        '총손금불산입액': total_non_deductible,
    }


# ══════════════════════════════════════════════
# Ch07. 감가상각비
# ══════════════════════════════════════════════

# 정률법 상각률 테이블 (시행령 별표, 주요 내용연수)
# 공식: 상각률 = 1 - (잔존가액/취득가액)^(1/내용연수)
# 잔존가액 = 취득가액의 5% (영§26②)
DECLINING_BALANCE_RATES = {
    2:  0.5279,
    3:  0.3945,
    4:  0.3133,
    5:  0.2592,
    6:  0.2207,
    8:  0.1706,
    10: 0.1389,
    12: 0.1173,
    15: 0.0952,
    20: 0.0724,
    25: 0.0586,
    30: 0.0492,
    40: 0.0373,
    50: 0.0300,
    60: 0.0251,
}


def get_declining_balance_rate(*, useful_life: int) -> float:
    """정률법 상각률 조회 (시행령 별표).

    Args:
        useful_life: 내용연수

    Returns:
        float: 상각률 (테이블에 없으면 1-(0.05)^(1/n) 계산)
    """
    if useful_life in DECLINING_BALANCE_RATES:
        return DECLINING_BALANCE_RATES[useful_life]
    # 테이블에 없는 경우 직접 계산
    return round(1 - (0.05 ** (1 / useful_life)), 4)


# 법정내용연수 (시행규칙 별표5/6, 주요 자산)
STATUTORY_USEFUL_LIFE = {
    '건물': {'철근콘크리트': 40, '철골철근콘크리트': 40, '연와조': 30, '목조': 20, '기타': 20},
    '구축물': {'기타': 20},
    '기계장치': {'기타': 8},
    '차량운반구': {'기타': 5},
    '공구기구비품': {'기타': 5},
    '선박': {'기타': 12},
    '항공기': {'기타': 12},
    '소프트웨어': {'기타': 5},
    '영업권': {'기타': 5},
    '특허권': {'기타': 10},
    '광업권': {'기타': 20},
}


def get_statutory_useful_life(
    *,
    asset_type: str,
    structure_type: str = '기타',
) -> dict:
    """법정내용연수 조회 (시행규칙 별표5/6).

    Args:
        asset_type: 자산유형 ('건물', '기계장치', '차량운반구', ...)
        structure_type: 구조유형 (건물의 경우 '철근콘크리트' 등, 기본 '기타')

    Returns:
        dict: {자산유형, 구조유형, 내용연수}
    """
    if asset_type not in STATUTORY_USEFUL_LIFE:
        return {
            '자산유형': asset_type,
            '구조유형': structure_type,
            '내용연수': None,
            '비고': '미등록 자산유형',
        }

    life_map = STATUTORY_USEFUL_LIFE[asset_type]
    life = life_map.get(structure_type, life_map.get('기타'))

    return {
        '자산유형': asset_type,
        '구조유형': structure_type,
        '내용연수': life,
    }


def calculate_depreciation_limit(
    *,
    acquisition_cost: int,
    useful_life: int,
    method: str = '정액법',
    current_year: int = 1,
    prior_accumulated: int = 0,
    company_recorded: int = 0,
    residual_value: int = 0,
    months: int = 12,
) -> dict:
    """감가상각비 시부인 계산 (§23, 영§26).

    상각범위액 vs 회사계상액 비교.
    - 회사계상액 ≤ 상각범위액: 전액 손금산입
    - 회사계상액 > 상각범위액: 초과액 손금불산입(유보)

    정액법: (취득가 - 잔존가) / 내용연수 × (월수/12)
    정률법: 미상각잔액 × 상각률 × (월수/12)

    Args:
        acquisition_cost: 취득가액
        useful_life: 내용연수
        method: '정액법' | '정률법'
        current_year: 당기 연차 (1부터)
        prior_accumulated: 전기까지 누적상각액 (세무상 인정액)
        company_recorded: 회사 계상 감가상각비
        residual_value: 잔존가액 (정액법, 기본 0)
        months: 사업연도 월수 (기본 12)

    Returns:
        dict: {취득가액, 내용연수, 상각방법, 상각범위액, 회사계상액,
               손금산입액, 손금불산입액, 누적상각액}
    """
    months = max(1, min(12, months))
    month_ratio = months / 12

    if method == '정액법':
        annual_limit = int((acquisition_cost - residual_value) / useful_life)
        depreciation_limit = int(annual_limit * month_ratio)
    elif method == '정률법':
        rate = get_declining_balance_rate(useful_life=useful_life)
        book_value = acquisition_cost - prior_accumulated
        if book_value <= 0:
            depreciation_limit = 0
        else:
            depreciation_limit = int(book_value * rate * month_ratio)
    else:
        depreciation_limit = 0

    # 미상각잔액 체크: 상각범위액이 미상각잔액 초과하면 미상각잔액까지만
    remaining = acquisition_cost - prior_accumulated
    depreciation_limit = min(depreciation_limit, max(remaining, 0))

    # 시부인
    deductible = min(company_recorded, depreciation_limit)
    excess = max(company_recorded - depreciation_limit, 0)

    return {
        '취득가액': acquisition_cost,
        '내용연수': useful_life,
        '상각방법': method,
        '상각범위액': depreciation_limit,
        '회사계상액': company_recorded,
        '손금산입액': deductible,
        '손금불산입액': excess,
        '소득처분': '유보' if excess > 0 else '-',
        '누적상각액': prior_accumulated + deductible,
    }


# ══════════════════════════════════════════════
# Ch08. 충당금·준비금
# ══════════════════════════════════════════════

def calculate_retirement_allowance_reserve(
    *,
    total_estimated_retirement: int,
    prior_reserve_balance: int = 0,
    actual_payments: int = 0,
    company_booked: int = 0,
) -> dict:
    """퇴직급여충당금 한도 (§33, 영§60).

    한도 = 총추계액(전 임직원 퇴직 시 예상 지급액) - 전기잔액 + 당기지급액
    실무: 기말 총추계액이 한도.

    Args:
        total_estimated_retirement: 기말 퇴직급여 총추계액
        prior_reserve_balance: 전기말 충당금 잔액
        actual_payments: 당기 실제 퇴직금 지급액
        company_booked: 당기 회사 계상 퇴직급여충당금 전입액

    Returns:
        dict: {총추계액, 전기잔액, 당기지급, 한도액, 회사전입액,
               손금산입액, 손금불산입액}
    """
    # 한도 = 총추계액 - (전기잔액 - 당기지급액)
    adjusted_prior = prior_reserve_balance - actual_payments
    limit = max(total_estimated_retirement - max(adjusted_prior, 0), 0)

    deductible = min(company_booked, limit)
    excess = max(company_booked - limit, 0)

    return {
        '총추계액': total_estimated_retirement,
        '전기잔액': prior_reserve_balance,
        '당기지급': actual_payments,
        '한도액': limit,
        '회사전입액': company_booked,
        '손금산입액': deductible,
        '손금불산입액': excess,
        '소득처분': '유보' if excess > 0 else '-',
    }


def calculate_bad_debt_reserve(
    *,
    receivables_balance: int,
    bad_debt_actual_rate: float = 0.0,
    statutory_rate: float = 0.01,
    prior_reserve: int = 0,
    company_booked: int = 0,
) -> dict:
    """대손충당금 한도 (§34, 영§61).

    한도율 = max(대손실적률, 1%)
    한도액 = 채권잔액 × 한도율
    설정한도 = 한도액 - 전기잔액 환입분(잔액과 상계 후)

    Args:
        receivables_balance: 기말 채권잔액 (매출채권+대여금 등)
        bad_debt_actual_rate: 대손실적률 (실제 대손발생/전기 채권잔액)
        statutory_rate: 법정 최저율 (기본 1% = 0.01)
        prior_reserve: 전기말 대손충당금 잔액
        company_booked: 회사 계상 대손충당금 전입액

    Returns:
        dict: {채권잔액, 적용률, 한도액, 전기잔액, 설정한도, 회사전입액,
               손금산입액, 손금불산입액}
    """
    applied_rate = max(bad_debt_actual_rate, statutory_rate)
    gross_limit = int(receivables_balance * applied_rate)

    # 설정한도 = 한도액 - 전기잔액 (전기잔액이 크면 한도 0)
    net_limit = max(gross_limit - prior_reserve, 0)

    deductible = min(company_booked, net_limit)
    excess = max(company_booked - net_limit, 0)

    return {
        '채권잔액': receivables_balance,
        '적용률': applied_rate,
        '한도액': gross_limit,
        '전기잔액': prior_reserve,
        '설정한도': net_limit,
        '회사전입액': company_booked,
        '손금산입액': deductible,
        '손금불산입액': excess,
        '소득처분': '유보' if excess > 0 else '-',
    }


# ══════════════════════════════════════════════
# Ch09. 부당행위계산부인
# ══════════════════════════════════════════════

def calculate_unfair_transaction_denial(
    *,
    market_value: int,
    transaction_price: int,
    transaction_type: str = '저가양도',
) -> dict:
    """부당행위계산부인 (§52, 영§88).

    특수관계인 거래에서 시가와 거래가액 차이가
    시가의 5% 또는 3억원 중 적은 금액 이상이면 부인.

    Args:
        market_value: 시가
        transaction_price: 실제 거래가액
        transaction_type: '저가양도' | '고가매입'

    Returns:
        dict: {시가, 거래가액, 거래유형, 차이, 판정기준, 부인여부, 익금산입액, 소득처분}
    """
    diff = abs(market_value - transaction_price)
    threshold = min(int(market_value * 0.05), 300_000_000)

    is_denied = diff >= threshold and diff > 0

    if is_denied:
        if transaction_type == '저가양도':
            inclusion = market_value - transaction_price
        elif transaction_type == '고가매입':
            inclusion = transaction_price - market_value
        else:
            inclusion = diff
        disposition = '기타사외유출'
    else:
        inclusion = 0
        disposition = '-'

    return {
        '시가': market_value,
        '거래가액': transaction_price,
        '거래유형': transaction_type,
        '차이': diff,
        '판정기준': threshold,
        '부인여부': is_denied,
        '익금산입액': max(inclusion, 0),
        '소득처분': disposition,
    }


# ══════════════════════════════════════════════
# Ch11. 세액공제·세액감면
# ══════════════════════════════════════════════

def calculate_foreign_tax_credit(
    *,
    foreign_tax_paid: int,
    foreign_source_income: int,
    taxable_base: int,
    computed_tax: int,
) -> dict:
    """외국납부세액공제 (§57).

    공제한도 = 산출세액 × (국외원천소득 / 과세표준)

    Args:
        foreign_tax_paid: 외국법인세 납부액
        foreign_source_income: 국외원천소득
        taxable_base: 과세표준
        computed_tax: 산출세액

    Returns:
        dict: {외국법인세, 국외원천소득, 공제한도, 세액공제, 이월공제액}
    """
    if taxable_base <= 0 or computed_tax <= 0:
        return {
            '외국법인세': foreign_tax_paid,
            '국외원천소득': foreign_source_income,
            '공제한도': 0,
            '세액공제': 0,
            '이월공제액': foreign_tax_paid,
        }

    credit_limit = int(computed_tax * foreign_source_income / taxable_base)
    actual_credit = min(foreign_tax_paid, credit_limit)
    carryover = max(foreign_tax_paid - credit_limit, 0)

    return {
        '외국법인세': foreign_tax_paid,
        '국외원천소득': foreign_source_income,
        '공제한도': credit_limit,
        '세액공제': actual_credit,
        '이월공제액': carryover,
    }


def calculate_sme_tax_reduction(
    *,
    computed_tax: int,
    reduction_rate: float,
    reduction_limit: int = 0,
) -> dict:
    """중소기업 세액감면 (조특법 §7).

    Args:
        computed_tax: 산출세액
        reduction_rate: 감면율
        reduction_limit: 감면 한도액 (0이면 한도 없음)

    Returns:
        dict: {산출세액, 감면율, 감면액, 한도, 실감면액}
    """
    gross_reduction = int(computed_tax * reduction_rate)
    actual = min(gross_reduction, reduction_limit) if reduction_limit > 0 else gross_reduction

    return {
        '산출세액': computed_tax,
        '감면율': reduction_rate,
        '감면액': gross_reduction,
        '한도': reduction_limit,
        '실감면액': actual,
    }


# ══════════════════════════════════════════════
# Ch12. 최저한세
# ══════════════════════════════════════════════

def apply_minimum_tax(
    *,
    computed_tax: int,
    total_reductions: int,
    taxable_base: int,
    is_sme: bool = False,
) -> dict:
    """최저한세 적용 (조특법 §132).

    - 중소기업: 7%
    - 일반 100억 이하: 10%
    - 일반 100억 초과 1,000억 이하: 12%
    - 일반 1,000억 초과: 17%

    Args:
        computed_tax: 산출세액
        total_reductions: 조특법상 감면·공제 합계
        taxable_base: 과세표준
        is_sme: 중소기업 여부

    Returns:
        dict: {산출세액, 감면합계, 감면후세액, 최저한세율, 최저한세액,
               적용여부, 납부세액, 감면배제액}
    """
    after_reduction = computed_tax - total_reductions

    if is_sme:
        min_rate = 0.07
        rate_label = '중소기업 7%'
    elif taxable_base <= 10_000_000_000:
        min_rate = 0.10
        rate_label = '일반 10%'
    elif taxable_base <= 100_000_000_000:
        min_rate = 0.12
        rate_label = '일반 12%'
    else:
        min_rate = 0.17
        rate_label = '일반 17%'

    min_tax = int(taxable_base * min_rate)

    if after_reduction < min_tax:
        applied = True
        final_tax = min_tax
        excluded = min_tax - after_reduction
    else:
        applied = False
        final_tax = after_reduction
        excluded = 0

    return {
        '산출세액': computed_tax,
        '감면합계': total_reductions,
        '감면후세액': after_reduction,
        '최저한세율': min_rate,
        '최저한세율구분': rate_label,
        '최저한세액': min_tax,
        '적용여부': applied,
        '납부세액': final_tax,
        '감면배제액': excluded,
    }


# ══════════════════════════════════════════════
# Ch13. 토지등 양도소득에 대한 법인세
# ══════════════════════════════════════════════

def calculate_land_transfer_additional_tax(
    *,
    transfer_gain: int,
    asset_type: str = '비사업용토지',
    is_unregistered: bool = False,
) -> dict:
    """토지등 양도소득에 대한 법인세 (§55의2).

    - 주택·별장: 20% (미등기 40%)
    - 비사업용 토지: 10% (미등기 40%)
    - 분양권: 20%

    Args:
        transfer_gain: 토지등 양도소득
        asset_type: '주택' | '비사업용토지' | '분양권' | '별장'
        is_unregistered: 미등기 여부

    Returns:
        dict: {양도소득, 자산유형, 미등기, 추가세율, 추가법인세}
    """
    if transfer_gain <= 0:
        return {
            '양도소득': transfer_gain,
            '자산유형': asset_type,
            '미등기': is_unregistered,
            '추가세율': 0,
            '추가법인세': 0,
        }

    if is_unregistered:
        rate = 0.40
    elif asset_type in ('주택', '별장'):
        rate = 0.20
    elif asset_type == '비사업용토지':
        rate = 0.10
    elif asset_type == '분양권':
        rate = 0.20
    else:
        rate = 0.10

    return {
        '양도소득': transfer_gain,
        '자산유형': asset_type,
        '미등기': is_unregistered,
        '추가세율': rate,
        '추가법인세': int(transfer_gain * rate),
    }


# ══════════════════════════════════════════════
# Ch14. 신고·납부
# ══════════════════════════════════════════════

def calculate_interim_prepayment(
    *,
    prior_year_computed_tax: int,
    prior_year_credits: int = 0,
    prior_year_months: int = 12,
) -> dict:
    """중간예납세액 계산 (§63의2①1호).

    중간예납세액 = (직전 산출세액 - 공제감면세액) × (6 / 직전 사업연도 월수)

    Args:
        prior_year_computed_tax: 직전 사업연도 산출세액
        prior_year_credits: 직전 사업연도 공제감면세액
        prior_year_months: 직전 사업연도 월수

    Returns:
        dict: {직전산출세액, 직전공제감면, 직전월수, 중간예납세액}
    """
    prior_months = max(1, prior_year_months)
    net_tax = max(prior_year_computed_tax - prior_year_credits, 0)
    interim = int(net_tax * 6 / prior_months)

    return {
        '직전산출세액': prior_year_computed_tax,
        '직전공제감면': prior_year_credits,
        '직전월수': prior_months,
        '중간예납세액': interim,
    }


# ══════════════════════════════════════════════
# Ch01. 법인세 총설
# ══════════════════════════════════════════════

def classify_corporation_type(
    *,
    is_domestic: bool = True,
    is_profit: bool = True,
) -> dict:
    """납세의무자 판정 (§1~§4)."""
    if is_domestic:
        if is_profit:
            return {'유형': '내국영리법인', '과세범위': '국내외 모든 소득',
                    '납세의무': '각사업연도소득 + 토지등양도소득 + 청산소득'}
        else:
            return {'유형': '내국비영리법인', '과세범위': '수익사업소득만 과세',
                    '납세의무': '각사업연도소득 + 토지등양도소득'}
    else:
        return {'유형': '외국법인', '과세범위': '국내원천소득만 과세',
                '납세의무': '각사업연도소득 + 토지등양도소득'}


# ══════════════════════════════════════════════
# 종합: 전체 파이프라인
# ══════════════════════════════════════════════

def calculate_corporate_tax_full(
    *,
    accounting_profit: int,
    additions: list[dict] | None = None,
    deductions: list[dict] | None = None,
    carried_losses: list[dict] | None = None,
    is_sme: bool = False,
    nontaxable_income: int = 0,
    income_deductions: int = 0,
    sme_reduction_rate: float = 0.0,
    sme_reduction_limit: int = 0,
    foreign_tax_paid: int = 0,
    foreign_source_income: int = 0,
    other_credits: int = 0,
    land_transfer_gain: int = 0,
    land_asset_type: str = '비사업용토지',
    land_unregistered: bool = False,
    prepaid_tax: int = 0,
) -> dict:
    """법인세 종합계산 — 회계이익부터 납부세액까지 전체 파이프라인."""
    # Step 1: 세무조정
    adj = calculate_taxable_income(
        accounting_profit=accounting_profit,
        additions=additions,
        deductions=deductions,
    )
    income_per_year = adj['각사업연도소득']

    # Step 2: 과세표준
    base_result = calculate_corporate_tax_base(
        income_per_year=income_per_year,
        carried_losses=carried_losses,
        is_sme=is_sme,
        nontaxable_income=nontaxable_income,
        income_deductions=income_deductions,
    )
    taxable_base = base_result['과세표준']

    # Step 3: 세율
    rate_result = apply_corporate_tax_rate(taxable_base=taxable_base)
    computed_tax = rate_result['산출세액']

    # Step 4: 조특법 감면
    total_reductions = 0
    sme_result = None
    if sme_reduction_rate > 0:
        sme_result = calculate_sme_tax_reduction(
            computed_tax=computed_tax,
            reduction_rate=sme_reduction_rate,
            reduction_limit=sme_reduction_limit,
        )
        total_reductions += sme_result['실감면액']

    # Step 5: 최저한세
    min_tax_result = None
    if total_reductions > 0:
        min_tax_result = apply_minimum_tax(
            computed_tax=computed_tax,
            total_reductions=total_reductions,
            taxable_base=taxable_base,
            is_sme=is_sme,
        )
        after_min_tax = min_tax_result['납부세액']
    else:
        after_min_tax = computed_tax

    # Step 6: 세액공제
    ftc_result = None
    total_credits = other_credits
    if foreign_tax_paid > 0:
        ftc_result = calculate_foreign_tax_credit(
            foreign_tax_paid=foreign_tax_paid,
            foreign_source_income=foreign_source_income,
            taxable_base=taxable_base,
            computed_tax=after_min_tax,
        )
        total_credits += ftc_result['세액공제']

    after_credits = max(after_min_tax - total_credits, 0)

    # Step 7: 토지추가과세
    land_result = None
    additional_land_tax = 0
    if land_transfer_gain > 0:
        land_result = calculate_land_transfer_additional_tax(
            transfer_gain=land_transfer_gain,
            asset_type=land_asset_type,
            is_unregistered=land_unregistered,
        )
        additional_land_tax = land_result['추가법인세']

    # Step 8: 결정세액
    determined_tax = after_credits + additional_land_tax

    # Step 9: 납부세액
    tax_due = determined_tax - prepaid_tax

    return {
        '당기순이익': accounting_profit,
        '각사업연도소득': income_per_year,
        '과세표준': taxable_base,
        '산출세액': computed_tax,
        '감면합계': total_reductions,
        '최저한세적용': min_tax_result['적용여부'] if min_tax_result else False,
        '최저한세후세액': after_min_tax,
        '세액공제합계': total_credits,
        '토지추가과세': additional_land_tax,
        '결정세액': determined_tax,
        '기납부세액': prepaid_tax,
        '납부할세액': tax_due,
        '세무조정내역': adj,
        '과세표준내역': base_result,
        '세율내역': rate_result,
        '중소기업감면': sme_result,
        '최저한세내역': min_tax_result,
        '외국납부세액공제': ftc_result,
        '토지추가과세내역': land_result,
    }
