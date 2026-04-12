"""Phase 1 소득세 인증 게이트 (certify_phase1.py)

Phase 2(부가가치세)로 넘어가기 전 소득세 Ch01~Ch15 전 챕터를 공식 인증한다.

성공 기준:
  - Ch01~Ch15 전 챕터 전용 assert 100% 통과 (exact match)
  - 통합 시나리오 S1~S7 전부 PASS
  - 전체 통과율 22/22 달성 시 Phase 2 진행 허가

종료 코드: 0 = 인증 통과, 1 = 인증 실패.
"""

from __future__ import annotations
import sys
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from tax_calculator import (
    calculate_executive_retirement_limit,
    calculate_exit_tax,
    calculate_exit_tax_adjustment,
    calculate_exit_tax_foreign_credit,
    calculate_loss_netting,
    calculate_pension_income,
    calculate_retirement_income_tax,
    calculate_stock_transfer_tax,
    calculate_tax,
    calculate_local_tax,
    get_other_income_expense_ratio,
)
from eval_scenarios import (
    scenario_ch01_resident_and_taxable_period,
    scenario_ch02_interest_income,
    scenario_ch03_dividend_income,
    scenario_ch04_business_expense_limits,
    scenario_ch05_employment_income,
    scenario_ch07_other_income,
    scenario_ch09_deductions,
    scenario_ch11_tax_credits,
    scenario_ch13_transfer_income,
    scenario_ch14_withholding,
    scenario_ch15_nonresident,
    scenario_1_employee,
    scenario_2_freelancer,
    scenario_3_transfer,
    scenario_4_retirement_income_tax,
    scenario_5_pension_income,
    scenario_6_loss_netting_order,
    scenario_7_sme_employment_tax_reduction,
)

# ── 결과 수집 ──────────────────────────────────────────────────────────────────

_results: list[tuple[str, str, str]] = []  # (id, name, status)


def _run(chapter_id: str, chapter_name: str, fn) -> bool:
    try:
        fn()
        _results.append((chapter_id, chapter_name, "PASS"))
        return True
    except AssertionError as e:
        _results.append((chapter_id, chapter_name, f"FAIL: {e}"))
        return False
    except Exception as e:
        _results.append((chapter_id, chapter_name, f"ERROR: {type(e).__name__}: {e}"))
        return False


# ── Ch06: 연금소득 (eval_scenarios에 전용 챕터 함수 없음) ───────────────────────

def _ch06_pension_income():
    """§47의2 연금소득공제 구간 및 과세방식 분기 — exact match.

    1,200만: 700~1,400만 구간 → 490만 + (1200-700만)×20% = 590만
             연금소득금액 = 1200만 - 590만 = 610만, 과세방식 = 분리과세선택가능
    2,000만: 1,400만 초과 구간 → 630만 + (2000-1400만)×10% = 690만
             연금소득금액 = 2000만 - 690만 = 1310만, 과세방식 = 종합과세
    """
    r1 = calculate_pension_income(12_000_000)
    assert r1["연금소득공제"] == 5_900_000, \
        f"Ch06 1200만 연금소득공제: 기대 5,900,000 / 실제 {r1['연금소득공제']}"
    assert r1["연금소득금액"] == 6_100_000, \
        f"Ch06 1200만 연금소득금액: 기대 6,100,000 / 실제 {r1['연금소득금액']}"
    assert r1["과세방식"] == "분리과세선택가능", \
        f"Ch06 1200만 과세방식: 기대 분리과세선택가능 / 실제 {r1['과세방식']}"

    r2 = calculate_pension_income(20_000_000)
    assert r2["연금소득공제"] == 6_900_000, \
        f"Ch06 2000만 연금소득공제: 기대 6,900,000 / 실제 {r2['연금소득공제']}"
    assert r2["연금소득금액"] == 13_100_000, \
        f"Ch06 2000만 연금소득금액: 기대 13,100,000 / 실제 {r2['연금소득금액']}"
    assert r2["과세방식"] == "종합과세", \
        f"Ch06 2000만 과세방식: 기대 종합과세 / 실제 {r2['과세방식']}"


# ── Ch08: 종합소득금액 (결손금 통산 순서) ─────────────────────────────────────

def _ch08_aggregate_income():
    """§45 결손금 통산 순서: 근로→연금→기타→이자→배당.

    근로 3,000만 + 기타 500만 + 이자 300만, 사업결손금 1,000만
    → 근로에서 먼저 1,000만 공제: 근로 2,000만 / 기타·이자 그대로
    잔여결손금 0
    """
    incomes = {
        "근로소득": 30_000_000,
        "기타소득": 5_000_000,
        "이자소득": 3_000_000,
    }
    result = calculate_loss_netting(incomes, 10_000_000, "general")
    after = result["통산후소득"]
    assert after["근로소득"] == 20_000_000, \
        f"Ch08 근로소득 공제 후: 기대 20,000,000 / 실제 {after['근로소득']}"
    assert after["기타소득"] == 5_000_000, \
        f"Ch08 기타소득 그대로: 기대 5,000,000 / 실제 {after['기타소득']}"
    assert after["이자소득"] == 3_000_000, \
        f"Ch08 이자소득 그대로: 기대 3,000,000 / 실제 {after['이자소득']}"
    assert result["잔여결손금"] == 0, \
        f"Ch08 잔여결손금: 기대 0 / 실제 {result['잔여결손금']}"


# ── Ch10: 세액 계산 (세율 구간 경계값) ───────────────────────────────────────

def _ch10_tax_calculation():
    """§55 세율 구간별 산출세액 exact match (2024년 귀속 세율표).

    2024년 귀속 세율표 (소득세법 §55):
      ~1,400만    6%   누진공제 0
      ~5,000만   15%   누진공제 1,260,000
      ~8,800만   24%   누진공제 5,760,000
      ~1.5억     35%   누진공제 15,440,000

    구간별 대표값:
      1,000만: 6%  → 10,000,000×6% = 600,000
      5,000만: 15% → 50,000,000×15%-1,260,000 = 6,240,000   (15% 구간 상한)
      7,000만: 24% → 70,000,000×24%-5,760,000 = 11,040,000
      1억:     35% → 100,000,000×35%-15,440,000 = 19,560,000
    """
    t1 = calculate_tax(10_000_000)
    assert t1["산출세액"] == 600_000, \
        f"Ch10 1000만 산출세액: 기대 600,000 / 실제 {t1['산출세액']}"
    assert t1["적용세율"] == 0.06, \
        f"Ch10 1000만 세율: 기대 0.06 / 실제 {t1['적용세율']}"

    # 5,000만: 15% 구간 상한 (50,000,000×15%-1,260,000 = 6,240,000)
    t2 = calculate_tax(50_000_000)
    assert t2["산출세액"] == 6_240_000, \
        f"Ch10 5000만 산출세액: 기대 6,240,000 / 실제 {t2['산출세액']}"
    assert t2["적용세율"] == 0.15, \
        f"Ch10 5000만 세율: 기대 0.15 / 실제 {t2['적용세율']}"

    # 7,000만: 24% 구간 (70,000,000×24%-5,760,000 = 11,040,000)
    t3 = calculate_tax(70_000_000)
    assert t3["산출세액"] == 11_040_000, \
        f"Ch10 7000만 산출세액: 기대 11,040,000 / 실제 {t3['산출세액']}"
    assert t3["적용세율"] == 0.24, \
        f"Ch10 7000만 세율: 기대 0.24 / 실제 {t3['적용세율']}"

    # 1억: 35% 구간 (100,000,000×35%-15,440,000 = 19,560,000)
    t4 = calculate_tax(100_000_000)
    assert t4["산출세액"] == 19_560_000, \
        f"Ch10 1억 산출세액: 기대 19,560,000 / 실제 {t4['산출세액']}"
    assert t4["적용세율"] == 0.35, \
        f"Ch10 1억 세율: 기대 0.35 / 실제 {t4['적용세율']}"


# ── Ch12: 퇴직소득 (전 단계 exact match) ─────────────────────────────────────

def _ch12_retirement_income():
    """§22 근속연수공제 + §48 환산급여·세액 전 단계 exact match (2024년 귀속).

    퇴직급여 1억5천만, 근속 20년:
      근속연수공제: 15,000,000 + (20-10)×2,500,000 = 40,000,000
      환산급여:     (150,000,000 - 40,000,000) × 12 / 20 = 66,000,000
      환산급여공제: 8,000,000 + (66,000,000-8,000,000)×60% = 42,800,000
      환산과세표준: 66,000,000 - 42,800,000 = 23,200,000
      환산산출세액: 23,200,000×15% - 1,260,000 = 2,220,000
      퇴직소득세액: int(2,220,000 × 20 / 12) = 3,700,000
      지방소득세:   370,000
      총납부세액:   4,070,000
    """
    r = calculate_retirement_income_tax(
        retirement_pay=150_000_000,
        years_of_service=20,
    )
    assert r["근속연수공제"] == 40_000_000, \
        f"Ch12 근속연수공제: 기대 40,000,000 / 실제 {r['근속연수공제']}"
    assert r["환산급여"] == 66_000_000, \
        f"Ch12 환산급여: 기대 66,000,000 / 실제 {r['환산급여']}"
    assert r["환산급여공제"] == 42_800_000, \
        f"Ch12 환산급여공제: 기대 42,800,000 / 실제 {r['환산급여공제']}"
    assert r["환산과세표준"] == 23_200_000, \
        f"Ch12 환산과세표준: 기대 23,200,000 / 실제 {r['환산과세표준']}"
    assert r["환산산출세액"] == 2_220_000, \
        f"Ch12 환산산출세액: 기대 2,220,000 / 실제 {r['환산산출세액']}"
    assert r["퇴직소득산출세액"] == 3_700_000, \
        f"Ch12 퇴직소득산출세액: 기대 3,700,000 / 실제 {r['퇴직소득산출세액']}"
    assert r["지방소득세"] == 370_000, \
        f"Ch12 지방소득세: 기대 370,000 / 실제 {r['지방소득세']}"
    assert r["총납부세액"] == 4_070_000, \
        f"Ch12 총납부세액: 기대 4,070,000 / 실제 {r['총납부세액']}"


# ── Ch12-b: 임원 퇴직급여 한도 (2025 세무사 Q53) ──────────────────────────────

def _ch12_executive_retirement_limit():
    """§22③ 임원 퇴직급여 한도 + 영§42의2⑥ A금액 선택권 (2025 Q53).

    甲: 2011.1.20 입사 → 2025.2.20 퇴직 (임원)
      지급: 퇴직금 450M + 위로금 14M + 국민연금 일시금 20M (공적연금 제외)
      B구간 근속 96개월 (2012.1.1~2019.12.31), 2019.12.31 이전 3년 연평균 96M
      C구간 근속 62개월 (2020.1.1~2025.2.20, 61월 20일 절상), 퇴직 전 3년 연평균 120M
      2011.12.31 가정 규정 퇴직금 = 35M
      전체 근무월수 169, 2011.12.31 이전 월수 12

    기대:
      B구간 한도 = 96M × 10% × 96/12 × 3 = 230,400,000
      C구간 한도 = 120M × 10% × 62/12 × 2 = 124,000,000
      임원한도   = 354,400,000
      비율법 A   = 464M × 12 / 169 = 32,946,745
      규정법 A   = 35,000,000 (선택: 35M 가 크므로 근로소득 최소화)
      한도 대상 기본 = 464M − 35M = 429,000,000
      초과 (근로소득화) = 74,600,000
      한도내 퇴직소득  = 354,400,000
    """
    r = calculate_executive_retirement_limit(
        avg_salary_pre_2020=96_000_000,
        avg_salary_pre_retire=120_000_000,
        months_b=96,
        months_c=62,
        total_retirement_pay=464_000_000,
        a_amount_rule=35_000_000,
        total_months=169,
        pre_2012_months=12,
    )
    assert r["한도_B구간"] == 230_400_000, \
        f"Ch12b B구간 한도: 기대 230,400,000 / 실제 {r['한도_B구간']}"
    assert r["한도_C구간"] == 124_000_000, \
        f"Ch12b C구간 한도: 기대 124,000,000 / 실제 {r['한도_C구간']}"
    assert r["임원한도"] == 354_400_000, \
        f"Ch12b 임원한도: 기대 354,400,000 / 실제 {r['임원한도']}"
    assert r["A금액_비율법"] == 32_946_745, \
        f"Ch12b 비율법 A: 기대 32,946,745 / 실제 {r['A금액_비율법']}"
    assert r["A금액_선택"] == 35_000_000, \
        f"Ch12b A금액 선택: 기대 35,000,000 (규정법) / 실제 {r['A금액_선택']}"
    assert r["한도_대상_기본금액"] == 429_000_000, \
        f"Ch12b 기본금액: 기대 429,000,000 / 실제 {r['한도_대상_기본금액']}"
    assert r["초과액_근로소득화"] == 74_600_000, \
        f"Ch12b 근로소득 재분류액: 기대 74,600,000 / 실제 {r['초과액_근로소득화']}"
    assert r["퇴직소득_산정기준"] == 354_400_000, \
        f"Ch12b 한도내 퇴직소득: 기대 354,400,000 / 실제 {r['퇴직소득_산정기준']}"


# ── §104 주식 양도세율 ────────────────────────────────────────────────────────

def _stock_transfer_tax():
    """§104①4·5 주식 양도세율: 대주주 20%/25%, 비상장중소 10%, 소액비과세.

    대주주 상장, 양도가 500M, 취득가 200M, 비용 5M, 보유 3년
      양도차익 295M → 과표 292.5M (3억 이하) → 20% = 58,500,000
    비상장 중소기업, 양도가 200M, 취득가 100M → 과표 97.5M → 10% = 9,750,000
    """
    r1 = calculate_stock_transfer_tax(
        transfer_price=500_000_000, acquisition_price=200_000_000,
        necessary_expenses=5_000_000, holding_years=3.0, stock_type="listed_major",
    )
    assert r1["양도차익"] == 295_000_000
    assert r1["양도소득과세표준"] == 292_500_000
    assert r1["산출세액"] == 58_500_000, f"대주주 20%: 기대 58,500,000 / 실제 {r1['산출세액']}"

    r2 = calculate_stock_transfer_tax(
        transfer_price=200_000_000, acquisition_price=100_000_000,
        stock_type="unlisted_sme",
    )
    assert r2["산출세액"] == 9_750_000, f"중소비상장 10%: 기대 9,750,000 / 실제 {r2['산출세액']}"

    r3 = calculate_stock_transfer_tax(
        transfer_price=100_000_000, acquisition_price=50_000_000,
        stock_type="listed_minor",
    )
    assert r3["산출세액"] == 0, "소액주주 비과세"


# ── 영§87 기타소득 필요경비 의제율 ──────────────────────────────────────────

def _other_income_expense_ratio():
    """시행령 §87 필요경비 의제율 매핑: 80%/60%/0%.

    Q52에서 수동 검증했던 항목: 산업재산권 60%, 주택입주지체상금 80%, 위약금 0%.
    """
    r1 = get_other_income_expense_ratio("patent")
    assert r1["의제율"] == 0.60, f"산업재산권: 기대 0.60 / 실제 {r1['의제율']}"

    r2 = get_other_income_expense_ratio("housing_delay")
    assert r2["의제율"] == 0.80, f"주택입주지체상금: 기대 0.80 / 실제 {r2['의제율']}"

    r3 = get_other_income_expense_ratio("penalty")
    assert r3["의제율"] == 0.00, f"위약금: 기대 0.00 / 실제 {r3['의제율']}"


# ── §118의9~16 국외전출세 ────────────────────────────────────────────────────

def _exit_tax_pipeline():
    """§118의10·12·13 국외전출세 과세표준 + 조정공제 + 외국납부세액공제.

    출국일 시가 800M, 취득가 300M (대주주 상장)
      양도소득금액 500M → 과표 497.5M (3억 이하 20% + 197.5M × 25%)
      산출세액 = 60M + 49,375,000 = 109,375,000

    실제 양도가 600M → 조정공제 = 109,375,000 × (800M-600M)/500M = 43,750,000
    외국납부 30M → 한도 = 109,375,000-43,750,000 = 65,625,000 → 공제 30M
    """
    r1 = calculate_exit_tax(
        market_value_at_exit=800_000_000, acquisition_price=300_000_000,
        stock_type="listed_major",
    )
    assert r1["양도소득금액"] == 500_000_000
    assert r1["양도소득과세표준"] == 497_500_000
    expected_tax = int(300_000_000 * 0.20 + 197_500_000 * 0.25)
    assert r1["산출세액"] == expected_tax, \
        f"국외전출세: 기대 {expected_tax} / 실제 {r1['산출세액']}"

    r2 = calculate_exit_tax_adjustment(
        exit_market_value=800_000_000, actual_sale_price=600_000_000,
        exit_computed_tax=expected_tax, exit_gain=500_000_000,
    )
    assert r2["조정공제_적용"] is True
    expected_adj = int(expected_tax * 200_000_000 / 500_000_000)
    assert r2["조정공제액"] == expected_adj, \
        f"조정공제: 기대 {expected_adj} / 실제 {r2['조정공제액']}"

    r3 = calculate_exit_tax_foreign_credit(
        foreign_tax_paid=30_000_000, exit_computed_tax=expected_tax,
        adjustment_credit=expected_adj,
    )
    assert r3["공제세액"] == 30_000_000, f"외국납부세액공제: 기대 30M / 실제 {r3['공제세액']}"
    expected_final = expected_tax - expected_adj - 30_000_000
    assert r3["최종세액"] == expected_final


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("Phase 1 소득세 인증 게이트")
    print("=" * 80)
    print()

    # 챕터별 테스트
    print("[챕터별 테스트]")
    _run("Ch01", "소득세 총설 (거주자 판정·과세기간)", scenario_ch01_resident_and_taxable_period)
    _run("Ch02", "이자소득 (비과세·분리과세)", scenario_ch02_interest_income)
    _run("Ch03", "배당소득 (의제배당·인정배당)", scenario_ch03_dividend_income)
    _run("Ch04", "사업소득 필요경비 (접대비·감가상각·업무용차)", scenario_ch04_business_expense_limits)
    _run("Ch05", "근로소득 (비과세·간이세액표)", scenario_ch05_employment_income)
    _run("Ch06", "연금소득 (공제액·과세방식 분기 exact)", _ch06_pension_income)
    _run("Ch07", "기타소득 (무조건 분리과세 세율 세분화)", scenario_ch07_other_income)
    _run("Ch08", "종합소득금액 (결손금 통산 순서)", _ch08_aggregate_income)
    _run("Ch09", "종합소득공제 (주택청약·종합한도)", scenario_ch09_deductions)
    _run("Ch10", "세액 계산 (세율 구간 경계값 exact)", _ch10_tax_calculation)
    _run("Ch11", "세액공제·감면 (근로·보험·의료·교육·기부·재해)", scenario_ch11_tax_credits)
    _run("Ch12", "퇴직소득 (환산급여·세액 전 단계 exact)", _ch12_retirement_income)
    _run("Ch12b", "임원 퇴직급여 한도 (§22③+영§42의2⑥, 2025 Q53)", _ch12_executive_retirement_limit)
    _run("Ch12c", "주식 양도세율 (§104①4·5, 대주주/비상장/소액)", _stock_transfer_tax)
    _run("Ch13", "양도소득 (1세대1주택·취득가액의제·세액)", scenario_ch13_transfer_income)
    _run("Ch14", "신고납부 (원천징수 세율표 통합)", scenario_ch14_withholding)
    _run("Ch15", "비거주자 (국내원천소득 원천징수)", scenario_ch15_nonresident)
    _run("Ch15b", "기타소득 필요경비 의제율 (영§87 자동매핑)", _other_income_expense_ratio)
    _run("Ch15c", "국외전출세 파이프라인 (§118의9~16)", _exit_tax_pipeline)

    # 통합 시나리오
    print("\n[통합 시나리오]")
    _run("S1", "근로자 연말정산 (김민준, 총급여 6천만)", scenario_1_employee)
    _run("S2", "프리랜서 종합소득세 (이지은, 사업+금융소득)", scenario_2_freelancer)
    _run("S3", "양도소득세 복합 (비사업용토지·주택)", scenario_3_transfer)
    _run("S4", "퇴직소득세 (박정수, 근속 20년)", scenario_4_retirement_income_tax)
    _run("S5", "연금소득 (최영희, 분리과세·종합과세 분기)", scenario_5_pension_income)
    _run("S6", "결손금 통산 순서 + 부동산임대 격리", scenario_6_loss_netting_order)
    _run("S7", "중소기업취업자 감면 (청년 90%·일반 70%)", scenario_7_sme_employment_tax_reduction)

    # ── 결과 요약 테이블 ────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("인증 결과")
    print("=" * 80)

    ch_results = [(cid, name, s) for cid, name, s in _results if cid.startswith("Ch")]
    s_results  = [(cid, name, s) for cid, name, s in _results if cid.startswith("S")]

    print("\n  챕터별 성공 기준 (Ch01~Ch15, 100% 통과 필요):")
    for cid, name, status in ch_results:
        mark = "✓" if status == "PASS" else "✗"
        print(f"  {mark} {cid}  {name}")
        if status != "PASS":
            print(f"       └─ {status}")

    print("\n  통합 시나리오 (S1~S7, 100% 통과 필요):")
    for cid, name, status in s_results:
        mark = "✓" if status == "PASS" else "✗"
        print(f"  {mark} {cid}  {name}")
        if status != "PASS":
            print(f"       └─ {status}")

    ch_pass = sum(1 for _, _, s in ch_results if s == "PASS")
    s_pass  = sum(1 for _, _, s in s_results  if s == "PASS")
    total   = len(_results)
    passed  = ch_pass + s_pass

    print()
    print(f"  챕터 테스트: {ch_pass}/{len(ch_results)}  |  통합 시나리오: {s_pass}/7  |  전체: {passed}/{total}")
    print()

    if passed == total:
        print("  [CERTIFIED] Phase 1 소득세 인증 완료")
        print("              Phase 2 (부가가치세) 진행 허가")
        sys.exit(0)
    else:
        failed = total - passed
        print(f"  [BLOCKED] {failed}개 항목 실패 — 수정 후 재실행 필요")
        sys.exit(1)


if __name__ == "__main__":
    main()
