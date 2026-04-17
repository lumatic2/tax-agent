"""세액 계산 엔진 — 2024년 귀속 종합소득세 세율표 기준

세율표 (소득세법 제55조):
  1,400만원 이하        6%   누진공제 0
  1,400만~5,000만원    15%   누진공제 1,260,000
  5,000만~8,800만원    24%   누진공제 5,760,000
  8,800만~1.5억원      35%   누진공제 15,440,000
  1.5억~3억원          38%   누진공제 19,940,000
  3억~5억원            40%   누진공제 25,940,000
  5억~10억원           42%   누진공제 35,940,000
  10억원 초과          45%   누진공제 65,940,000
"""

from datetime import date
from typing import Optional


def _brackets_2024():
    # (상한, 세율, 누진공제액) — 상한 None = 최고구간
    return [
        (14_000_000,   0.06,  0),
        (50_000_000,   0.15,  1_260_000),
        (88_000_000,   0.24,  5_760_000),
        (150_000_000,  0.35,  15_440_000),
        (300_000_000,  0.38,  19_940_000),
        (500_000_000,  0.40,  25_940_000),
        (1_000_000_000, 0.42, 35_940_000),
        (None,          0.45, 65_940_000),
    ]


def calculate_employment_income_deduction(gross_salary):
    """근로소득공제 계산 (소득세법 제47조).

    총급여에서 공제할 근로소득공제액을 반환한다.

    구간:
        ~500만원        70%
        500~1,500만원   40%  (+ 350만원)
        1,500~4,500만원 15%  (+ 750만원)
        4,500~1억원      5%  (+ 1,200만원)
        1억원 초과      상한 1,475만원
    """
    gross_salary = int(gross_salary)
    if gross_salary <= 5_000_000:
        return int(gross_salary * 0.70)
    elif gross_salary <= 15_000_000:
        return 3_500_000 + int((gross_salary - 5_000_000) * 0.40)
    elif gross_salary <= 45_000_000:
        return 7_500_000 + int((gross_salary - 15_000_000) * 0.15)
    elif gross_salary <= 100_000_000:
        return 12_000_000 + int((gross_salary - 45_000_000) * 0.05)
    else:
        return 14_750_000  # 상한 1,475만원


def calculate_employee_discount_taxable(market_price: int, discount_price: int, year: int = 2025) -> dict:
    """임직원 자사·계열사 제품 할인 구입 시 근로소득 과세금액 계산.

    2025년 이후 (소득세법 시행령 §38①16호 개정):
        비과세 한도 = max(시가 × 20%, 연 240만원)
        단, 재판매 금지 조건 충족 시만 비과세 적용

    2024년 이전:
        소득세법 시행규칙 §20의2: 할인율 50% 이하이면 비과세

    Args:
        market_price: 시가 (원)
        discount_price: 실제 구입가 (원)
        year: 귀속연도

    Returns:
        dict: {할인액, 비과세한도, 과세금액}
    """
    discount_amount = market_price - discount_price
    if discount_amount <= 0:
        return {'할인액': 0, '비과세한도': 0, '과세금액': 0}

    if year >= 2025:
        # 2025년 이후: max(시가×20%, 연240만원)
        exempt_limit = max(int(market_price * 0.20), 2_400_000)
    else:
        # 2024년 이전: 할인율 50% 이하면 전액 비과세
        discount_rate = discount_amount / market_price
        exempt_limit = discount_amount if discount_rate <= 0.50 else 0

    taxable = max(discount_amount - exempt_limit, 0)
    return {
        '할인액': discount_amount,
        '비과세한도': min(exempt_limit, discount_amount),
        '과세금액': taxable,
    }


def calculate_nontaxable_employment_income(items: dict[str, int] | list[dict], year: int = 2025) -> dict:
    """근로소득 지급 항목별 비과세 금액과 총급여를 계산한다.

    소득세법 §12(3) 기준의 대표 비과세 근로소득 항목을 지원한다.
    각 항목의 연간 지급액과 조건값을 받아 항목별 비과세/과세 금액을 계산하고,
    총지급액에서 비과세 합계를 차감한 총급여를 반환한다.

    Args:
        items: 지급 항목 리스트.
            각 항목 예시:
            {
                "type": "식대",
                "amount": 2_400_000,
                "meal_provided": False,
                "months": 12,
            }
        year: 귀속연도. 현재 구현은 2025년 기준 한도를 적용한다.

    Returns:
        {
            "items": [
                {"type": str, "total": int, "nontaxable": int, "taxable": int},
                ...
            ],
            "total_paid": int,
            "total_nontaxable": int,
            "gross_salary": int,
        }
    """
    monthly_limits = {
        "자가운전보조금": 200_000,
        "식대": 200_000,
        "보육수당": 200_000,
        "연구보조비": 200_000,
        "야간근무수당": 200_000,
        "벽지수당": 60_000,
        "위험수당": 200_000,
        "출산보육수당": 200_000,
        "국외근로소득_일반": 1_000_000,
        "국외근로소득_건설": 3_000_000,
    }
    annual_limits = {
        "직무발명보상금": 7_000_000,
        "생산직야간근로수당": 2_400_000,
    }
    fully_nontaxable_types = {
        "출산지원금",
        "실업급여",
        "육아휴직급여",
        "사택제공이익",
        "학자금",
    }

    if isinstance(items, dict):
        income_by_type = {str(key): int(value) for key, value in items.items()}
        result_details: dict[str, dict[str, int]] = {}
        taxable_income = 0
        total_paid = 0
        total_nontaxable = 0
        handled_types: set[str] = set()

        for item_type, monthly_limit in monthly_limits.items():
            received = income_by_type.get(item_type, 0)
            if received <= 0:
                continue
            nontaxable = min(received, monthly_limit)
            taxable = received - nontaxable
            taxable_income += taxable
            total_paid += received
            total_nontaxable += nontaxable
            result_details[item_type] = {
                "수령액": received,
                "비과세": nontaxable,
                "과세": taxable,
            }
            handled_types.add(item_type)

        for item_type, annual_limit in annual_limits.items():
            received = income_by_type.get(item_type, 0)
            if received <= 0:
                continue
            nontaxable = min(received, annual_limit)
            taxable = received - nontaxable
            taxable_income += taxable
            total_paid += received
            total_nontaxable += nontaxable
            result_details[item_type] = {
                "수령액": received,
                "비과세": nontaxable,
                "과세": taxable,
            }
            handled_types.add(item_type)

        for item_type, received in income_by_type.items():
            if item_type in handled_types:
                continue
            total_paid += received
            taxable_income += received
            result_details[item_type] = {
                "수령액": received,
                "비과세": 0,
                "과세": received,
            }

        _ = year

        return {
            **result_details,
            "총수령액": total_paid,
            "총비과세": total_nontaxable,
            "총과세": taxable_income,
            "총급여": taxable_income,
            "비고": "월 한도·연 한도를 반영한 2024년 귀속 프로젝트 계산 결과",
        }

    result_items = []
    total_paid = 0
    total_nontaxable = 0

    for item in items:
        item_type = str(item.get("type", "기타"))
        amount = int(item.get("amount", 0))
        months = int(item.get("months", 12))

        if amount < 0:
            raise ValueError("amount는 0 이상이어야 합니다.")
        if months < 0:
            raise ValueError("months는 0 이상이어야 합니다.")

        if item_type in fully_nontaxable_types:
            nontaxable = amount
        elif item_type == "자가운전보조금":
            if bool(item.get("own_vehicle", False)):
                nontaxable = min(amount, monthly_limits[item_type] * months)
            else:
                nontaxable = 0
        elif item_type == "식대":
            if not bool(item.get("meal_provided", False)):
                nontaxable = min(amount, monthly_limits[item_type] * months)
            else:
                nontaxable = 0
        elif item_type == "보육수당":
            if int(item.get("child_age", 999)) <= 6:
                nontaxable = min(amount, monthly_limits[item_type] * months)
            else:
                nontaxable = 0
        elif item_type in annual_limits:
            nontaxable = min(amount, annual_limits[item_type])
        elif item_type in monthly_limits:
            nontaxable = min(amount, monthly_limits[item_type] * months)
        else:
            nontaxable = 0

        taxable = amount - nontaxable
        result_items.append(
            {
                "type": item_type,
                "total": amount,
                "nontaxable": nontaxable,
                "taxable": taxable,
            }
        )
        total_paid += amount
        total_nontaxable += nontaxable

    _ = year

    return {
        "items": result_items,
        "total_paid": total_paid,
        "total_nontaxable": total_nontaxable,
        "gross_salary": total_paid - total_nontaxable,
    }


def calculate_simplified_withholding(
    monthly_salary: int,
    dependents: int = 1,
    adjustment_rate: float = 1.0,
    nontaxable_amount: int = 0,
) -> dict:
    """근로소득 간이세액표에 준한 프로젝트 원천징수 추정치를 계산한다."""
    monthly_salary = max(int(monthly_salary), 0)
    dependents = max(int(dependents), 1)
    nontaxable_amount = max(int(nontaxable_amount), 0)

    monthly_taxable_salary = max(monthly_salary - nontaxable_amount, 0)
    annual_salary = monthly_taxable_salary * 12

    if annual_salary <= 5_000_000:
        annual_deduction = int(annual_salary * 0.70)
    elif annual_salary <= 15_000_000:
        annual_deduction = 3_500_000 + int((annual_salary - 5_000_000) * 0.40)
    elif annual_salary <= 45_000_000:
        annual_deduction = 7_500_000 + int((annual_salary - 15_000_000) * 0.15)
    elif annual_salary <= 100_000_000:
        annual_deduction = 12_000_000 + int((annual_salary - 45_000_000) * 0.05)
    else:
        annual_deduction = 14_750_000 + int((annual_salary - 100_000_000) * 0.02)
    annual_deduction = min(annual_deduction, 20_000_000)

    monthly_earned_income_deduction = int(annual_deduction / 12)
    monthly_basic_deduction = int(1_500_000 * dependents / 12)
    monthly_tax_base = max(
        monthly_taxable_salary - monthly_earned_income_deduction - monthly_basic_deduction,
        0,
    )
    annual_tax_base = monthly_tax_base * 12

    if annual_tax_base <= 14_000_000:
        annual_computed_tax = int(annual_tax_base * 0.06)
    elif annual_tax_base <= 50_000_000:
        annual_computed_tax = 840_000 + int((annual_tax_base - 14_000_000) * 0.15)
    elif annual_tax_base <= 88_000_000:
        annual_computed_tax = 6_240_000 + int((annual_tax_base - 50_000_000) * 0.24)
    elif annual_tax_base <= 150_000_000:
        annual_computed_tax = 15_360_000 + int((annual_tax_base - 88_000_000) * 0.35)
    elif annual_tax_base <= 300_000_000:
        annual_computed_tax = 37_060_000 + int((annual_tax_base - 150_000_000) * 0.38)
    elif annual_tax_base <= 500_000_000:
        annual_computed_tax = 94_060_000 + int((annual_tax_base - 300_000_000) * 0.40)
    elif annual_tax_base <= 1_000_000_000:
        annual_computed_tax = 174_060_000 + int((annual_tax_base - 500_000_000) * 0.42)
    else:
        annual_computed_tax = 384_060_000 + int((annual_tax_base - 1_000_000_000) * 0.45)

    if annual_computed_tax <= 1_300_000:
        annual_tax_credit = int(annual_computed_tax * 0.55)
    else:
        annual_tax_credit = 715_000 + int((annual_computed_tax - 1_300_000) * 0.30)

    if annual_salary <= 33_000_000:
        credit_limit = 740_000
    elif annual_salary <= 70_000_000:
        credit_limit = max(740_000 - int((annual_salary - 33_000_000) * 8 / 1000), 660_000)
    else:
        credit_limit = 660_000
    annual_tax_credit = min(annual_tax_credit, credit_limit)

    annual_final_tax = max(annual_computed_tax - annual_tax_credit, 0)
    monthly_final_tax = int(annual_final_tax / 12)
    withholding_tax = int(monthly_final_tax * float(adjustment_rate) / 10) * 10
    local_income_tax = int(withholding_tax * 0.10 / 10) * 10

    return {
        "월급여": monthly_salary,
        "비과세": nontaxable_amount,
        "월과세급여": monthly_taxable_salary,
        "월근로소득공제": monthly_earned_income_deduction,
        "월기본공제": monthly_basic_deduction,
        "월과세표준": monthly_tax_base,
        "연환산과세표준": annual_tax_base,
        "연산출세액": annual_computed_tax,
        "연근로소득세액공제": annual_tax_credit,
        "연결정세액": annual_final_tax,
        "월결정세액": monthly_final_tax,
        "원천징수세액": withholding_tax,
        "지방소득세": local_income_tax,
        "비고": "소득세법 §129 간이세액표를 근로소득공제·기본공제·세액공제로 단순화한 프로젝트 추정치",
    }


def calculate_wage_income_tax(gross_salary, extra_deductions=None):
    """근로소득자 전용 원스톱 세액 계산 (소득세법 제47조, 제50조, 제55조).

    총급여부터 최종납부세액까지 한 번에 계산한다.

    Args:
        gross_salary: 총급여 (연봉에서 비과세 제외한 금액)
        extra_deductions: 추가 소득공제 dict (없으면 기본공제만 적용)
            {
                "국민연금": 2_640_000,    # 납부한 국민연금 보험료
                "건강보험": 1_200_000,    # 납부한 건강보험료
                "신용카드": 500_000,      # 신용카드 소득공제
                # 기타 소득공제 항목 추가 가능
            }

    Returns:
        {
            "총급여": int,
            "근로소득공제": int,
            "근로소득금액": int,
            "소득공제_내역": dict,   # 기본공제(150만) + extra_deductions
            "소득공제_합계": int,
            "과세표준": int,
            "산출세액": int,
            "적용세율": float,
            "지방소득세": int,
            "총납부예상": int,
        }

    사용 예시:
        # 총급여 6,000만원, 국민연금 264만원 납부
        result = calculate_wage_income_tax(60_000_000, {"국민연금": 2_640_000})
    """
    gross_salary = int(gross_salary)
    extra_deductions = extra_deductions or {}

    # 1. 근로소득공제 (소득세법 제47조)
    emp_deduction = calculate_employment_income_deduction(gross_salary)
    earned_income = gross_salary - emp_deduction

    # 2. 소득공제 (기본공제 본인 150만원은 항상 포함 — 소득세법 제50조)
    deduction_detail = {"기본공제(본인)": 1_500_000}
    deduction_detail.update({k: int(v) for k, v in extra_deductions.items()})
    total_deductions = sum(deduction_detail.values())

    # 3. 과세표준
    taxable_income = max(earned_income - total_deductions, 0)

    # 4. 산출세액 및 지방소득세
    tax_result = calculate_tax(taxable_income)
    local_tax = calculate_local_tax(tax_result["산출세액"])

    return {
        "총급여": gross_salary,
        "근로소득공제": emp_deduction,
        "근로소득금액": earned_income,
        "소득공제_내역": deduction_detail,
        "소득공제_합계": total_deductions,
        "과세표준": taxable_income,
        "산출세액": tax_result["산출세액"],
        "적용세율": tax_result["적용세율"],
        "지방소득세": local_tax,
        "총납부예상": tax_result["산출세액"] + local_tax,
    }


def calculate_tax(taxable_income):
    """과세표준으로 산출세액 계산.

    Returns:
        {"산출세액": int, "적용세율": float, "누진공제액": int}
    """
    taxable_income = int(taxable_income)
    if taxable_income < 0:
        raise ValueError("taxable_income는 0 이상이어야 합니다.")

    for upper, rate, deduction in _brackets_2024():
        if upper is None or taxable_income <= upper:
            tax = int(taxable_income * rate - deduction)
            computed = max(tax, 0)
            return {
                "산출세액": computed,
                "적용세율": rate,
                "누진공제액": deduction,
                "지방소득세": int(computed * 0.10),
            }


def calculate_local_tax(income_tax):
    """지방소득세 = 소득세의 10%"""
    return int(max(int(income_tax), 0) * 0.10)


def calculate_financial_income(
    interest: int = 0,
    dividend: int = 0,
    gross_up_eligible_dividend: int = 0,
    grossup_mode: str = "full",
) -> dict:
    """금융소득(이자·배당소득) 계산 및 종합과세 판정 (소득세법 §16, §17, §14③6, §62, 2024년 귀속).

    [법령 근거 — 법제처 API 직접 조회 확인 (2026-04-01)]
    §16②: 이자소득금액 = 총수입금액 (필요경비 공제 없음)
    §17③: 배당소득금액 = 총수입금액 + Gross-up(×10%)
           Gross-up 대상: 내국법인 일반배당(§17①1~4), 집합투자기구 일부(§17①5)
           Gross-up 제외: 의제배당 일부, 재평가적립금 배당, 자본준비금 감액배당 등 §17③1~7
    §14③6: 이자+배당 합계 2,000만 이하 → 분리과세(원천징수 14%), 종합과세 제외
            2,000만 초과 → 전액 종합과세
    §62: 종합과세 시 산출세액 = Max(①, ②)
         ①: 일반 누진세율 (종합소득 전체에 기본세율 적용)
         ②: 2,000만×14% + (종합과세기준금액 초과분 + 다른 종합소득) × 기본세율

    Args:
        interest: 이자소득 총수입금액 (원)
        dividend: 배당소득 총수입금액 (원)
        gross_up_eligible_dividend: Gross-up 대상 배당금액 (원)
            내국법인 일반배당 해당분. 모르면 dividend 전액으로 보수적 적용 가능.

    Returns:
        dict: {이자소득금액, 배당소득금액, Gross_up금액, 금융소득합계,
               종합과세여부, 분리과세세액, 종합과세편입금액, 비고}
    """
    THRESHOLD = 20_000_000  # §14③6 종합과세기준금액
    WITHHOLDING_RATE = 0.14  # §129①1라목 원천징수세율

    interest_income = interest                     # §16② 필요경비 없음
    raw_total = interest + dividend                # Gross-up 前 원금

    if raw_total <= THRESHOLD:
        # §14③6: 분리과세 — 종합소득 미합산, Gross-up 적용 안 함
        sep_tax = int(raw_total * WITHHOLDING_RATE)
        return {
            '이자소득금액': interest_income,
            '배당소득금액': dividend,
            'Gross_up금액': 0,
            '금융소득합계': raw_total,
            '종합과세여부': False,
            '분리과세세액': sep_tax,
            '종합과세편입금액': 0,
            '비고': f'이자+배당 {raw_total:,}원 ≤ 2,000만 → 분리과세(14%)',
        }

    # 종합과세 — Gross-up 계산 방식 두 가지
    #   full: §17③ 문언 그대로 Gross-up 대상 배당 **전액** × 10% 가산 (기본값, 교재 다수)
    #   threshold: 비Gross-up 소득을 2천만 한도에 우선 배치 후 Gross-up 대상 잔여분만 10% 가산
    #              (세무사·CPA 시험 기출 실무 해석)
    if grossup_mode == "threshold":
        non_grossup_base = interest + max(dividend - gross_up_eligible_dividend, 0)
        remaining_limit = max(THRESHOLD - non_grossup_base, 0)
        grossup_taxable = max(gross_up_eligible_dividend - remaining_limit, 0)
        gross_up = int(grossup_taxable * 0.10)
        mode_note = (
            f'Gross-up 대상 {gross_up_eligible_dividend:,}원 중 2천만 초과분 '
            f'{grossup_taxable:,}원 × 10% = {gross_up:,}원 (threshold 모드)'
        )
    else:  # "full"
        gross_up = int(gross_up_eligible_dividend * 0.10)
        mode_note = f'Gross-up 대상 {gross_up_eligible_dividend:,}원 × 10% = {gross_up:,}원 (full 모드)'

    dividend_income = dividend + gross_up
    total = interest_income + dividend_income

    return {
        '이자소득금액': interest_income,
        '배당소득금액': dividend_income,
        'Gross_up금액': gross_up,
        '금융소득합계': total,
        '종합과세여부': True,
        '§62_비교필요': True,
        '분리과세세액': None,
        '종합과세편입금액': total,
        '비고': f'이자+배당 원금 {raw_total:,}원 > 2,000만 → 종합과세. {mode_note}',
    }


def compare_financial_income_tax(
    other_comprehensive_income: int,
    financial_income: int,
    total_deductions: int,
) -> dict:
    """§62 금융소득 종합과세 시 비교산출세액 계산.

    금융소득(이자+배당)이 2,000만원을 초과하여 종합과세되는 경우,
    산출세액은 아래 두 방법 중 큰 금액을 적용한다.

    - 방법①: 전체 종합소득(금융소득 포함)에 기본 누진세율 적용
    - 방법②: 2,000만원×14% + (금융소득 중 2,000만원 초과분 + 금융소득 외 종합소득) × 기본 누진세율

    Args:
        other_comprehensive_income: 금융소득 외 종합소득 금액(원)
        financial_income: 금융소득 합계(이자+배당, 원)
        total_deductions: 종합소득 소득공제 합계(원)

    Returns:
        dict: {
            '방법①_산출세액': int,
            '방법②_산출세액': int,
            '최종산출세액': int,
            '적용방법': str,  # '방법①' 또는 '방법②'
        }
    """
    THRESHOLD = 20_000_000

    other_comprehensive_income = int(other_comprehensive_income)
    financial_income = int(financial_income)
    total_deductions = int(total_deductions)

    # 방법①: 전체 종합소득(금융소득 포함)에 기본 누진세율 적용
    method1_base = max(other_comprehensive_income + financial_income - total_deductions, 0)
    method1_tax = calculate_tax(method1_base)['산출세액']

    # 방법②: 2,000만원×14% + (초과분 + 금융소득 외 종합소득) × 기본 누진세율
    sep_tax = int(THRESHOLD * 0.14)
    excess_financial = financial_income - THRESHOLD
    progressive_base = max(other_comprehensive_income + excess_financial - total_deductions, 0)
    progressive_tax = calculate_tax(progressive_base)['산출세액']
    method2_tax = sep_tax + progressive_tax

    final_tax = max(method1_tax, method2_tax)
    applied = '방법①' if method1_tax >= method2_tax else '방법②'

    return {
        '방법①_산출세액': int(method1_tax),
        '방법②_산출세액': int(method2_tax),
        '최종산출세액': int(final_tax),
        '적용방법': applied,
    }


def calculate_dividend_tax_credit(
    gross_up: int,
    dividend_income: int,
    total_financial_income: int,
) -> dict:
    """배당세액공제 계산 (소득세법 §56, 법제처 API 확인 완료 2026-04-01).

    [법령 근거]
    §56①: 종합소득금액에 §17③ 단서가 적용되는 배당소득금액이 합산된 경우,
           총수입금액에 더한 금액(= Gross-up 금액)을 산출세액에서 공제.
    §56④: 배당세액공제 대상 = 종합과세기준금액(2,000만원) 초과분의 배당소득금액만 해당.
           → 공제액 = Gross-up × (종합과세 대상 배당소득 / 전체 배당소득금액)

    ※ 이 함수는 calculate_financial_income()이 종합과세여부=True를 반환한 경우에만 호출한다.
       분리과세(2,000만 이하)면 배당세액공제 없음.

    Args:
        gross_up: §17③에 따라 배당소득금액에 가산된 Gross-up 금액 (= Gross-up 대상 배당 × 10%)
        dividend_income: 배당소득금액 (총수입금액 + Gross-up, §17③ 적용 후)
        total_financial_income: 금융소득 합계 (이자소득금액 + 배당소득금액)
            — §56④ 적용: 2,000만 초과분 중 배당 비중 계산에 사용

    Returns:
        dict: {
            '배당세액공제액': int,       # 산출세액에서 차감할 금액
            '공제대상_배당소득': int,    # §56④ — 2,000만 초과분 중 배당 해당분
            'Gross_up금액': int,
            '근거': str,
        }

    사용 예시:
        fin = calculate_financial_income(interest=5_000_000, dividend=20_000_000,
                                         gross_up_eligible_dividend=20_000_000)
        # gross_up = 2,000,000, dividend_income = 22,000,000, total = 27,000,000 → 종합과세
        credit = calculate_dividend_tax_credit(
            gross_up=fin['Gross_up금액'],
            dividend_income=fin['배당소득금액'],
            total_financial_income=fin['금융소득합계'],
        )
    """
    THRESHOLD = 20_000_000  # §14③6 종합과세기준금액

    if total_financial_income <= THRESHOLD or gross_up <= 0:
        # 분리과세이거나 Gross-up 없으면 공제 없음
        return {
            '배당세액공제액': 0,
            '공제대상_배당소득': 0,
            'Gross_up금액': gross_up,
            '근거': '종합과세기준금액 이하 또는 Gross-up 대상 배당 없음 — 배당세액공제 해당 없음',
        }

    # §56④: 2,000만 초과분 중 배당소득이 차지하는 비율로 안분
    # 종합과세 편입 금액 = total_financial_income (전액 종합과세)
    # 이 중 배당소득 비중 = dividend_income / total_financial_income
    # 2,000만 초과분 = total_financial_income - THRESHOLD
    excess = total_financial_income - THRESHOLD

    if dividend_income <= 0 or total_financial_income <= 0:
        return {
            '배당세액공제액': 0,
            '공제대상_배당소득': 0,
            'Gross_up금액': gross_up,
            '근거': '배당소득금액 0 — 배당세액공제 해당 없음',
        }

    # 초과분 중 배당에 귀속되는 금액 (배당 비중으로 안분)
    dividend_ratio = dividend_income / total_financial_income
    eligible_dividend = int(excess * dividend_ratio)  # §56④ 공제 대상 배당소득

    # 공제액 = Gross-up × (공제대상 배당소득 / 배당소득금액)
    # = 공제대상 배당소득의 Gross-up 해당분
    credit = int(gross_up * (eligible_dividend / dividend_income))

    return {
        '배당세액공제액': credit,
        '공제대상_배당소득': eligible_dividend,
        'Gross_up금액': gross_up,
        '근거': (
            f'§56①④: 금융소득 {total_financial_income:,}원 중 2,000만 초과분 {excess:,}원 × '
            f'배당비중 {dividend_ratio:.1%} = 공제대상 배당소득 {eligible_dividend:,}원, '
            f'Gross-up 안분공제액 {credit:,}원'
        ),
    }


def calculate_business_income(
    revenue: int,
    industry_code: str,
    method: str = 'auto',
    prev_year_revenue: int = 0,
    major_expenses: dict = None,
    actual_expenses: int = 0
) -> dict:
    """사업소득금액 계산 (소득세법 제19조, 국세청 고시 제2025-6호(2024년 귀속 경비율)).

    업종별 단순/기준경비율은 `data/expense_rate_2024.json`을 참조한다.

    Returns:
        {"수입금액": int, "업종코드": str, "업종명": str, "적용방법": str,
         "단순경비율": float|None, "기준경비율": float|None, "필요경비": int,
         "사업소득금액": int, "소득률": float}
    """
    import json
    import os

    revenue = int(revenue)
    if revenue < 0:
        raise ValueError("revenue는 0 이상이어야 합니다.")

    industry_code = str(industry_code)
    method = str(method)
    prev_year_revenue = int(prev_year_revenue)
    actual_expenses = int(actual_expenses)
    major_expenses = major_expenses or {}

    if method not in ("auto", "단순", "기준", "실제"):
        raise ValueError("method는 'auto'|'단순'|'기준'|'실제' 중 하나여야 합니다.")

    _DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
    rate_path = os.path.join(_DATA_DIR, "expense_rate_2024.json")

    with open(rate_path, "r", encoding="utf-8") as f:
        rate_table = json.load(f)

    thresholds = rate_table.get("_threshold", {})
    industry = rate_table.get(industry_code)
    if not isinstance(industry, dict):
        raise ValueError("알 수 없는 업종코드입니다.")

    industry_name = industry.get("name", "")
    category = industry.get("category", "")
    simple_rate = industry.get("단순경비율")
    standard_rate = industry.get("기준경비율")

    if method == "auto":
        threshold = thresholds.get(category)
        if threshold is None:
            method = "기준"
        else:
            method = "단순" if prev_year_revenue < int(threshold) else "기준"

    if method == "단순":
        if simple_rate is None:
            raise ValueError("단순경비율 정보가 없습니다.")
        needed_expenses = int(revenue * float(simple_rate))
        applied_method = "단순경비율"
        out_simple_rate = float(simple_rate)
        out_standard_rate = None

    elif method == "기준":
        if standard_rate is None:
            raise ValueError("기준경비율 정보가 없습니다.")

        major_sum = (
            int(major_expenses.get("매입비용", 0))
            + int(major_expenses.get("임차료", 0))
            + int(major_expenses.get("인건비", 0))
        )
        needed_expenses = major_sum + int(revenue * float(standard_rate))
        applied_method = "기준경비율"
        out_simple_rate = None
        out_standard_rate = float(standard_rate)

    else:  # method == "실제"
        if actual_expenses < 0:
            raise ValueError("actual_expenses는 0 이상이어야 합니다.")
        needed_expenses = actual_expenses
        applied_method = "실제경비"
        out_simple_rate = None
        out_standard_rate = None

    business_income = int(revenue - int(needed_expenses))
    income_rate = (business_income / revenue) if revenue else 0.0

    return {
        "수입금액": revenue,
        "업종코드": industry_code,
        "업종명": industry_name,
        "적용방법": applied_method,
        "단순경비율": out_simple_rate,
        "기준경비율": out_standard_rate,
        "필요경비": int(needed_expenses),
        "사업소득금액": business_income,
        "소득률": float(income_rate),
    }


def calculate_pension_income(
    total_pension: int,
    pension_type: str = '사적',
    separation_tax: bool | None = None,
) -> dict:
    """연금소득금액 계산 (소득세법 §20의3 연금소득, §47의2 연금소득공제, 2024년 귀속).

    [법령 출처 — 추후 법제처 API 연결 시 검증 필요]
    §20의3: 연금소득 범위 (공적연금·사적연금)
    §47의2: 연금소득공제 구간
        총연금액 350만 이하 → 전액 공제
        350만 초과 700만 이하 → 350만 + 초과분×40%
        700만 초과 1,400만 이하 → 490만 + 초과분×20%
        1,400만 초과 → 630만 + 초과분×10% (한도 900만)
    §14③7: 사적연금 연 1,500만 이하 → 분리과세(15%) 선택 가능
             1,500만 초과 → 종합과세 의무

    Args:
        total_pension: 총연금액 (원) — 공적연금 또는 사적연금 합계
        pension_type: '공적' | '사적'
        separation_tax: 분리과세 선택 여부 (None=자동판정, True/False=강제)
            - 사적연금 1,500만 이하일 때만 선택 가능
            - 공적연금은 무조건 종합과세

    Returns:
        dict: {총연금액, 연금소득공제, 연금소득금액, 과세방식, 분리과세세율}
    """
    # §47의2 연금소득공제
    if total_pension <= 3_500_000:
        deduction = total_pension
    elif total_pension <= 7_000_000:
        deduction = 3_500_000 + int((total_pension - 3_500_000) * 0.40)
    elif total_pension <= 14_000_000:
        deduction = 4_900_000 + int((total_pension - 7_000_000) * 0.20)
    else:
        deduction = 6_300_000 + int((total_pension - 14_000_000) * 0.10)
    deduction = min(deduction, 9_000_000)  # 한도 900만

    pension_income = max(total_pension - deduction, 0)

    # 과세방식 판정
    if pension_type == '공적':
        tax_method = '종합과세'
        sep_rate = None
    else:
        threshold = 15_000_000
        if separation_tax is True and total_pension <= threshold:
            tax_method = '분리과세'
            sep_rate = 0.15
        elif separation_tax is False or total_pension > threshold:
            tax_method = '종합과세'
            sep_rate = None
        else:
            # auto: 1,500만 이하 → 분리과세 유리 여부는 Claude가 판단, 여기선 표시만
            tax_method = '분리과세선택가능' if total_pension <= threshold else '종합과세'
            sep_rate = 0.15 if total_pension <= threshold else None

    return {
        '총연금액': total_pension,
        '연금소득공제': deduction,
        '연금소득금액': pension_income,
        '연금유형': pension_type,
        '과세방식': tax_method,
        '분리과세세율': sep_rate,
        '분리과세세액': int(total_pension * sep_rate) if sep_rate else None,
    }


def _calculate_lottery_tax(prize_amount: int, ticket_cost: int = 0) -> dict:
    prize = int(prize_amount)
    cost = int(ticket_cost)
    income = max(prize - cost, 0)
    THRESHOLD = 300_000_000
    if income <= THRESHOLD:
        tax = int(income * 0.20)
        note = f'3억 이하: {income:,}원 × 20% = {tax:,}원'
    else:
        tax_below = int(THRESHOLD * 0.20)
        tax_above = int((income - THRESHOLD) * 0.33)
        tax = tax_below + tax_above
        note = f'3억×20%={tax_below:,}원 | {(income-THRESHOLD):,}원×33%={tax_above:,}원 | 합계={tax:,}원'
    local_tax = int(tax * 0.10)
    return {'당첨금액': prize, '필요경비': cost, '기타소득금액': income,
            '세율_3억이하': 0.20, '세율_3억초과': 0.33,
            '원천징수세액': tax, '지방소득세': local_tax, '비고': note}


def _calculate_slot_machine_tax(prize_amount: int) -> dict:
    prize = int(prize_amount)
    tax = int(prize * 0.30)
    local_tax = int(tax * 0.10)
    return {'당첨금액': prize, '기타소득금액': prize,
            '원천징수세액': tax, '지방소득세': local_tax,
            '비고': f'슬롯머신: {prize:,}원 × 30% = {tax:,}원'}


def calculate_other_income(
    gross_income: int,
    income_type: str = 'general',
    expense_ratio: float = 0.60,
    ticket_cost: int = 0,
) -> dict:
    """기타소득 원천징수세액 계산 (소득세법 §14②, §84, §87①2, 2024년 귀속)."""
    gross = int(gross_income)

    if income_type == 'lottery':
        result = _calculate_lottery_tax(gross, ticket_cost)
        return {
            '총수입금액': result['당첨금액'],
            '필요경비': result['필요경비'],
            '기타소득금액': result['기타소득금액'],
            '원천징수세율': '20%/33%',
            '원천징수세액': result['원천징수세액'],
            '지방소득세': result['지방소득세'],
            '소득유형': 'lottery',
            '비고': result['비고'],
        }

    if income_type == 'slot_machine':
        result = _calculate_slot_machine_tax(gross)
        return {
            '총수입금액': result['당첨금액'],
            '필요경비': 0,
            '기타소득금액': result['기타소득금액'],
            '원천징수세율': 0.30,
            '원천징수세액': result['원천징수세액'],
            '지방소득세': result['지방소득세'],
            '소득유형': 'slot_machine',
            '비고': result['비고'],
        }

    if income_type == 'pension_account':
        income_amount = gross
        tax = int(income_amount * 0.15)
        local_tax = int(tax * 0.10)
        return {
            '총수입금액': gross,
            '필요경비': 0,
            '기타소득금액': income_amount,
            '원천징수세율': 0.15,
            '원천징수세액': tax,
            '지방소득세': local_tax,
            '소득유형': 'pension_account',
            '비고': f'연금계좌 기타소득: {income_amount:,}원 × 15% = {tax:,}원',
        }

    expense = int(gross * float(expense_ratio))
    income_amount = max(gross - expense, 0)
    tax = int(income_amount * 0.20)
    local_tax = int(tax * 0.10)
    return {
        '총수입금액': gross,
        '필요경비': expense,
        '기타소득금액': income_amount,
        '원천징수세율': 0.20,
        '원천징수세액': tax,
        '지방소득세': local_tax,
        '소득유형': 'general',
        '비고': f'일반 기타소득: 필요경비 {expense:,}원, 기타소득금액 {income_amount:,}원 × 20% = {tax:,}원',
    }


def calculate_personal_deductions(persons: list) -> dict:
    """인적공제 계산 (소득세법 §50 기본공제, §51 추가공제, 2024년 귀속).

    Args:
        persons: list of dict, 각 항목:
            - relation: '본인'|'배우자'|'직계존속'|'직계비속'|'형제자매'|'위탁아동'
            - age: int (만 나이)
            - disabled: bool
            - single_parent: bool (본인에만 적용)
            - female_head: bool (본인에만 적용)
            - annual_income: int (기본값 0)
            - wage_only: bool (기본값 False)
    """
    basic_count = 0
    elderly_amount = 0      # 경로우대 (70세 이상) 1인당 100만
    disabled_amount = 0     # 장애인 1인당 200만
    female_head_amount = 0  # 부녀자 50만
    single_parent_amount = 0  # 한부모 100만
    warnings = []

    has_single_parent = any(p.get("single_parent") for p in persons)

    for p in persons:
        relation = p.get("relation", "")
        age = int(p.get("age", 0))
        disabled = bool(p.get("disabled", False))
        annual_income = int(p.get("annual_income", 0) or 0)
        wage_only = bool(p.get("wage_only", False))

        # 소득요건 (§50①3): 본인은 소득요건 없음
        if relation != "본인":
            if relation in {"배우자", "직계존속", "직계비속", "형제자매", "위탁아동"}:
                income_ok = True
                if annual_income > 1_000_000:
                    income_ok = bool(wage_only and annual_income <= 5_000_000)
                if not income_ok:
                    warnings.append(
                        f"부양가족 소득요건 미충족으로 기본공제 제외: relation={relation}, annual_income={annual_income}, wage_only={wage_only}"
                    )
                    continue

        # 기본공제 (§50): 본인·배우자·부양가족 1인당 150만
        basic_count += 1

        # 경로우대 (§51①1): 70세 이상
        if age >= 70:
            elderly_amount += 1_000_000

        # 장애인 (§51①2): 1인당 200만
        if disabled:
            disabled_amount += 2_000_000

        # 부녀자·한부모는 본인에만 적용
        if relation == "본인":
            if p.get("female_head"):
                if has_single_parent:
                    # 한부모와 중복 불가 — 한부모 우선 (§51①4 단서)
                    single_parent_amount = 1_000_000
                else:
                    female_head_amount = 500_000
            elif p.get("single_parent"):
                single_parent_amount = 1_000_000

    basic_amount = basic_count * 1_500_000
    additional_detail = {}
    if elderly_amount:
        additional_detail["경로우대"] = elderly_amount
    if disabled_amount:
        additional_detail["장애인"] = disabled_amount
    if female_head_amount:
        additional_detail["부녀자"] = female_head_amount
    if single_parent_amount:
        additional_detail["한부모"] = single_parent_amount

    additional_total = sum(additional_detail.values())

    return {
        "기본공제_인원": basic_count,
        "기본공제액": basic_amount,
        "추가공제_내역": additional_detail,
        "추가공제액": additional_total,
        "인적공제_합계": basic_amount + additional_total,
        "warnings": warnings,
    }


def calculate_special_deductions(
    income_data: dict,
    housing_loan_repayment: int = 0,
    mortgage_interest: int = 0,
    mortgage_fixed_rate: bool = False,
    mortgage_nonannuity: bool = False,
) -> dict:
    """특별소득공제 계산 (소득세법 §52, 2024년 귀속).

    Args:
        income_data:
            - gross_salary: 총급여
            - national_pension: 국민연금 (전액 공제)
            - health_insurance: 건강보험료 (전액 공제)
            - employment_insurance: 고용보험료 (전액 공제)
            - housing_fund: 주택자금공제 (한도 판단은 호출자 책임)
            - medical_expense: 의료비 지출액
            - education_expense: 교육비 지출액 (한도 판단은 호출자 책임)
            - donation: 기부금 (한도 판단은 호출자 책임)
        housing_loan_repayment:
            - 주택임차차입금 원리금 상환액 (40% 공제, 한도 400만)
        mortgage_interest:
            - 장기주택저당차입금 이자상환액 (전액 공제, 유형별 한도 적용)
        mortgage_fixed_rate:
            - 장기주택저당차입금 고정금리 여부
        mortgage_nonannuity:
            - 장기주택저당차입금 비거치식 분할상환 여부
    """
    gross_salary = int(income_data.get("gross_salary", 0))
    national_pension = int(income_data.get("national_pension", 0))
    health_insurance = int(income_data.get("health_insurance", 0))
    employment_insurance = int(income_data.get("employment_insurance", 0))
    housing_fund = int(income_data.get("housing_fund", 0))
    housing_loan_repayment = int(
        housing_loan_repayment or income_data.get("housing_loan_repayment", 0)
    )
    mortgage_interest = int(
        mortgage_interest or income_data.get("mortgage_interest", 0)
    )
    mortgage_fixed_rate = bool(
        mortgage_fixed_rate or income_data.get("mortgage_fixed_rate", False)
    )
    mortgage_nonannuity = bool(
        mortgage_nonannuity or income_data.get("mortgage_nonannuity", False)
    )
    medical_expense = int(income_data.get("medical_expense", 0))
    education_expense = int(income_data.get("education_expense", 0))
    donation = int(income_data.get("donation", 0))

    # 보험료공제 (§52①): 국민연금+건강보험+고용보험 전액
    insurance_deduction = national_pension + health_insurance + employment_insurance

    # 주택임차차입금 원리금 상환액 공제 (§52④): 상환액의 40%, 한도 400만
    housing_loan_repayment_deduction = min(int(housing_loan_repayment * 0.4), 4_000_000)

    if mortgage_fixed_rate and mortgage_nonannuity:
        mortgage_interest_limit = 20_000_000
    elif mortgage_fixed_rate or mortgage_nonannuity:
        mortgage_interest_limit = 15_000_000
    else:
        mortgage_interest_limit = 6_000_000
    mortgage_interest_deduction = min(mortgage_interest, mortgage_interest_limit)

    # 의료비공제 (§52②): (의료비 - 총급여×3%) 초과분, 한도 700만
    medical_threshold = int(gross_salary * 0.03)
    medical_deduction = min(max(medical_expense - medical_threshold, 0), 7_000_000)

    total = (
        insurance_deduction
        + housing_fund
        + housing_loan_repayment_deduction
        + mortgage_interest_deduction
        + medical_deduction
        + education_expense
        + donation
    )
    original_total = total
    apply_method = "특별공제"
    if total < 1_300_000:
        total = 1_300_000
        apply_method = "표준공제"

    return {
        "보험료공제": insurance_deduction,
        "주택자금공제": housing_fund,
        "housing_loan_repayment_deduction": housing_loan_repayment_deduction,
        "mortgage_interest_deduction": mortgage_interest_deduction,
        "mortgage_interest_limit": mortgage_interest_limit,
        "의료비공제": medical_deduction,
        "교육비공제": education_expense,
        "기부금공제": donation,
        "특별공제_합계": total,
        "적용방식": apply_method,
        "특별공제_합계_원래": original_total,
    }


def calculate_card_deduction(gross_salary: int, card_usage: dict) -> dict:
    """신용카드 소득공제 (조세특례제한법 §126의2, 2024년 귀속).

    Args:
        gross_salary: 총급여
        card_usage:
            - credit_card: 신용카드 사용액
            - debit_card: 체크카드·현금영수증 사용액
            - traditional_market: 전통시장 사용액
            - public_transit: 대중교통 사용액
    """
    gross_salary = int(gross_salary)
    credit = int(card_usage.get("credit_card", 0))
    debit = int(card_usage.get("debit_card", 0))
    market = int(card_usage.get("traditional_market", 0))
    transit = int(card_usage.get("public_transit", 0))

    total_usage = credit + debit + market + transit
    threshold = int(gross_salary * 0.25)  # 총급여 25% 초과분부터 공제

    # 공제대상: 전체 사용액에서 최저 사용금액(threshold) 차감
    # 순서: 신용카드(공제율 낮은 것) → 체크카드 → 전통시장 → 대중교통 순으로 threshold 소진
    remaining_threshold = threshold
    def consume(amount, threshold_left):
        used = min(amount, threshold_left)
        return amount - used, threshold_left - used

    credit_net, remaining_threshold = consume(credit, remaining_threshold)
    debit_net, remaining_threshold = consume(debit, remaining_threshold)
    market_net, remaining_threshold = consume(market, remaining_threshold)
    transit_net, _ = consume(transit, remaining_threshold)

    credit_deduction = int(credit_net * 0.15)
    debit_deduction = int(debit_net * 0.30)
    market_deduction = int(market_net * 0.40)
    transit_deduction = int(transit_net * 0.40)

    # 기본 한도
    if gross_salary <= 70_000_000:
        base_limit = 3_000_000
    elif gross_salary <= 120_000_000:
        base_limit = 2_500_000
    else:
        base_limit = 2_000_000

    # 전통시장·대중교통 각 300만 추가 한도 (2023년 귀속부터 상향, 이후 연장)
    market_limit = 3_000_000
    transit_limit = 3_000_000

    # 기본 한도 적용 (신용카드+체크카드 합산)
    base_deduction = min(credit_deduction + debit_deduction, base_limit)
    # 추가 한도 적용
    market_deduction_final = min(market_deduction, market_limit)
    transit_deduction_final = min(transit_deduction, transit_limit)

    total_deduction = base_deduction + market_deduction_final + transit_deduction_final

    return {
        "총사용액": total_usage,
        "공제대상금액": max(total_usage - threshold, 0),
        "신용카드공제": credit_deduction,
        "체크카드공제": debit_deduction,
        "전통시장공제": market_deduction,
        "대중교통공제": transit_deduction,
        "공제한도": base_limit + market_limit + transit_limit,
        "최종공제액": total_deduction,
    }


def calculate_retirement_income_tax(
    retirement_pay: int,
    years_of_service: int,
    deferred_amount: int = 0,
) -> dict:
    """퇴직소득세 계산 (소득세법 제48조~제49조, 2024년 귀속).

    Args:
        retirement_pay: 퇴직급여 (원)
        years_of_service: 근속연수 (년, 1 이상)
        deferred_amount: DC형 퇴직연금 계좌 이전액 (원, 기본값 0)

    Returns:
        {
            "퇴직급여": int,
            "근속연수": int,
            "근속연수공제": int,
            "환산급여": int,
            "환산급여공제": int,
            "환산과세표준": int,
            "환산산출세액": int,
            "퇴직소득산출세액": int,
            "deferred_tax": int,
            "withholding_tax": int,
            "지방소득세": int,
            "총납부세액": int,
        }
    """
    retirement_pay = int(retirement_pay)
    years = max(int(years_of_service), 1)
    deferred_amount = max(int(deferred_amount), 0)

    # 1. 근속연수공제 (소득세법 제22② — 2024년 귀속 이후 개정)
    if years <= 5:
        tenure_deduction = years * 1_000_000
    elif years <= 10:
        tenure_deduction = 5_000_000 + (years - 5) * 2_000_000
    elif years <= 20:
        tenure_deduction = 15_000_000 + (years - 10) * 2_500_000
    else:
        tenure_deduction = 40_000_000 + (years - 20) * 3_000_000

    # 2. 환산급여
    converted_salary = int((retirement_pay - tenure_deduction) * 12 / years)
    converted_salary = max(converted_salary, 0)

    # 3. 환산급여공제
    cs = converted_salary
    if cs <= 8_000_000:
        converted_deduction = cs
    elif cs <= 70_000_000:
        converted_deduction = 8_000_000 + int((cs - 8_000_000) * 0.60)
    elif cs <= 100_000_000:
        converted_deduction = 45_200_000 + int((cs - 70_000_000) * 0.55)
    elif cs <= 300_000_000:
        converted_deduction = 61_700_000 + int((cs - 100_000_000) * 0.45)
    else:
        converted_deduction = 151_700_000 + int((cs - 300_000_000) * 0.35)

    # 4. 환산과세표준
    converted_taxable = max(converted_salary - converted_deduction, 0)

    # 5~7. 세액 계산
    converted_tax = calculate_tax(converted_taxable)["산출세액"]
    retirement_tax = int(converted_tax * years / 12)
    total_retirement_income = max(retirement_pay, 0)
    deferred_amount = min(deferred_amount, total_retirement_income)

    if total_retirement_income == 0:
        deferred_tax = 0
    else:
        deferred_tax = int(retirement_tax * (deferred_amount / total_retirement_income))

    withholding_tax = int(max(retirement_tax - deferred_tax, 0))
    local_tax = calculate_local_tax(withholding_tax)

    return {
        "퇴직급여": retirement_pay,
        "근속연수": years,
        "근속연수공제": tenure_deduction,
        "환산급여": converted_salary,
        "환산급여공제": converted_deduction,
        "환산과세표준": converted_taxable,
        "환산산출세액": converted_tax,
        "퇴직소득산출세액": retirement_tax,
        "deferred_tax": deferred_tax,
        "withholding_tax": withholding_tax,
        "지방소득세": local_tax,
        "총납부세액": withholding_tax + local_tax,
    }


def calculate_executive_retirement_limit(
    *,
    avg_salary_pre_2020: int,
    avg_salary_pre_retire: int,
    months_b: int,
    months_c: int,
    total_retirement_pay: int = 0,
    a_amount_rule: int = 0,
    total_months: int = 0,
    pre_2012_months: int = 0,
    select_min_earned: bool = True,
) -> dict:
    """임원 퇴직급여 한도 계산 (소득세법 §22③, 시행령 §42의2⑥).

    구간별 공식:
      B구간 (2012.1.1~2019.12.31): 2019.12.31 이전 3년 연평균 × 1/10 × (B월수/12) × 3
      C구간 (2020.1.1~퇴직일):     퇴직 전 3년 연평균 × 1/10 × (C월수/12) × 2

    2011.12.31 이전 근속분(A금액)은 한도 공식 대상 밖. 영§42의2⑥에 따라
    아래 두 방법 중 납세자가 선택:
      ① 비율법: 전체 퇴직급여 × (2011.12.31 이전 월수 ÷ 전체 월수)
      ② 규정법: 2011.12.31 당시 임원퇴직급여지급규정에 따라 가정한 퇴직금

    `select_min_earned=True` 이면 두 방법 중 큰 쪽을 선택한다
    (A금액이 크면 한도 대상 기본금액이 작아져 근로소득 재분류액이 최소화됨).

    인자는 전부 keyword-only. 근무월수는 호출자가 "1월 미만 절상" 을 이미
    반영한 값으로 전달해야 한다 (§22④1).
    공적연금(§22①1) 일시금은 한도 대상이 아니므로 호출자가 별도 합산한다.
    """
    avg_pre_2020 = int(avg_salary_pre_2020)
    avg_pre_retire = int(avg_salary_pre_retire)
    months_b = max(int(months_b), 0)
    months_c = max(int(months_c), 0)
    total_retirement_pay = max(int(total_retirement_pay), 0)
    a_amount_rule = max(int(a_amount_rule), 0)
    total_months = max(int(total_months), 0)
    pre_2012_months = max(int(pre_2012_months), 0)

    limit_b = int(avg_pre_2020 * 0.1 * (months_b / 12) * 3 + 0.5)
    limit_c = int(avg_pre_retire * 0.1 * (months_c / 12) * 2 + 0.5)
    executive_limit = limit_b + limit_c

    if total_months > 0 and pre_2012_months > 0 and total_retirement_pay > 0:
        a_ratio = int(total_retirement_pay * pre_2012_months / total_months)
    else:
        a_ratio = 0

    if select_min_earned:
        a_selected = max(a_ratio, a_amount_rule)
    else:
        a_selected = a_amount_rule

    limit_base = max(total_retirement_pay - a_selected, 0)
    excess = max(limit_base - executive_limit, 0)
    retirement_within_limit = limit_base - excess

    return {
        "한도_B구간": limit_b,
        "한도_C구간": limit_c,
        "임원한도": executive_limit,
        "A금액_비율법": a_ratio,
        "A금액_규정법": a_amount_rule,
        "A금액_선택": a_selected,
        "한도_대상_기본금액": limit_base,
        "초과액_근로소득화": excess,
        "퇴직소득_산정기준": retirement_within_limit,
        "비고": (
            "공적연금(§22①1) 일시금은 한도 대상 밖 — 호출자가 별도 합산. "
            f"A금액 선택: {'비율법' if a_selected == a_ratio and a_ratio >= a_amount_rule else '규정법'}"
        ),
    }


def calculate_business_income_estimated(
    revenue: int,
    method: str,
    standard_expense_rate: float,
    simple_expense_rate: float,
    major_expenses: int = 0,
) -> dict:
    """추계신고 사업소득금액 계산 (소득세법 §80, 시행령 §143)."""
    revenue = int(revenue)
    major_expenses = int(major_expenses)
    standard_expense_rate = float(standard_expense_rate)
    simple_expense_rate = float(simple_expense_rate)

    if revenue < 0:
        raise ValueError("revenue는 0 이상이어야 합니다.")
    if major_expenses < 0:
        raise ValueError("major_expenses는 0 이상이어야 합니다.")
    if not 0 <= standard_expense_rate <= 1:
        raise ValueError("standard_expense_rate는 0과 1 사이여야 합니다.")
    if not 0 <= simple_expense_rate <= 1:
        raise ValueError("simple_expense_rate는 0과 1 사이여야 합니다.")
    if method not in ("standard", "simple"):
        raise ValueError("method는 'standard' 또는 'simple'이어야 합니다.")

    if method == "standard":
        estimated_expense = major_expenses + int(revenue * standard_expense_rate)
        business_income = max(revenue - estimated_expense, 0)
        note = "기준경비율 방식: 주요경비 + 수입금액 × 기준경비율"
    else:
        estimated_expense = int(revenue * simple_expense_rate)
        business_income = revenue - estimated_expense
        note = "단순경비율 방식: 수입금액 × 단순경비율"

    return {
        "method": method,
        "revenue": revenue,
        "estimated_expense": int(estimated_expense),
        "business_income": int(business_income),
        "note": note,
    }


def calculate_daily_wage_tax(daily_wage: int, work_days: int = 1) -> dict:
    """일용근로소득세 원천징수세액 계산 (소득세법 §129①8, §78)."""
    daily_wage = int(daily_wage)
    work_days = int(work_days)

    if daily_wage < 0:
        raise ValueError("daily_wage는 0 이상이어야 합니다.")
    if work_days < 1:
        raise ValueError("work_days는 1 이상이어야 합니다.")

    nontaxable_per_day = 150_000
    taxable_per_day = max(daily_wage - nontaxable_per_day, 0)
    tax_per_day = int(taxable_per_day * 0.06)
    deduction_per_day = int(tax_per_day * 0.55)
    withholding_per_day = tax_per_day - deduction_per_day
    total_withholding = withholding_per_day * work_days
    local_tax = int(total_withholding * 0.10)

    return {
        "daily_wage": daily_wage,
        "work_days": work_days,
        "nontaxable_per_day": nontaxable_per_day,
        "taxable_per_day": taxable_per_day,
        "tax_per_day": tax_per_day,
        "deduction_per_day": deduction_per_day,
        "withholding_per_day": withholding_per_day,
        "total_withholding": total_withholding,
        "local_tax": local_tax,
        "total_tax": total_withholding + local_tax,
    }


def calculate_earned_income_tax_credit(income_tax, gross_salary):
    """근로소득세액공제 계산 (소득세법 §59, 2024년 귀속).

    산출세액 기준:
        130만원 이하: 산출세액의 55%
        130만원 초과: 71만5천원 + (산출세액 - 130만원) × 30%

    공제 한도(총급여 기준):
        3,300만원 이하: 74만원
        3,300만~7,000만원: 74만 - (총급여 - 3,300만) × 8/1000 (최저 66만원)
        7,000만원 초과: 66만 - (총급여 - 7,000만) × 1/2 (최저 50만원)

    Args:
        income_tax: 산출세액
        gross_salary: 총급여 (한도 계산용)

    Returns:
        {
            "산출세액": int,
            "근로소득세액공제액": int,  # 한도 적용 전
            "공제한도": int,
            "최종공제액": int,  # min(공제액, 한도)
        }
    """
    income_tax = int(income_tax)
    gross_salary = int(gross_salary)

    # 1. 공제액 (산출세액 기준)
    if income_tax <= 1_300_000:
        credit_amount = income_tax * 55 // 100
    else:
        credit_amount = 715_000 + (income_tax - 1_300_000) * 30 // 100

    # 2. 공제한도 (총급여 기준)
    if gross_salary <= 33_000_000:
        credit_limit = 740_000
    elif gross_salary <= 70_000_000:
        reduction = (gross_salary - 33_000_000) * 8 // 1_000
        credit_limit = max(740_000 - reduction, 660_000)
    else:
        reduction = (gross_salary - 70_000_000) // 2
        credit_limit = max(660_000 - reduction, 500_000)

    final_credit = min(credit_amount, credit_limit)

    return {
        "산출세액": income_tax,
        "근로소득세액공제액": credit_amount,
        "공제한도": credit_limit,
        "최종공제액": final_credit,
    }


def calculate_tax_credits(tax_data):
    """주요 세액공제 계산 (소득세법 §59의4, 조세특례제한법 각 조항, 2024년 귀속).

    Args:
        tax_data: dict
            - income_tax: 산출세액
            - gross_salary: 총급여 (공제율 분기용)
            - children_count: 기본공제 대상 자녀 수 (만 8세 이상)
            - medical_expense: 의료비 지출액 (세액공제용, 총급여×3% 초과분)
            - education_expense: 교육비 지출액
            - monthly_rent: 연간 월세 지출액
            - irp_pension: IRP + 연금저축 납입액 (연 900만 한도)
            - total_income: 종합소득금액 (IRP 공제율 분기용)

    Returns:
        {
            "자녀세액공제": int,
            "의료비세액공제": int,
            "교육비세액공제": int,
            "월세세액공제": int,
            "IRP연금세액공제": int,
            "세액공제_합계": int,
        }
    """
    tax_data = tax_data or {}

    gross_salary = int(tax_data.get("gross_salary", 0) or 0)
    children_count = int(tax_data.get("children_count", 0) or 0)
    medical_expense = int(tax_data.get("medical_expense", 0) or 0)
    education_expense = int(tax_data.get("education_expense", 0) or 0)
    monthly_rent = int(tax_data.get("monthly_rent", 0) or 0)
    irp_pension = int(tax_data.get("irp_pension", 0) or 0)
    total_income = int(tax_data.get("total_income", 0) or 0)

    # 1. 자녀세액공제 (소득세법 §59의2)
    if children_count <= 0:
        child_credit = 0
    elif children_count == 1:
        child_credit = 150_000
    elif children_count == 2:
        child_credit = 350_000
    else:
        child_credit = 350_000 + (children_count - 2) * 300_000

    # 2. 의료비세액공제 (소득세법 §59의4①): 15%
    medical_base = max(medical_expense, 0)
    medical_credit = medical_base * 15 // 100

    # 3. 교육비세액공제 (소득세법 §59의4②): 15%
    education_base = max(education_expense, 0)
    education_credit = education_base * 15 // 100

    # 4. 월세세액공제 (조특법 §95의2): 17% / 15%, 연 750만원 한도
    rent_base = min(max(monthly_rent, 0), 7_500_000)
    if gross_salary <= 55_000_000 and total_income <= 45_000_000:
        rent_credit = rent_base * 17 // 100
    elif gross_salary <= 80_000_000:
        rent_credit = rent_base * 15 // 100
    else:
        rent_credit = 0

    # 5. IRP·연금저축세액공제 (소득세법 §59의3): 16.5% / 13.2% (지방소득세 포함), 연 900만원 한도
    pension_base = min(max(irp_pension, 0), 9_000_000)
    if gross_salary <= 55_000_000 and total_income <= 45_000_000:
        pension_credit = pension_base * 165 // 1_000
    else:
        pension_credit = pension_base * 132 // 1_000

    total_credit = child_credit + medical_credit + education_credit + rent_credit + pension_credit

    return {
        "자녀세액공제": child_credit,
        "의료비세액공제": medical_credit,
        "교육비세액공제": education_credit,
        "월세세액공제": rent_credit,
        "IRP연금세액공제": pension_credit,
        "세액공제_합계": total_credit,
    }


def simulate_comprehensive_vs_separate(income_data):
    """종합과세 vs 분리과세 세액 비교 시뮬레이션.

    income_data 예시:
        {
            "comprehensive_income": 50_000_000,   # 종합과세 대상 소득 합계
            "separate_tax_items": [               # 분리과세 선택 항목
                {"amount": 10_000_000, "rate": 0.14},  # 금융소득 등
            ]
        }
    """
    comprehensive_income = int(income_data.get("comprehensive_income", 0) or 0)
    separate_items = income_data.get("separate_tax_items", []) or []

    # 종합과세 세액
    comp_tax = calculate_tax(comprehensive_income)
    comp_local = calculate_local_tax(comp_tax["산출세액"])
    comp_total = comp_tax["산출세액"] + comp_local

    # 분리과세 세액
    sep_total = 0
    sep_breakdown = []
    for item in separate_items:
        amount = int(item.get("amount", 0) or 0)
        rate = float(item.get("rate", 0) or 0)
        tax = int(amount * rate)
        local = calculate_local_tax(tax)
        sep_breakdown.append({
            "금액": amount,
            "세율": rate,
            "소득세": tax,
            "지방소득세": local,
        })
        sep_total += tax + local

    return {
        "종합과세": {
            "과세표준": comprehensive_income,
            "소득세": comp_tax["산출세액"],
            "지방소득세": comp_local,
            "합계": comp_total,
        },
        "분리과세": {
            "항목": sep_breakdown,
            "합계": sep_total,
        },
        "총합(종합+분리)": comp_total + sep_total,
    }


def calculate_loss_netting(incomes: dict, loss: int, loss_type: str) -> dict:
    """결손금 당기 통산 계산 (소득세법 §45).

    법령 근거:
        - 소득세법 §45①: 사업소득 결손금은 당해 과세기간 종합소득과세표준 계산 시
          근로→연금→기타→이자→배당 순서로 통산
        - 소득세법 §45②: 부동산임대업(주거용 제외) 결손금은 타소득과 통산 불가 (이월만 가능)

    Note:
        - 소득세법 §45⑤(금융소득 분리과세 관련) 세부 로직은 §62 통합 시 처리 예정이며,
          본 함수에서는 별도 파라미터/분기 없이 주석으로만 명시한다.

    Args:
        incomes: 당기 소득금액 dict.
            키: '사업소득', '근로소득', '연금소득', '기타소득', '이자소득', '배당소득'
            (부동산임대업 소득은 '부동산임대소득' 키 사용)
            값: int (원)
        loss: 결손금 금액 (양수 입력). 예) 적자 500만원이면 5_000_000
        loss_type: 'general' | 'real_estate'
            - 'general': §45① 적용 (근로→연금→기타→이자→배당 순 통산)
            - 'real_estate': §45② (당기 타소득 통산 불가; 이월만 가능)

    Returns:
        {
          '통산후소득': dict,
          '통산완료여부': bool,
          '잔여결손금': int,
          '공제내역': list[dict],
          '근거': str,
        }

    Example:
        incomes = {
            "사업소득": 0,
            "근로소득": 10_000_000,
            "연금소득": 3_000_000,
            "기타소득": 0,
            "이자소득": 1_000_000,
            "배당소득": 0,
        }
        result = calculate_loss_netting(incomes, loss=5_000_000, loss_type="general")
        # 근로소득에서 5,000,000 공제 → 잔여결손금 0, 통산완료여부 True
    """
    incomes = incomes or {}
    if not isinstance(incomes, dict):
        raise ValueError("incomes must be a dict")

    remaining_loss = int(loss or 0)
    if remaining_loss < 0:
        raise ValueError("loss must be a non-negative int")

    if loss_type not in ("general", "real_estate"):
        raise ValueError("loss_type must be 'general' or 'real_estate'")

    net_incomes = {k: max(int(v or 0), 0) for k, v in incomes.items()}

    if remaining_loss == 0:
        return {
            "통산후소득": net_incomes,
            "통산완료여부": True,
            "잔여결손금": 0,
            "공제내역": [],
            "근거": "소득세법 §45 (결손금 통산)",
        }

    if loss_type == "real_estate":
        rent_income = max(int(net_incomes.get("부동산임대소득", 0) or 0), 0)
        deduct = min(rent_income, remaining_loss)
        net_incomes["부동산임대소득"] = rent_income - deduct
        remaining_loss -= deduct

        deductions = []
        if deduct > 0:
            deductions.append({"소득유형": "부동산임대소득", "공제액": deduct})

        return {
            "통산후소득": net_incomes,
            "통산완료여부": remaining_loss == 0,
            "잔여결손금": max(remaining_loss, 0),
            "공제내역": deductions,
            "근거": "소득세법 §45② (부동산임대업 결손금은 타소득 통산 불가; 부동산임대소득 내에서만 공제)",
        }

    deduction_order = ["근로소득", "연금소득", "기타소득", "이자소득", "배당소득"]
    deductions = []
    for income_type in deduction_order:
        if remaining_loss <= 0:
            break
        available = max(int(net_incomes.get(income_type, 0) or 0), 0)
        if available <= 0:
            continue
        deduct = min(available, remaining_loss)
        net_incomes[income_type] = available - deduct
        remaining_loss -= deduct
        if deduct > 0:
            deductions.append({"소득유형": income_type, "공제액": deduct})

    return {
        "통산후소득": net_incomes,
        "통산완료여부": remaining_loss == 0,
        "잔여결손금": max(remaining_loss, 0),
        "공제내역": deductions,
        "근거": "소득세법 §45①, §45② (결손금 통산 순서 및 부동산임대업 결손금 통산 제한)",
    }


def calculate_loss_carryforward(
    incomes: dict,
    carryforward_losses: list[dict],
    loss_type: str = "general",
) -> dict:
    """이월결손금 공제 계산 (소득세법 §45).

    법령 근거:
        - 소득세법 §45③: 이월결손금은 발생일로부터 15년 이내, 선발생분 우선 공제
          (일반이월결손금 공제 순: 사업→근로→연금→기타→이자→배당)
          부동산임대업 이월결손금은 부동산임대업 소득에서만 공제
        - 소득세법 §45⑥: 당기 결손금과 이월결손금이 동시에 있으면 당기 결손금 먼저 공제

    Note:
        - 소득세법 §45⑤(금융소득 분리과세 관련) 원천징수세율(14%) 부분 공제 제외 등
          세부 로직은 §62 통합 시 처리 예정이며, 본 함수에서는 별도 파라미터 처리 생략.
        - 일반이월결손금 공제 순서에서 '부동산임대소득'은 별도 관리되어 '사업소득' 앞에 위치한다.

    Args:
        incomes: 당기 소득금액 dict (calculate_loss_netting 통산 후 결과 사용 권장)
        carryforward_losses: 이월결손금 목록.
            [{'연도': int, 'loss_type': str, '금액': int}, ...]
            연도 오름차순 정렬(선발생 우선 공제 — §45③)되어 있다고 가정한다.
        loss_type: 'general' | 'real_estate' (항목에 loss_type 누락 시 기본값으로 사용)

    Returns:
        {
          '공제후소득': dict,
          '공제내역': list[dict],
          '미공제이월결손금': list[dict],
          '근거': str,
        }

    Example:
        incomes = {"근로소득": 8_000_000, "사업소득": 2_000_000, "부동산임대소득": 1_000_000}
        carry = [
            {"연도": 2016, "loss_type": "general", "금액": 3_000_000},
            {"연도": 2010, "loss_type": "general", "금액": 1_000_000},  # 15년 초과 시 미공제
            {"연도": 2024, "loss_type": "real_estate", "금액": 700_000},
        ]
        result = calculate_loss_carryforward(incomes, carry)
        # 2016 일반이월: 부동산임대→사업→근로 순으로 공제
        # 2024 부동산임대 이월: 부동산임대소득에서만 공제
    """
    from datetime import date

    incomes = incomes or {}
    if not isinstance(incomes, dict):
        raise ValueError("incomes must be a dict")

    if carryforward_losses is None:
        carryforward_losses = []
    if not isinstance(carryforward_losses, list):
        raise ValueError("carryforward_losses must be a list")

    if loss_type not in ("general", "real_estate"):
        raise ValueError("loss_type must be 'general' or 'real_estate'")

    current_year = date.today().year
    deducted_incomes = {k: max(int(v or 0), 0) for k, v in incomes.items()}

    deduction_details = []
    remaining_carry = []

    for item in carryforward_losses:
        if not isinstance(item, dict):
            raise ValueError("carryforward_losses items must be dicts")

        year = int(item.get("연도"))
        item_type = item.get("loss_type", loss_type) or loss_type
        if item_type not in ("general", "real_estate"):
            raise ValueError("loss_type in carryforward_losses must be 'general' or 'real_estate'")

        amount = int(item.get("금액", 0) or 0)
        if amount <= 0:
            continue

        age = current_year - year
        if age < 0 or age > 15:
            remaining_carry.append({"연도": year, "loss_type": item_type, "금액": amount})
            continue

        remaining_amount = amount
        deducted_total = 0

        if item_type == "real_estate":
            targets = ["부동산임대소득"]
        else:
            targets = ["부동산임대소득", "사업소득", "근로소득", "연금소득", "기타소득", "이자소득", "배당소득"]

        for income_key in targets:
            if remaining_amount <= 0:
                break
            available = max(int(deducted_incomes.get(income_key, 0) or 0), 0)
            if available <= 0:
                continue
            deduct = min(available, remaining_amount)
            deducted_incomes[income_key] = available - deduct
            remaining_amount -= deduct
            deducted_total += deduct

        deduction_details.append(
            {
                "연도": year,
                "loss_type": item_type,
                "공제액": deducted_total,
                "잔액": remaining_amount,
            }
        )

        if remaining_amount > 0:
            remaining_carry.append({"연도": year, "loss_type": item_type, "금액": remaining_amount})

    return {
        "공제후소득": deducted_incomes,
        "공제내역": deduction_details,
        "미공제이월결손금": remaining_carry,
        "근거": "소득세법 §45③, §45⑥ (이월결손금 15년/선발생 우선 및 당기 결손금 우선 공제)",
    }


def calculate_long_term_deduction(
    gain: int,
    holding_years: float,
    asset_type: str = 'general',
    residence_years: float = 0.0
) -> dict:
    """장기보유특별공제액 계산 (소득세법 §95②, 2026-04-01 법제처 API 확인 완료).

    §95②: 보유기간 3년 이상 토지·건물(미등기·단기중과 제외)에 대해 장기보유특별공제 적용.
      - 표1(일반 부동산): 보유기간 3년 이상 구간별 6%~30%
      - 표2(1세대1주택): 보유기간 공제율 + 거주기간 공제율 합산
          * 보유기간: 연 4% (최대 40%)
          * 거주기간: 연 4% (최대 40%)
          * 합계 최대 80%

    Args:
        gain: 양도차익 (원, 양수)
        holding_years: 보유기간 (연수, float. 예: 3.5)
        asset_type: 'general' | 'one_house'
        residence_years: 거주기간 (연수, float). asset_type='one_house'일 때만 사용.

    Returns:
        {
            '공제율_보유': float,
            '공제율_거주': float,
            '공제율_합계': float,
            '장기보유특별공제액': int,
            '근거': str,
        }

    사용 예시:
        # 1세대1주택, 보유 10.2년/거주 6.0년, 양도차익 5억원
        calculate_long_term_deduction(
            gain=500_000_000,
            holding_years=10.2,
            asset_type="one_house",
            residence_years=6.0,
        )
    """
    import math

    gain = int(gain)
    holding_years = float(holding_years)
    residence_years = float(residence_years)

    if gain < 0:
        raise ValueError("gain은 0 이상이어야 합니다.")
    if holding_years < 0 or residence_years < 0:
        raise ValueError("holding_years/residence_years는 0 이상이어야 합니다.")
    if asset_type not in ("general", "one_house"):
        raise ValueError("asset_type은 'general' 또는 'one_house'여야 합니다.")

    def _general_holding_rate(years: float) -> float:
        if years < 3:
            return 0.0
        if years < 4:
            return 0.06
        if years < 5:
            return 0.08
        if years < 6:
            return 0.10
        if years < 7:
            return 0.12
        if years < 8:
            return 0.14
        if years < 9:
            return 0.16
        if years < 10:
            return 0.18
        if years < 11:
            return 0.20
        if years < 12:
            return 0.22
        if years < 13:
            return 0.24
        if years < 14:
            return 0.26
        if years < 15:
            return 0.28
        return 0.30

    def _one_house_holding_rate(years: float) -> float:
        if years < 3:
            return 0.0
        if years < 4:
            return 0.12
        if years < 5:
            return 0.16
        if years < 6:
            return 0.20
        if years < 7:
            return 0.24
        if years < 8:
            return 0.28
        if years < 9:
            return 0.32
        if years < 10:
            return 0.36
        return 0.40

    def _one_house_residence_rate(years: float) -> float:
        if years < 2:
            return 0.0
        if years < 3:
            return 0.08
        if years < 4:
            return 0.12
        if years < 5:
            return 0.16
        if years < 6:
            return 0.20
        if years < 7:
            return 0.24
        if years < 8:
            return 0.28
        if years < 9:
            return 0.32
        if years < 10:
            return 0.36
        return 0.40

    rate_holding = 0.0
    rate_residence = 0.0
    if asset_type == "general":
        rate_holding = _general_holding_rate(holding_years)
        basis = "소득세법 §95② 표1(일반 부동산) - 보유기간 3년 이상 구간별 6%~30%"
    else:
        rate_holding = _one_house_holding_rate(holding_years)
        rate_residence = _one_house_residence_rate(residence_years)
        rate_holding = min(rate_holding, 0.40)
        rate_residence = min(rate_residence, 0.40)
        basis = "소득세법 §95② 표2(1세대1주택) - 보유+거주 합산(각 최대 40%, 합계 최대 80%)"

    rate_total = min(rate_holding + rate_residence, 0.80)
    deduction_amount = int(math.floor(gain * rate_total))

    return {
        "공제율_보유": float(rate_holding),
        "공제율_거주": float(rate_residence),
        "공제율_합계": float(rate_total),
        "장기보유특별공제액": int(max(deduction_amount, 0)),
        "근거": basis,
    }


def calculate_transfer_income_tax(
    transfer_price: int,
    acquisition_price: int,
    necessary_expenses: int = 0,
    holding_years: float = 0.0,
    asset_type: str = 'general',
    house_type: str = 'none',
    residence_years: float = 0.0,
    multi_house_count: int = 1,
    is_adjusted_area: bool = False,
    is_unregistered: bool = False
) -> dict:
    """양도소득세 원스톱 계산 (소득세법 §94~§97, §104, §89①3, §103; 2026-04-01 법제처 API 확인 완료).

    [핵심 법령 근거]
    §96: 양도가액 = 실지거래가액
    §97①: 필요경비 = 취득가액 + 자본적지출액 + 양도비용
    §95①: 양도소득금액 = 양도차익 - 장기보유특별공제액
    §103: 양도소득기본공제 250만원
    §104①: 세율(단기/미등기/일반)
      - 보유 2년 이상 일반: §55 기본 누진세율
      - 보유 1년 이상 2년 미만: 40% (주택/조합원입주권/분양권: 60%)
      - 보유 1년 미만: 50% (주택/조합원입주권/분양권: 70%)
      - 미등기양도: 70%
    §104⑦: 다주택 중과(조정대상지역)
      - 1세대 2주택: 기본세율 + 20%p
      - 1세대 3주택 이상: 기본세율 + 30%p
      - 2년 미만 보유 시 중과세율과 단기세율 중 큰 것 적용
    §89①3: 1세대1주택 비과세(요건 충족 + 양도가액 12억 이하), 12억 초과는 고가주택 과세

    사용 예시:
        # 일반 토지/건물, 보유 6.2년, 양도가 5억, 취득가 3억, 비용 2천만원
        calculate_transfer_income_tax(
            transfer_price=500_000_000,
            acquisition_price=300_000_000,
            necessary_expenses=20_000_000,
            holding_years=6.2,
            asset_type="general",
        )

        # 1세대1주택, 보유 11년/거주 8년, 양도가 15억(고가주택)
        calculate_transfer_income_tax(
            transfer_price=1_500_000_000,
            acquisition_price=700_000_000,
            necessary_expenses=30_000_000,
            holding_years=11.0,
            residence_years=8.0,
            asset_type="one_house",
            house_type="house",
        )
    """
    import math

    transfer_price = int(transfer_price)
    acquisition_price = int(acquisition_price)
    necessary_expenses = int(necessary_expenses)
    holding_years = float(holding_years)
    residence_years = float(residence_years)
    multi_house_count = int(multi_house_count)

    if transfer_price < 0 or acquisition_price < 0 or necessary_expenses < 0:
        raise ValueError("transfer_price/acquisition_price/necessary_expenses는 0 이상이어야 합니다.")
    if holding_years < 0 or residence_years < 0:
        raise ValueError("holding_years/residence_years는 0 이상이어야 합니다.")
    if asset_type not in ("general", "one_house"):
        raise ValueError("asset_type은 'general' 또는 'one_house'여야 합니다.")
    if house_type not in ("none", "house", "apt_right", "presale"):
        raise ValueError("house_type은 'none'|'house'|'apt_right'|'presale'여야 합니다.")
    if multi_house_count < 1:
        raise ValueError("multi_house_count는 1 이상이어야 합니다.")

    THRESHOLD_ONE_HOUSE_EXEMPT = 1_200_000_000  # §89①3 12억
    BASIC_DEDUCTION = 2_500_000  # §103

    total_cost = acquisition_price + necessary_expenses  # §97①
    gain_raw = transfer_price - total_cost
    gain = int(max(gain_raw, 0))
    note = ""
    if gain_raw <= 0:
        note = "양도차익이 0 이하이므로 산출세액은 0원입니다."

    is_exempt = False
    taxable_gain = gain
    if asset_type == "one_house" and gain > 0:
        cond_hold = holding_years >= 2.0
        cond_res = (not is_adjusted_area) or (residence_years >= 2.0)
        if cond_hold and cond_res:
            if transfer_price <= THRESHOLD_ONE_HOUSE_EXEMPT:
                is_exempt = True
                note = "1세대1주택 비과세(§89①3): 2년 보유(조정대상지역은 2년 거주 추가) + 양도가액 12억 이하"
            else:
                ratio = (transfer_price - THRESHOLD_ONE_HOUSE_EXEMPT) / transfer_price
                taxable_gain = int(math.floor(gain * ratio))
                note = (
                    "고가주택 과세(§89①3): 과세 양도차익 = 양도차익 × (양도가액-12억) / 양도가액"
                )

    if is_exempt:
        return {
            "양도가액": transfer_price,
            "취득가액": acquisition_price,
            "필요경비": int(total_cost),
            "양도차익": int(gain),
            "과세_양도차익": 0,
            "장기보유특별공제액": 0,
            "양도소득금액": 0,
            "양도소득기본공제": BASIC_DEDUCTION,
            "양도소득과세표준": 0,
            "적용세율": 0.0,
            "세율_설명": "비과세(§89①3)",
            "산출세액": 0,
            "지방소득세": 0,
            "총납부세액": 0,
            "비과세여부": True,
            "비고": note,
        }

    if is_unregistered:
        ltd_amount = 0
        ltd_basis = "미등기양도(§104①): 장기보유특별공제 적용 없음"
    else:
        ltd_res = calculate_long_term_deduction(
            gain=taxable_gain,
            holding_years=holding_years,
            asset_type=asset_type,
            residence_years=residence_years,
        )
        ltd_amount = int(ltd_res["장기보유특별공제액"])
        ltd_basis = str(ltd_res["근거"])

    transfer_income_amount = int(max(taxable_gain - ltd_amount, 0))  # §95①
    tax_base = int(max(transfer_income_amount - BASIC_DEDUCTION, 0))  # §103

    def _short_term_rate(years: float, ht: str) -> float | None:
        is_house_like = ht in ("house", "apt_right", "presale")
        if years < 1:
            return 0.70 if is_house_like else 0.50
        if years < 2:
            return 0.60 if is_house_like else 0.40
        if ht == "presale":
            return 0.60
        return None

    add_rate = 0.0
    if is_adjusted_area and multi_house_count >= 2 and house_type in ("house", "apt_right", "presale"):
        add_rate = 0.20 if multi_house_count == 2 else 0.30

    applied_rate = 0.0
    rate_desc = ""
    income_tax = 0

    if tax_base <= 0:
        applied_rate = 0.0
        rate_desc = "과세표준이 0원입니다."
        income_tax = 0
    elif is_unregistered:
        applied_rate = 0.70
        rate_desc = "미등기양도(§104①): 70% 비례세율"
        income_tax = int(tax_base * applied_rate)
    else:
        short_rate = _short_term_rate(holding_years, house_type)
        if short_rate is not None and holding_years < 2:
            short_tax = int(tax_base * short_rate)
            if add_rate > 0:
                base = calculate_tax(tax_base)
                multi_tax = int(base["산출세액"] + tax_base * add_rate)
                if multi_tax >= short_tax:
                    applied_rate = float(base["적용세율"] + add_rate)
                    rate_desc = (
                        f"다주택 중과(§104⑦): 기본 누진세율 + {int(add_rate*100)}%p "
                        f"(2년 미만: 단기세율 {int(short_rate*100)}%와 비교 후 큰 세액 적용)"
                    )
                    income_tax = multi_tax
                else:
                    applied_rate = float(short_rate)
                    rate_desc = (
                        f"단기양도(§104①): {int(short_rate*100)}% 비례세율 "
                        f"(2년 미만: 중과세액과 비교 후 큰 세액 적용)"
                    )
                    income_tax = short_tax
            else:
                applied_rate = float(short_rate)
                rate_desc = f"단기양도(§104①): {int(short_rate*100)}% 비례세율"
                income_tax = short_tax
        else:
            base_rate = _short_term_rate(holding_years, house_type)
            if house_type == "presale" and base_rate is not None:
                applied_rate = float(base_rate + add_rate)
                rate_desc = (
                    f"분양권(§104①): {int(base_rate*100)}% 비례세율"
                    + (f" + 다주택중과 {int(add_rate*100)}%p(§104⑦)" if add_rate > 0 else "")
                )
                income_tax = int(tax_base * applied_rate)
            else:
                base = calculate_tax(tax_base)
                applied_rate = round(base["적용세율"] + add_rate, 4)
                rate_desc = (
                    "기본 누진세율(§55) 적용"
                    + (f" + 다주택중과 {int(add_rate*100)}%p(§104⑦)" if add_rate > 0 else "")
                )
                income_tax = int(base["산출세액"] + tax_base * add_rate)

    local_tax = calculate_local_tax(income_tax)
    total_tax = int(income_tax + local_tax)

    return {
        "양도가액": transfer_price,
        "취득가액": acquisition_price,
        "필요경비": int(total_cost),
        "양도차익": int(gain),
        "과세_양도차익": int(taxable_gain),
        "장기보유특별공제액": int(ltd_amount),
        "양도소득금액": int(transfer_income_amount),
        "양도소득기본공제": int(BASIC_DEDUCTION),
        "양도소득과세표준": int(tax_base),
        "적용세율": float(applied_rate),
        "세율_설명": str(rate_desc),
        "산출세액": int(max(income_tax, 0)),
        "지방소득세": int(local_tax),
        "총납부세액": int(max(total_tax, 0)),
        "비과세여부": False,
        "비고": "; ".join([s for s in [note, ltd_basis] if s]),
    }


def calculate_interim_prepayment(prev_year_tax: int) -> dict:
    """중간예납세액 계산 (소득세법 §65).

    직전 과세기간 종합소득세액(결정세액 기준)의 50%를 중간예납기준액으로 산정한다.
    다만, 중간예납기준액이 50만원 미만이면 징수하지 않는다(§65③).

    Args:
        prev_year_tax: 직전 과세기간 종합소득세액 (결정세액 기준, 원)

    Returns:
        {
          '중간예납기준액': int,   # prev_year_tax × 50%
          '납부의무여부': bool,    # 기준액 50만원 미만이면 False
          '납부기한': str,         # '매년 11월 30일'
          '근거': str,
        }

    사용 예시:
        calculate_interim_prepayment(3_000_000)
        # {'중간예납기준액': 1500000, '납부의무여부': True, '납부기한': '매년 11월 30일', ...}
    """
    prev_year_tax = int(prev_year_tax)
    기준액 = int(prev_year_tax * 0.5)
    납부의무여부 = not (int(prev_year_tax * 0.5) < 500_000)

    return {
        "중간예납기준액": int(기준액),
        "납부의무여부": bool(납부의무여부),
        "납부기한": "매년 11월 30일",
        "근거": "소득세법 제65조(중간예납) 및 같은 조 제3항(중간예납기준액 50만원 미만 징수하지 않음)",
    }


def calculate_penalty_tax(
    base_tax: int,
    penalty_type: str,
    days_late: int = 0,
    is_fraudulent: bool = False,
    is_offshore: bool = False,
) -> dict:
    """가산세 계산 (국세기본법 §47의2~§47의4).

    - 무신고(§47의2): 무신고납부세액 × 20% (부정행위 40%, 역외거래 부정 60%)
    - 과소신고(§47의3): 과소신고납부세액 × 10% (부정행위분 40% + 일반분 10%)
      * 단순화: 이 함수에서는 base_tax 전액을 부정행위분으로 가정한다(부정행위=True일 때).
    - 납부지연(§47의4): 미납세액 × 경과일수 × 0.022%/일

    Args:
        base_tax: 기준 세액 (원)
            - penalty_type='no_filing': 무신고납부세액
            - penalty_type='under_filing': 과소신고납부세액
            - penalty_type='late_payment': 미납세액
        penalty_type: 'no_filing' | 'under_filing' | 'late_payment'
        days_late: 경과일수 (penalty_type='late_payment'일 때 사용)
        is_fraudulent: 부정행위 여부 (no_filing/under_filing에만 적용)
        is_offshore: 역외거래 부정행위 여부 (is_fraudulent=True일 때만 의미)

    Returns:
        {
          '가산세액': int,
          '적용세율_또는_일수': str,   # 예: '20%', '0.022%/일 × 30일'
          '근거': str,
          '비고': str,
        }

    사용 예시:
        calculate_penalty_tax(10_000_000, 'no_filing')  # 일반 무신고
        calculate_penalty_tax(10_000_000, 'under_filing', is_fraudulent=True)  # 부정 과소신고(단순화)
        calculate_penalty_tax(5_000_000, 'late_payment', days_late=30)  # 납부지연
    """
    LATE_PAYMENT_RATE_DAILY = 0.00022  # 0.022%/일 (국세기본법 시행령 §27의4)

    base_tax = int(base_tax)
    days_late = int(days_late)

    if base_tax < 0:
        raise ValueError("base_tax must be >= 0")
    if days_late < 0:
        raise ValueError("days_late must be >= 0")
    if penalty_type not in ("no_filing", "under_filing", "late_payment"):
        raise ValueError("penalty_type must be one of: 'no_filing', 'under_filing', 'late_payment'")

    if penalty_type == "no_filing":
        if is_fraudulent:
            rate = 0.60 if is_offshore else 0.40
            applied = "60%" if is_offshore else "40%"
            note = "부정행위 무신고" + ("(역외거래)" if is_offshore else "")
        else:
            rate = 0.20
            applied = "20%"
            note = "일반 무신고"

        penalty = int(base_tax * rate)
        return {
            "가산세액": int(penalty),
            "적용세율_또는_일수": applied,
            "근거": "국세기본법 제47의2(무신고가산세)",
            "비고": note,
        }

    if penalty_type == "under_filing":
        if is_fraudulent:
            rate = 0.40
            applied = "40%"
            note = "부정행위 과소신고(단순화: base_tax 전액을 부정행위분으로 가정)"
        else:
            rate = 0.10
            applied = "10%"
            note = "일반 과소신고"

        penalty = int(base_tax * rate)
        return {
            "가산세액": int(penalty),
            "적용세율_또는_일수": applied,
            "근거": "국세기본법 제47의3(과소신고가산세)",
            "비고": note,
        }

    penalty = int(base_tax * days_late * LATE_PAYMENT_RATE_DAILY)
    return {
        "가산세액": int(penalty),
        "적용세율_또는_일수": f"0.022%/일 × {days_late}일",
        "근거": "국세기본법 제47의4(납부지연가산세) 및 국세기본법 시행령 제27의4(일할 이자율)",
        "비고": "",
    }


def calculate_joint_business_income(total_income: int, partners: list[dict]) -> dict:
    """공동사업장 손익 배분 (소득세법 §43).

    - §43①: 공동사업장을 1거주자로 보아 소득금액을 계산
    - §43②: 소득금액을 손익분배비율(없으면 지분비율)로 각 공동사업자에게 배분

    Args:
        total_income: 공동사업장 총 소득금액 (원, 양수=이익, 음수=결손)
        partners: 공동사업자 목록
            [{'이름': str, '분배비율': float}, ...]  # 분배비율 합계 = 1.0
            분배비율 미입력 시 지분비율(예: '지분비율')로 대체 (이 함수에선 동일하게 처리)

    Returns:
        {
          '총소득금액': int,
          '배분내역': list[dict],  # [{'이름': str, '분배비율': float, '배분소득': int}, ...]
          '근거': str,
        }

    사용 예시:
        calculate_joint_business_income(
            10_000_000,
            [{'이름': 'A', '분배비율': 0.6}, {'이름': 'B', '분배비율': 0.4}],
        )
        # {'총소득금액': 10000000, '배분내역': [...], '근거': ...}
    """
    total_income = int(total_income)

    배분내역: list[dict] = []
    분배비율_합계 = 0.0

    정규화_파트너: list[dict] = []
    for p in partners:
        if not isinstance(p, dict):
            raise ValueError("partners must be a list of dict")
        이름 = p.get("이름")
        비율 = p.get("분배비율", p.get("지분비율"))
        if 이름 is None or 비율 is None:
            raise ValueError("each partner must include '이름' and '분배비율' (or '지분비율')")
        비율 = float(비율)
        if 비율 < 0:
            raise ValueError("분배비율 must be >= 0")
        분배비율_합계 += 비율
        정규화_파트너.append({"이름": str(이름), "분배비율": 비율})

    if abs(분배비율_합계 - 1.0) > 1e-9:
        raise ValueError("분배비율 합계는 1.0이어야 합니다.")

    누적배분 = 0
    for idx, p in enumerate(정규화_파트너):
        이름 = p["이름"]
        비율 = float(p["분배비율"])

        if idx == len(정규화_파트너) - 1:
            배분소득 = int(total_income - 누적배분)
        else:
            배분소득 = int(round(total_income * 비율))
            누적배분 += int(배분소득)

        배분내역.append({"이름": 이름, "분배비율": float(비율), "배분소득": int(배분소득)})

    return {
        "총소득금액": int(total_income),
        "배분내역": 배분내역,
        "근거": "소득세법 제43조(공동사업장 소득금액 계산 및 배분)",
    }


def calculate_sme_employment_tax_reduction(
    income_tax: int,
    worker_type: str,
    years_employed: float,
) -> dict:
    """중소기업취업자 소득세 감면 (조세특례제한법 §30).

    - 청년(만 15~34세): 감면율 90%, 감면기간 5년, 한도 200만원/년
    - 일반(60세 이상·장애인·경력단절 여성): 감면율 70%, 감면기간 3년, 한도 200만원/년
    - 감면세액 = min(산출세액 × 감면율, 2,000,000원)
    - 취업일부터 감면기간 내 근로소득에만 적용 (이 함수는 경과연수로 단순 판정)

    Args:
        income_tax: 근로소득 산출세액 (원)
        worker_type: 'youth' | 'general'
            'youth': 청년(만 15~34세) — 감면율 90%, 5년
            'general': 60세이상·장애인·경력단절 — 감면율 70%, 3년
        years_employed: 취업 후 경과 연수 (float)
            감면 기간 초과 시 감면 없음

    Returns:
        {
          '산출세액': int,
          '감면율': float,
          '감면한도': int,           # 200만원/년
          '감면세액': int,           # min(산출세액 × 감면율, 200만원)
          '감면후세액': int,
          '감면기간_초과여부': bool,
          '근거': str,
        }

    사용 예시:
        calculate_sme_employment_tax_reduction(3_000_000, 'youth', 1.2)
        # {'산출세액': 3000000, '감면율': 0.9, '감면세액': 2000000, ...}
    """
    감면한도 = 2_000_000

    income_tax = int(income_tax)
    years_employed = float(years_employed)

    if income_tax < 0:
        raise ValueError("income_tax must be >= 0")
    if years_employed < 0:
        raise ValueError("years_employed must be >= 0")
    if worker_type not in ("youth", "general"):
        raise ValueError("worker_type must be one of: 'youth', 'general'")

    if worker_type == "youth":
        감면율 = 0.90
        감면율_정수 = 90
        감면기간 = 5.0
    else:
        감면율 = 0.70
        감면율_정수 = 70
        감면기간 = 3.0

    감면기간_초과여부 = bool(years_employed >= 감면기간)

    if 감면기간_초과여부:
        감면세액 = 0
    else:
        감면세액 = min(int(income_tax * 감면율_정수 // 100), int(감면한도))

    감면후세액 = int(max(income_tax - 감면세액, 0))

    return {
        "산출세액": int(income_tax),
        "감면율": float(감면율),
        "감면한도": int(감면한도),
        "감면세액": int(감면세액),
        "감면후세액": int(감면후세액),
        "감면기간_초과여부": bool(감면기간_초과여부),
        "근거": "조세특례제한법 제30조(중소기업 취업자에 대한 소득세 감면)",
    }


def calculate_foreign_tax_credit(
    income_tax: int,
    total_income: int,
    foreign_income: int,
    foreign_tax_paid: int,
) -> dict:
    """외국납부세액공제 (소득세법 §57).

    - 공제한도금액 = 산출세액 × (국외원천소득 / 종합소득금액)
    - 공제세액 = min(공제한도금액, 실제 외국납부세액)
    - 초과납부세액은 이월공제(5년) 가능하나 이 함수는 당기 공제만 계산

    Args:
        income_tax: 종합소득 산출세액 (원)
        total_income: 종합소득금액 (원)
        foreign_income: 국외원천소득 (원)
        foreign_tax_paid: 실제 외국에서 납부한 세액 (원)

    Returns:
        {
          '공제한도금액': int,   # 산출세액 × (국외원천소득 / 종합소득금액)
          '실외국납부세액': int,
          '공제세액': int,       # min(공제한도금액, 실외국납부세액)
          '초과납부세액': int,   # 한도 초과분 (이월 가능)
          '근거': str,
        }

    사용 예시:
        calculate_foreign_tax_credit(10_000_000, 100_000_000, 20_000_000, 3_000_000)
        # {'공제한도금액': 2000000, '공제세액': 2000000, '초과납부세액': 1000000, ...}
    """
    income_tax = int(income_tax)
    total_income = int(total_income)
    foreign_income = int(foreign_income)
    foreign_tax_paid = int(foreign_tax_paid)

    if income_tax < 0:
        raise ValueError("income_tax must be >= 0")
    if total_income < 0:
        raise ValueError("total_income must be >= 0")
    if foreign_income < 0:
        raise ValueError("foreign_income must be >= 0")
    if foreign_tax_paid < 0:
        raise ValueError("foreign_tax_paid must be >= 0")

    if total_income == 0:
        공제한도금액 = 0
    else:
        공제한도금액 = int(income_tax * (foreign_income / total_income))

    공제세액 = int(min(int(공제한도금액), int(foreign_tax_paid)))
    초과납부세액 = int(max(int(foreign_tax_paid) - int(공제한도금액), 0))

    return {
        "공제한도금액": int(공제한도금액),
        "실외국납부세액": int(foreign_tax_paid),
        "공제세액": int(공제세액),
        "초과납부세액": int(초과납부세액),
        "근거": "소득세법 제57조(외국납부세액공제)",
    }


def calculate_non_business_land_tax(taxable_income: int) -> dict:
    """비사업용 토지 양도소득세 계산 (소득세법 §104①8).

    - 기본세율(소득세법 §55) + 10%p 가산 누진세율 적용
    - 누진공제액 방식으로 산출세액 계산

    세율표(기본세율 + 10%p, 누진공제액 포함):
        1,400만 이하: 16% (누진공제 0)
        1,400만~5,000만: 25% (누진공제 1,260,000)
        5,000만~8,800만: 34% (누진공제 5,760,000)
        8,800만~1.5억: 45% (누진공제 15,440,000)
        1.5억~3억: 48% (누진공제 19,940,000)
        3억~5억: 50% (누진공제 25,940,000)
        5억~10억: 52% (누진공제 35,940,000)
        10억 초과: 55% (누진공제 65,940,000)

    Args:
        taxable_income: 양도소득과세표준 (원)

    Returns:
        {
          '과세표준': int,
          '산출세액': int,
          '적용세율': float,   # 예: 0.16
          '근거': str,
        }

    사용 예시:
        calculate_non_business_land_tax(10_000_000)
        # {'과세표준': 10000000, '산출세액': 1600000, '적용세율': 0.16, ...}
    """
    과세표준 = int(taxable_income)

    if 과세표준 <= 0:
        return {
            "과세표준": int(과세표준),
            "산출세액": 0,
            "적용세율": 0.0,
            "근거": "소득세법 제104조 제1항 제8호(비사업용 토지)",
        }

    구간표 = [
        (14_000_000, 0.16, 0),
        (50_000_000, 0.25, 1_260_000),
        (88_000_000, 0.34, 5_760_000),
        (150_000_000, 0.45, 15_440_000),
        (300_000_000, 0.48, 19_940_000),
        (500_000_000, 0.50, 25_940_000),
        (1_000_000_000, 0.52, 35_940_000),
        (float("inf"), 0.55, 65_940_000),
    ]

    적용세율 = 0.0
    누진공제 = 0
    for 상한, 세율, 공제 in 구간표:
        if 과세표준 <= 상한:
            적용세율 = float(세율)
            누진공제 = int(공제)
            break

    산출세액 = int(max(int(과세표준 * 적용세율) - 누진공제, 0))
    return {
        "과세표준": int(과세표준),
        "산출세액": int(산출세액),
        "적용세율": float(적용세율),
        "근거": "소득세법 제104조 제1항 제8호(비사업용 토지)",
    }


# ---------------------------------------------------------------------------
# Ch01. 소득세 총설
# ---------------------------------------------------------------------------

def is_resident(
    has_domestic_address: bool = False,
    domestic_days: int = 0,
) -> dict:
    """거주자/비거주자 판정 (소득세법 §1의2, 시행령 §2).

    거주자 요건 (둘 중 하나 충족):
      (1) 국내에 주소를 둔 경우
      (2) 국내에 183일 이상의 거소를 둔 경우

    거주자: 국내외 전 소득에 대해 납세의무
    비거주자: 국내원천소득에 대해서만 납세의무

    Args:
        has_domestic_address: 국내 주소 보유 여부
            (계속 183일+ 필요 직업, 국내 생계 가족+183일+ 거주 예상 등 포함)
        domestic_days: 해당 과세기간 내 국내 거소 일수 (주소 없이 거소만 있는 경우)

    Returns:
        {
          '구분': '거주자' | '비거주자',
          '판정근거': str,        # 어느 요건으로 거주자 판정됐는지
          '납세의무': str,        # 국내외 전소득 | 국내원천소득
          '거주자': bool,
          '근거': str,
        }

    사용 예시:
        is_resident(has_domestic_address=True)
        # {'구분': '거주자', '판정근거': '국내 주소 보유', ...}

        is_resident(domestic_days=200)
        # {'구분': '거주자', '판정근거': '국내 거소 183일 이상(200일)', ...}

        is_resident(has_domestic_address=False, domestic_days=100)
        # {'구분': '비거주자', ...}
    """
    if has_domestic_address:
        return {
            "구분": "거주자",
            "판정근거": "국내 주소 보유",
            "납세의무": "국내외 전 소득",
            "거주자": True,
            "근거": "소득세법 §1의2①1호, 시행령 §2①",
        }
    if domestic_days >= 183:
        return {
            "구분": "거주자",
            "판정근거": f"국내 거소 183일 이상({domestic_days}일)",
            "납세의무": "국내외 전 소득",
            "거주자": True,
            "근거": "소득세법 §1의2①1호, 시행령 §2②",
        }
    return {
        "구분": "비거주자",
        "판정근거": f"국내 주소 없음, 거소 {domestic_days}일(183일 미만)",
        "납세의무": "국내원천소득만",
        "거주자": False,
        "근거": "소득세법 §1의2①2호",
    }


def get_taxable_period(
    year: int,
    death_date: Optional[date] = None,
    departure_date: Optional[date] = None,
) -> dict:
    """과세기간 특례 계산 (소득세법 §5).

    원칙: 1월 1일 ~ 12월 31일 (1년)
    특례:
      - 사망: 1월 1일 ~ 사망일 (§5②)
      - 출국(거주자 → 비거주자): 1월 1일 ~ 출국일 (§5③)

    Args:
        year: 귀속연도
        death_date: 사망일 (사망 특례 시 입력)
        departure_date: 출국일 (출국 특례 시 입력; 해당일 이후 비거주자 전환)

    Returns:
        {
          '과세기간시작': date,
          '과세기간종료': date,
          '일수': int,
          '특례': '원칙' | '사망' | '출국',
          '신고기한안내': str,
          '근거': str,
        }

    사용 예시:
        get_taxable_period(2024)
        # 과세기간: 2024-01-01 ~ 2024-12-31 (366일)

        get_taxable_period(2024, death_date=date(2024, 8, 15))
        # 과세기간: 2024-01-01 ~ 2024-08-15 (228일)

        get_taxable_period(2024, departure_date=date(2024, 9, 30))
        # 과세기간: 2024-01-01 ~ 2024-09-30 (274일)
    """
    시작 = date(year, 1, 1)

    if death_date is not None:
        종료 = death_date
        일수 = (종료 - 시작).days + 1
        return {
            "과세기간시작": 시작,
            "과세기간종료": 종료,
            "일수": 일수,
            "특례": "사망",
            "신고기한안내": f"사망일({death_date}) 속하는 달의 말일부터 6개월 이내 (상속인/납세관리인 신고)",
            "근거": "소득세법 §5②, §74①",
        }

    if departure_date is not None:
        종료 = departure_date
        일수 = (종료 - 시작).days + 1
        return {
            "과세기간시작": 시작,
            "과세기간종료": 종료,
            "일수": 일수,
            "특례": "출국",
            "신고기한안내": f"출국일({departure_date}) 전날까지 신고·납부 의무",
            "근거": "소득세법 §5③, §74③",
        }

    종료 = date(year, 12, 31)
    일수 = (종료 - 시작).days + 1
    return {
        "과세기간시작": 시작,
        "과세기간종료": 종료,
        "일수": 일수,
        "특례": "원칙",
        "신고기한안내": f"다음 연도 5월 1일 ~ 5월 31일",
        "근거": "소득세법 §5①",
    }


def calculate_nontaxable_interest(items: list[dict]) -> dict:
    """비과세 이자소득 판정 (프로젝트 2024년 귀속 기준).

    - 비과세종합저축: 원금 2천만원 한도
    - ISA: 일반형 200만원, 서민/저소득형 400만원 한도
    - 조합등예탁금: 원금 3천만원 한도
    """
    details: list[dict] = []
    total_nontaxable = 0
    total_taxable = 0

    for item in items:
        item_type = str(item.get("type", "other"))
        amount = int(item.get("amount", 0))
        principal = int(item.get("principal", 0))
        isa_type = str(item.get("isa_type", "general"))

        if item_type == "nontaxable_savings":
            if principal <= 20_000_000:
                nontaxable = amount
            elif principal > 0:
                nontaxable = int(amount * 20_000_000 / principal)
            else:
                nontaxable = 0
        elif item_type == "isa":
            isa_limit = 4_000_000 if isa_type == "low_income" else 2_000_000
            nontaxable = min(amount, isa_limit)
        elif item_type == "coop":
            if principal <= 30_000_000:
                nontaxable = amount
            elif principal > 0:
                nontaxable = int(amount * 30_000_000 / principal)
            else:
                nontaxable = 0
        else:
            nontaxable = 0

        nontaxable = max(min(nontaxable, amount), 0)
        taxable = amount - nontaxable

        details.append(
            {
                "type": item_type,
                "이자소득": amount,
                "비과세": nontaxable,
                "과세": taxable,
            }
        )
        total_nontaxable += nontaxable
        total_taxable += taxable

    return {
        "항목별_내역": details,
        "총비과세이자": total_nontaxable,
        "총과세이자": total_taxable,
        "비고": "비과세종합저축·ISA·조합등예탁금 한도를 반영한 프로젝트 계산 결과",
    }


def calculate_interest_income_tax(
    taxable_interest,
    has_anonymous: bool = False,
    long_term_bond_interest: int = 0,
    long_term_bond_separate_election: bool = False,
    workplace_mutual_aid_excess: int = 0,
) -> dict:
    """이자소득세 계산 — 무조건 분리과세 분류 및 종합과세 이월액 반환."""
    remaining = int(taxable_interest)
    long_term_bond_interest = int(long_term_bond_interest)
    workplace_mutual_aid_excess = int(workplace_mutual_aid_excess)

    anonymous_tax = None
    long_term_bond_tax = None
    notes: list[str] = []

    if remaining < 0:
        raise ValueError("taxable_interest는 0 이상이어야 합니다.")

    if has_anonymous:
        anonymous_tax = int(remaining * 0.45)
        notes.append("비실명 이자는 전액 45% 무조건 분리과세")
        remaining = 0
    else:
        if long_term_bond_separate_election and long_term_bond_interest > 0:
            separated_base = min(long_term_bond_interest, remaining)
            long_term_bond_tax = int(separated_base * 0.30)
            remaining -= separated_base
            notes.append(f"장기채권 이자 {_format_amount(separated_base)}에 30% 분리과세 선택 적용")

        if workplace_mutual_aid_excess > 0:
            deducted = min(workplace_mutual_aid_excess, remaining)
            remaining -= deducted
            notes.append(
                f"직장공제회 초과반환금 {_format_amount(deducted)}은 기본세율 특례 대상으로 별도 신고"
            )

    separate_subtotal = 0
    if anonymous_tax is not None:
        separate_subtotal += anonymous_tax
    if long_term_bond_tax is not None:
        separate_subtotal += long_term_bond_tax

    if not notes:
        notes.append("무조건 분리과세 대상 없음")

    return {
        "비실명_분리과세세액": anonymous_tax,
        "장기채권_분리과세세액": long_term_bond_tax,
        "직장공제회_초과반환금": max(min(workplace_mutual_aid_excess, int(taxable_interest)), 0),
        "종합과세_이자합계": remaining,
        "무조건분리과세_소계": separate_subtotal,
        "비고": "; ".join(notes),
    }


def _format_amount(amount: int) -> str:
    return f"{int(amount):,}원"


def calculate_deemed_dividend(
    deemed_type,
    received_amount,
    acquisition_cost,
    capital_reserve_transfer: bool = False,
    revaluation_reserve_transfer: bool = False,
) -> dict:
    """의제배당 계산 (소득세법 제17조 제2항·제3항, 2024년 귀속 프로젝트 기준)."""
    valid_types = {
        "surplus_transfer",
        "capital_reduction",
        "dissolution",
        "merger",
        "split",
    }
    if deemed_type not in valid_types:
        raise ValueError(
            "deemed_type must be one of: surplus_transfer, capital_reduction, dissolution, merger, split"
        )

    received_amount = int(received_amount)
    acquisition_cost = int(acquisition_cost)

    if received_amount < 0:
        raise ValueError("received_amount는 0 이상이어야 합니다.")
    if acquisition_cost < 0:
        raise ValueError("acquisition_cost는 0 이상이어야 합니다.")

    is_exempt = False
    gross_up_target = False
    note = ""

    if deemed_type == "surplus_transfer":
        if capital_reserve_transfer:
            deemed_dividend = 0
            is_exempt = True
            note = "자본준비금의 자본전입으로 인한 의제배당 제외"
        elif revaluation_reserve_transfer:
            deemed_dividend = 0
            is_exempt = True
            note = "재평가적립금의 자본전입으로 인한 의제배당 제외"
        else:
            deemed_dividend = received_amount
            gross_up_target = deemed_dividend > 0
            note = "잉여금의 자본전입으로 취득한 주식가액 전액 과세"
    else:
        deemed_dividend = max(received_amount - acquisition_cost, 0)
        gross_up_target = deemed_dividend > 0
        type_notes = {
            "capital_reduction": "감자·주식소각으로 받은 재산가액에서 주식취득가액 차감",
            "dissolution": "해산 잔여재산 분배액에서 주식취득가액 차감",
            "merger": "합병대가에서 소멸법인 주식취득가액 차감",
            "split": "분할대가에서 분할 전 주식취득가액 차감",
        }
        note = type_notes[deemed_type]

    gross_up = int(deemed_dividend * 0.10) if gross_up_target else 0
    dividend_income = int(deemed_dividend + gross_up)

    return {
        "의제배당유형": deemed_type,
        "취득재산가액": received_amount,
        "주식취득가액": acquisition_cost,
        "의제배당금액": int(deemed_dividend),
        "비과세여부": bool(is_exempt),
        "Gross_up_대상": bool(gross_up_target),
        "Gross_up금액": int(gross_up),
        "배당소득금액": int(dividend_income),
        "비고": note,
    }


def calculate_recognized_dividend(recognized_amount, recipient_type: str = "resident") -> dict:
    """인정배당 계산 (소득세법 제17조 제1항 제4호·제3항, 2024년 귀속 프로젝트 기준)."""
    if recipient_type not in {"resident", "nonresident"}:
        raise ValueError("recipient_type must be one of: resident, nonresident")

    recognized_amount = int(recognized_amount)
    if recognized_amount < 0:
        raise ValueError("recognized_amount는 0 이상이어야 합니다.")

    gross_up = int(recognized_amount * 0.10) if recipient_type == "resident" else 0
    dividend_income = int(recognized_amount + gross_up)

    if recipient_type == "resident":
        taxation = "거주자 종합과세 기준 Gross-up 10% 적용"
        note = "법인세법상 배당처분 금액에 Gross-up 가산"
    else:
        taxation = "비거주자 원천과세 기준 Gross-up 배제"
        note = "비거주자는 Gross-up 없이 인정배당금액만 배당소득으로 반영"

    return {
        "인정배당금액": recognized_amount,
        "Gross_up금액": int(gross_up),
        "배당소득금액": int(dividend_income),
        "수령인유형": recipient_type,
        "과세방식": taxation,
        "비고": note,
    }


# 내용연수별 정률법 상각률 (소득세법 시행규칙 별표 기준)
_DECLINING_BALANCE_RATES = {
    2: 0.451, 3: 0.369, 4: 0.316, 5: 0.451,
    6: 0.394, 7: 0.449, 8: 0.313, 9: 0.288,
    10: 0.259, 15: 0.184, 20: 0.142, 40: 0.074,
}


def calculate_entertainment_expense_limit(
    revenue: int,
    actual_expense: int,
    is_sme: bool = False,
    months: int = 12,
) -> dict:
    rev = int(revenue)
    actual = int(actual_expense)
    months = max(1, min(12, int(months)))

    base_limit_annual = 36_000_000 if is_sme else 12_000_000
    base_limit = int(base_limit_annual * months / 12)

    if rev <= 10_000_000_000:
        rev_limit = int(rev * 0.003)
    elif rev <= 50_000_000_000:
        rev_limit = 30_000_000 + int((rev - 10_000_000_000) * 0.002)
    else:
        rev_limit = 110_000_000 + int((rev - 50_000_000_000) * 0.0003)

    total_limit = base_limit + rev_limit
    deductible = min(actual, total_limit)
    excess = max(actual - total_limit, 0)

    sme_label = '중소기업' if is_sme else '일반'
    return {
        '기본한도': base_limit,
        '수입금액한도': rev_limit,
        '총한도': total_limit,
        '실지출액': actual,
        '필요경비산입액': deductible,
        '한도초과_불산입액': excess,
        '비고': f'{sme_label} 기본한도 {base_limit:,}원 + 수입금액한도 {rev_limit:,}원 = 총한도 {total_limit:,}원',
    }


def calculate_depreciation(
    acquisition_cost: int,
    useful_life: int,
    method: str,
    book_value=None,
    salvage_ratio: float = 0.05,
) -> dict:
    cost = int(acquisition_cost)
    bv = int(book_value) if book_value is not None else cost
    salvage = int(cost * salvage_ratio)

    if method == 'straight_line':
        depreciable = cost - salvage
        annual_limit = int(depreciable / useful_life)
        note = f'정액법: ({cost:,} - {salvage:,}) / {useful_life}년 = {annual_limit:,}원/년'
    elif method == 'declining_balance':
        rate = _DECLINING_BALANCE_RATES.get(useful_life)
        if rate is None:
            if salvage_ratio > 0:
                rate = round(1 - (salvage_ratio ** (1 / useful_life)), 3)
            else:
                rate = round(1 - (0.05 ** (1 / useful_life)), 3)
        annual_limit = int(bv * rate)
        annual_limit = min(annual_limit, max(bv - salvage, 0))
        note = f'정률법: 기초장부가액 {bv:,}원 × 상각률 {rate} = {annual_limit:,}원 (내용연수 {useful_life}년)'
    else:
        raise ValueError(f'지원하지 않는 상각방법: {method}')

    return {
        '상각방법': '정액법' if method == 'straight_line' else '정률법',
        '취득가액': cost,
        '내용연수': useful_life,
        '잔존가액': salvage,
        '연간상각한도': annual_limit,
        '비고': note,
    }


def calculate_car_expense_limit(
    total_car_expense: int,
    business_use_ratio: float,
    depreciation_in_expense: int = 0,
    months: int = 12,
) -> dict:
    total = int(total_car_expense)
    ratio = max(0.0, min(1.0, float(business_use_ratio)))
    depr = int(depreciation_in_expense)
    months = max(1, min(12, int(months)))

    business_amount = int(total * ratio)
    non_business = total - business_amount

    depr_annual_limit = int(8_000_000 * months / 12)
    business_depr = int(depr * ratio)
    depr_excess = max(business_depr - depr_annual_limit, 0)

    deductible = business_amount - depr_excess
    total_disallowed = non_business + depr_excess

    notes = [f'업무사용비율 {ratio*100:.0f}%: 업무사용금액 {business_amount:,}원']
    if non_business > 0:
        notes.append(f'비업무사용 불산입 {non_business:,}원')
    if depr_excess > 0:
        notes.append(f'감가상각비 한도초과 이월 {depr_excess:,}원 (한도 {depr_annual_limit:,}원)')

    return {
        '총관련비용': total,
        '업무사용비율': ratio,
        '업무사용금액': business_amount,
        '비업무사용_불산입': non_business,
        '감가상각비_연한도': depr_annual_limit,
        '감가상각비_한도초과_이월': depr_excess,
        '필요경비산입액': deductible,
        '총불산입액': total_disallowed,
        '비고': ' | '.join(notes),
    }


def calculate_housing_savings_deduction(
    annual_payment: int,
    total_salary: int,
    is_householder: bool = True,
    has_house: bool = False,
) -> dict:
    payment = int(annual_payment)
    salary = int(total_salary)
    salary_limit = 70_000_000
    payment_annual_limit = 2_400_000
    deduction_limit = 3_000_000
    deduction_rate = 0.40

    if not is_householder:
        return {
            '납입액': payment,
            '공제율': deduction_rate,
            '공제대상납입액': 0,
            '산출공제액': 0,
            '공제한도': deduction_limit,
            '공제액': 0,
            '적용여부': False,
            '미적용사유': '세대주 아님',
            '비고': '세대주 요건 미충족 — 공제 불가',
        }
    if has_house:
        return {
            '납입액': payment,
            '공제율': deduction_rate,
            '공제대상납입액': 0,
            '산출공제액': 0,
            '공제한도': deduction_limit,
            '공제액': 0,
            '적용여부': False,
            '미적용사유': '주택 보유',
            '비고': '무주택 요건 미충족 — 공제 불가',
        }
    if salary > salary_limit:
        return {
            '납입액': payment,
            '공제율': deduction_rate,
            '공제대상납입액': 0,
            '산출공제액': 0,
            '공제한도': deduction_limit,
            '공제액': 0,
            '적용여부': False,
            '미적용사유': f'총급여 {salary:,}원 > 7,000만원',
            '비고': '총급여 7,000만원 초과 — 공제 불가',
        }

    eligible_payment = min(payment, payment_annual_limit)
    calculated = int(eligible_payment * deduction_rate)
    deduction = min(calculated, deduction_limit)
    return {
        '납입액': payment,
        '공제율': deduction_rate,
        '공제대상납입액': eligible_payment,
        '산출공제액': calculated,
        '공제한도': deduction_limit,
        '공제액': deduction,
        '적용여부': True,
        '미적용사유': '',
        '비고': f'납입액 {eligible_payment:,}원 × {deduction_rate:.0%} = {calculated:,}원 (한도 {deduction_limit:,}원 이내)',
    }


def apply_deduction_aggregate_limit(deductions: dict) -> dict:
    aggregate_limit = 25_000_000
    total = sum(deductions.values())
    if total <= aggregate_limit:
        return {
            '입력공제합계': total,
            '종합한도': aggregate_limit,
            '적용공제합계': total,
            '한도초과액': 0,
            '항목별_조정': dict(deductions),
            '비고': f'합계 {total:,}원 ≤ 한도 {aggregate_limit:,}원 — 전액 공제',
        }

    excess = total - aggregate_limit
    ratio = aggregate_limit / total
    adjusted = {key: int(value * ratio) for key, value in deductions.items()}
    adjusted_total = sum(adjusted.values())
    diff = aggregate_limit - adjusted_total
    if diff > 0 and deductions:
        largest_key = max(deductions, key=deductions.get)
        adjusted[largest_key] += diff

    return {
        '입력공제합계': total,
        '종합한도': aggregate_limit,
        '적용공제합계': aggregate_limit,
        '한도초과액': excess,
        '항목별_조정': adjusted,
        '비고': f'합계 {total:,}원 > 한도 {aggregate_limit:,}원 — {excess:,}원 초과분 불공제',
    }


def calculate_insurance_tax_credit(general_insurance: int = 0, disability_insurance: int = 0) -> dict:
    general_insurance = max(int(general_insurance), 0)
    disability_insurance = max(int(disability_insurance), 0)

    general_credit = int(min(general_insurance, 1_000_000) * 0.12)
    disability_credit = int(min(disability_insurance, 1_000_000) * 0.15)
    total_credit = general_credit + disability_credit

    return {
        '보장성보험료': general_insurance,
        '장애인보장성보험료': disability_insurance,
        '보장성공제액': general_credit,
        '장애인공제액': disability_credit,
        '총세액공제액': total_credit,
        '비고': '소득세법 §59의4① 기준: 보장성 12%(한도 100만), 장애인전용 15%(한도 100만)',
    }


def calculate_medical_tax_credit_detail(
    total_salary,
    general_medical=0,
    self_medical=0,
    infertility_medical=0,
    premature_medical=0,
) -> dict:
    total_salary = max(int(total_salary), 0)
    general_medical = max(int(general_medical), 0)
    self_medical = max(int(self_medical), 0)
    infertility_medical = max(int(infertility_medical), 0)
    premature_medical = max(int(premature_medical), 0)

    threshold = int(total_salary * 0.03)
    general_after = max(general_medical - threshold, 0)
    remaining_threshold = max(threshold - general_medical, 0)
    self_after = max(self_medical - remaining_threshold, 0)

    general_eligible = min(general_after, 2_000_000)
    general_credit = int(general_eligible * 0.15)
    self_credit = int(self_after * 0.15)
    infertility_credit = int(infertility_medical * 0.30)
    premature_credit = int(premature_medical * 0.20)
    total_credit = general_credit + self_credit + infertility_credit + premature_credit

    return {
        '총급여': total_salary,
        '공제문턱': threshold,
        '총의료비': general_medical + self_medical + infertility_medical + premature_medical,
        '일반의료비': general_medical,
        '본인등의료비': self_medical,
        '난임시술비': infertility_medical,
        '미숙아의료비': premature_medical,
        '일반공제대상': general_eligible,
        '일반세액공제': general_credit,
        '본인등세액공제': self_credit,
        '난임세액공제': infertility_credit,
        '미숙아세액공제': premature_credit,
        '총세액공제액': total_credit,
        '비고': '소득세법 §59의4② 기준: 총급여 3% 문턱을 일반의료비 우선 차감 후 본인등에 차감, 일반의료비 공제대상 한도 200만',
    }


def calculate_education_tax_credit(
    self_education=0,
    preschool_children=None,
    elementary_middle_high=None,
    university_students=None,
    disability_special=0,
) -> dict:
    preschool_children = preschool_children or []
    elementary_middle_high = elementary_middle_high or []
    university_students = university_students or []

    self_education = max(int(self_education), 0)
    disability_special = max(int(disability_special), 0)

    preschool_and_school = sum(
        min(max(int(amount), 0), 3_000_000)
        for amount in [*preschool_children, *elementary_middle_high]
    )
    university_total = sum(
        min(max(int(amount), 0), 9_000_000)
        for amount in university_students
    )
    eligible_total = self_education + preschool_and_school + university_total + disability_special
    total_credit = int(eligible_total * 0.15)

    return {
        '본인교육비': self_education,
        '취학전초중고교육비': preschool_and_school,
        '대학교육비': university_total,
        '장애인특수교육비': disability_special,
        '공제대상합계': eligible_total,
        '총세액공제액': total_credit,
        '비고': '소득세법 §59의4③ 기준: 본인·장애인 특수교육비 무한, 취학전·초중고 1인당 300만, 대학생 1인당 900만',
    }


def calculate_donation_tax_credit(
    legal_donation=0,
    designated_donation=0,
    political_donation=0,
) -> dict:
    legal_donation = max(int(legal_donation), 0)
    designated_donation = max(int(designated_donation), 0)
    political_donation = max(int(political_donation), 0)

    general_donation = legal_donation + designated_donation

    tier1_base = min(general_donation, 10_000_000)
    tier2_base = min(max(general_donation - 10_000_000, 0), 20_000_000)
    tier3_base = max(general_donation - 30_000_000, 0)
    donation_credit = (
        int(tier1_base * 0.15)
        + int(tier2_base * 0.30)
        + int(tier3_base * 0.40)
    )

    political_credit = 0
    first_band = min(political_donation, 100_000)
    if first_band > 0:
        political_credit += int(first_band * (100 / 110))
    second_band = min(max(political_donation - 100_000, 0), 9_900_000)
    if second_band > 0:
        political_credit += int(second_band * 0.15)
    third_band = max(political_donation - 10_000_000, 0)
    if third_band > 0:
        political_credit += int(third_band * 0.25)

    total_credit = donation_credit + political_credit

    return {
        '법정지정기부금': general_donation,
        '정치자금기부금': political_donation,
        '기부금세액공제': donation_credit,
        '정치자금세액공제': political_credit,
        '총세액공제액': total_credit,
        '비고': '소득세법 §59의4④ 기준: 법정·지정기부금 1천만 이하 15%, 3천만 이하 30%, 3천만 초과 40%(2024 한시), 정치자금기부금 별도 계산',
    }


def calculate_disaster_tax_credit(calculated_tax, disaster_loss, total_business_assets) -> dict:
    calculated_tax = max(int(calculated_tax), 0)
    disaster_loss = max(int(disaster_loss), 0)
    total_business_assets = int(total_business_assets)

    if total_business_assets <= 0:
        return {
            '산출세액': calculated_tax,
            '재해손실액': disaster_loss,
            '사업용자산총액': total_business_assets,
            '재해손실비율': 0.0,
            '공제액': 0,
            '비고': '소득세법 §58의2 기준: 사업용자산총액이 0 이하이면 재해손실세액공제를 적용할 수 없음',
        }

    ratio = min(disaster_loss / total_business_assets, 1.0)
    credit = min(int(calculated_tax * ratio), calculated_tax)

    return {
        '산출세액': calculated_tax,
        '재해손실액': disaster_loss,
        '사업용자산총액': total_business_assets,
        '재해손실비율': round(ratio, 4),
        '공제액': credit,
        '비고': '소득세법 §58의2 기준: 산출세액 × 재해손실비율',
    }


def check_one_house_exemption(
    transfer_price: int,
    acquisition_price: int,
    holding_years: float,
    residence_years: float = 0.0,
    is_adjustment_zone: bool = False,
    household_house_count: int = 1,
) -> dict:
    price = int(transfer_price)
    acq = int(acquisition_price)
    gain = max(price - acq, 0)
    THRESHOLD = 1_200_000_000
    unmet = []

    if household_house_count != 1:
        unmet.append(f'세대 주택수 {household_house_count}채 (1채 요건 미충족)')
    if holding_years < 2.0:
        unmet.append(f'보유기간 {holding_years}년 < 2년')
    if is_adjustment_zone and residence_years < 2.0:
        unmet.append(f'조정대상지역 거주기간 {residence_years}년 < 2년')

    if unmet:
        return {
            '양도가액': price,
            '취득가액': acq,
            '양도차익': gain,
            '보유기간': holding_years,
            '거주기간': residence_years,
            '비과세여부': False,
            '비과세사유': '',
            '고가주택여부': price > THRESHOLD,
            '과세대상양도차익': gain,
            '비과세양도차익': 0,
            '미충족요건': unmet,
            '비고': f'비과세 요건 미충족: {", ".join(unmet)}',
        }

    is_expensive = price > THRESHOLD
    if not is_expensive:
        return {
            '양도가액': price,
            '취득가액': acq,
            '양도차익': gain,
            '보유기간': holding_years,
            '거주기간': residence_years,
            '비과세여부': True,
            '비과세사유': '1세대1주택 (12억 이하)',
            '고가주택여부': False,
            '과세대상양도차익': 0,
            '비과세양도차익': gain,
            '미충족요건': [],
            '비고': f'양도가액 {price:,}원 ≤ 12억 — 전액 비과세',
        }

    taxable_gain = int(gain * (price - THRESHOLD) / price)
    nontaxable_gain = gain - taxable_gain
    return {
        '양도가액': price,
        '취득가액': acq,
        '양도차익': gain,
        '보유기간': holding_years,
        '거주기간': residence_years,
        '비과세여부': True,
        '비과세사유': '1세대1주택 (고가주택 — 초과분만 과세)',
        '고가주택여부': True,
        '과세대상양도차익': taxable_gain,
        '비과세양도차익': nontaxable_gain,
        '미충족요건': [],
        '비고': f'고가주택: 양도차익 {gain:,}원 × ({price:,}-12억)/{price:,} = 과세 {taxable_gain:,}원',
    }


def calculate_estimated_acquisition_price(
    transfer_standard_price: int,
    acquisition_standard_price: int,
    actual_transfer_price: int,
    necessary_expense: int = 0,
) -> dict:
    transfer = int(actual_transfer_price)
    t_std = int(transfer_standard_price)
    a_std = int(acquisition_standard_price)
    expense = int(necessary_expense)

    if t_std <= 0:
        return {
            '실지양도가액': transfer,
            '양도당시기준시가': t_std,
            '취득당시기준시가': a_std,
            '환산취득가액': 0,
            '필요경비': expense,
            '양도차익': max(transfer - expense, 0),
            '비고': '양도당시기준시가 0 — 환산 불가',
        }

    ratio = a_std / t_std
    estimated_acq = int(transfer * ratio)
    gain = max(transfer - estimated_acq - expense, 0)
    return {
        '실지양도가액': transfer,
        '양도당시기준시가': t_std,
        '취득당시기준시가': a_std,
        '환산취득가액': estimated_acq,
        '필요경비': expense,
        '양도차익': gain,
        '비고': f'환산취득가액 = {transfer:,}원 × ({a_std:,}/{t_std:,}) = {estimated_acq:,}원 | 양도차익 {gain:,}원',
    }


def calculate_withholding_tax(income_amount: int, income_type: str, is_resident: bool = True) -> dict:
    amount = int(income_amount)
    RESIDENT_RATES = {
        'interest': (0.14, '§129①1호'),
        'dividend': (0.14, '§129①2호'),
        'business_service': (0.03, '§129①3호'),
        'other': (0.20, '§129①6호'),
        'pension': (0.05, '§129①5호'),
    }
    NONRESIDENT_RATES = {
        'interest': (0.20, '§156①1호'),
        'dividend': (0.20, '§156①2호'),
        'royalty': (0.20, '§156①7호'),
        'personal_service': (0.20, '§156①6호'),
        'other': (0.20, '§156①'),
    }
    if is_resident:
        if income_type not in RESIDENT_RATES:
            raise ValueError(f'지원하지 않는 거주자 소득유형: {income_type}')
        rate, basis = RESIDENT_RATES[income_type]
    else:
        if income_type not in NONRESIDENT_RATES:
            raise ValueError(f'지원하지 않는 비거주자 소득유형: {income_type}')
        rate, basis = NONRESIDENT_RATES[income_type]
    tax = int(amount * rate)
    local_tax = int(tax * 0.10)
    total = tax + local_tax
    return {
        '소득금액': amount,
        '소득유형': income_type,
        '거주자여부': is_resident,
        '원천징수세율': rate,
        '원천징수세액': tax,
        '지방소득세': local_tax,
        '총부담세액': total,
        '법령근거': basis,
        '비고': f'{amount:,}원 × {rate:.0%} = {tax:,}원 (지방소득세 포함 총 {total:,}원)',
    }


def calculate_nonresident_tax(
    income_amount: int,
    income_type: str,
    treaty_rate=None,
    treaty_country: str = '',
) -> dict:
    amount = int(income_amount)
    BASE_RATE = 0.20
    applied_rate = float(treaty_rate) if treaty_rate is not None else BASE_RATE
    tax = int(amount * applied_rate)
    local_tax = int(tax * 0.10)
    total = tax + local_tax
    treaty_note = (
        f' (조세조약 {treaty_country} 제한세율 {applied_rate:.0%})'
        if treaty_rate is not None
        else ''
    )
    return {
        '국내원천소득금액': amount,
        '소득유형': income_type,
        '기본세율': BASE_RATE,
        '적용세율': applied_rate,
        '조세조약국': treaty_country,
        '원천징수세액': tax,
        '지방소득세': local_tax,
        '총부담세액': total,
        '비고': f'{amount:,}원 × {applied_rate:.0%} = {tax:,}원{treaty_note}',
    }


# ── §104 주식 양도소득세 ──────────────────────────────────────────────────────


def calculate_stock_transfer_tax(
    transfer_price: int,
    acquisition_price: int,
    necessary_expenses: int = 0,
    holding_years: float = 0.0,
    stock_type: str = "listed_major",
) -> dict:
    """주식 양도소득세 계산 (소득세법 §104①, 2024년 귀속).

    stock_type:
      listed_major   — 상장·코스닥 대주주 (§104①5: 3억 이하 20%, 3억 초과 25%, 1년 미만 45%)
      listed_minor   — 상장·코스닥 소액주주 (비과세, 금투세 유예)
      unlisted       — 비상장 일반 (§104①4: 3억 이하 20%, 3억 초과 25%)
      unlisted_sme   — 비상장 중소기업 (§104①4: 10%)
    """
    tp = int(transfer_price)
    ap = int(acquisition_price)
    ne = int(necessary_expenses)
    hy = float(holding_years)

    gain = max(tp - ap - ne, 0)
    basic_deduction = 2_500_000
    tax_base = max(gain - basic_deduction, 0)

    if stock_type == "listed_minor":
        return {
            "양도차익": gain, "양도소득과세표준": 0, "적용세율": 0.0,
            "산출세액": 0, "지방소득세": 0, "총납부세액": 0,
            "세율_설명": "소액주주 상장주식 비과세 (금투세 유예)",
            "비고": "소액주주 상장주식은 2024년 귀속 기준 양도소득세 비과세",
        }

    if stock_type == "unlisted_sme":
        rate = 0.10
        tax = int(tax_base * rate)
        desc = "비상장 중소기업(§104①4): 10%"
    elif stock_type in ("listed_major", "unlisted"):
        if hy < 1 and stock_type == "listed_major":
            rate = 0.45
            tax = int(tax_base * rate)
            desc = "대주주 1년 미만 보유(§104①5): 45%"
        else:
            if tax_base <= 300_000_000:
                rate = 0.20
                tax = int(tax_base * rate)
                desc = f"{'대주주' if stock_type == 'listed_major' else '비상장'}(§104①{'5' if stock_type == 'listed_major' else '4'}): 3억 이하 20%"
            else:
                tax = int(300_000_000 * 0.20 + (tax_base - 300_000_000) * 0.25)
                rate = tax / tax_base if tax_base else 0.0
                desc = f"{'대주주' if stock_type == 'listed_major' else '비상장'}(§104①{'5' if stock_type == 'listed_major' else '4'}): 3억 이하 20% + 3억 초과 25%"
    else:
        raise ValueError(f"stock_type은 listed_major|listed_minor|unlisted|unlisted_sme 중 하나: {stock_type}")

    local_tax = calculate_local_tax(tax)
    return {
        "양도가액": tp, "취득가액": ap, "필요경비": ne,
        "양도차익": gain, "양도소득기본공제": basic_deduction,
        "양도소득과세표준": tax_base,
        "적용세율": round(rate, 4), "세율_설명": desc,
        "산출세액": tax, "지방소득세": local_tax,
        "총납부세액": tax + local_tax,
        "비고": "",
    }


# ── 영§87 기타소득 필요경비 의제율 자동매핑 ──────────────────────────────────


def get_other_income_expense_ratio(item_subtype: str) -> dict:
    """기타소득 필요경비 의제율 자동 결정 (시행령 §87①).

    item_subtype (§21 항목 키워드):
      prize_public     — 공익법인 시상·포상금 (§87①1호 가, 80%)
      housing_delay    — 주택입주지체상금 (§87①1호 다, 80%)
      patent           — 산업재산권 양도·대여 (§87①1의2호, §21①7, 60%)
      goodwill         — 영업권 양도·대여 (§87①1의2호, §21①8의2, 60%)
      mining_right     — 광업권·어업권 등 (§87①1의2호, §21①9, 60%)
      temp_property    — 물품·장소 일시대여 (§87①1의2호, §21①15, 60%)
      ai_copyright     — 인적용역 기타소득 (§87①1의2호, §21①19, 60%)
      penalty          — 위약금·배상금 (의제 없음, 0%)
      bribe            — 뇌물 등 (의제 없음, 0%)
      invention        — 직무발명보상금 (의제 없음, 0%)
      general          — 기타 (의제 없음, 0%)
    """
    _MAP = {
        "prize_public":  (0.80, "§87①1호 가: 공익법인 시상금 80%"),
        "housing_delay": (0.80, "§87①1호 다: 주택입주지체상금 80%"),
        "patent":        (0.60, "§87①1의2호: 산업재산권(§21①7) 60%"),
        "goodwill":      (0.60, "§87①1의2호: 영업권(§21①8의2) 60%"),
        "mining_right":  (0.60, "§87①1의2호: 광업권·어업권(§21①9) 60%"),
        "temp_property": (0.60, "§87①1의2호: 물품·장소 일시대여(§21①15) 60%"),
        "ai_copyright":  (0.60, "§87①1의2호: 인적용역 기타소득(§21①19) 60%"),
        "penalty":       (0.00, "의제 없음: 위약금·배상금"),
        "bribe":         (0.00, "의제 없음: 뇌물"),
        "invention":     (0.00, "의제 없음: 직무발명보상금"),
        "general":       (0.00, "의제 없음: 일반 기타소득"),
    }
    if item_subtype not in _MAP:
        raise ValueError(f"item_subtype은 {list(_MAP.keys())} 중 하나: {item_subtype}")
    ratio, basis = _MAP[item_subtype]
    return {"의제율": ratio, "법령근거": basis, "항목": item_subtype}


# ── §118의9~16 국외전출세 파이프라인 ────────────────────────────────────────


def calculate_exit_tax(
    market_value_at_exit: int,
    acquisition_price: int,
    necessary_expenses: int = 0,
    stock_type: str = "listed_major",
) -> dict:
    """국외전출세 과세표준 및 산출세액 (소득세법 §118의9~§118의10).

    출국일 당시 시가를 양도가액으로 의제하여 주식 양도소득세를 계산한다.
    """
    mv = int(market_value_at_exit)
    ap = int(acquisition_price)
    ne = int(necessary_expenses)

    gain = max(mv - ap - ne, 0)
    basic_deduction = 2_500_000
    tax_base = max(gain - basic_deduction, 0)

    inner = calculate_stock_transfer_tax(
        transfer_price=mv, acquisition_price=ap,
        necessary_expenses=ne, holding_years=99.0,
        stock_type=stock_type,
    )

    return {
        "출국일_시가": mv, "취득가액": ap, "필요경비": ne,
        "양도소득금액": gain, "양도소득기본공제": basic_deduction,
        "양도소득과세표준": tax_base,
        "산출세액": inner["산출세액"],
        "적용세율": inner["적용세율"],
        "세율_설명": inner["세율_설명"],
        "비고": "§118의10: 출국일 당시 시가를 양도가액으로 의제",
    }


def calculate_exit_tax_adjustment(
    exit_market_value: int,
    actual_sale_price: int,
    exit_computed_tax: int,
    exit_gain: int,
) -> dict:
    """국외전출세 조정공제 (소득세법 §118의12).

    실제 양도가액 < 출국일 시가인 경우, 과다납부분을 비례 환급.
    조정공제액 = 산출세액 × (출국일 시가 − 실제 양도가액) ÷ 양도소득금액
    """
    mv = int(exit_market_value)
    actual = int(actual_sale_price)
    tax = int(exit_computed_tax)
    gain = int(exit_gain)

    if actual >= mv or gain <= 0:
        return {
            "조정공제_적용": False, "조정공제액": 0,
            "비고": "실제 양도가액 ≥ 출국일 시가이므로 조정공제 없음",
        }

    diff = mv - actual
    adjustment = int(tax * diff / gain)

    return {
        "조정공제_적용": True,
        "출국일_시가": mv, "실제_양도가액": actual,
        "차액": diff, "양도소득금액": gain,
        "산출세액": tax, "조정공제액": adjustment,
        "조정후_세액": max(tax - adjustment, 0),
        "비고": f"§118의12: 산출세액 × (시가−실제양도가액) ÷ 양도소득금액 = {adjustment:,}원",
    }


def calculate_exit_tax_foreign_credit(
    foreign_tax_paid: int,
    exit_computed_tax: int,
    adjustment_credit: int = 0,
) -> dict:
    """국외전출자 외국납부세액공제 (소득세법 §118의13).

    한도 = 산출세액 − 조정공제액. 한도 내에서 외국납부세액을 공제.
    """
    foreign = int(foreign_tax_paid)
    tax = int(exit_computed_tax)
    adj = int(adjustment_credit)

    limit = max(tax - adj, 0)
    credit = min(foreign, limit)

    return {
        "외국납부세액": foreign,
        "산출세액": tax, "조정공제액": adj,
        "공제한도": limit, "공제세액": credit,
        "최종세액": max(tax - adj - credit, 0),
        "비고": f"§118의13: 한도 {limit:,}원 내 공제 {credit:,}원",
    }
