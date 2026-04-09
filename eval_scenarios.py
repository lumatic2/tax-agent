import math
import sys
from datetime import date

from tax_calculator import (
    apply_deduction_aggregate_limit,
    is_resident,
    get_taxable_period,
    calculate_business_income,
    calculate_card_deduction,
    calculate_dividend_tax_credit,
    calculate_entertainment_expense_limit,
    calculate_deemed_dividend,
    calculate_depreciation,
    calculate_earned_income_tax_credit,
    calculate_employment_income_deduction,
    calculate_insurance_tax_credit,
    calculate_housing_savings_deduction,
    compare_financial_income_tax,
    calculate_car_expense_limit,
    calculate_disaster_tax_credit,
    calculate_financial_income,
    calculate_donation_tax_credit,
    calculate_education_tax_credit,
    calculate_estimated_acquisition_price,
    calculate_interest_income_tax,
    calculate_long_term_deduction,
    calculate_loss_carryforward,
    calculate_loss_netting,
    calculate_medical_tax_credit_detail,
    calculate_non_business_land_tax,
    calculate_nonresident_tax,
    calculate_nontaxable_employment_income,
    calculate_nontaxable_interest,
    calculate_other_income,
    calculate_pension_income,
    calculate_penalty_tax,
    calculate_personal_deductions,
    check_one_house_exemption,
    calculate_recognized_dividend,
    calculate_retirement_income_tax,
    calculate_sme_employment_tax_reduction,
    calculate_special_deductions,
    calculate_simplified_withholding,
    calculate_tax_credits,
    calculate_tax,
    calculate_withholding_tax,
    calculate_transfer_income_tax,
    calculate_local_tax,
)


def _ensure_utf8_stdout():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def _won(amount: int) -> str:
    return f"{int(amount):,}원"


def _pct(rate: float) -> str:
    return f"{rate * 100:.1f}%"


def scenario_1_employee():
    print("\n" + "=" * 80)
    print("시나리오 1: 근로자 연말정산 — 김민준(40세, 기혼)")
    print("=" * 80)

    gross_salary = 60_000_000
    national_pension = 2_700_000
    health_insurance = 2_100_000
    private_insurance = 1_200_000  # 보장성(참고: tax_calculator 세액공제 항목에 없음)
    medical_expense = 2_500_000
    education_expense = 3_000_000
    credit_card = 28_000_000
    irp = 3_000_000

    # 1. 근로소득공제
    emp_deduction = calculate_employment_income_deduction(gross_salary)
    employment_income = gross_salary - emp_deduction
    print(f"[1] 근로소득공제: {_won(emp_deduction)}")
    print(f"    근로소득금액(총급여-공제): {_won(employment_income)}")

    # 2. 인적공제
    persons = [
        {"relation": "본인", "age": 40, "disabled": False},
        {"relation": "배우자", "age": 40, "disabled": False},
        {"relation": "직계비속", "age": 8, "disabled": False},
        {"relation": "직계비속", "age": 12, "disabled": False},
    ]
    personal = calculate_personal_deductions(persons)
    print(f"[2] 인적공제(기본공제 인원): {personal['기본공제_인원']}명")
    print(f"    인적공제 합계: {_won(personal['인적공제_합계'])}")

    # 3. 특별공제
    # 변경 이유:
    # - main.py의 실사용 파이프라인(_compute_wage_components)과 동일 기준을 맞춘다.
    # - 의료비/교육비는 여기서 소득공제로 중복 반영하지 않고, 아래 8번 세액공제에서만 반영한다.
    special_in = {
        "gross_salary": gross_salary,
        "national_pension": national_pension,
        "health_insurance": health_insurance,
        "employment_insurance": 0,
        "housing_fund": 0,
        "medical_expense": 0,
        "education_expense": 0,
        "donation": 0,
    }
    special = calculate_special_deductions(special_in)
    print(f"[3] 특별공제(보험료공제): {_won(special['보험료공제'])}")
    print(f"    특별공제(의료비공제): {_won(special['의료비공제'])}")
    print(f"    특별공제(교육비공제): {_won(special['교육비공제'])}")
    print(f"    특별공제 합계: {_won(special['특별공제_합계'])}")
    print(f"    보장성보험료(참고): {_won(private_insurance)}")

    # 4. 신용카드 소득공제
    card_usage = {
        "credit_card": credit_card,
        "debit_card": 0,
        "traditional_market": 0,
        "public_transit": 0,
    }
    card = calculate_card_deduction(gross_salary, card_usage)
    print(f"[4] 신용카드공제(총사용액): {_won(card['총사용액'])}")
    print(f"    신용카드공제(공제대상금액): {_won(card['공제대상금액'])}")
    print(f"    신용카드공제(최종공제액): {_won(card['최종공제액'])}")

    # 5. 과세표준
    total_deductions = (
        int(personal["인적공제_합계"])
        + int(special["특별공제_합계"])
        + int(card["최종공제액"])
    )
    tax_base = max(int(employment_income) - int(total_deductions), 0)
    print(f"[5] 소득공제 합계: {_won(total_deductions)}")
    print(f"    과세표준: {_won(tax_base)}")

    # 6. 산출세액
    tax = calculate_tax(tax_base)
    print(f"[6] 산출세액: {_won(tax['산출세액'])} (적용세율={_pct(tax['적용세율'])})")

    # 7. 근로소득세액공제
    earned_credit = calculate_earned_income_tax_credit(tax["산출세액"], gross_salary)
    print(f"[7] 근로소득세액공제(최종): {_won(earned_credit['최종공제액'])}")

    # 8. 세액공제(자녀/의료/교육/IRP)
    med_base_for_credit = max(medical_expense - int(gross_salary * 0.03), 0)
    credits_in = {
        "gross_salary": gross_salary,
        "children_count": 2,  # 만 8세 이상 2명
        "medical_expense": med_base_for_credit,
        "education_expense": education_expense,
        "irp_pension": irp,
        "total_income": employment_income,
    }
    credits = calculate_tax_credits(credits_in)
    print(f"[8] 세액공제(자녀): {_won(credits['자녀세액공제'])}")
    print(f"    세액공제(의료): {_won(credits['의료비세액공제'])}")
    print(f"    세액공제(교육): {_won(credits['교육비세액공제'])}")
    print(f"    세액공제(IRP): {_won(credits['IRP연금세액공제'])}")
    print(f"    세액공제 합계: {_won(credits['세액공제_합계'])}")

    # 9. 최종납부세액
    final_tax = int(tax["산출세액"]) - int(earned_credit["최종공제액"]) - int(credits["세액공제_합계"])
    final_tax = max(final_tax, 0)
    local_tax = calculate_local_tax(final_tax)
    print(f"[9] 최종납부세액(소득세): {_won(final_tax)}")
    print(f"    지방소득세(10%): {_won(local_tax)}")
    print(f"    최종납부세액(합계): {_won(final_tax + local_tax)}")

    # 검증
    assert gross_salary == 60_000_000, 'scenario_1: gross_salary'
    assert emp_deduction == 12_750_000, 'scenario_1: emp_deduction'
    assert employment_income == 47_250_000, 'scenario_1: employment_income'
    assert personal["기본공제_인원"] == 4, "scenario_1: personal['기본공제_인원']"
    assert personal["인적공제_합계"] == 6_000_000, "scenario_1: personal['인적공제_합계']"
    assert special["보험료공제"] == 4_800_000, "scenario_1: special['보험료공제']"
    assert special["의료비공제"] == 0, "scenario_1: special['의료비공제']"
    assert special["교육비공제"] == 0, "scenario_1: special['교육비공제']"
    assert special["특별공제_합계"] == 4_800_000, "scenario_1: special['특별공제_합계']"
    assert card["최종공제액"] == 1_950_000, "scenario_1: card['최종공제액']"
    assert total_deductions == 12_750_000, 'scenario_1: total_deductions'
    assert tax_base == 34_500_000, 'scenario_1: tax_base'
    assert tax["산출세액"] == 3_915_000, "scenario_1: tax['산출세액']"
    assert tax["적용세율"] == 0.15, "scenario_1: tax['적용세율']"
    assert earned_credit["최종공제액"] == 660_000, "scenario_1: earned_credit['최종공제액']"
    assert credits["자녀세액공제"] == 350_000, "scenario_1: credits['자녀세액공제']"
    assert credits["의료비세액공제"] == 105_000, "scenario_1: credits['의료비세액공제']"
    assert credits["교육비세액공제"] == 450_000, "scenario_1: credits['교육비세액공제']"
    assert credits["IRP연금세액공제"] == 396_000, "scenario_1: credits['IRP연금세액공제']"
    assert credits["세액공제_합계"] == 1_301_000, "scenario_1: credits['세액공제_합계']"
    assert final_tax == 1_954_000, 'scenario_1: final_tax'
    assert local_tax == 195_400, 'scenario_1: local_tax'
    assert final_tax + local_tax == 2_149_400, 'scenario_1: final_tax + local_tax'
    print("✓ PASS")


def scenario_2_freelancer():
    print("\n" + "=" * 80)
    print("시나리오 2: 프리랜서 종합소득세 — 이지은(32세, 미혼)")
    print("=" * 80)

    industry_code = "940909"
    revenue = 45_000_000
    prev_year_revenue = 24_000_000
    interest = 5_000_000
    dividend = 18_000_000
    gross_up_eligible_dividend = 18_000_000
    carry_losses = [{"연도": 2023, "loss_type": "general", "금액": 3_000_000}]

    # 1. 사업소득금액
    business = calculate_business_income(
        revenue=revenue,
        industry_code=industry_code,
        method="단순",
        prev_year_revenue=prev_year_revenue,
    )
    print(f"[1] 사업소득(수입금액): {_won(business['수입금액'])}")
    if business["단순경비율"] is not None:
        print(f"    단순경비율(데이터): {business['단순경비율'] * 100:.1f}%")
    print(f"    필요경비: {_won(business['필요경비'])}")
    print(f"    사업소득금액: {_won(business['사업소득금액'])}")

    # 2. 금융소득(종합과세 판정 포함)
    fin = calculate_financial_income(
        interest=interest,
        dividend=dividend,
        gross_up_eligible_dividend=gross_up_eligible_dividend,
    )
    print(f"[2] 금융소득(이자소득금액): {_won(fin['이자소득금액'])}")
    print(f"    금융소득(배당소득금액): {_won(fin['배당소득금액'])}")
    print(f"    Gross-up 금액: {_won(fin['Gross_up금액'])}")
    print(f"    금융소득 합계: {_won(fin['금융소득합계'])}")
    print(f"    종합과세 여부: {fin['종합과세여부']}")

    # 3. 배당세액공제
    dividend_credit = calculate_dividend_tax_credit(
        gross_up=fin["Gross_up금액"],
        dividend_income=fin["배당소득금액"],
        total_financial_income=fin["금융소득합계"],
    )
    print(f"[3] 배당세액공제액: {_won(dividend_credit['배당세액공제액'])}")
    print(f"    공제대상 배당소득: {_won(dividend_credit['공제대상_배당소득'])}")

    # 4. 기타소득금액(300만 이하 → 분리과세 선택 가정)
    other = calculate_other_income(2_000_000, income_type='general')
    print(f"[4] 기타소득 총수입금액: {_won(other['총수입금액'])}")
    print(f"    기타소득금액: {_won(other['기타소득금액'])}")
    print(f"    원천징수세액(참고): {_won(other['원천징수세액'])}")
    print("    과세처리: 300만원 이하 일반 기타소득으로 분리과세 선택 가정")

    # 5. 이월결손금 공제(§45)
    incomes_before_loss = {
        "사업소득": int(business["사업소득금액"]),
        "이자소득": int(fin["이자소득금액"]),
        "배당소득": int(fin["배당소득금액"]) if fin["종합과세여부"] else 0,
        "기타소득": 0,
    }
    before_sum = sum(incomes_before_loss.values())
    loss_res = calculate_loss_carryforward(incomes_before_loss, carry_losses)
    incomes_after_loss = loss_res["공제후소득"]
    after_sum = sum(int(v) for v in incomes_after_loss.values())
    print(f"[5] 공제 전 종합소득금액(합계): {_won(before_sum)}")
    print(f"    이월결손금 공제 후(합계): {_won(after_sum)}")
    print(f"    공제내역: {loss_res['공제내역']}")

    # 6. 종합소득 과세표준(기본공제 150만)
    personal = calculate_personal_deductions([{"relation": "본인", "age": 32, "disabled": False}])
    comprehensive_income = after_sum
    tax_base = max(int(comprehensive_income) - int(personal["인적공제_합계"]), 0)
    print(f"[6] 기본공제(본인): {_won(personal['인적공제_합계'])}")
    print(f"    종합소득 과세표준: {_won(tax_base)}")

    # 7. 산출세액
    tax = calculate_tax(tax_base)
    print(f"[7] 산출세액: {_won(tax['산출세액'])} (적용세율={_pct(tax['적용세율'])})")

    # 8. §62 비교산출세액 적용 후 배당세액공제 차감 → 결정세액
    other_comprehensive_income = int(after_sum) - int(fin["금융소득합계"])
    comp = compare_financial_income_tax(
        other_comprehensive_income=other_comprehensive_income,
        financial_income=int(fin["금융소득합계"]),
        total_deductions=int(personal["인적공제_합계"]),
    )
    final_tax = max(int(comp["최종산출세액"]) - int(dividend_credit["배당세액공제액"]), 0)
    local_tax = calculate_local_tax(final_tax)
    print(f"[8] §62 방법①(전체종합과세): {_won(comp['방법①_산출세액'])}")
    print(f"    §62 방법②(2천만분리+초과누진): {_won(comp['방법②_산출세액'])}")
    print(f"    §62 적용방법: {comp['적용방법']} → 최종산출세액: {_won(comp['최종산출세액'])}")
    print(f"    결정세액(소득세, 배당세액공제 차감): {_won(final_tax)}")
    print(f"    지방소득세(10%): {_won(local_tax)}")
    print(f"    결정세액(합계): {_won(final_tax + local_tax)}")

    # 9. 납부지연 가산세(60일)
    penalty = calculate_penalty_tax(final_tax, "late_payment", days_late=60)
    print(f"[9] 납부지연 가산세(60일): {_won(penalty['가산세액'])} ({penalty['적용세율_또는_일수']})")

    # 검증
    assert business["적용방법"] == "단순경비율", "scenario_2: business['적용방법']"
    assert business["사업소득금액"] == 16_155_000, "scenario_2: business['사업소득금액']"
    assert fin["이자소득금액"] == 5_000_000, "scenario_2: fin['이자소득금액']"
    assert fin["배당소득금액"] == 19_800_000, "scenario_2: fin['배당소득금액']"
    assert fin["Gross_up금액"] == 1_800_000, "scenario_2: fin['Gross_up금액']"
    assert fin["금융소득합계"] == 24_800_000, "scenario_2: fin['금융소득합계']"
    assert fin["종합과세여부"] == True, "scenario_2: fin['종합과세여부']"
    assert dividend_credit["배당세액공제액"] == 348_387, "scenario_2: dividend_credit['배당세액공제액']"
    assert other["기타소득금액"] == 800_000, "scenario_2: other['기타소득금액']"
    assert after_sum == 37_955_000, "scenario_2: after_sum"
    assert tax_base == 36_455_000, "scenario_2: tax_base"
    assert comp["방법①_산출세액"] == 4_208_250, "scenario_2: comp['방법①_산출세액']"
    assert comp["방법②_산출세액"] == 4_008_250, "scenario_2: comp['방법②_산출세액']"
    assert comp["최종산출세액"] == 4_208_250, "scenario_2: comp['최종산출세액']"
    assert comp["적용방법"] == "방법①", "scenario_2: comp['적용방법']"
    assert final_tax == 3_859_863, "scenario_2: final_tax"
    assert local_tax == 385_986, "scenario_2: local_tax"
    assert final_tax + local_tax == 4_245_849, "scenario_2: final_tax + local_tax"
    assert penalty["가산세액"] == 50_950, "scenario_2: penalty['가산세액']"
    print("✓ PASS")


def scenario_3_transfer():
    print("\n" + "=" * 80)
    print("시나리오 3: 양도소득세 복합")
    print("=" * 80)

    # 3A — 1세대1주택 비과세
    print("\n[3A] 1세대1주택 비과세")
    res_3a = calculate_transfer_income_tax(
        transfer_price=900_000_000,
        acquisition_price=400_000_000,
        necessary_expenses=0,
        holding_years=3.0,
        residence_years=2.5,
        asset_type="one_house",
        house_type="house",
        is_adjusted_area=False,
    )
    print(f"    비과세여부: {res_3a['비과세여부']}")
    print(f"    총납부세액: {_won(res_3a['총납부세액'])}")
    assert res_3a["비과세여부"] == True, "scenario_3: 3A res_3a['비과세여부']"
    assert res_3a["총납부세액"] == 0, "scenario_3: 3A res_3a['총납부세액']"

    # 3B — 고가주택(1세대1주택)
    print("\n[3B] 고가주택 과세(1세대1주택)")
    transfer_price = 2_000_000_000
    acquisition_price = 700_000_000
    necessary_expenses = 30_000_000
    res_3b = calculate_transfer_income_tax(
        transfer_price=transfer_price,
        acquisition_price=acquisition_price,
        necessary_expenses=necessary_expenses,
        holding_years=12.0,
        residence_years=8.0,
        asset_type="one_house",
        house_type="house",
        is_adjusted_area=False,
    )
    print(f"    양도차익: {_won(res_3b['양도차익'])}")
    print(f"    과세_양도차익: {_won(res_3b['과세_양도차익'])}")
    print(f"    장기보유특별공제액: {_won(res_3b['장기보유특별공제액'])}")
    print(f"    양도소득과세표준: {_won(res_3b['양도소득과세표준'])}")
    print(f"    산출세액: {_won(res_3b['산출세액'])}")
    print(f"    총납부세액: {_won(res_3b['총납부세액'])}")
    assert res_3b["비과세여부"] == False, "scenario_3: 3B res_3b['비과세여부']"
    assert res_3b["양도차익"] == 1_270_000_000, "scenario_3: 3B res_3b['양도차익']"
    assert res_3b["과세_양도차익"] == 508_000_000, "scenario_3: 3B res_3b['과세_양도차익']"
    assert res_3b["장기보유특별공제액"] == 365_760_000, "scenario_3: 3B res_3b['장기보유특별공제액']"
    assert res_3b["양도소득과세표준"] == 139_740_000, "scenario_3: 3B res_3b['양도소득과세표준']"
    assert res_3b["산출세액"] == 33_469_000, "scenario_3: 3B res_3b['산출세액']"
    assert res_3b["총납부세액"] == 36_815_900, "scenario_3: 3B res_3b['총납부세액']"

    # 3C — 다주택자 중과(조정대상지역, 3주택)
    print("\n[3C] 다주택자 중과(조정대상지역, 3주택)")
    res_3c = calculate_transfer_income_tax(
        transfer_price=800_000_000,
        acquisition_price=500_000_000,
        necessary_expenses=0,
        holding_years=4.0,
        asset_type="general",
        house_type="house",
        residence_years=0.0,
        multi_house_count=3,
        is_adjusted_area=True,
    )
    print(f"    양도소득과세표준: {_won(res_3c['양도소득과세표준'])}")
    print(f"    세율 설명: {res_3c['세율_설명']}")
    print(f"    적용세율(구간세율+가산): {_pct(res_3c['적용세율'])}")
    print(f"    산출세액: {_won(res_3c['산출세액'])}")
    assert res_3c["양도소득과세표준"] == 273_500_000, "scenario_3: 3C res_3c['양도소득과세표준']"
    assert res_3c["적용세율"] == 0.68, "scenario_3: 3C res_3c['적용세율']"
    assert res_3c["산출세액"] == 166_040_000, "scenario_3: 3C res_3c['산출세액']"
    assert res_3c["총납부세액"] == 182_644_000, "scenario_3: 3C res_3c['총납부세액']"

    # 3D — 비사업용 토지
    print("\n[3D] 비사업용 토지(기본세율+10%p)")
    transfer_price = 400_000_000
    acquisition_price = 200_000_000
    holding_years = 7.0
    gain = max(transfer_price - acquisition_price, 0)
    ltd = calculate_long_term_deduction(
        gain=gain,
        holding_years=holding_years,
        asset_type="general",
        residence_years=0.0,
    )
    gain_after_ltd = max(int(gain) - int(ltd["장기보유특별공제액"]), 0)
    tax_base = max(gain_after_ltd - 2_500_000, 0)
    nonbiz = calculate_non_business_land_tax(tax_base)
    print(f"    양도차익: {_won(gain)}")
    print(f"    장기보유특별공제액(표1): {_won(ltd['장기보유특별공제액'])} (공제율={_pct(ltd['공제율_합계'])})")
    print(f"    과세표준(기본공제 반영): {_won(tax_base)}")
    print(f"    산출세액(비사업용): {_won(nonbiz['산출세액'])} (적용세율={_pct(nonbiz['적용세율'])})")
    assert ltd["장기보유특별공제액"] == 28_000_000, "scenario_3: 3D ltd['장기보유특별공제액']"
    assert tax_base == 169_500_000, "scenario_3: 3D tax_base"
    assert nonbiz["산출세액"] == 61_420_000, "scenario_3: 3D nonbiz['산출세액']"
    assert nonbiz["적용세율"] == 0.48, "scenario_3: 3D nonbiz['적용세율']"

    print("✓ PASS")


def scenario_4_retirement_income_tax():
    print("\n" + "=" * 80)
    print("시나리오 4: 퇴직소득세 — 박정수(근속 20년, 퇴직금 1억 5천만)")
    print("=" * 80)

    retirement = calculate_retirement_income_tax(retirement_pay=150_000_000, years_of_service=20)

    retirement["퇴직소득금액"] = max(int(retirement["퇴직급여"]) - int(retirement["근속연수공제"]), 0)
    retirement["근속연수공제액"] = int(retirement["근속연수공제"])
    retirement["환산급여공제액"] = int(retirement["환산급여공제"])
    retirement["퇴직소득세액"] = int(retirement["퇴직소득산출세액"])

    print(f"    퇴직소득금액: {_won(retirement['퇴직소득금액'])}")
    print(f"    근속연수공제액: {_won(retirement['근속연수공제액'])}")
    print(f"    환산급여: {_won(retirement['환산급여'])}")
    print(f"    환산급여공제액: {_won(retirement['환산급여공제액'])}")
    print(f"    환산산출세액: {_won(retirement['환산산출세액'])}")
    print(f"    퇴직소득세액: {_won(retirement['퇴직소득세액'])}")
    print(f"    지방소득세: {_won(retirement['지방소득세'])}")
    print(f"    총납부세액: {_won(retirement['총납부세액'])}")

    assert retirement["퇴직소득세액"] >= 0, "scenario_4: retirement['퇴직소득세액']"
    assert (
        retirement["총납부세액"] == retirement["퇴직소득세액"] + retirement["지방소득세"]
    ), "scenario_4: retirement['총납부세액']"

    print('✓ PASS')


def scenario_5_pension_income():
    print("\n" + "=" * 80)
    print("시나리오 5: 연금소득 — 최영희(65세, 다른 종합소득 없음)")
    print("=" * 80)

    print("\n[5A] 총연금액 1,200만 (1,500만 이하 → 분리과세 선택 가능)")
    pension_a = calculate_pension_income(total_pension=12_000_000)
    print(f"    총연금액: {_won(pension_a['총연금액'])}")
    print(f"    연금소득공제액: {_won(pension_a['연금소득공제'])}")
    print(f"    연금소득금액: {_won(pension_a['연금소득금액'])}")
    print(f"    과세방식: {pension_a['과세방식']}")
    if pension_a["과세방식"] in ("분리과세", "분리과세선택가능"):
        print(f"    분리과세세액: {_won(pension_a['분리과세세액'])}")
    assert pension_a["과세방식"] == "분리과세선택가능", "scenario_5: 5A pension_a['과세방식']"

    print("\n[5B] 총연금액 2,000만 (1,500만 초과 → 종합과세)")
    pension_b = calculate_pension_income(total_pension=20_000_000)
    print(f"    총연금액: {_won(pension_b['총연금액'])}")
    print(f"    연금소득공제액: {_won(pension_b['연금소득공제'])}")
    print(f"    연금소득금액: {_won(pension_b['연금소득금액'])}")
    print(f"    과세방식: {pension_b['과세방식']}")
    assert pension_b["과세방식"] == "종합과세", "scenario_5: 5B pension_b['과세방식']"

    print('✓ PASS')


def scenario_6_loss_netting_order():
    print("\n" + "=" * 80)
    print("시나리오 6: 결손금 통산 순서 검증 — 소득세법 §45")
    print("=" * 80)

    incomes = {
        "근로소득": 30_000_000,
        "연금소득": 5_000_000,
        "기타소득": 2_000_000,
        "이자소득": 3_000_000,
        "배당소득": 2_000_000,
    }
    loss = 20_000_000
    result = calculate_loss_netting(incomes, loss, "general")
    after = result["통산후소득"]
    total_after = sum(int(v) for v in after.values())
    total_deducted = sum(int(x["공제액"]) for x in result["공제내역"])

    print(f"    통산 전 소득 합계: {_won(sum(incomes.values()))}")
    print(f"    결손금: {_won(loss)}")
    print(f"    통산 후 소득 합계: {_won(total_after)}")
    print(f"    공제내역: {result['공제내역']}")
    print(f"    잔여결손금: {_won(result['잔여결손금'])}")

    assert total_after == 22_000_000, "scenario_6: total_after"
    assert after["근로소득"] < 30_000_000, "scenario_6: after['근로소득']"
    assert total_deducted == 20_000_000, "scenario_6: total_deducted"

    print("\n[6B] 부동산임대업 결손금 격리(부동산임대소득에서만 공제)")
    incomes2 = {"근로소득": 30_000_000, "부동산임대소득": 5_000_000}
    loss2 = 3_000_000
    result2 = calculate_loss_netting(incomes2, loss2, "real_estate")
    after2 = result2["통산후소득"]
    total_deducted2 = sum(int(x["공제액"]) for x in result2["공제내역"])

    print(f"    통산 전 소득: {incomes2}")
    print(f"    결손금: {_won(loss2)}")
    print(f"    통산 후 소득: {after2}")
    print(f"    공제내역: {result2['공제내역']}")
    print(f"    잔여결손금: {_won(result2['잔여결손금'])}")

    assert after2["근로소득"] == 30_000_000, "scenario_6: 6B after2['근로소득']"
    assert after2["부동산임대소득"] == 2_000_000, "scenario_6: 6B after2['부동산임대소득']"
    assert total_deducted2 == 3_000_000, "scenario_6: 6B total_deducted2"

    print('✓ PASS')


def scenario_7_sme_employment_tax_reduction():
    print("\n" + "=" * 80)
    print("시나리오 7: 중소기업취업자 감면 — 이준혁(26세 청년, 중소기업 3년 근무)")
    print("=" * 80)

    print("\n[7A] 산출세액 300만, 청년(90%), 3년")
    sme_a = calculate_sme_employment_tax_reduction(
        income_tax=3_000_000,
        worker_type="youth",
        years_employed=3,
    )
    sme_a["감면액"] = int(sme_a["산출세액"] * sme_a["감면율"])
    sme_a["최종감면액"] = int(sme_a["감면세액"])
    sme_a["최종납부세액"] = int(sme_a["감면후세액"])
    print(f"    감면율: {_pct(sme_a['감면율'])}")
    print(f"    감면액(한도 전): {_won(sme_a['감면액'])}")
    print(f"    최종감면액(한도 후): {_won(sme_a['최종감면액'])}")
    print(f"    최종납부세액: {_won(sme_a['최종납부세액'])}")
    assert sme_a["감면율"] == 0.9, "scenario_7: 7A sme_a['감면율']"
    assert sme_a["감면액"] == 2_700_000, "scenario_7: 7A sme_a['감면액']"
    assert sme_a["최종감면액"] == 2_000_000, "scenario_7: 7A sme_a['최종감면액']"
    assert sme_a["최종납부세액"] == 1_000_000, "scenario_7: 7A sme_a['최종납부세액']"

    print("\n[7B] 산출세액 150만, 일반(70%), 2년")
    sme_b = calculate_sme_employment_tax_reduction(
        income_tax=1_500_000,
        worker_type="general",
        years_employed=2,
    )
    sme_b["감면액"] = int(sme_b["산출세액"] * sme_b["감면율"])
    sme_b["최종감면액"] = int(sme_b["감면세액"])
    sme_b["최종납부세액"] = int(sme_b["감면후세액"])
    print(f"    감면율: {_pct(sme_b['감면율'])}")
    print(f"    감면액(한도 전): {_won(sme_b['감면액'])}")
    print(f"    최종감면액(한도 후): {_won(sme_b['최종감면액'])}")
    print(f"    최종납부세액: {_won(sme_b['최종납부세액'])}")
    assert sme_b["감면율"] == 0.7, "scenario_7: 7B sme_b['감면율']"
    assert sme_b["감면액"] == 1_050_000, "scenario_7: 7B sme_b['감면액']"
    assert sme_b["최종감면액"] == 1_050_000, "scenario_7: 7B sme_b['최종감면액']"
    assert sme_b["최종납부세액"] == 450_000, "scenario_7: 7B sme_b['최종납부세액']"

    print('✓ PASS')


def scenario_ch01_resident_and_taxable_period():
    """Ch01. 소득세 총설 — 거주자 판정 및 과세기간 특례"""
    print("\n" + "=" * 80)
    print("SCENARIO CH01: 소득세 총설 — 거주자 판정 및 과세기간 특례")
    print("=" * 80)

    # [CH01-A] 국내 주소 보유 → 거주자
    print("\n[CH01-A] 국내 주소 보유 → 거주자")
    r_a = is_resident(has_domestic_address=True, domestic_days=50)
    print(f"    구분: {r_a['구분']}")
    print(f"    판정근거: {r_a['판정근거']}")
    assert r_a["거주자"] is True, "CH01-A: 국내 주소 보유 → 거주자"
    assert r_a["구분"] == "거주자", "CH01-A: 구분 == 거주자"
    assert r_a["납세의무"] == "국내외 전 소득", "CH01-A: 납세의무"

    # [CH01-B] 국내 거소 200일 (주소 없음) → 거주자
    print("\n[CH01-B] 국내 거소 200일 → 거주자")
    r_b = is_resident(has_domestic_address=False, domestic_days=200)
    print(f"    구분: {r_b['구분']}")
    print(f"    판정근거: {r_b['판정근거']}")
    assert r_b["거주자"] is True, "CH01-B: 거소 200일 → 거주자"
    assert r_b["구분"] == "거주자", "CH01-B: 구분"
    assert "200일" in r_b["판정근거"], "CH01-B: 일수 반영"

    # [CH01-C] 국내 거소 182일 (183일 미만) → 비거주자
    print("\n[CH01-C] 국내 거소 182일 → 비거주자")
    r_c = is_resident(has_domestic_address=False, domestic_days=182)
    print(f"    구분: {r_c['구분']}")
    assert r_c["거주자"] is False, "CH01-C: 거소 182일 → 비거주자"
    assert r_c["구분"] == "비거주자", "CH01-C: 구분"
    assert r_c["납세의무"] == "국내원천소득만", "CH01-C: 납세의무"

    # [CH01-D] 경계값: 정확히 183일 → 거주자
    print("\n[CH01-D] 국내 거소 183일(경계값) → 거주자")
    r_d = is_resident(has_domestic_address=False, domestic_days=183)
    assert r_d["거주자"] is True, "CH01-D: 거소 183일(경계값) → 거주자"

    # [CH01-E] 과세기간 원칙 (2024년)
    print("\n[CH01-E] 2024년 과세기간 원칙")
    p_e = get_taxable_period(2024)
    print(f"    과세기간: {p_e['과세기간시작']} ~ {p_e['과세기간종료']} ({p_e['일수']}일)")
    assert p_e["특례"] == "원칙", "CH01-E: 특례 == 원칙"
    assert p_e["과세기간시작"] == date(2024, 1, 1), "CH01-E: 시작일"
    assert p_e["과세기간종료"] == date(2024, 12, 31), "CH01-E: 종료일"
    assert p_e["일수"] == 366, "CH01-E: 2024년 윤년 366일"

    # [CH01-F] 사망 특례 — 2024년 8월 15일 사망
    print("\n[CH01-F] 사망 특례 — 2024-08-15 사망")
    p_f = get_taxable_period(2024, death_date=date(2024, 8, 15))
    print(f"    과세기간: {p_f['과세기간시작']} ~ {p_f['과세기간종료']} ({p_f['일수']}일)")
    print(f"    신고기한: {p_f['신고기한안내']}")
    assert p_f["특례"] == "사망", "CH01-F: 특례 == 사망"
    assert p_f["과세기간종료"] == date(2024, 8, 15), "CH01-F: 종료일 == 사망일"
    # 2024-01-01 ~ 2024-08-15: 31+29+31+30+31+30+31+15 = 228일
    assert p_f["일수"] == 228, "CH01-F: 228일"

    # [CH01-G] 출국 특례 — 2024년 9월 30일 출국
    print("\n[CH01-G] 출국 특례 — 2024-09-30 출국")
    p_g = get_taxable_period(2024, departure_date=date(2024, 9, 30))
    print(f"    과세기간: {p_g['과세기간시작']} ~ {p_g['과세기간종료']} ({p_g['일수']}일)")
    print(f"    신고기한: {p_g['신고기한안내']}")
    assert p_g["특례"] == "출국", "CH01-G: 특례 == 출국"
    assert p_g["과세기간종료"] == date(2024, 9, 30), "CH01-G: 종료일 == 출국일"
    # 2024-01-01 ~ 2024-09-30: 31+29+31+30+31+30+31+31+30 = 274일
    assert p_g["일수"] == 274, "CH01-G: 274일"

    print('✓ PASS')


def scenario_ch02_interest_income():
    print("\n" + "=" * 80)
    print("SCENARIO CH02: 이자소득")
    print("=" * 80)

    print("\n[CH02-A] 비과세종합저축 원금 1,500만 / 이자 45만")
    ch02_a = calculate_nontaxable_interest(
        [{"type": "nontaxable_savings", "amount": 450_000, "principal": 15_000_000}]
    )
    print(f"    총비과세이자: {_won(ch02_a['총비과세이자'])}")
    print(f"    총과세이자: {_won(ch02_a['총과세이자'])}")
    assert ch02_a["총비과세이자"] == 450_000, "CH02-A: 총비과세이자"
    assert ch02_a["총과세이자"] == 0, "CH02-A: 총과세이자"

    print("\n[CH02-B] ISA 일반형 이자 300만")
    ch02_b = calculate_nontaxable_interest(
        [{"type": "isa", "amount": 3_000_000, "principal": 0, "isa_type": "general"}]
    )
    print(f"    총비과세이자: {_won(ch02_b['총비과세이자'])}")
    print(f"    총과세이자: {_won(ch02_b['총과세이자'])}")
    assert ch02_b["총비과세이자"] == 2_000_000, "CH02-B: 총비과세이자"
    assert ch02_b["총과세이자"] == 1_000_000, "CH02-B: 총과세이자"

    print("\n[CH02-C] ISA 서민형 이자 300만")
    ch02_c = calculate_nontaxable_interest(
        [{"type": "isa", "amount": 3_000_000, "principal": 0, "isa_type": "low_income"}]
    )
    print(f"    총비과세이자: {_won(ch02_c['총비과세이자'])}")
    print(f"    총과세이자: {_won(ch02_c['총과세이자'])}")
    assert ch02_c["총비과세이자"] == 3_000_000, "CH02-C: 총비과세이자"
    assert ch02_c["총과세이자"] == 0, "CH02-C: 총과세이자"

    print("\n[CH02-D] 일반 이자 1,500만")
    ch02_d = calculate_interest_income_tax(15_000_000)
    print(f"    종합과세_이자합계: {_won(ch02_d['종합과세_이자합계'])}")
    print(f"    무조건분리과세_소계: {_won(ch02_d['무조건분리과세_소계'])}")
    assert ch02_d["종합과세_이자합계"] == 15_000_000, "CH02-D: 종합과세_이자합계"
    assert ch02_d["무조건분리과세_소계"] == 0, "CH02-D: 무조건분리과세_소계"

    print("\n[CH02-E] 비실명 이자 1,000만")
    ch02_e = calculate_interest_income_tax(10_000_000, has_anonymous=True)
    print(f"    비실명_분리과세세액: {_won(ch02_e['비실명_분리과세세액'])}")
    print(f"    무조건분리과세_소계: {_won(ch02_e['무조건분리과세_소계'])}")
    print(f"    종합과세_이자합계: {_won(ch02_e['종합과세_이자합계'])}")
    assert ch02_e["비실명_분리과세세액"] == 4_500_000, "CH02-E: 비실명_분리과세세액"
    assert ch02_e["무조건분리과세_소계"] == 4_500_000, "CH02-E: 무조건분리과세_소계"
    assert ch02_e["종합과세_이자합계"] == 0, "CH02-E: 종합과세_이자합계"

    print("\n[CH02-F] 장기채권 이자 500만 분리과세 선택")
    ch02_f = calculate_interest_income_tax(
        5_000_000,
        long_term_bond_interest=5_000_000,
        long_term_bond_separate_election=True,
    )
    print(f"    장기채권_분리과세세액: {_won(ch02_f['장기채권_분리과세세액'])}")
    print(f"    종합과세_이자합계: {_won(ch02_f['종합과세_이자합계'])}")
    assert ch02_f["장기채권_분리과세세액"] == 1_500_000, "CH02-F: 장기채권_분리과세세액"
    assert ch02_f["종합과세_이자합계"] == 0, "CH02-F: 종합과세_이자합계"

    print('✓ PASS')


def scenario_ch03_dividend_income():
    print("\n" + "=" * 80)
    print("SCENARIO CH03: 배당소득")
    print("=" * 80)

    print("\n[CH03-A] capital_reduction, received=50,000,000, cost=30,000,000")
    ch03_a = calculate_deemed_dividend("capital_reduction", 50_000_000, 30_000_000)
    print(f"    의제배당금액: {_won(ch03_a['의제배당금액'])}")
    print(f"    Gross_up금액: {_won(ch03_a['Gross_up금액'])}")
    print(f"    배당소득금액: {_won(ch03_a['배당소득금액'])}")
    assert ch03_a["의제배당금액"] == 20_000_000, "CH03-A: 의제배당금액"
    assert ch03_a["Gross_up금액"] == 2_000_000, "CH03-A: Gross_up금액"
    assert ch03_a["배당소득금액"] == 22_000_000, "CH03-A: 배당소득금액"
    assert ch03_a["비과세여부"] is False, "CH03-A: 비과세여부"

    print("\n[CH03-B] surplus_transfer, received=10,000,000, cost=0")
    ch03_b = calculate_deemed_dividend("surplus_transfer", 10_000_000, 0)
    print(f"    의제배당금액: {_won(ch03_b['의제배당금액'])}")
    print(f"    Gross_up금액: {_won(ch03_b['Gross_up금액'])}")
    print(f"    배당소득금액: {_won(ch03_b['배당소득금액'])}")
    assert ch03_b["의제배당금액"] == 10_000_000, "CH03-B: 의제배당금액"
    assert ch03_b["Gross_up금액"] == 1_000_000, "CH03-B: Gross_up금액"
    assert ch03_b["배당소득금액"] == 11_000_000, "CH03-B: 배당소득금액"
    assert ch03_b["비과세여부"] is False, "CH03-B: 비과세여부"

    print("\n[CH03-C] surplus_transfer, capital_reserve_transfer=True")
    ch03_c = calculate_deemed_dividend(
        "surplus_transfer",
        10_000_000,
        0,
        capital_reserve_transfer=True,
    )
    print(f"    의제배당금액: {_won(ch03_c['의제배당금액'])}")
    print(f"    Gross_up금액: {_won(ch03_c['Gross_up금액'])}")
    assert ch03_c["의제배당금액"] == 0, "CH03-C: 의제배당금액"
    assert ch03_c["Gross_up금액"] == 0, "CH03-C: Gross_up금액"
    assert ch03_c["배당소득금액"] == 0, "CH03-C: 배당소득금액"
    assert ch03_c["비과세여부"] is True, "CH03-C: 비과세여부"

    print("\n[CH03-D] dissolution, received=80,000,000, cost=50,000,000")
    ch03_d = calculate_deemed_dividend("dissolution", 80_000_000, 50_000_000)
    print(f"    의제배당금액: {_won(ch03_d['의제배당금액'])}")
    print(f"    Gross_up금액: {_won(ch03_d['Gross_up금액'])}")
    print(f"    배당소득금액: {_won(ch03_d['배당소득금액'])}")
    assert ch03_d["의제배당금액"] == 30_000_000, "CH03-D: 의제배당금액"
    assert ch03_d["Gross_up금액"] == 3_000_000, "CH03-D: Gross_up금액"
    assert ch03_d["배당소득금액"] == 33_000_000, "CH03-D: 배당소득금액"

    print("\n[CH03-E] recognized, amount=5,000,000, resident")
    ch03_e = calculate_recognized_dividend(5_000_000, recipient_type="resident")
    print(f"    인정배당금액: {_won(ch03_e['인정배당금액'])}")
    print(f"    Gross_up금액: {_won(ch03_e['Gross_up금액'])}")
    print(f"    배당소득금액: {_won(ch03_e['배당소득금액'])}")
    assert ch03_e["인정배당금액"] == 5_000_000, "CH03-E: 인정배당금액"
    assert ch03_e["Gross_up금액"] == 500_000, "CH03-E: Gross_up금액"
    assert ch03_e["배당소득금액"] == 5_500_000, "CH03-E: 배당소득금액"

    print("\n[CH03-F] recognized, amount=5,000,000, nonresident")
    ch03_f = calculate_recognized_dividend(5_000_000, recipient_type="nonresident")
    print(f"    Gross_up금액: {_won(ch03_f['Gross_up금액'])}")
    print(f"    배당소득금액: {_won(ch03_f['배당소득금액'])}")
    assert ch03_f["Gross_up금액"] == 0, "CH03-F: Gross_up금액"
    assert ch03_f["배당소득금액"] == 5_000_000, "CH03-F: 배당소득금액"

    print('PASS')


def scenario_ch04_business_expense_limits():
    print("\n" + "=" * 80)
    print("SCENARIO CH04: 사업소득 필요경비")
    print("=" * 80)

    print("\n[CH04-A] 일반사업자 수입 50억, 실지출 2,000만")
    ch04_a = calculate_entertainment_expense_limit(
        revenue=5_000_000_000,
        actual_expense=20_000_000,
        is_sme=False,
    )
    print(f"    기본한도: {_won(ch04_a['기본한도'])}")
    print(f"    수입금액한도: {_won(ch04_a['수입금액한도'])}")
    print(f"    총한도: {_won(ch04_a['총한도'])}")
    print(f"    필요경비산입액: {_won(ch04_a['필요경비산입액'])}")
    assert ch04_a["기본한도"] == 12_000_000, "CH04-A: 기본한도"
    assert ch04_a["수입금액한도"] == 15_000_000, "CH04-A: 수입금액한도"
    assert ch04_a["총한도"] == 27_000_000, "CH04-A: 총한도"
    assert ch04_a["필요경비산입액"] == 20_000_000, "CH04-A: 필요경비산입액"
    assert ch04_a["한도초과_불산입액"] == 0, "CH04-A: 한도초과_불산입액"

    print("\n[CH04-B] 중소기업 수입 30억, 실지출 5,000만")
    ch04_b = calculate_entertainment_expense_limit(
        revenue=3_000_000_000,
        actual_expense=50_000_000,
        is_sme=True,
    )
    print(f"    기본한도: {_won(ch04_b['기본한도'])}")
    print(f"    수입금액한도: {_won(ch04_b['수입금액한도'])}")
    print(f"    총한도: {_won(ch04_b['총한도'])}")
    print(f"    한도초과 불산입액: {_won(ch04_b['한도초과_불산입액'])}")
    assert ch04_b["기본한도"] == 36_000_000, "CH04-B: 기본한도"
    assert ch04_b["수입금액한도"] == 9_000_000, "CH04-B: 수입금액한도"
    assert ch04_b["총한도"] == 45_000_000, "CH04-B: 총한도"
    assert ch04_b["필요경비산입액"] == 45_000_000, "CH04-B: 필요경비산입액"
    assert ch04_b["한도초과_불산입액"] == 5_000_000, "CH04-B: 한도초과_불산입액"

    print("\n[CH04-C] 정액법 취득가액 5,000만, 내용연수 5년")
    ch04_c = calculate_depreciation(
        acquisition_cost=50_000_000,
        useful_life=5,
        method="straight_line",
    )
    print(f"    잔존가액: {_won(ch04_c['잔존가액'])}")
    print(f"    연간상각한도: {_won(ch04_c['연간상각한도'])}")
    assert ch04_c["잔존가액"] == 2_500_000, "CH04-C: 잔존가액"
    assert ch04_c["연간상각한도"] == 9_500_000, "CH04-C: 연간상각한도"

    print("\n[CH04-D] 정률법 취득가액 3,000만, 내용연수 5년")
    ch04_d = calculate_depreciation(
        acquisition_cost=30_000_000,
        useful_life=5,
        method="declining_balance",
    )
    print(f"    연간상각한도: {_won(ch04_d['연간상각한도'])}")
    assert ch04_d["연간상각한도"] == 13_530_000, "CH04-D: 연간상각한도"

    print("\n[CH04-E] 업무용승용차 총비용 2,000만, 업무 80%, 감가상각 1,200만")
    ch04_e = calculate_car_expense_limit(
        total_car_expense=20_000_000,
        business_use_ratio=0.8,
        depreciation_in_expense=12_000_000,
    )
    print(f"    업무사용금액: {_won(ch04_e['업무사용금액'])}")
    print(f"    비업무사용 불산입: {_won(ch04_e['비업무사용_불산입'])}")
    print(f"    감가상각비 한도초과 이월: {_won(ch04_e['감가상각비_한도초과_이월'])}")
    print(f"    필요경비산입액: {_won(ch04_e['필요경비산입액'])}")
    print(f"    총불산입액: {_won(ch04_e['총불산입액'])}")
    assert ch04_e["업무사용금액"] == 16_000_000, "CH04-E: 업무사용금액"
    assert ch04_e["비업무사용_불산입"] == 4_000_000, "CH04-E: 비업무사용_불산입"
    assert ch04_e["감가상각비_한도초과_이월"] == 1_600_000, "CH04-E: 감가상각비_한도초과_이월"
    assert ch04_e["필요경비산입액"] == 14_400_000, "CH04-E: 필요경비산입액"
    assert ch04_e["총불산입액"] == 5_600_000, "CH04-E: 총불산입액"

    print("\n[CH04-F] 업무용승용차 총비용 1,000만, 업무 50%, 감가상각 600만")
    ch04_f = calculate_car_expense_limit(
        total_car_expense=10_000_000,
        business_use_ratio=0.5,
        depreciation_in_expense=6_000_000,
    )
    print(f"    업무사용금액: {_won(ch04_f['업무사용금액'])}")
    print(f"    감가상각비 한도초과 이월: {_won(ch04_f['감가상각비_한도초과_이월'])}")
    print(f"    필요경비산입액: {_won(ch04_f['필요경비산입액'])}")
    assert ch04_f["업무사용금액"] == 5_000_000, "CH04-F: 업무사용금액"
    assert ch04_f["감가상각비_한도초과_이월"] == 0, "CH04-F: 감가상각비_한도초과_이월"
    assert ch04_f["필요경비산입액"] == 5_000_000, "CH04-F: 필요경비산입액"

    print("✓ PASS")


def scenario_ch05_employment_income():
    print("\n" + "=" * 80)
    print("SCENARIO CH05: 근로소득 비과세 및 간이세액표 원천징수")
    print("=" * 80)

    print("\n[CH05-A] 식대 30만 + 자가운전보조금 25만")
    ch05_a = calculate_nontaxable_employment_income({"식대": 300_000, "자가운전보조금": 250_000})
    print(f"    식대: {ch05_a['식대']}")
    print(f"    자가운전보조금: {ch05_a['자가운전보조금']}")
    assert ch05_a["식대"]["비과세"] == 200_000, "CH05-A: 식대 비과세"
    assert ch05_a["식대"]["과세"] == 100_000, "CH05-A: 식대 과세"
    assert ch05_a["자가운전보조금"]["비과세"] == 200_000, "CH05-A: 자가운전보조금 비과세"
    assert ch05_a["자가운전보조금"]["과세"] == 50_000, "CH05-A: 자가운전보조금 과세"

    print("\n[CH05-B] 직무발명보상금 1,000만")
    ch05_b = calculate_nontaxable_employment_income({"직무발명보상금": 10_000_000})
    print(f"    직무발명보상금: {ch05_b['직무발명보상금']}")
    assert ch05_b["직무발명보상금"]["비과세"] == 7_000_000, "CH05-B: 비과세"
    assert ch05_b["직무발명보상금"]["과세"] == 3_000_000, "CH05-B: 과세"

    print("\n[CH05-C] 생산직야간근로수당 300만")
    ch05_c = calculate_nontaxable_employment_income({"생산직야간근로수당": 3_000_000})
    print(f"    생산직야간근로수당: {ch05_c['생산직야간근로수당']}")
    assert ch05_c["생산직야간근로수당"]["비과세"] == 2_400_000, "CH05-C: 비과세"
    assert ch05_c["생산직야간근로수당"]["과세"] == 600_000, "CH05-C: 과세"

    print("\n[CH05-D] 월급여 300만, 부양가족 1명")
    ch05_d = calculate_simplified_withholding(3_000_000, 1, 1.0)
    print(f"    원천징수세액: {_won(ch05_d['원천징수세액'])}")
    print(f"    지방소득세: {_won(ch05_d['지방소득세'])}")
    assert 120_000 <= ch05_d["원천징수세액"] <= 150_000, "CH05-D: 원천징수세액 범위"
    assert ch05_d["지방소득세"] == int(ch05_d["원천징수세액"] * 0.1 / 10) * 10, "CH05-D: 지방소득세"

    print("\n[CH05-E] 월급여 500만, 부양가족 3명, 조정률 80% vs 100%")
    ch05_e_80 = calculate_simplified_withholding(5_000_000, 3, 0.8)
    ch05_e_100 = calculate_simplified_withholding(5_000_000, 3, 1.0)
    print(f"    80% 원천징수세액: {_won(ch05_e_80['원천징수세액'])}")
    print(f"    100% 원천징수세액: {_won(ch05_e_100['원천징수세액'])}")
    assert ch05_e_80["원천징수세액"] <= ch05_e_100["원천징수세액"], "CH05-E: 80% <= 100%"

    print("\n[CH05-F] 월급여 200만, 비과세 20만")
    ch05_f = calculate_simplified_withholding(2_000_000, 1, 1.0, nontaxable_amount=200_000)
    print(f"    월과세급여: {_won(ch05_f['월과세급여'])}")
    print(f"    원천징수세액: {_won(ch05_f['원천징수세액'])}")
    assert ch05_f["월과세급여"] == 1_800_000, "CH05-F: 월과세급여"
    assert ch05_f["원천징수세액"] >= 0, "CH05-F: 원천징수세액"

    print("✓ PASS")


def scenario_ch07_other_income():
    print('\n' + '='*80)
    print('시나리오 Ch07: 기타소득 — 무조건 분리과세 세율 세분화')
    print('='*80)

    # [CH07-A] 복권 2억 → 20% = 4,000만
    r_a = calculate_other_income(200_000_000, income_type='lottery')
    assert r_a['기타소득금액'] == 200_000_000
    assert r_a['원천징수세액'] == 40_000_000, f'CH07-A: {r_a["원천징수세액"]}'

    # [CH07-B] 복권 5억 → 3억×20% + 2억×33% = 12,600만
    r_b = calculate_other_income(500_000_000, income_type='lottery')
    assert r_b['원천징수세액'] == 126_000_000, f'CH07-B: {r_b["원천징수세액"]}'

    # [CH07-C] 복권 5억, 구입비용 1,000원
    # 기타소득 = 499,999,000 → 3억×20%=60,000,000 + 199,999,000×33%=65,999,670 = 125,999,670
    r_c = calculate_other_income(500_000_000, income_type='lottery', ticket_cost=1_000)
    assert r_c['필요경비'] == 1_000
    assert r_c['기타소득금액'] == 499_999_000
    assert r_c['원천징수세액'] == 125_999_670, f'CH07-C: {r_c["원천징수세액"]}'

    # [CH07-D] 슬롯머신 1,000만 → 30% = 300만
    r_d = calculate_other_income(10_000_000, income_type='slot_machine')
    assert r_d['원천징수세액'] == 3_000_000

    # [CH07-E] 강연료 500만 → 필요경비 60%, 세액 40만
    r_e = calculate_other_income(5_000_000, income_type='general')
    assert r_e['필요경비'] == 3_000_000
    assert r_e['기타소득금액'] == 2_000_000
    assert r_e['원천징수세액'] == 400_000

    # [CH07-F] 연금계좌 기타소득 300만 → 15% = 45만
    r_f = calculate_other_income(3_000_000, income_type='pension_account')
    assert r_f['원천징수세액'] == 450_000

    print('✓ PASS')


def scenario_ch09_deductions():
    print('\n' + '='*80)
    print('시나리오 Ch09: 종합소득공제 — 주택청약저축 + 소득공제 종합한도')
    print('='*80)

    # [CH09-A] 납입240만, 총급여5,000만 → 96만
    r_a = calculate_housing_savings_deduction(2_400_000, 50_000_000)
    assert r_a['적용여부'] == True
    assert r_a['공제대상납입액'] == 2_400_000
    assert r_a['산출공제액'] == 960_000
    assert r_a['공제액'] == 960_000

    # [CH09-B] 납입300만 → 납입한도 240만 적용
    r_b = calculate_housing_savings_deduction(3_000_000, 50_000_000)
    assert r_b['공제대상납입액'] == 2_400_000
    assert r_b['공제액'] == 960_000

    # [CH09-C] 총급여 8,000만 → 불가
    r_c = calculate_housing_savings_deduction(2_400_000, 80_000_000)
    assert r_c['적용여부'] == False
    assert r_c['공제액'] == 0

    # [CH09-D] 주택 보유 → 불가
    r_d = calculate_housing_savings_deduction(2_400_000, 50_000_000, has_house=True)
    assert r_d['적용여부'] == False
    assert r_d['공제액'] == 0

    # [CH09-E] 합계 2,000만 → 전액
    r_e = apply_deduction_aggregate_limit({'주택청약저축': 960_000, '신용카드': 15_000_000, '노란우산': 4_040_000})
    assert r_e['입력공제합계'] == 20_000_000
    assert r_e['한도초과액'] == 0
    assert r_e['적용공제합계'] == 20_000_000

    # [CH09-F] 합계 3,000만 → 500만 초과
    r_f = apply_deduction_aggregate_limit({'주택청약저축': 960_000, '신용카드': 20_000_000, '노란우산': 9_040_000})
    assert r_f['입력공제합계'] == 30_000_000
    assert r_f['한도초과액'] == 5_000_000
    assert r_f['적용공제합계'] == 25_000_000

    print('✓ PASS')


def scenario_ch11_tax_credits():
    print('\n' + '='*80)
    print('시나리오 Ch11: 세액공제 상세')
    print('='*80)

    r_a = calculate_insurance_tax_credit(1_000_000, 500_000)
    assert r_a['보장성공제액'] == 120_000, "CH11-A: 보장성공제액"
    assert r_a['장애인공제액'] == 75_000, "CH11-A: 장애인공제액"
    assert r_a['총세액공제액'] == 195_000, "CH11-A: 총세액공제액"

    r_b = calculate_insurance_tax_credit(10_000_000, 0)
    assert r_b['보장성공제액'] == 120_000, "CH11-B: 보장성공제액"

    r_c = calculate_medical_tax_credit_detail(
        50_000_000,
        general_medical=2_000_000,
        self_medical=1_000_000,
    )
    assert r_c['공제문턱'] == 1_500_000, "CH11-C: 공제문턱"
    assert r_c['일반공제대상'] == 500_000, "CH11-C: 일반공제대상"
    assert r_c['일반세액공제'] == 75_000, "CH11-C: 일반세액공제"
    assert r_c['본인등세액공제'] == 150_000, "CH11-C: 본인등세액공제"
    assert r_c['총세액공제액'] == 225_000, "CH11-C: 총세액공제액"

    r_d = calculate_education_tax_credit(
        self_education=5_000_000,
        university_students=[10_000_000],
    )
    assert r_d['본인교육비'] == 5_000_000, "CH11-D: 본인교육비"
    assert r_d['대학교육비'] == 9_000_000, "CH11-D: 대학교육비"
    assert r_d['공제대상합계'] == 14_000_000, "CH11-D: 공제대상합계"
    assert r_d['총세액공제액'] == 2_100_000, "CH11-D: 총세액공제액"

    r_e = calculate_donation_tax_credit(legal_donation=15_000_000)
    assert r_e['기부금세액공제'] == 3_000_000, "CH11-E: 기부금세액공제"

    r_f = calculate_disaster_tax_credit(5_000_000, 200_000_000, 500_000_000)
    assert r_f['재해손실비율'] == 0.4, "CH11-F: 재해손실비율"
    assert r_f['공제액'] == 2_000_000, "CH11-F: 공제액"

    print('✓ PASS')


def scenario_ch13_transfer_income():
    print('\n' + '='*80)
    print('시나리오 Ch13: 양도소득 — 1세대1주택 비과세 + 취득가액 의제')
    print('='*80)

    # [CH13-A] 양도10억, 보유3년 → 전액 비과세
    r_a = check_one_house_exemption(1_000_000_000, 500_000_000, 3.0)
    assert r_a['비과세여부'] == True
    assert r_a['고가주택여부'] == False
    assert r_a['과세대상양도차익'] == 0
    assert r_a['비과세양도차익'] == 500_000_000

    # [CH13-B] 양도15억, 취득8억, 보유3년 → 과세양도차익 1.4억
    # 양도차익=7억, 과세=7억×(15억-12억)/15억=1.4억
    r_b = check_one_house_exemption(1_500_000_000, 800_000_000, 3.0)
    assert r_b['비과세여부'] == True
    assert r_b['고가주택여부'] == True
    assert r_b['양도차익'] == 700_000_000
    assert r_b['과세대상양도차익'] == 140_000_000, f'CH13-B: {r_b["과세대상양도차익"]}'

    # [CH13-C] 보유1.5년 → 비과세 불가
    r_c = check_one_house_exemption(1_000_000_000, 500_000_000, 1.5)
    assert r_c['비과세여부'] == False
    assert r_c['과세대상양도차익'] == 500_000_000

    # [CH13-D] 조정지역 거주1년 → 비과세 불가
    r_d = check_one_house_exemption(1_000_000_000, 500_000_000, 3.0, residence_years=1.0, is_adjustment_zone=True)
    assert r_d['비과세여부'] == False

    # [CH13-E] 환산취득가액: 양도5억, 양도기준4억, 취득기준2억 → 환산2.5억, 차익2.5억
    r_e = calculate_estimated_acquisition_price(400_000_000, 200_000_000, 500_000_000)
    assert r_e['환산취득가액'] == 250_000_000, f'CH13-E: {r_e["환산취득가액"]}'
    assert r_e['양도차익'] == 250_000_000

    # [CH13-F] 2주택 → 비과세 불가
    r_f = check_one_house_exemption(1_000_000_000, 500_000_000, 3.0, household_house_count=2)
    assert r_f['비과세여부'] == False

    print('✓ PASS')


def scenario_ch14_withholding():
    print('\n' + '='*80)
    print('시나리오 Ch14: 원천징수 세율표 통합')
    print('='*80)
    r_a = calculate_withholding_tax(10_000_000, 'interest', is_resident=True)
    assert r_a['원천징수세율'] == 0.14
    assert r_a['원천징수세액'] == 1_400_000
    assert r_a['지방소득세'] == 140_000
    r_b = calculate_withholding_tax(5_000_000, 'dividend', is_resident=True)
    assert r_b['원천징수세액'] == 700_000
    r_c = calculate_withholding_tax(1_000_000, 'business_service', is_resident=True)
    assert r_c['원천징수세액'] == 30_000
    r_d = calculate_withholding_tax(2_000_000, 'other', is_resident=True)
    assert r_d['원천징수세액'] == 400_000
    r_e = calculate_withholding_tax(10_000_000, 'interest', is_resident=False)
    assert r_e['원천징수세율'] == 0.20
    assert r_e['원천징수세액'] == 2_000_000
    r_f = calculate_withholding_tax(5_000_000, 'royalty', is_resident=False)
    assert r_f['원천징수세액'] == 1_000_000
    print('✓ PASS')


def scenario_ch15_nonresident():
    print('\n' + '='*80)
    print('시나리오 Ch15: 비거주자 과세 — 국내원천소득 원천징수')
    print('='*80)
    r_a = calculate_nonresident_tax(10_000_000, 'interest')
    assert r_a['적용세율'] == 0.20
    assert r_a['원천징수세액'] == 2_000_000
    r_b = calculate_nonresident_tax(5_000_000, 'dividend', treaty_rate=0.15, treaty_country='미국')
    assert r_b['적용세율'] == 0.15
    assert r_b['원천징수세액'] == 750_000
    assert r_b['조세조약국'] == '미국'
    r_c = calculate_nonresident_tax(3_000_000, 'royalty', treaty_rate=0.10, treaty_country='일본')
    assert r_c['원천징수세액'] == 300_000
    r_d = calculate_nonresident_tax(2_000_000, 'personal_service')
    assert r_d['원천징수세액'] == 400_000
    r_e = calculate_nonresident_tax(10_000_000, 'other', treaty_rate=0.0, treaty_country='싱가포르')
    assert r_e['원천징수세액'] == 0
    assert r_e['적용세율'] == 0.0
    r_f = calculate_nonresident_tax(5_000_000, 'interest')
    assert r_f['원천징수세액'] == 1_000_000
    assert r_f['지방소득세'] == 100_000
    assert r_f['총부담세액'] == 1_100_000
    print('✓ PASS')


if __name__ == "__main__":
    _ensure_utf8_stdout()
    scenario_ch01_resident_and_taxable_period()
    scenario_ch02_interest_income()
    scenario_ch03_dividend_income()
    scenario_ch04_business_expense_limits()
    scenario_ch05_employment_income()
    scenario_ch07_other_income()
    scenario_ch09_deductions()
    scenario_ch11_tax_credits()
    scenario_ch13_transfer_income()
    scenario_ch14_withholding()
    scenario_ch15_nonresident()
    scenario_1_employee()
    scenario_2_freelancer()
    scenario_3_transfer()
    scenario_4_retirement_income_tax()
    scenario_5_pension_income()
    scenario_6_loss_netting_order()
    scenario_7_sme_employment_tax_reduction()
