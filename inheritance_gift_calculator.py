"""상속세·증여세 계산 엔진 — 상속세및증여세법 기준

Phase 3: Ch01(상속세) → Ch02(증여세) → Ch03(재산평가) → Ch04(신고·납부)
"""

from datetime import date
from typing import Optional


# ──────────────────────────────────────────────
# 공통: 세율표 (§26, §56 공통 적용)
# ──────────────────────────────────────────────

INHERITANCE_GIFT_TAX_BRACKETS = [
    # (과세표준 상한, 세율, 누진공제)
    (100_000_000, 0.10, 0),
    (500_000_000, 0.20, 10_000_000),
    (1_000_000_000, 0.30, 60_000_000),
    (3_000_000_000, 0.40, 160_000_000),
    (float('inf'), 0.50, 460_000_000),
]


def apply_tax_rate(taxable_base: int) -> dict:
    """상속세·증여세 세율 적용 (§26).

    과세표준에 누진세율 적용하여 산출세액 계산.
    1억 이하 10%, 5억 이하 20%, 10억 이하 30%, 30억 이하 40%, 30억 초과 50%.

    Args:
        taxable_base: 과세표준

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

    for upper, rate, progressive_deduction in INHERITANCE_GIFT_TAX_BRACKETS:
        if taxable_base <= upper:
            tax = int(taxable_base * rate) - progressive_deduction
            return {
                '과세표준': taxable_base,
                '적용세율': rate,
                '누진공제': progressive_deduction,
                '산출세액': max(tax, 0),
            }

    # fallback (should not reach)
    rate = 0.50
    progressive_deduction = 460_000_000
    tax = int(taxable_base * rate) - progressive_deduction
    return {
        '과세표준': taxable_base,
        '적용세율': rate,
        '누진공제': progressive_deduction,
        '산출세액': max(tax, 0),
    }


# ══════════════════════════════════════════════
# Ch01. 상속세
# ══════════════════════════════════════════════

# ──────────────────────────────────────────────
# §13 상속세 과세가액
# ──────────────────────────────────────────────

def calculate_inheritance_tax_base_amount(
    *,
    gross_estate: int,
    public_charges: int = 0,
    funeral_expenses: int = 0,
    funeral_enshrined: int = 0,
    debts: int = 0,
    pre_gift_to_heirs: int = 0,
    pre_gift_to_others: int = 0,
) -> dict:
    """상속세 과세가액 계산 (§13, §14).

    과세가액 = 총상속재산 - 공과금 - 장례비용 - 채무 + 사전증여가산

    장례비용 (시행령 §9②):
    - 일반장례: 최소 500만 / 최대 1,000만 (증빙 기준)
    - 봉안시설: 별도 500만 한도
    - 합계 최대 1,500만

    Args:
        gross_estate: 총상속재산가액
        public_charges: 공과금 (§14①1)
        funeral_expenses: 일반 장례비용 (봉안 제외, §14①2)
        funeral_enshrined: 봉안시설/자연장지 비용 (별도 한도)
        debts: 채무 (§14①3)
        pre_gift_to_heirs: 상속인 사전증여 (10년 이내, §13①1)
        pre_gift_to_others: 비상속인 사전증여 (5년 이내, §13①2)

    Returns:
        dict: {총상속재산, 공과금, 장례비용, 봉안비용, 장례비용공제, 채무,
               차감후가액, 사전증여_상속인, 사전증여_비상속인, 과세가액}
    """
    # 장례비용 공제 (시행령 §9②)
    # 일반장례: min(max(실비, 500만), 1,000만)
    # 봉안시설: min(봉안비, 500만)
    general_funeral = max(min(funeral_expenses, 10_000_000), 5_000_000)
    enshrined_ded = min(funeral_enshrined, 5_000_000)
    funeral_deduction = general_funeral + enshrined_ded

    deductions = public_charges + funeral_deduction + debts
    net_estate = gross_estate - deductions
    if net_estate < 0:
        net_estate = 0

    pre_gift_total = pre_gift_to_heirs + pre_gift_to_others
    taxable_amount = net_estate + pre_gift_total

    return {
        '총상속재산': gross_estate,
        '공과금': public_charges,
        '장례비용': funeral_expenses,
        '봉안비용': funeral_enshrined,
        '장례비용공제': funeral_deduction,
        '채무': debts,
        '차감후가액': net_estate,
        '사전증여_상속인': pre_gift_to_heirs,
        '사전증여_비상속인': pre_gift_to_others,
        '과세가액': taxable_amount,
    }


# ──────────────────────────────────────────────
# §18~§24 상속공제
# ──────────────────────────────────────────────

def calculate_basic_deduction() -> dict:
    """기초공제 (§18).

    거주자·비거주자 모두 2억원.

    Returns:
        dict: {기초공제: 200_000_000, 근거: '§18'}
    """
    return {
        '기초공제': 200_000_000,
        '근거': '§18',
    }


def calculate_spouse_deduction(
    *,
    actual_inheritance: int,
    legal_share_amount: int,
) -> dict:
    """배우자 상속공제 (§19).

    공제액 = min(실제상속액, min(법정상속지분상당액, 30억))
    최소 5억 보장 (실제상속 없거나 5억 미만이어도)

    Args:
        actual_inheritance: 배우자 실제 상속받은 금액
        legal_share_amount: 배우자 법정상속지분 상당액

    Returns:
        dict: {배우자상속공제, 실제상속액, 법정상속지분상당액, 적용기준, 근거}
    """
    if actual_inheritance <= 0:
        return {
            '배우자상속공제': 500_000_000,
            '실제상속액': 0,
            '법정상속지분상당액': legal_share_amount,
            '적용기준': '최소보장 5억 (실제상속 없음)',
            '근거': '§19④',
        }

    cap = min(legal_share_amount, 3_000_000_000)
    deduction = min(actual_inheritance, cap)

    if deduction < 500_000_000:
        return {
            '배우자상속공제': 500_000_000,
            '실제상속액': actual_inheritance,
            '법정상속지분상당액': legal_share_amount,
            '적용기준': '최소보장 5억',
            '근거': '§19④',
        }

    return {
        '배우자상속공제': deduction,
        '실제상속액': actual_inheritance,
        '법정상속지분상당액': legal_share_amount,
        '적용기준': f'min(실제{actual_inheritance:,}, min(법정{legal_share_amount:,}, 30억))',
        '근거': '§19①',
    }


def calculate_other_personal_deductions(
    *,
    children_count: int = 0,
    minor_years_remaining: list[int] | None = None,
    elderly_count: int = 0,
    disabled_life_expectancy: list[int] | None = None,
) -> dict:
    """그 밖의 인적공제 (§20).

    1. 자녀공제: 1인당 5천만원
    2. 미성년자공제: 1천만원 × (19세까지 잔여연수)
    3. 경로우대공제(65세+): 1인당 5천만원
    4. 장애인공제: 1천만원 × 기대여명
    (중복 합산 가능)

    Args:
        children_count: 자녀 수 (태아 포함)
        minor_years_remaining: 미성년자별 [19세까지 잔여연수] 리스트 (1년 미만 → 1)
        elderly_count: 65세 이상 인원 수
        disabled_life_expectancy: 장애인별 [기대여명 연수] 리스트 (1년 미만 → 1)

    Returns:
        dict: {자녀공제, 미성년자공제, 경로우대공제, 장애인공제,
               인적공제합계, 내역}
    """
    if minor_years_remaining is None:
        minor_years_remaining = []
    if disabled_life_expectancy is None:
        disabled_life_expectancy = []

    child_ded = children_count * 50_000_000
    minor_ded = sum(max(y, 1) * 10_000_000 for y in minor_years_remaining)
    elderly_ded = elderly_count * 50_000_000
    disabled_ded = sum(max(y, 1) * 10_000_000 for y in disabled_life_expectancy)

    total = child_ded + minor_ded + elderly_ded + disabled_ded

    return {
        '자녀공제': child_ded,
        '미성년자공제': minor_ded,
        '경로우대공제': elderly_ded,
        '장애인공제': disabled_ded,
        '인적공제합계': total,
        '내역': {
            '자녀수': children_count,
            '미성년자_잔여연수': minor_years_remaining,
            '경로우대_인원': elderly_count,
            '장애인_기대여명': disabled_life_expectancy,
        },
        '근거': '§20',
    }


def calculate_lump_sum_deduction(
    *,
    basic_deduction: int,
    personal_deductions: int,
    is_sole_spouse_heir: bool = False,
) -> dict:
    """일괄공제 (§21).

    max(기초공제+인적공제, 5억)
    배우자 단독상속 시 → 기초+인적만 (5억 일괄공제 선택 불가)

    Args:
        basic_deduction: 기초공제 (§18)
        personal_deductions: 인적공제 합계 (§20)
        is_sole_spouse_heir: 배우자 단독 상속 여부

    Returns:
        dict: {일괄공제적용여부, 기초공제, 인적공제, 개별합계, 일괄공제액, 적용액, 근거}
    """
    itemized = basic_deduction + personal_deductions
    lump_sum = 500_000_000

    if is_sole_spouse_heir:
        return {
            '일괄공제적용여부': False,
            '기초공제': basic_deduction,
            '인적공제': personal_deductions,
            '개별합계': itemized,
            '일괄공제액': lump_sum,
            '적용액': itemized,
            '근거': '§21② 배우자 단독상속 → 개별공제만',
        }

    use_lump = lump_sum > itemized
    applied = max(itemized, lump_sum)

    return {
        '일괄공제적용여부': use_lump,
        '기초공제': basic_deduction,
        '인적공제': personal_deductions,
        '개별합계': itemized,
        '일괄공제액': lump_sum,
        '적용액': applied,
        '근거': '§21① max(기초+인적, 5억)',
    }


def calculate_financial_asset_deduction(
    *,
    financial_assets: int,
    financial_debts: int = 0,
) -> dict:
    """금융재산 상속공제 (§22).

    순금융재산 = 금융재산 - 금융채무
    - 2천만 이하: 전액
    - 2천만 초과: max(순금융재산 × 20%, 2천만), 한도 2억

    Args:
        financial_assets: 금융재산 가액
        financial_debts: 금융채무

    Returns:
        dict: {금융재산, 금융채무, 순금융재산, 금융재산공제, 근거}
    """
    net = financial_assets - financial_debts
    if net <= 0:
        return {
            '금융재산': financial_assets,
            '금융채무': financial_debts,
            '순금융재산': 0,
            '금융재산공제': 0,
            '근거': '§22 순금융재산 없음',
        }

    if net <= 20_000_000:
        deduction = net
    else:
        deduction = max(int(net * 0.20), 20_000_000)
        deduction = min(deduction, 200_000_000)

    return {
        '금융재산': financial_assets,
        '금융채무': financial_debts,
        '순금융재산': net,
        '금융재산공제': deduction,
        '근거': '§22',
    }


def calculate_cohabitation_house_deduction(
    *,
    house_value: int,
    house_debt: int = 0,
    cohabitation_years: int = 0,
    is_one_house: bool = False,
    heir_is_lineal_descendant: bool = True,
) -> dict:
    """동거주택 상속공제 (§23의2).

    요건: 10년 이상 동거 + 1세대1주택 + 직계비속(배우자 포함) 상속
    공제: (주택가액 - 담보채무) × 100%, 한도 6억

    Args:
        house_value: 상속주택 가액
        house_debt: 해당 주택 담보 채무
        cohabitation_years: 동거 기간 (연)
        is_one_house: 1세대1주택 해당 여부
        heir_is_lineal_descendant: 상속인이 직계비속(+배우자)인지

    Returns:
        dict: {동거주택상속공제, 요건충족여부, 사유, 근거}
    """
    reasons = []
    if cohabitation_years < 10:
        reasons.append(f'동거기간 {cohabitation_years}년 < 10년')
    if not is_one_house:
        reasons.append('1세대1주택 미해당')
    if not heir_is_lineal_descendant:
        reasons.append('상속인이 직계비속이 아님')

    if reasons:
        return {
            '동거주택상속공제': 0,
            '요건충족여부': False,
            '사유': reasons,
            '근거': '§23의2',
        }

    net_value = max(house_value - house_debt, 0)
    deduction = min(net_value, 600_000_000)

    return {
        '동거주택상속공제': deduction,
        '요건충족여부': True,
        '주택가액': house_value,
        '담보채무': house_debt,
        '순가액': net_value,
        '근거': '§23의2',
    }


def calculate_family_business_deduction(
    *,
    business_asset_value: int,
    years_managed: int,
    is_sme: bool = True,
    is_mid_sized: bool = False,
) -> dict:
    """가업상속공제 (§18의2).

    가업상속재산가액 전액 공제, 경영기간별 한도:
    - 10~20년: 300억
    - 20~30년: 400억
    - 30년+: 600억

    요건: 피상속인 10년 이상 계속경영, 중소/중견기업

    Args:
        business_asset_value: 가업상속재산 가액
        years_managed: 피상속인 경영 연수
        is_sme: 중소기업 여부
        is_mid_sized: 중견기업 여부 (매출 5천억 미만)

    Returns:
        dict: {가업상속공제, 한도, 경영기간, 요건충족여부, 근거}
    """
    if years_managed < 10 or (not is_sme and not is_mid_sized):
        return {
            '가업상속공제': 0,
            '요건충족여부': False,
            '사유': '경영기간 10년 미만' if years_managed < 10 else '중소/중견기업 아님',
            '근거': '§18의2',
        }

    if years_managed >= 30:
        cap = 60_000_000_000
    elif years_managed >= 20:
        cap = 40_000_000_000
    else:
        cap = 30_000_000_000

    deduction = min(business_asset_value, cap)

    return {
        '가업상속공제': deduction,
        '가업재산가액': business_asset_value,
        '한도': cap,
        '경영기간': years_managed,
        '요건충족여부': True,
        '근거': '§18의2',
    }


def calculate_farming_deduction(
    *,
    farming_asset_value: int,
    is_eligible: bool = True,
) -> dict:
    """영농상속공제 (§18의3).

    영농상속재산가액 전액 공제, 한도 30억.
    영농: 양축, 영어, 영림 포함.

    Args:
        farming_asset_value: 영농상속재산 가액
        is_eligible: 요건 충족 여부 (피상속인 영농 종사 등)

    Returns:
        dict: {영농상속공제, 한도, 근거}
    """
    if not is_eligible:
        return {
            '영농상속공제': 0,
            '요건충족여부': False,
            '근거': '§18의3',
        }

    cap = 3_000_000_000
    deduction = min(farming_asset_value, cap)

    return {
        '영농상속공제': deduction,
        '영농재산가액': farming_asset_value,
        '한도': cap,
        '요건충족여부': True,
        '근거': '§18의3',
    }


def calculate_total_inheritance_deductions(
    *,
    taxable_amount: int,
    lump_sum_or_itemized: int,
    spouse_deduction: int = 0,
    financial_deduction: int = 0,
    cohabitation_deduction: int = 0,
    family_business_deduction: int = 0,
    farming_deduction: int = 0,
    disaster_loss: int = 0,
    pre_gift_added: int = 0,
    bequest_to_non_heir: int = 0,
    forfeited_inheritance: int = 0,
) -> dict:
    """공제 합계 및 한도 적용 (§24).

    총공제 한도 = 과세가액 - 유증(비상속인) - 포기상속 - 사전증여가산
    (사전증여가산 차감은 과세가액 5억 초과 시에만)

    Args:
        taxable_amount: 과세가액 (§13)
        lump_sum_or_itemized: 일괄공제 또는 기초+인적 (§21)
        spouse_deduction: 배우자 상속공제 (§19)
        financial_deduction: 금융재산 공제 (§22)
        cohabitation_deduction: 동거주택 공제 (§23의2)
        family_business_deduction: 가업상속공제 (§18의2)
        farming_deduction: 영농상속공제 (§18의3)
        disaster_loss: 재해손실 공제 (§23)
        pre_gift_added: 사전증여 가산액 (§13)
        bequest_to_non_heir: 비상속인 유증 재산가액
        forfeited_inheritance: 포기상속 재산가액

    Returns:
        dict: {공제합계_산출, 공제한도, 공제합계_적용, 내역, 근거}
    """
    raw_total = (
        lump_sum_or_itemized
        + spouse_deduction
        + financial_deduction
        + cohabitation_deduction
        + family_business_deduction
        + farming_deduction
        + disaster_loss
    )

    # §24 한도: 과세가액 - 유증 - 포기 - 사전증여(5억 초과 시만)
    limit_deductions = bequest_to_non_heir + forfeited_inheritance
    if taxable_amount > 500_000_000:
        limit_deductions += pre_gift_added

    cap = max(taxable_amount - limit_deductions, 0)
    applied = min(raw_total, cap)

    return {
        '공제합계_산출': raw_total,
        '공제한도': cap,
        '공제합계_적용': applied,
        '내역': {
            '일괄공제_또는_기초인적': lump_sum_or_itemized,
            '배우자공제': spouse_deduction,
            '금융재산공제': financial_deduction,
            '동거주택공제': cohabitation_deduction,
            '가업상속공제': family_business_deduction,
            '영농상속공제': farming_deduction,
            '재해손실공제': disaster_loss,
        },
        '근거': '§24',
    }


def calculate_generation_skipping_surcharge(
    *,
    computed_tax: int,
    heir_share_ratio: float,
    is_minor: bool = False,
    minor_inheritance_over_2b: bool = False,
) -> dict:
    """세대생략 할증과세 (§27).

    피상속인의 자녀를 제외한 직계비속(손자녀 등) → 30% 할증
    미성년자 + 20억 초과 → 40% 할증
    대습상속은 제외

    Args:
        computed_tax: 산출세액
        heir_share_ratio: 해당 상속인/수유자 재산 비율
        is_minor: 미성년자 여부
        minor_inheritance_over_2b: 미성년자이고 상속재산 20억 초과 여부

    Returns:
        dict: {할증세액, 할증율, 근거}
    """
    if is_minor and minor_inheritance_over_2b:
        surcharge_rate = 0.40
    else:
        surcharge_rate = 0.30

    surcharge = int(computed_tax * heir_share_ratio * surcharge_rate)

    return {
        '할증세액': surcharge,
        '할증율': surcharge_rate,
        '산출세액': computed_tax,
        '상속비율': heir_share_ratio,
        '근거': '§27',
    }


def calculate_pre_gift_tax_credit(
    *,
    pre_gift_tax_paid: int,
    computed_tax: int,
    total_taxable_base: int,
    pre_gift_taxable_base: int,
) -> dict:
    """증여세액 공제 (§28).

    사전증여 가산분에 대해 당시 납부한 증여세산출세액을 공제.
    한도: 산출세액 × (증여재산 과세표준 / 전체 과세표준)

    Args:
        pre_gift_tax_paid: 사전증여 시 납부한 증여세산출세액
        computed_tax: 상속세 산출세액
        total_taxable_base: 상속세 전체 과세표준
        pre_gift_taxable_base: 가산된 증여재산의 과세표준

    Returns:
        dict: {증여세액공제, 한도, 근거}
    """
    if total_taxable_base <= 0 or pre_gift_taxable_base <= 0:
        return {
            '증여세액공제': 0,
            '한도': 0,
            '근거': '§28',
        }

    cap = int(computed_tax * pre_gift_taxable_base / total_taxable_base)
    credit = min(pre_gift_tax_paid, cap)

    return {
        '증여세액공제': credit,
        '한도': cap,
        '기납부증여세': pre_gift_tax_paid,
        '근거': '§28',
    }


def calculate_inheritance_tax(
    *,
    gross_estate: int,
    public_charges: int = 0,
    funeral_expenses: int = 0,
    funeral_enshrined: int = 0,
    debts: int = 0,
    pre_gift_to_heirs: int = 0,
    pre_gift_to_others: int = 0,
    has_spouse: bool = True,
    spouse_actual_inheritance: int = 0,
    spouse_legal_share_amount: int = 0,
    children_count: int = 0,
    minor_years_remaining: list[int] | None = None,
    elderly_count: int = 0,
    disabled_life_expectancy: list[int] | None = None,
    is_sole_spouse_heir: bool = False,
    financial_assets: int = 0,
    financial_debts: int = 0,
    cohabitation_house_value: int = 0,
    cohabitation_house_debt: int = 0,
    cohabitation_years: int = 0,
    is_one_house: bool = False,
    heir_is_lineal_descendant: bool = True,
    disaster_loss: int = 0,
    bequest_to_non_heir: int = 0,
    forfeited_inheritance: int = 0,
    pre_gift_tax_paid: int = 0,
    generation_skipping: bool = False,
    generation_skipping_ratio: float = 0.0,
    generation_skipping_minor: bool = False,
    generation_skipping_over_2b: bool = False,
    appraisal_fee: int = 0,
    reporting_credit_rate: float = 0.03,
) -> dict:
    """상속세 종합 계산 (§13~§28).

    전체 흐름:
    1. 과세가액 (§13) = 총상속재산 - 공과금등 + 사전증여
    2. 공제 (§18~§24) = 일괄/기초인적 + 배우자 + 금융 + 동거주택 + 재해
    3. 과세표준 (§25) = 과세가액 - 공제 - 감정수수료
    4. 산출세액 (§26) = 세율 적용
    5. 세대생략 할증 (§27)
    6. 증여세액 공제 (§28)
    7. 신고세액공제 (3%)
    8. 납부세액

    Args:
        (위 개별 함수 참조)
        appraisal_fee: 감정평가 수수료
        reporting_credit_rate: 신고세액공제율 (기본 3%)

    Returns:
        dict: 전체 계산 상세
    """
    # 1. 과세가액
    base = calculate_inheritance_tax_base_amount(
        gross_estate=gross_estate,
        public_charges=public_charges,
        funeral_expenses=funeral_expenses,
        debts=debts,
        pre_gift_to_heirs=pre_gift_to_heirs,
        pre_gift_to_others=pre_gift_to_others,
        funeral_enshrined=funeral_enshrined,
    )

    taxable_amount = base['과세가액']

    # 2. 공제
    basic = calculate_basic_deduction()

    personal = calculate_other_personal_deductions(
        children_count=children_count,
        minor_years_remaining=minor_years_remaining,
        elderly_count=elderly_count,
        disabled_life_expectancy=disabled_life_expectancy,
    )

    lump = calculate_lump_sum_deduction(
        basic_deduction=basic['기초공제'],
        personal_deductions=personal['인적공제합계'],
        is_sole_spouse_heir=is_sole_spouse_heir,
    )

    spouse_ded = {'배우자상속공제': 0}
    if has_spouse:
        spouse_ded = calculate_spouse_deduction(
            actual_inheritance=spouse_actual_inheritance,
            legal_share_amount=spouse_legal_share_amount,
        )

    fin_ded = calculate_financial_asset_deduction(
        financial_assets=financial_assets,
        financial_debts=financial_debts,
    )

    cohab_ded = calculate_cohabitation_house_deduction(
        house_value=cohabitation_house_value,
        house_debt=cohabitation_house_debt,
        cohabitation_years=cohabitation_years,
        is_one_house=is_one_house,
        heir_is_lineal_descendant=heir_is_lineal_descendant,
    )

    pre_gift_added = pre_gift_to_heirs + pre_gift_to_others

    total_ded = calculate_total_inheritance_deductions(
        taxable_amount=taxable_amount,
        lump_sum_or_itemized=lump['적용액'],
        spouse_deduction=spouse_ded['배우자상속공제'],
        financial_deduction=fin_ded['금융재산공제'],
        cohabitation_deduction=cohab_ded['동거주택상속공제'],
        disaster_loss=disaster_loss,
        pre_gift_added=pre_gift_added,
        bequest_to_non_heir=bequest_to_non_heir,
        forfeited_inheritance=forfeited_inheritance,
    )

    # 3. 과세표준
    # 감정평가수수료 한도 500만원 (시행령 §25①2)
    appraisal_fee_capped = min(appraisal_fee, 5_000_000)
    taxable_base = max(taxable_amount - total_ded['공제합계_적용'] - appraisal_fee_capped, 0)

    # 과세최저한 (§25②)
    if taxable_base < 500_000:
        taxable_base = 0

    # 4. 산출세액
    tax_calc = apply_tax_rate(taxable_base)
    computed_tax = tax_calc['산출세액']

    # 5. 세대생략 할증
    surcharge = 0
    if generation_skipping and generation_skipping_ratio > 0:
        gs = calculate_generation_skipping_surcharge(
            computed_tax=computed_tax,
            heir_share_ratio=generation_skipping_ratio,
            is_minor=generation_skipping_minor,
            minor_inheritance_over_2b=generation_skipping_over_2b,
        )
        surcharge = gs['할증세액']

    total_computed = computed_tax + surcharge

    # 6. 증여세액 공제
    gift_credit = 0
    if pre_gift_tax_paid > 0 and pre_gift_added > 0:
        gc = calculate_pre_gift_tax_credit(
            pre_gift_tax_paid=pre_gift_tax_paid,
            computed_tax=total_computed,
            total_taxable_base=taxable_base,
            pre_gift_taxable_base=pre_gift_added,  # 간이 적용
        )
        gift_credit = gc['증여세액공제']

    after_credits = max(total_computed - gift_credit, 0)

    # 7. 신고세액공제
    reporting_credit = int(after_credits * reporting_credit_rate)

    # 8. 납부세액
    tax_payable = max(after_credits - reporting_credit, 0)

    return {
        '과세가액': taxable_amount,
        '공제합계': total_ded['공제합계_적용'],
        '감정평가수수료': appraisal_fee_capped,
        '과세표준': taxable_base,
        '세율': tax_calc['적용세율'],
        '산출세액': computed_tax,
        '세대생략할증': surcharge,
        '증여세액공제': gift_credit,
        '신고세액공제': reporting_credit,
        '납부세액': tax_payable,
        '상세': {
            '과세가액_상세': base,
            '기초공제': basic,
            '인적공제': personal,
            '일괄공제': lump,
            '배우자공제': spouse_ded,
            '금융재산공제': fin_ded,
            '동거주택공제': cohab_ded,
            '공제한도': total_ded,
        },
    }


# ══════════════════════════════════════════════
# Ch02. 증여세
# ══════════════════════════════════════════════

# ──────────────────────────────────────────────
# §47 증여세 과세가액
# ──────────────────────────────────────────────

def calculate_gift_tax_base_amount(
    *,
    gift_value: int,
    assumed_debts: int = 0,
    prior_gifts_10yr: int = 0,
) -> dict:
    """증여세 과세가액 계산 (§47).

    과세가액 = 증여재산가액 - 인수채무 + 10년 이내 동일인 합산(1천만 이상)

    Args:
        gift_value: 증여재산 가액
        assumed_debts: 수증자 인수 채무
        prior_gifts_10yr: 10년 이내 동일인 기증여 합산액

    Returns:
        dict: {증여재산가액, 인수채무, 차감가액, 기증여합산, 과세가액, 근거}
    """
    net_gift = max(gift_value - assumed_debts, 0)
    taxable_amount = net_gift + prior_gifts_10yr

    return {
        '증여재산가액': gift_value,
        '인수채무': assumed_debts,
        '차감가액': net_gift,
        '기증여합산': prior_gifts_10yr,
        '과세가액': taxable_amount,
        '근거': '§47',
    }


# ──────────────────────────────────────────────
# §53 증여재산 공제
# ──────────────────────────────────────────────

GIFT_DEDUCTION_TABLE = {
    '배우자': 600_000_000,
    '직계존속': 50_000_000,
    '직계존속_미성년': 20_000_000,
    '직계비속': 50_000_000,
    '기타친족': 10_000_000,
}


def calculate_gift_deduction(
    *,
    donor_relationship: str,
    is_minor: bool = False,
    prior_deductions_used: int = 0,
) -> dict:
    """증여재산 공제 (§53).

    10년 합산 한도:
    - 배우자: 6억
    - 직계존속: 5천만 (미성년 2천만)
    - 직계비속: 5천만
    - 기타친족(4촌혈족/3촌인척): 1천만

    Args:
        donor_relationship: '배우자'|'직계존속'|'직계비속'|'기타친족'
        is_minor: 미성년자 수증자 여부 (직계존속 증여 시)
        prior_deductions_used: 10년 내 이미 사용한 공제액

    Returns:
        dict: {증여재산공제, 공제한도, 기사용공제, 잔여공제, 근거}
    """
    if donor_relationship == '직계존속' and is_minor:
        limit = GIFT_DEDUCTION_TABLE['직계존속_미성년']
    elif donor_relationship in GIFT_DEDUCTION_TABLE:
        limit = GIFT_DEDUCTION_TABLE[donor_relationship]
    else:
        limit = 0

    remaining = max(limit - prior_deductions_used, 0)

    return {
        '증여재산공제': remaining,
        '공제한도': limit,
        '기사용공제': prior_deductions_used,
        '잔여공제': remaining,
        '근거': '§53',
    }


# ──────────────────────────────────────────────
# §53의2 혼인·출산 증여재산 공제
# ──────────────────────────────────────────────

def calculate_marriage_childbirth_deduction(
    *,
    is_marriage_gift: bool = False,
    is_childbirth_gift: bool = False,
    prior_marriage_deduction: int = 0,
    prior_childbirth_deduction: int = 0,
) -> dict:
    """혼인·출산 증여재산 공제 (§53의2).

    혼인 전후 2년 이내 직계존속 증여 → 1억 추가
    출산/입양 2년 이내 직계존속 증여 → 1억 추가
    혼인+출산 합산 한도 1억

    Args:
        is_marriage_gift: 혼인 관련 증여 여부
        is_childbirth_gift: 출산/입양 관련 증여 여부
        prior_marriage_deduction: 기사용 혼인공제
        prior_childbirth_deduction: 기사용 출산공제

    Returns:
        dict: {혼인출산공제, 혼인공제, 출산공제, 근거}
    """
    total_limit = 100_000_000
    prior_total = prior_marriage_deduction + prior_childbirth_deduction
    remaining_total = max(total_limit - prior_total, 0)

    marriage_ded = 0
    childbirth_ded = 0

    if is_marriage_gift:
        marriage_limit = max(100_000_000 - prior_marriage_deduction, 0)
        marriage_ded = min(marriage_limit, remaining_total)
        remaining_total -= marriage_ded

    if is_childbirth_gift:
        childbirth_limit = max(100_000_000 - prior_childbirth_deduction, 0)
        childbirth_ded = min(childbirth_limit, remaining_total)

    total_ded = marriage_ded + childbirth_ded

    return {
        '혼인출산공제': total_ded,
        '혼인공제': marriage_ded,
        '출산공제': childbirth_ded,
        '합산한도': total_limit,
        '기사용합계': prior_total,
        '근거': '§53의2',
    }


def calculate_gift_tax(
    *,
    gift_value: int,
    assumed_debts: int = 0,
    prior_gifts_10yr: int = 0,
    donor_relationship: str = '직계존속',
    is_minor: bool = False,
    prior_deductions_used: int = 0,
    is_marriage_gift: bool = False,
    is_childbirth_gift: bool = False,
    prior_marriage_deduction: int = 0,
    prior_childbirth_deduction: int = 0,
    prior_gift_tax_paid: int = 0,
    appraisal_fee: int = 0,
    reporting_credit_rate: float = 0.03,
) -> dict:
    """증여세 종합 계산 (§47~§58).

    전체 흐름:
    1. 과세가액 (§47) = 증여재산 - 인수채무 + 10년 합산
    2. 공제 (§53, §53의2)
    3. 과세표준 (§55) = 과세가액 - 공제 - 감정수수료
    4. 산출세액 (§56) = §26 세율 적용
    5. 기납부세액 공제 (세대생략 할증은 증여세에도 적용 §57)
    6. 신고세액공제
    7. 납부세액

    Args:
        (위 개별 함수 참조)
        prior_gift_tax_paid: 10년 합산분 기납부 증여세
        appraisal_fee: 감정평가 수수료
        reporting_credit_rate: 신고세액공제율 (기본 3%)

    Returns:
        dict: 전체 계산 상세
    """
    # 1. 과세가액
    base = calculate_gift_tax_base_amount(
        gift_value=gift_value,
        assumed_debts=assumed_debts,
        prior_gifts_10yr=prior_gifts_10yr,
    )
    taxable_amount = base['과세가액']

    # 2. 공제
    gift_ded = calculate_gift_deduction(
        donor_relationship=donor_relationship,
        is_minor=is_minor,
        prior_deductions_used=prior_deductions_used,
    )

    marriage_ded = calculate_marriage_childbirth_deduction(
        is_marriage_gift=is_marriage_gift,
        is_childbirth_gift=is_childbirth_gift,
        prior_marriage_deduction=prior_marriage_deduction,
        prior_childbirth_deduction=prior_childbirth_deduction,
    )

    total_deduction = gift_ded['증여재산공제'] + marriage_ded['혼인출산공제']

    # 3. 과세표준
    # 감정평가수수료 한도 500만원 (시행령 §49의2)
    appraisal_fee_capped = min(appraisal_fee, 5_000_000)
    taxable_base = max(taxable_amount - total_deduction - appraisal_fee_capped, 0)

    if taxable_base < 500_000:
        taxable_base = 0

    # 4. 산출세액
    tax_calc = apply_tax_rate(taxable_base)
    computed_tax = tax_calc['산출세액']

    # 5. 기납부세액 공제 (§58)
    after_prior_credit = max(computed_tax - prior_gift_tax_paid, 0)

    # 6. 신고세액공제
    reporting_credit = int(after_prior_credit * reporting_credit_rate)

    # 7. 납부세액
    tax_payable = max(after_prior_credit - reporting_credit, 0)

    return {
        '과세가액': taxable_amount,
        '증여재산공제': gift_ded['증여재산공제'],
        '혼인출산공제': marriage_ded['혼인출산공제'],
        '공제합계': total_deduction,
        '감정평가수수료': appraisal_fee_capped,
        '과세표준': taxable_base,
        '세율': tax_calc['적용세율'],
        '산출세액': computed_tax,
        '기납부세액공제': prior_gift_tax_paid,
        '신고세액공제': reporting_credit,
        '납부세액': tax_payable,
        '상세': {
            '과세가액_상세': base,
            '증여재산공제_상세': gift_ded,
            '혼인출산공제_상세': marriage_ded,
        },
    }


# ──────────────────────────────────────────────
# 특수증여: §35, §37, §41의4
# ──────────────────────────────────────────────

def calculate_low_price_transfer_gift(
    *,
    market_value: int,
    transfer_price: int,
    is_related_party: bool = True,
) -> dict:
    """저가 양수에 따른 이익의 증여 (§35).

    특수관계인간: 증여재산가액 = 시가 - 대가 - 기준금액
    기준금액 = min(시가 * 30%, 3억)
    (시가-대가 < 기준금액이면 비과세)

    비특수관계인: 시가의 30% 이상 차이 + 3억 이상이면 과세

    Args:
        market_value: 시가
        transfer_price: 양수가액 (대가)
        is_related_party: 특수관계인 여부

    Returns:
        dict: {증여재산가액, 이익, 기준금액, 과세여부, 근거}
    """
    benefit = market_value - transfer_price
    if benefit <= 0:
        return {
            '증여재산가액': 0,
            '이익': 0,
            '과세여부': False,
            '사유': '이익 없음 (고가 양수)',
            '근거': '§35',
        }

    if is_related_party:
        threshold = min(int(market_value * 0.30), 300_000_000)
        if benefit < threshold:
            return {
                '증여재산가액': 0,
                '이익': benefit,
                '기준금액': threshold,
                '과세여부': False,
                '사유': f'이익 {benefit:,} < 기준금액 {threshold:,}',
                '근거': '§35①',
            }
        gift_value = benefit - threshold
    else:
        # 비특수관계인: 시가의 30% 이상 차이 AND 3억 이상
        if benefit < int(market_value * 0.30) or benefit < 300_000_000:
            return {
                '증여재산가액': 0,
                '이익': benefit,
                '과세여부': False,
                '사유': '비특수관계인 기준 미충족',
                '근거': '§35②',
            }
        threshold = min(int(market_value * 0.30), 300_000_000)
        gift_value = benefit - threshold

    return {
        '증여재산가액': gift_value,
        '이익': benefit,
        '기준금액': threshold,
        '시가': market_value,
        '대가': transfer_price,
        '과세여부': True,
        '근거': '§35①' if is_related_party else '§35②',
    }


def calculate_high_price_transfer_gift(
    *,
    market_value: int,
    transfer_price: int,
    is_related_party: bool = True,
) -> dict:
    """고가 양도에 따른 이익의 증여 (§35).

    양도자가 시가보다 높은 가격에 양도받음 → 양도자에게 증여.

    Args:
        market_value: 시가
        transfer_price: 양도가액 (대가)
        is_related_party: 특수관계인 여부

    Returns:
        dict: {증여재산가액, 이익, 기준금액, 과세여부, 근거}
    """
    benefit = transfer_price - market_value
    if benefit <= 0:
        return {
            '증여재산가액': 0,
            '이익': 0,
            '과세여부': False,
            '사유': '이익 없음',
            '근거': '§35',
        }

    threshold = min(int(market_value * 0.30), 300_000_000)
    if benefit < threshold:
        return {
            '증여재산가액': 0,
            '이익': benefit,
            '기준금액': threshold,
            '과세여부': False,
            '근거': '§35',
        }

    gift_value = benefit - threshold
    return {
        '증여재산가액': gift_value,
        '이익': benefit,
        '기준금액': threshold,
        '과세여부': True,
        '근거': '§35',
    }


def calculate_free_use_of_real_estate_gift(
    *,
    property_value: int,
    annual_benefit_rate: float = 0.02,
    annuity_pv_factor: float = 3.7907,
    threshold: int = 100_000_000,
) -> dict:
    """부동산 무상사용에 따른 이익의 증여 (§37).

    증여재산가액 = 부동산 시가 * 부동산무상사용 연간이익률 * 연금현가계수

    기준금액(1억원) 미만이면 비과세.

    Args:
        property_value: 부동산 시가
        annual_benefit_rate: 부동산무상사용 연간이익률 (기재부령, 기본 2%)
        annuity_pv_factor: 5년 연금현가계수 (이자율에 따라 변동)
        threshold: 비과세 기준금액 (기본 1억)

    Returns:
        dict: {증여재산가액, 연간이익, 과세여부, 근거}
    """
    annual_benefit = int(property_value * annual_benefit_rate)
    gift_value = int(property_value * annual_benefit_rate * annuity_pv_factor)

    if gift_value < threshold:
        return {
            '증여재산가액': 0,
            '산출가액': gift_value,
            '연간이익': annual_benefit,
            '과세여부': False,
            '사유': f'산출가액 {gift_value:,} < 기준 {threshold:,}',
            '근거': '§37①',
        }

    return {
        '증여재산가액': gift_value,
        '부동산시가': property_value,
        '연간이익률': annual_benefit_rate,
        '연금현가계수': annuity_pv_factor,
        '연간이익': annual_benefit,
        '과세여부': True,
        '근거': '§37①',
    }


def calculate_interest_free_loan_gift(
    *,
    loan_amount: int,
    loan_rate: float = 0.0,
    appropriate_rate: float = 0.045,
    loan_period_years: float = 1.0,
    threshold: int = 10_000_000,
) -> dict:
    """금전 무상대출 등에 따른 이익의 증여 (§41의4).

    무상대출: 증여재산가액 = 대출금 * 적정이자율
    저리대출: 증여재산가액 = 대출금 * (적정이자율 - 실제이자율)

    기준금액(1천만원) 미만이면 비과세.
    대출기간 미정 → 1년. 1년 이상 → 매년 갱신.

    Args:
        loan_amount: 대출금액
        loan_rate: 실제 이자율 (무상이면 0)
        appropriate_rate: 적정이자율 (기재부령, 기본 4.6%)
        loan_period_years: 대출기간 (연, 미정이면 1)
        threshold: 비과세 기준금액 (기본 1천만)

    Returns:
        dict: {증여재산가액, 연간이익, 과세여부, 근거}
    """
    rate_diff = appropriate_rate - loan_rate
    if rate_diff <= 0:
        return {
            '증여재산가액': 0,
            '과세여부': False,
            '사유': '이자율 차이 없음',
            '근거': '§41의4',
        }

    annual_benefit = int(loan_amount * rate_diff)
    # 1년 단위 계산 (§41의4②)
    gift_value = annual_benefit

    if gift_value < threshold:
        return {
            '증여재산가액': 0,
            '연간이익': annual_benefit,
            '과세여부': False,
            '사유': f'연간이익 {annual_benefit:,} < 기준 {threshold:,}',
            '근거': '§41의4①',
        }

    return {
        '증여재산가액': gift_value,
        '대출금액': loan_amount,
        '적정이자율': appropriate_rate,
        '실제이자율': loan_rate,
        '이자율차이': rate_diff,
        '연간이익': annual_benefit,
        '과세여부': True,
        '근거': '§41의4①',
    }


# ══════════════════════════════════════════════
# Ch03. 재산의 평가
# ══════════════════════════════════════════════

# ──────────────────────────────────────────────
# §61 부동산 보충적 평가
# ──────────────────────────────────────────────

def evaluate_land(
    *,
    officially_assessed_price: int,
    multiplier: float = 1.0,
) -> dict:
    """토지 보충적 평가 (§61①1).

    개별공시지가 × 배율 (배율방법)
    배율이 없으면 개별공시지가 그대로.

    Args:
        officially_assessed_price: 개별공시지가 (원/m2)
        multiplier: 지역별 배율 (국세청장 고시)

    Returns:
        dict: {평가액, 공시지가, 배율, 근거}
    """
    value = int(officially_assessed_price * multiplier)
    return {
        '평가액': value,
        '공시지가': officially_assessed_price,
        '배율': multiplier,
        '근거': '§61①1',
    }


def evaluate_building(
    *,
    nts_standard_price: int,
) -> dict:
    """건물 보충적 평가 (§61①2).

    국세청장이 산정/고시하는 가액.

    Args:
        nts_standard_price: 국세청장 고시 기준시가

    Returns:
        dict: {평가액, 근거}
    """
    return {
        '평가액': nts_standard_price,
        '근거': '§61①2',
    }


def evaluate_housing(
    *,
    officially_assessed_housing_price: int,
) -> dict:
    """주택 보충적 평가 (§61①3).

    개별주택가격 또는 공동주택가격 (부동산공시법).

    Args:
        officially_assessed_housing_price: 개별주택/공동주택 공시가격

    Returns:
        dict: {평가액, 근거}
    """
    return {
        '평가액': officially_assessed_housing_price,
        '근거': '§61①3',
    }


def evaluate_leased_property(
    *,
    annual_rent: int,
    deposit: int = 0,
    deposit_conversion_rate: float = 0.045,
    supplementary_value: int = 0,
) -> dict:
    """임대재산 평가 (§61⑤).

    임대료 기준 평가 = (연간임대료 + 보증금 × 환산율) / 환산율
    보충적 평가와 비교 → 큰 금액 적용

    Args:
        annual_rent: 연간 임대료
        deposit: 보증금/전세금
        deposit_conversion_rate: 보증금 환산율 (기재부령)
        supplementary_value: 보충적 평가액 (§61①~④ 기준)

    Returns:
        dict: {평가액, 임대기준평가, 보충적평가, 적용방법, 근거}
    """
    # 임대료 환산: (연임대료 + 보증금×환산율) / 환산율
    if deposit_conversion_rate > 0:
        lease_value = int(
            (annual_rent + deposit * deposit_conversion_rate) / deposit_conversion_rate
        )
    else:
        lease_value = 0

    applied = max(lease_value, supplementary_value)
    method = '임대기준' if lease_value >= supplementary_value else '보충적평가'

    return {
        '평가액': applied,
        '임대기준평가': lease_value,
        '보충적평가': supplementary_value,
        '적용방법': method,
        '근거': '§61⑤',
    }


# ──────────────────────────────────────────────
# §63 유가증권 등 평가
# ──────────────────────────────────────────────

def evaluate_listed_stock(
    *,
    daily_prices: list[int],
) -> dict:
    """상장주식 평가 (§63①1가).

    평가기준일 전후 2개월간 종가 평균액.

    Args:
        daily_prices: 전후 2개월간 매일 종가 리스트

    Returns:
        dict: {평가액, 거래일수, 근거}
    """
    if not daily_prices:
        return {'평가액': 0, '거래일수': 0, '근거': '§63①1가'}

    avg = int(sum(daily_prices) / len(daily_prices))
    return {
        '평가액': avg,
        '거래일수': len(daily_prices),
        '근거': '§63①1가',
    }


def evaluate_unlisted_stock(
    *,
    net_asset_value_per_share: int,
    net_profit_value_per_share: int,
    is_real_estate_company: bool = False,
) -> dict:
    """비상장주식 보충적 평가 (§63①1나, 시행령 §54).

    일반법인: (순손익가치×3 + 순자산가치×2) / 5
    부동산과다법인: (순손익가치×2 + 순자산가치×3) / 5

    Args:
        net_asset_value_per_share: 1주당 순자산가치
        net_profit_value_per_share: 1주당 순손익가치
        is_real_estate_company: 부동산과다보유법인 여부

    Returns:
        dict: {평가액, 순자산가치, 순손익가치, 가중치, 근거}
    """
    if is_real_estate_company:
        value = int(
            (net_profit_value_per_share * 2 + net_asset_value_per_share * 3) / 5
        )
        weights = '순손익2 : 순자산3'
    else:
        value = int(
            (net_profit_value_per_share * 3 + net_asset_value_per_share * 2) / 5
        )
        weights = '순손익3 : 순자산2'

    return {
        '평가액': value,
        '순자산가치': net_asset_value_per_share,
        '순손익가치': net_profit_value_per_share,
        '가중치': weights,
        '근거': '§63①1나, 시행령§54',
    }


def evaluate_max_shareholder_premium(
    *,
    base_value: int,
    is_max_shareholder: bool = True,
    is_sme: bool = False,
    is_mid_sized: bool = False,
    has_3yr_loss: bool = False,
) -> dict:
    """최대주주 할증평가 (§63③).

    최대주주 등의 주식: 평가액 × 20% 할증
    중소·중견기업, 3년 연속 결손 법인 등은 제외

    Args:
        base_value: 기본 평가액
        is_max_shareholder: 최대주주/최대출자자 여부
        is_sme: 중소기업 여부
        is_mid_sized: 중견기업 여부
        has_3yr_loss: 3년 연속 결손금 여부

    Returns:
        dict: {평가액, 할증여부, 할증액, 근거}
    """
    excluded = is_sme or is_mid_sized or has_3yr_loss

    if not is_max_shareholder or excluded:
        return {
            '평가액': base_value,
            '할증여부': False,
            '할증액': 0,
            '제외사유': '중소기업' if is_sme else ('중견기업' if is_mid_sized else ('3년결손' if has_3yr_loss else '비최대주주')),
            '근거': '§63③',
        }

    premium = int(base_value * 0.20)
    return {
        '평가액': base_value + premium,
        '할증여부': True,
        '할증액': premium,
        '근거': '§63③',
    }


def evaluate_deposit(
    *,
    principal: int,
    accrued_interest: int = 0,
    withholding_tax: int = 0,
) -> dict:
    """예금 등 평가 (§63④).

    평가액 = 예입총액 + 미수이자 - 원천징수세액

    Args:
        principal: 예입총액
        accrued_interest: 경과 미수이자
        withholding_tax: 원천징수세액 상당

    Returns:
        dict: {평가액, 근거}
    """
    value = principal + accrued_interest - withholding_tax
    return {
        '평가액': value,
        '예입총액': principal,
        '미수이자': accrued_interest,
        '원천징수세액': withholding_tax,
        '근거': '§63④',
    }


# ══════════════════════════════════════════════
# Ch04. 신고·납부
# ══════════════════════════════════════════════

def get_inheritance_filing_deadline(
    *,
    death_date: date,
    is_foreign_address: bool = False,
) -> dict:
    """상속세 신고기한 (§67).

    사망일 속하는 달 말일 + 6개월 (외국 주소 9개월)

    Args:
        death_date: 사망일 (상속개시일)
        is_foreign_address: 피상속인/상속인 외국 주소 여부

    Returns:
        dict: {신고기한, 상속개시일, 외국주소여부, 근거}
    """
    months = 9 if is_foreign_address else 6

    # 말일 계산
    month_end_month = death_date.month
    month_end_year = death_date.year

    # 달 말일로 이동
    if month_end_month == 12:
        month_end = date(month_end_year, 12, 31)
    else:
        month_end = date(month_end_year, month_end_month + 1, 1)
        from datetime import timedelta
        month_end = month_end - timedelta(days=1)

    # +N개월
    target_month = month_end.month + months
    target_year = month_end.year
    while target_month > 12:
        target_month -= 12
        target_year += 1

    # 해당 월의 말일
    if target_month == 12:
        deadline = date(target_year, 12, 31)
    else:
        deadline = date(target_year, target_month + 1, 1) - timedelta(days=1)

    return {
        '신고기한': deadline.isoformat(),
        '상속개시일': death_date.isoformat(),
        '외국주소여부': is_foreign_address,
        '기간': f'{months}개월',
        '근거': '§67',
    }


def calculate_installment_payment(
    *,
    tax_payable: int,
    is_inheritance: bool = True,
    is_family_business: bool = False,
    is_special_gift: bool = False,
) -> dict:
    """연부연납 안내 (§71).

    요건: 납부세액 2천만원 초과
    상속: 일반 10년, 가업상속 20년(거치10+연부10)
    증여: 일반 5년, 조특법§30의6 15년

    Args:
        tax_payable: 납부세액
        is_inheritance: 상속세 여부 (False면 증여세)
        is_family_business: 가업상속/중소중견기업 상속 여부
        is_special_gift: 조특법 §30의6 적용 여부

    Returns:
        dict: {연부연납가능, 최대기간, 각회최소, 근거}
    """
    if tax_payable <= 20_000_000:
        return {
            '연부연납가능': False,
            '사유': f'납부세액 {tax_payable:,}원 ≤ 2천만원',
            '근거': '§71①',
        }

    if is_inheritance:
        if is_family_business:
            max_years = 20
            note = '가업상속: 허가일부터 20년 또는 거치10년+연부10년'
        else:
            max_years = 10
            note = '일반상속: 허가일부터 10년'
    else:
        if is_special_gift:
            max_years = 15
            note = '조특법§30의6 증여: 허가일부터 15년'
        else:
            max_years = 5
            note = '일반증여: 허가일부터 5년'

    return {
        '연부연납가능': True,
        '납부세액': tax_payable,
        '최대기간': f'{max_years}년',
        '각회최소': '1천만원 초과',
        '안내': note,
        '근거': '§71',
    }


def check_payment_in_kind_eligibility(
    *,
    tax_payable: int,
    real_estate_and_securities: int,
    total_estate: int,
    financial_assets: int = 0,
) -> dict:
    """물납 요건 판정 (§73).

    상속세만 해당 (증여세 불가).
    요건 3가지 모두 충족:
    1. 부동산+유가증권 > 상속재산 50%
    2. 납부세액 > 2천만
    3. 납부세액 > 금융재산

    Args:
        tax_payable: 상속세 납부세액
        real_estate_and_securities: 부동산+유가증권 가액
        total_estate: 총상속재산 가액
        financial_assets: 금융재산 가액

    Returns:
        dict: {물납가능, 요건충족, 근거}
    """
    requirements = {
        '부동산유가증권_50%초과': real_estate_and_securities > total_estate * 0.5,
        '납부세액_2천만초과': tax_payable > 20_000_000,
        '납부세액_금융재산초과': tax_payable > financial_assets,
    }

    all_met = all(requirements.values())

    return {
        '물납가능': all_met,
        '요건충족': requirements,
        '부동산유가증권비율': round(real_estate_and_securities / total_estate * 100, 1) if total_estate > 0 else 0,
        '근거': '§73',
    }
