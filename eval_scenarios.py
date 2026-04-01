import math
import sys

from tax_calculator import (
    calculate_business_income,
    calculate_card_deduction,
    calculate_dividend_tax_credit,
    calculate_earned_income_tax_credit,
    calculate_employment_income_deduction,
    compare_financial_income_tax,
    calculate_financial_income,
    calculate_long_term_deduction,
    calculate_loss_carryforward,
    calculate_loss_netting,
    calculate_non_business_land_tax,
    calculate_other_income,
    calculate_pension_income,
    calculate_penalty_tax,
    calculate_personal_deductions,
    calculate_retirement_income_tax,
    calculate_sme_employment_tax_reduction,
    calculate_special_deductions,
    calculate_tax_credits,
    calculate_tax,
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

    # 3. 특별공제 (사회보험료 + 의료비(3% 초과분) + 교육비)
    special_in = {
        "gross_salary": gross_salary,
        "national_pension": national_pension,
        "health_insurance": health_insurance,
        "employment_insurance": 0,
        "housing_fund": 0,
        "medical_expense": medical_expense,
        "education_expense": education_expense,
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
    assert special["의료비공제"] == 700_000, "scenario_1: special['의료비공제']"
    assert special["교육비공제"] == 3_000_000, "scenario_1: special['교육비공제']"
    assert special["특별공제_합계"] == 8_500_000, "scenario_1: special['특별공제_합계']"
    assert card["최종공제액"] == 1_950_000, "scenario_1: card['최종공제액']"
    assert total_deductions == 16_450_000, 'scenario_1: total_deductions'
    assert tax_base == 30_800_000, 'scenario_1: tax_base'
    assert tax["산출세액"] == 3_360_000, "scenario_1: tax['산출세액']"
    assert tax["적용세율"] == 0.15, "scenario_1: tax['적용세율']"
    assert earned_credit["최종공제액"] == 660_000, "scenario_1: earned_credit['최종공제액']"
    assert credits["자녀세액공제"] == 350_000, "scenario_1: credits['자녀세액공제']"
    assert credits["의료비세액공제"] == 105_000, "scenario_1: credits['의료비세액공제']"
    assert credits["교육비세액공제"] == 450_000, "scenario_1: credits['교육비세액공제']"
    assert credits["IRP연금세액공제"] == 396_000, "scenario_1: credits['IRP연금세액공제']"
    assert credits["세액공제_합계"] == 1_301_000, "scenario_1: credits['세액공제_합계']"
    assert final_tax == 1_399_000, 'scenario_1: final_tax'
    assert local_tax == 139_900, 'scenario_1: local_tax'
    assert final_tax + local_tax == 1_538_900, 'scenario_1: final_tax + local_tax'
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
    other_items = [{"종류": "강의료", "수입금액": 2_000_000}]  # 필요경비 60%
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

    # 4. 기타소득금액(300만 이하 → 분리과세 선택 가능)
    other = calculate_other_income(other_items)
    print(f"[4] 기타소득 수입합계: {_won(other['기타소득_수입합계'])}")
    print(f"    기타소득금액 합계: {_won(other['기타소득금액합계'])}")
    print(f"    과세방식: {other['과세방식']}")
    if other["분리과세세액(22%)"] is not None:
        print(f"    분리과세세액(참고): {_won(other['분리과세세액(22%)'])}")

    # 5. 이월결손금 공제(§45)
    incomes_before_loss = {
        "사업소득": int(business["사업소득금액"]),
        "이자소득": int(fin["이자소득금액"]),
        "배당소득": int(fin["배당소득금액"]) if fin["종합과세여부"] else 0,
        "기타소득": int(other["종합과세편입금액"]),
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
    assert other["기타소득금액합계"] == 800_000, "scenario_2: other['기타소득금액합계']"
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


if __name__ == "__main__":
    _ensure_utf8_stdout()
    scenario_1_employee()
    scenario_2_freelancer()
    scenario_3_transfer()
    scenario_4_retirement_income_tax()
    scenario_5_pension_income()
    scenario_6_loss_netting_order()
    scenario_7_sme_employment_tax_reduction()
