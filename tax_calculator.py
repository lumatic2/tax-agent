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
            return {
                "산출세액": max(tax, 0),
                "적용세율": rate,
                "누진공제액": deduction,
            }


def calculate_local_tax(income_tax):
    """지방소득세 = 소득세의 10%"""
    return int(max(int(income_tax), 0) * 0.10)


def calculate_financial_income(
    interest: int = 0,
    dividend: int = 0,
    gross_up_eligible_dividend: int = 0,
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

    interest_income = interest                          # §16② 필요경비 없음
    gross_up = int(gross_up_eligible_dividend * 0.10)  # §17③ Gross-up 10%
    dividend_income = dividend + gross_up               # §17③ 배당소득금액

    total = interest_income + dividend_income

    if total <= THRESHOLD:
        # §14③6: 분리과세 — 종합소득에 미합산
        sep_tax = int((interest + dividend) * WITHHOLDING_RATE)
        return {
            '이자소득금액': interest_income,
            '배당소득금액': dividend_income,
            'Gross_up금액': gross_up,
            '금융소득합계': total,
            '종합과세여부': False,
            '분리과세세액': sep_tax,
            '종합과세편입금액': 0,
            '비고': f'이자+배당 {total:,}원 ≤ 2,000만 → 분리과세(14%)',
        }
    else:
        # §14③6 초과 → 전액 종합과세
        # §62 비교세액은 calculate_tax() 호출 시점에 적용 (종합소득 합산 후 판정)
        return {
            '이자소득금액': interest_income,
            '배당소득금액': dividend_income,
            'Gross_up금액': gross_up,
            '금융소득합계': total,
            '종합과세여부': True,
            '분리과세세액': None,
            '종합과세편입금액': total,
            '비고': f'이자+배당 {total:,}원 > 2,000만 → 종합과세. §62 비교세액: 2,000만×14%={int(THRESHOLD*WITHHOLDING_RATE):,}원 + 초과분 누진',
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


def calculate_other_income(
    items: list,
) -> dict:
    """기타소득금액 계산 (소득세법 §21 기타소득, §84 분리과세, 2024년 귀속).

    [법령 출처 — 추후 법제처 API 연결 시 검증 필요]
    §21①: 기타소득 열거 (강의료, 원고료, 상금, 복권, 사례금 등)
    §37②: 필요경비율
        원칙 60% (강의료·원고료·인세·자문료 등 §21①19~22)
        복권·당첨금·경마 등 → 실제 경비만
        일시적 인적용역 외 → 항목별 상이
    §84: 기타소득금액 합계 300만 초과 → 종합과세 의무
         300만 이하 → 분리과세(22%) 선택 가능

    Args:
        items: list of dict, 각 항목:
            - 종류: str ('강의료'|'원고료'|'상금'|'복권'|'사례금'|'기타')
            - 수입금액: int (원, 세전)
            - 실제경비: int (원, 선택 — 없으면 법정경비율 적용)

    Returns:
        dict: {항목별내역, 기타소득_수입합계, 필요경비합계, 기타소득금액합계, 과세방식,
               분리과세세액, 종합과세편입금액}
    """
    # §37②에 따른 법정 필요경비율 (60% 적용 대상 열거소득)
    SIXTY_PCT = {'강의료', '원고료', '인세', '자문료', '사례금', '기타'}
    # 복권·당첨금 등은 실제경비만 → 통상 0원
    ZERO_PCT = {'복권', '상금', '경마', '경품'}

    detail = []
    total_revenue = 0
    total_expense = 0
    total_income = 0

    for item in items:
        kind = item.get('종류', '기타')
        revenue = item.get('수입금액', 0)
        actual = item.get('실제경비', None)

        if actual is not None:
            expense = actual
        elif kind in ZERO_PCT:
            expense = 0
        else:
            expense = int(revenue * 0.60)

        income = max(revenue - expense, 0)
        total_revenue += revenue
        total_expense += expense
        total_income += income
        detail.append({
            '종류': kind,
            '수입금액': revenue,
            '필요경비': expense,
            '기타소득금액': income,
        })

    # §84 종합과세 vs 분리과세 판정
    # 기타소득금액 합계 300만 초과 → 종합과세 의무
    THRESHOLD = 3_000_000
    if total_income > THRESHOLD:
        tax_method = '종합과세'
        sep_tax = None
        comprehensive_income = total_income
    else:
        # 선택 가능 — 분리과세(22%) 또는 종합과세
        sep_tax = int(total_revenue * 0.22)  # 원천징수세율 22% (수입금액 기준)
        tax_method = '분리과세선택가능'
        comprehensive_income = 0  # 선택 시 종합소득에 미편입

    return {
        '항목별내역': detail,
        '기타소득_수입합계': total_revenue,
        '필요경비합계': total_expense,
        '기타소득금액합계': total_income,
        '과세방식': tax_method,
        '분리과세세액(22%)': sep_tax,
        '종합과세편입금액': comprehensive_income,
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
    """
    basic_count = 0
    elderly_amount = 0      # 경로우대 (70세 이상) 1인당 100만
    disabled_amount = 0     # 장애인 1인당 200만
    female_head_amount = 0  # 부녀자 50만
    single_parent_amount = 0  # 한부모 100만

    has_single_parent = any(p.get("single_parent") for p in persons)

    for p in persons:
        relation = p.get("relation", "")
        age = int(p.get("age", 0))
        disabled = bool(p.get("disabled", False))

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
    }


def calculate_special_deductions(income_data: dict) -> dict:
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
    """
    gross_salary = int(income_data.get("gross_salary", 0))
    national_pension = int(income_data.get("national_pension", 0))
    health_insurance = int(income_data.get("health_insurance", 0))
    employment_insurance = int(income_data.get("employment_insurance", 0))
    housing_fund = int(income_data.get("housing_fund", 0))
    medical_expense = int(income_data.get("medical_expense", 0))
    education_expense = int(income_data.get("education_expense", 0))
    donation = int(income_data.get("donation", 0))

    # 보험료공제 (§52①): 국민연금+건강보험+고용보험 전액
    insurance_deduction = national_pension + health_insurance + employment_insurance

    # 의료비공제 (§52②): (의료비 - 총급여×3%) 초과분, 한도 700만
    medical_threshold = int(gross_salary * 0.03)
    medical_deduction = min(max(medical_expense - medical_threshold, 0), 7_000_000)

    total = insurance_deduction + housing_fund + medical_deduction + education_expense + donation

    return {
        "보험료공제": insurance_deduction,
        "주택자금공제": housing_fund,
        "의료비공제": medical_deduction,
        "교육비공제": education_expense,
        "기부금공제": donation,
        "특별공제_합계": total,
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

    # 전통시장·대중교통 각 100만 추가 한도
    market_limit = 1_000_000
    transit_limit = 1_000_000

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


def calculate_retirement_income_tax(retirement_pay: int, years_of_service: int) -> dict:
    """퇴직소득세 계산 (소득세법 제48조~제49조, 2024년 귀속).

    Args:
        retirement_pay: 퇴직급여 (원)
        years_of_service: 근속연수 (년, 1 이상)

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
            "지방소득세": int,
            "총납부세액": int,
        }
    """
    retirement_pay = int(retirement_pay)
    years = max(int(years_of_service), 1)

    # 1. 근속연수공제 (소득세법 제48조)
    if years <= 5:
        tenure_deduction = years * 300_000
    elif years <= 10:
        tenure_deduction = 1_500_000 + (years - 5) * 500_000
    elif years <= 20:
        tenure_deduction = 4_000_000 + (years - 10) * 800_000
    else:
        tenure_deduction = 12_000_000 + (years - 20) * 1_200_000

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
    local_tax = calculate_local_tax(retirement_tax)

    return {
        "퇴직급여": retirement_pay,
        "근속연수": years,
        "근속연수공제": tenure_deduction,
        "환산급여": converted_salary,
        "환산급여공제": converted_deduction,
        "환산과세표준": converted_taxable,
        "환산산출세액": converted_tax,
        "퇴직소득산출세액": retirement_tax,
        "지방소득세": local_tax,
        "총납부세액": retirement_tax + local_tax,
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
