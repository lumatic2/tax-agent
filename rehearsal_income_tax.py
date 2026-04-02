"""실사용 리허설 테스트 (소득세법 중심).

변경 이유:
- 기존 시나리오 검증은 계산 모듈 단위 중심이라, 실제 CLI 파이프라인 결과와
  기대값이 어긋나는 경우를 즉시 드러내기 어렵다.
- 이 파일은 "사용자 질문" 기준으로 테스트를 고정해, 실사용 정확도를 점검한다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import legal_search
import main as app
import tax_calculator


@dataclass
class RehearsalResult:
    name: str
    question: str
    passed: bool
    detail: dict[str, Any]


def _run_wage_case() -> RehearsalResult:
    question = (
        "연봉 6천만원, 배우자+자녀2명, 의료비 250만원, 교육비 300만원, "
        "카드 2800만원, IRP 300만원이면 최종세액이 얼마인가?"
    )
    wage_inputs = {
        "gross_salary": 60_000_000,
        "insurance": {
            "national_pension": 2_700_000,
            "health_insurance": 2_100_000,
            "employment_insurance": 0,
        },
        "expenses": {"medical_expense": 2_500_000, "education_expense": 3_000_000, "donation": 0},
        "housing_fund": 0,
        "card_usage": {"credit_card": 28_000_000, "debit_card": 0, "traditional_market": 0, "public_transit": 0},
        "irp_pension": 3_000_000,
        "dependents": [
            {"relation": "배우자", "age": 40, "disabled": False, "annual_income": 0, "wage_only": False},
            {"relation": "직계비속", "age": 8, "disabled": False, "annual_income": 0, "wage_only": False},
            {"relation": "직계비속", "age": 12, "disabled": False, "annual_income": 0, "wage_only": False},
        ],
        "prepaid_tax": 0,
    }
    result = app._normalize_result_schema(app._calculate_wage_pipeline(wage_inputs), "근로소득자")

    # NOTE: 이 기대값은 eval_scenarios가 아니라 "실제 CLI 파이프라인" 기준으로 고정한다.
    # (의료/교육비는 세액공제로 반영되고, 소득공제로 중복 반영하지 않음)
    expected_total = 2_149_400
    actual_total = int(result["final"]["총결정세액"])
    return RehearsalResult(
        name="R1_근로소득",
        question=question,
        passed=actual_total == expected_total,
        detail={"expected_total": expected_total, "actual_total": actual_total, "final": result["final"]},
    )


def _run_invalid_industry_case() -> RehearsalResult:
    question = "프리랜서인데 업종코드를 잘못 넣으면 시스템이 어떻게 반응하나?"
    try:
        app._calculate_business_pipeline(
            {
                "industry_code": "999999",
                "revenue": 45_000_000,
                "prev_year_revenue": 24_000_000,
                "method": "단순",
                "major_expenses": {},
                "actual_expenses": 0,
                "dependents": [],
                "prepaid_tax": 0,
            }
        )
        return RehearsalResult(
            name="R2_업종코드오류",
            question=question,
            passed=False,
            detail={"error": "예외 미발생"},
        )
    except Exception as e:  # noqa: BLE001
        message = str(e)
        return RehearsalResult(
            name="R2_업종코드오류",
            question=question,
            passed="알 수 없는 업종코드" in message,
            detail={"error": message},
        )


def _run_composite_case() -> RehearsalResult:
    question = "근로+사업+금융소득이 섞여 있고 금융소득 2천만원 초과면 §62 비교산출이 제대로 적용되나?"
    composite_inputs = {
        "wage": {
            "gross_salary": 30_000_000,
            "insurance": {"national_pension": 1_200_000, "health_insurance": 900_000, "employment_insurance": 0},
            "expenses": {"medical_expense": 0, "education_expense": 0, "donation": 0},
            "housing_fund": 0,
            "card_usage": {"credit_card": 10_000_000, "debit_card": 0, "traditional_market": 0, "public_transit": 0},
            "irp_pension": 0,
            "dependents": [],
            "prepaid_tax": 0,
        },
        "business": {
            "industry_code": "940909",
            "revenue": 20_000_000,
            "prev_year_revenue": 12_000_000,
            "method": "단순",
            "major_expenses": {},
            "actual_expenses": 0,
            "dependents": [],
            "prepaid_tax": 0,
        },
        "financial": {
            "interest": 5_000_000,
            "dividend": 18_000_000,
            "gross_up_eligible_dividend": 18_000_000,
        },
        "other_income_items": [],
    }

    result = app._normalize_result_schema(app._calculate_composite_pipeline(composite_inputs), "복합소득자")
    has_62 = any("제62조" in ref.get("legal_ref", "") for ref in result["report"]["legal_refs"])
    passed = int(result["final"]["산출세액"]) > 0 and has_62
    return RehearsalResult(
        name="R3_복합소득_62조",
        question=question,
        passed=passed,
        detail={"final": result["final"], "has_62_reference": has_62},
    )


def _run_retirement_case() -> RehearsalResult:
    question = "퇴직금 1억5천, 근속 20년이면 퇴직소득세가 얼마인가?"
    result = tax_calculator.calculate_retirement_income_tax(150_000_000, 20)
    retirement_tax = int(result.get("퇴직소득산출세액", 0))
    total = int(result.get("총납부세액", 0))
    passed = retirement_tax == 5_540_000 and total == 6_094_000
    return RehearsalResult(
        name="R4_퇴직소득",
        question=question,
        passed=passed,
        detail={"퇴직소득산출세액": retirement_tax, "총납부세액": total},
    )


def _run_pension_case() -> RehearsalResult:
    question = "연금이 연 1,200만원이면 분리과세 선택 가능으로 분류되는가?"
    result = tax_calculator.calculate_pension_income(12_000_000)
    passed = result.get("과세방식") == "분리과세선택가능"
    return RehearsalResult(
        name="R5_연금과세방식",
        question=question,
        passed=passed,
        detail={"과세방식": result.get("과세방식"), "연금소득금액": result.get("연금소득금액")},
    )


def _run_law_grounding_case() -> RehearsalResult:
    question = "근거 법령(§55, §59, §62)을 실제 법령 본문 기준으로 확인할 수 있는가?"
    titles = [
        "세율",
        "근로소득세액공제",
        "이자소득 등에 대한 종합과세 시 세액 계산의 특례",
    ]
    search_result = legal_search.search_law("소득세법")
    laws = search_result.get("laws", [])
    if not laws:
        return RehearsalResult(
            name="R6_법령근거검증",
            question=question,
            passed=False,
            detail={"reason": "법령 검색 결과 없음"},
        )

    mst = str(laws[0].get("법령일련번호") or "")
    content = legal_search.get_law_content(mst)
    text = json.dumps(content, ensure_ascii=False)
    checks = [{"title": title, "ok": title in text} for title in titles]
    passed = all(item["ok"] for item in checks)
    return RehearsalResult(
        name="R6_법령근거검증",
        question=question,
        passed=passed,
        detail={"mst": mst, "checks": checks},
    )


def _run_boundary_and_exception_cases() -> list[RehearsalResult]:
    """경계값/예외/정책 계산 케이스를 묶어서 실행한다.

    변경 이유:
    - 실사용 정확도는 단일 happy-path보다 경계값/예외 처리에서 무너지는 경우가 많다.
    - 질문 단위 테스트를 30개 이상으로 늘리기 위해 반복 패턴을 한 함수에서 일괄 관리한다.
    """
    results: list[RehearsalResult] = []

    def _append(name: str, question: str, passed: bool, detail: dict[str, Any]) -> None:
        results.append(RehearsalResult(name=name, question=question, passed=passed, detail=detail))

    # R7~R10: 근로소득공제 경계/상한
    q = "총급여 500만원이면 근로소득공제가 정확히 350만원인가?"
    v = tax_calculator.calculate_employment_income_deduction(5_000_000)
    _append("R7_근로공제_500만경계", q, v == 3_500_000, {"actual": v, "expected": 3_500_000})

    q = "총급여 1,500만원이면 근로소득공제가 정확히 750만원인가?"
    v = tax_calculator.calculate_employment_income_deduction(15_000_000)
    _append("R8_근로공제_1500만경계", q, v == 7_500_000, {"actual": v, "expected": 7_500_000})

    q = "총급여 4,500만원이면 근로소득공제가 정확히 1,200만원인가?"
    v = tax_calculator.calculate_employment_income_deduction(45_000_000)
    _append("R9_근로공제_4500만경계", q, v == 12_000_000, {"actual": v, "expected": 12_000_000})

    q = "총급여가 1억원 초과(2억원)여도 근로소득공제 상한 1,475만원이 유지되는가?"
    v = tax_calculator.calculate_employment_income_deduction(200_000_000)
    _append("R10_근로공제_상한", q, v == 14_750_000, {"actual": v, "expected": 14_750_000})

    # R11~R14: 기본세율 계산/예외
    q = "과세표준 1,400만원의 산출세액이 84만원(6%)으로 계산되는가?"
    r = tax_calculator.calculate_tax(14_000_000)
    _append(
        "R11_세율_6퍼구간",
        q,
        r.get("산출세액") == 840_000 and r.get("적용세율") == 0.06,
        {"actual": r, "expected_tax": 840_000, "expected_rate": 0.06},
    )

    q = "과세표준 5,000만원의 산출세액이 624만원(15%구간, 누진공제 반영)으로 계산되는가?"
    r = tax_calculator.calculate_tax(50_000_000)
    _append(
        "R12_세율_15퍼구간",
        q,
        r.get("산출세액") == 6_240_000 and r.get("적용세율") == 0.15,
        {"actual": r, "expected_tax": 6_240_000, "expected_rate": 0.15},
    )

    q = "과세표준 12억원의 산출세액이 최고세율 45% 구간 공식대로 계산되는가?"
    r = tax_calculator.calculate_tax(1_200_000_000)
    _append(
        "R13_세율_최고구간",
        q,
        r.get("산출세액") == 474_060_000 and r.get("적용세율") == 0.45,
        {"actual": r, "expected_tax": 474_060_000, "expected_rate": 0.45},
    )

    q = "과세표준이 음수(-1)이면 ValueError로 차단되는가?"
    try:
        tax_calculator.calculate_tax(-1)
        _append("R14_세율_음수입력차단", q, False, {"error": "예외 미발생"})
    except ValueError as e:
        _append("R14_세율_음수입력차단", q, "0 이상" in str(e), {"error": str(e)})

    # R15: 지방소득세
    q = "소득세 391만5천원일 때 지방소득세가 정확히 39만1,500원(10%)인가?"
    v = tax_calculator.calculate_local_tax(3_915_000)
    _append("R15_지방소득세_10퍼", q, v == 391_500, {"actual": v, "expected": 391_500})

    # R16~R18: 금융소득/§62 비교
    q = "이자1천만원+배당800만원(그로스업 포함 합계 1,880만원)은 분리과세로 판정되는가?"
    r = tax_calculator.calculate_financial_income(10_000_000, 8_000_000, 8_000_000)
    _append(
        "R16_금융소득_분리과세",
        q,
        r.get("종합과세여부") is False and r.get("분리과세세액") == 2_520_000,
        {"actual": r, "expected_sep_tax": 2_520_000},
    )

    q = "이자500만원+배당1,800만원(그로스업 대상 1,800만원)은 종합과세로 판정되는가?"
    r = tax_calculator.calculate_financial_income(5_000_000, 18_000_000, 18_000_000)
    _append(
        "R17_금융소득_종합과세",
        q,
        r.get("종합과세여부") is True and r.get("금융소득합계") == 24_800_000,
        {"actual": r, "expected_total": 24_800_000},
    )

    q = "금융소득 2,100만원·타 종합소득 0원에서 §62 방법②가 선택되는가?"
    r = tax_calculator.compare_financial_income_tax(0, 21_000_000, 0)
    _append(
        "R18_62조_방법2선택",
        q,
        r.get("적용방법") == "방법②" and r.get("최종산출세액") == 2_860_000,
        {"actual": r, "expected_method": "방법②", "expected_tax": 2_860_000},
    )

    # R19~R20: 배당세액공제
    q = "분리과세 구간 또는 Gross-up 0이면 배당세액공제가 0으로 처리되는가?"
    r = tax_calculator.calculate_dividend_tax_credit(0, 8_800_000, 18_800_000)
    _append(
        "R19_배당세액공제_0처리",
        q,
        r.get("배당세액공제액") == 0,
        {"actual": r, "expected_credit": 0},
    )

    q = "종합과세 금융소득(총 2,480만원)에서 배당세액공제가 348,387원으로 계산되는가?"
    r = tax_calculator.calculate_dividend_tax_credit(1_800_000, 19_800_000, 24_800_000)
    _append(
        "R20_배당세액공제_안분계산",
        q,
        r.get("배당세액공제액") == 348_387 and r.get("공제대상_배당소득") == 3_832_258,
        {"actual": r, "expected_credit": 348_387},
    )

    # R21~R23: 사업소득 경비 방식
    q = "서비스업(940909) 전년도 수입 2,399만원이면 auto가 단순경비율을 선택하는가?"
    r = tax_calculator.calculate_business_income(45_000_000, "940909", "auto", 23_999_999)
    _append(
        "R21_사업소득_auto단순",
        q,
        r.get("적용방법") == "단순경비율" and r.get("사업소득금액") == 16_155_000,
        {"actual": r, "expected_method": "단순경비율"},
    )

    q = "서비스업(940909) 전년도 수입 2,400만원이면 auto가 기준경비율로 전환되는가?"
    r = tax_calculator.calculate_business_income(
        45_000_000,
        "940909",
        "auto",
        24_000_000,
        {"매입비용": 5_000_000, "임차료": 2_000_000, "인건비": 3_000_000},
    )
    _append(
        "R22_사업소득_auto기준",
        q,
        r.get("적용방법") == "기준경비율" and r.get("사업소득금액") == 28_970_000,
        {"actual": r, "expected_method": "기준경비율"},
    )

    q = "실제경비 방식에서 수입 3,000만원·필요경비 1,200만원이면 사업소득금액이 1,800만원인가?"
    r = tax_calculator.calculate_business_income(30_000_000, "940909", "실제", 0, actual_expenses=12_000_000)
    _append(
        "R23_사업소득_실제경비",
        q,
        r.get("적용방법") == "실제경비" and r.get("사업소득금액") == 18_000_000,
        {"actual": r, "expected_income": 18_000_000},
    )

    # R24~R25: 연금소득 경계
    q = "사적연금 총액이 1,500만원이면 분리과세선택가능으로 분류되는가?"
    r = tax_calculator.calculate_pension_income(15_000_000)
    _append(
        "R24_연금소득_1500만경계",
        q,
        r.get("과세방식") == "분리과세선택가능" and r.get("분리과세세액") == 2_250_000,
        {"actual": r, "expected_method": "분리과세선택가능"},
    )

    q = "사적연금 총액이 1,600만원이면 종합과세로 의무 전환되는가?"
    r = tax_calculator.calculate_pension_income(16_000_000)
    _append(
        "R25_연금소득_의무종합과세",
        q,
        r.get("과세방식") == "종합과세" and r.get("분리과세세율") is None,
        {"actual": r, "expected_method": "종합과세"},
    )

    # R26~R27: 기타소득 300만원 기준
    q = "강의료 200만원(기타소득금액 80만원)이면 분리과세선택가능으로 처리되는가?"
    r = tax_calculator.calculate_other_income([{"종류": "강의료", "수입금액": 2_000_000}])
    _append(
        "R26_기타소득_분리선택",
        q,
        r.get("과세방식") == "분리과세선택가능" and r.get("종합과세편입금액") == 0,
        {"actual": r, "expected_method": "분리과세선택가능"},
    )

    q = "강의료 800만원(기타소득금액 320만원)이면 종합과세 의무로 처리되는가?"
    r = tax_calculator.calculate_other_income([{"종류": "강의료", "수입금액": 8_000_000}])
    _append(
        "R27_기타소득_종합의무",
        q,
        r.get("과세방식") == "종합과세" and r.get("종합과세편입금액") == 3_200_000,
        {"actual": r, "expected_method": "종합과세"},
    )

    # R28~R29: 결손금 통산
    q = "일반결손금 2,000만원은 통산 순서대로 차감되어 근로소득부터 줄어드는가?"
    r = tax_calculator.calculate_loss_netting(
        {"근로소득": 30_000_000, "연금소득": 5_000_000, "기타소득": 2_000_000},
        20_000_000,
        "general",
    )
    after = r.get("통산후소득", {})
    _append(
        "R28_결손금통산_일반",
        q,
        after.get("근로소득") == 10_000_000 and r.get("잔여결손금") == 0,
        {"actual": r, "expected_wage_after": 10_000_000},
    )

    q = "부동산임대업 결손금은 다른 소득과 통산되지 않고 임대소득에서만 차감되는가?"
    r = tax_calculator.calculate_loss_netting(
        {"근로소득": 30_000_000, "부동산임대소득": 5_000_000},
        3_000_000,
        "real_estate",
    )
    after = r.get("통산후소득", {})
    _append(
        "R29_결손금통산_부동산임대격리",
        q,
        after.get("근로소득") == 30_000_000 and after.get("부동산임대소득") == 2_000_000,
        {"actual": r, "expected_rental_after": 2_000_000},
    )

    # R30: 중간예납 기준액 경계
    q = "직전세액 90만원이면 중간예납기준액 45만원으로 납부의무가 없어야 하는가?"
    r = tax_calculator.calculate_interim_prepayment(900_000)
    _append(
        "R30_중간예납_50만원미만면제",
        q,
        r.get("중간예납기준액") == 450_000 and r.get("납부의무여부") is False,
        {"actual": r, "expected_due": False},
    )

    return results


def run_rehearsal() -> dict[str, Any]:
    results = [
        _run_wage_case(),
        _run_invalid_industry_case(),
        _run_composite_case(),
        _run_retirement_case(),
        _run_pension_case(),
        _run_law_grounding_case(),
    ]
    results.extend(_run_boundary_and_exception_cases())

    payload = {
        "tests": [
            {
                "name": r.name,
                "question": r.question,
                "pass": r.passed,
                "detail": r.detail,
            }
            for r in results
        ]
    }
    payload["summary"] = {
        "pass": all(r.passed for r in results),
        "pass_count": sum(1 for r in results if r.passed),
        "total": len(results),
    }
    return payload


if __name__ == "__main__":
    print(json.dumps(run_rehearsal(), ensure_ascii=False, indent=2))
