"""세무 자료 파서

국세청 간소화 서비스 PDF 및 텍스트 파싱.
pdfplumber로 텍스트 추출 후 키워드 패턴으로 항목별 금액 파싱.
"""

import re
from pathlib import Path

try:
    import pdfplumber
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False


# 간소화 서비스 PDF에서 파싱할 항목 패턴
_PATTERNS = {
    # 소득 금액은 최소 6자리(100만원 이상)인 경우만 인식 — 연도(4자리) 오인식 방지
    "근로소득": r"근로\s*소득[^\d]*([\d,]{7,})",
    "사업소득": r"사업\s*소득[^\d]*([\d,]{7,})",
    "기타소득": r"기타\s*소득[^\d]*([\d,]{7,})",
    "이자소득": r"이자\s*소득[^\d]*([\d,]{7,})",
    "배당소득": r"배당\s*소득[^\d]*([\d,]{7,})",
    "의료비": r"의료비[^\d]*([\d,]+)",
    "교육비": r"교육비[^\d]*([\d,]+)",
    "연금저축": r"연금\s*저축[^\d]*([\d,]+)",
    "IRP": r"IRP[^\d]*([\d,]+)",
    "기부금": r"기부금[^\d]*([\d,]+)",
    # 신용카드·직불카드는 간소화 전용 패턴이 우선 처리 — fallback은 7자리 이상만
    "신용카드": r"신용\s*카드[^\d]*([\d,]{5,})",
    "체크카드": r"직불(?:카드)?[^\d]*([\d,]{5,})",
    # 월세는 7자리 이상(연간 100만 이상), 줄 안에서만 매칭 — 일련번호 오인식 방지
    "월세": r"월세\s*납입[^\d\n]*([\d,]{6,})",
    "주택청약": r"주택\s*청약[^\d]*([\d,]+)",
}

_DOC_TYPE_KEYWORDS = {
    "simplification": ["세액공제증명서류", "연말정산 간소화", "소득·세액공제", "소득 · 세액공제"],
    "payslip": ["근로소득 원천징수영수증", "근로소득 지급명세서", "원천징수영수증"],
    "business_income": ["사업소득", "사업자", "프리랜서"],
    "deduction_cert": ["소득공제", "세액공제"],
    "receipt": ["영수증", "의료비", "교육비"],
}


def _classify_doc_type(text):
    """텍스트 내용으로 문서 유형 추측."""
    for doc_type, keywords in _DOC_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return doc_type
    return "other"


def _parse_amounts(text):
    """텍스트에서 항목별 금액 추출. 간소화서비스 포맷 우선 적용."""
    amounts = {}

    # ── 간소화서비스 전용 패턴 (인별합계금액 / 합계금액 기준) ──────────────
    # 의료비: "의료비 인별합계금액 32,800"
    m = re.search(r"의료비\s*인별합계금액\s+([\d,]+)", text)
    if m:
        amounts["의료비"] = _to_int(m.group(1).replace(",", ""))

    # 교육비: "일반교육비 합계금액 5,675,000"
    m = re.search(r"일반교육비\s*합계금액\s+([\d,]+)", text)
    if m:
        amounts["교육비"] = _to_int(m.group(1).replace(",", ""))

    # 연금저축: "순납입금액 합계 6,000,000"
    m = re.search(r"순납입금액\s*합계\s+([\d,]+)", text)
    if m:
        amounts["연금저축"] = _to_int(m.group(1).replace(",", ""))

    # 신용카드 집계: [ 신용카드 ] 섹션의 합계금액 행 (공백 허용)
    m = re.search(r"\[\s*신용카드\s*\].*?합계금액\s*\n\s*([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", text, re.DOTALL)
    if m:
        amounts["신용카드"] = _to_int(m.group(5).replace(",", ""))
        amounts["신용카드_전통시장"] = _to_int(m.group(2).replace(",", ""))
        amounts["신용카드_대중교통"] = _to_int(m.group(3).replace(",", ""))
    else:
        # 전용 패턴 미매칭 시 fallback 방지용 — 0으로 초기화
        amounts.setdefault("신용카드", 0)

    # 직불카드 집계: [직불카드 등] 섹션의 합계금액 행
    m = re.search(r"\[\s*직불카드\s*등\s*\].*?합계금액\s*\n\s*([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", text, re.DOTALL)
    if m:
        amounts["체크카드"] = _to_int(m.group(5).replace(",", ""))
        amounts["체크카드_전통시장"] = _to_int(m.group(2).replace(",", ""))
        amounts["체크카드_대중교통"] = _to_int(m.group(3).replace(",", ""))
    else:
        amounts.setdefault("체크카드", 0)

    # 현금영수증 집계: "일반 전통시장 대중교통 문화체육 주택임차료 합계금액\n숫자..."
    m = re.search(r"현금영수증.*?주택임차료\s*합계금액\s*\n\s*([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", text, re.DOTALL)
    if m:
        amounts["현금영수증"] = _to_int(m.group(6).replace(",", ""))
        amounts["현금영수증_전통시장"] = _to_int(m.group(2).replace(",", ""))
        amounts["현금영수증_대중교통"] = _to_int(m.group(3).replace(",", ""))

    # ── 공통 패턴 (미매칭 항목 fallback) ────────────────────────────────────
    for label, pattern in _PATTERNS.items():
        if label in amounts:
            continue
        match = re.search(pattern, text)
        if match:
            raw = match.group(1).replace(",", "")
            try:
                amounts[label] = int(raw)
            except ValueError:
                pass

    return amounts


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_first_int(text, patterns):
    if not text:
        return 0
    for pattern in patterns:
        try:
            match = re.search(pattern, text)
        except re.error:
            continue
        if not match:
            continue
        raw = (match.group(1) or "").replace(",", "")
        val = _to_int(raw, default=0)
        if val:
            return val
    return 0


def map_to_pipeline_input(parsed_result) -> dict:
    """원천징수영수증/간소화 텍스트 파싱 결과를 tax_calculator 파이프라인 입력 형태로 매핑."""
    try:
        if not isinstance(parsed_result, dict):
            return {}

        raw_text = parsed_result.get("raw_text") or ""
        if not isinstance(raw_text, str):
            raw_text = str(raw_text)

        amounts = parsed_result.get("amounts") or {}
        if not isinstance(amounts, dict):
            amounts = {}

        def amt(label):
            return _to_int(amounts.get(label, 0) or 0, default=0)

        doc_type = parsed_result.get("doc_type", "")
        is_simplification = doc_type == "simplification"

        if is_simplification:
            gross_salary = 0
        else:
            gross_salary = _extract_first_int(
                raw_text,
                patterns=[
                    r"총\s*급여[^\d]*([\d,]+)",
                    r"총급여[^\d]*([\d,]+)",
                    r"지\s*급\s*총\s*액[^\d]*([\d,]+)",
                    r"지급총액[^\d]*([\d,]+)",
                ],
            ) or amt("근로소득")

        total_income = (
            amt("근로소득")
            + amt("사업소득")
            + amt("기타소득")
            + amt("이자소득")
            + amt("배당소득")
        )

        # 간소화서비스에는 4대보험 정보가 없음 → 0으로 처리
        if is_simplification:
            national_pension = 0
            health_insurance = 0
            employment_insurance = 0
        else:
            national_pension = _extract_first_int(
                raw_text,
                patterns=[
                    r"국민\s*연금[^\d]*([\d,]+)",
                    r"연금\s*보험료[^\d]*([\d,]+)",
                ],
            )
            health_insurance = _extract_first_int(
                raw_text,
                patterns=[
                    r"건강\s*보험[^\d]*([\d,]+)",
                    r"건강\s*보험료[^\d]*([\d,]+)",
                ],
            )
            employment_insurance = _extract_first_int(
                raw_text,
                patterns=[
                    r"고용\s*보험[^\d]*([\d,]+)",
                    r"고용\s*보험료[^\d]*([\d,]+)",
                ],
            )

        housing_fund = amt("주택청약") or _extract_first_int(
            raw_text,
            patterns=[
                r"주택\s*자금[^\d]*([\d,]+)",
                r"주택\s*청약[^\d]*([\d,]+)",
            ],
        )

        medical_total = amt("의료비")
        if gross_salary > 0:
            medical_base_for_credit = max(medical_total - int(gross_salary * 0.03), 0)
        else:
            medical_base_for_credit = medical_total

        pipeline_input = {
            "special_deductions_input": {
                "gross_salary": gross_salary,
                "national_pension": national_pension,
                "health_insurance": health_insurance,
                "employment_insurance": employment_insurance,
                "housing_fund": housing_fund,
                "medical_expense": medical_total,
                "education_expense": amt("교육비"),
                "donation": amt("기부금"),
            },
            "card_usage_input": {
                "credit_card": amt("신용카드"),
                "debit_card": amt("체크카드") + amt("현금영수증"),
                # 전통시장·대중교통은 신용+직불+현금영수증 합산
                "traditional_market": (
                    amt("신용카드_전통시장")
                    + amt("체크카드_전통시장")
                    + amt("현금영수증_전통시장")
                ),
                "public_transit": (
                    amt("신용카드_대중교통")
                    + amt("체크카드_대중교통")
                    + amt("현금영수증_대중교통")
                ),
            },
            "tax_credits_input": {
                "gross_salary": gross_salary,
                "children_count": 0,
                "medical_expense": medical_base_for_credit,
                "education_expense": amt("교육비"),
                "monthly_rent": amt("월세"),
                "irp_pension": amt("IRP") + amt("연금저축"),
                "total_income": total_income,
            },
            "financial_income": {
                "interest": amt("이자소득"),
                "dividend": amt("배당소득"),
            },
        }

        other_amount = amt("기타소득")
        if other_amount > 0:
            pipeline_input["other_income_items"] = [{"종류": "기타", "수입금액": other_amount}]

        business_amount = amt("사업소득")
        if business_amount > 0:
            pipeline_input["business_income"] = {"revenue": business_amount}

        withheld_income_tax = _extract_first_int(
            raw_text,
            patterns=[
                r"소득\s*세[^\d]*([\d,]+)",
                r"소득세[^\d]*([\d,]+)",
            ],
        )
        withheld_local_income_tax = _extract_first_int(
            raw_text,
            patterns=[
                r"지방\s*소득\s*세[^\d]*([\d,]+)",
                r"지방소득세[^\d]*([\d,]+)",
            ],
        )
        withheld_rural_special_tax = _extract_first_int(
            raw_text,
            patterns=[
                r"농어촌\s*특별\s*세[^\d]*([\d,]+)",
                r"농특세[^\d]*([\d,]+)",
            ],
        )
        if any([withheld_income_tax, withheld_local_income_tax, withheld_rural_special_tax]):
            pipeline_input["withholding_tax"] = {
                "withheld_income_tax": withheld_income_tax,
                "withheld_local_income_tax": withheld_local_income_tax,
                "withheld_rural_special_tax": withheld_rural_special_tax,
                "withheld_total_tax": (
                    withheld_income_tax + withheld_local_income_tax + withheld_rural_special_tax
                ),
            }

        return pipeline_input
    except Exception:
        return {}


def parse_pdf(file_path):
    """PDF 파일 파싱.

    Returns:
        {"doc_type": str, "raw_text": str, "amounts": dict, "pipeline_input": dict}
    """
    try:
        if not _PDF_AVAILABLE:
            return {}

        path = Path(file_path)
        if not path.exists():
            return {}

        with pdfplumber.open(path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        raw_text = "\n".join(pages)

        result = {
            "doc_type": _classify_doc_type(raw_text),
            "raw_text": raw_text,
            "amounts": _parse_amounts(raw_text),
        }
        result["pipeline_input"] = map_to_pipeline_input(result)

        # 빈 양식 감지: 원천징수영수증인데 총급여가 없으면 오류
        if result["doc_type"] == "payslip":
            gross = result["pipeline_input"].get("special_deductions_input", {}).get("gross_salary", 0)
            if gross < 1_000_000:
                result["parse_error"] = "blank_form"
                result["parse_error_message"] = "값이 채워진 원천징수영수증이 아닙니다. 실제 발급된 원천징수영수증 PDF를 올려주세요."

        return result
    except Exception:
        return {}


def parse_text(text):
    """텍스트 직접 파싱 (PDF 없이 붙여넣기 입력 지원).

    Returns:
        {"doc_type": str, "raw_text": str, "amounts": dict, "pipeline_input": dict}
    """
    try:
        if not isinstance(text, str):
            text = str(text)
        result = {
            "doc_type": _classify_doc_type(text),
            "raw_text": text,
            "amounts": _parse_amounts(text),
        }
        result["pipeline_input"] = map_to_pipeline_input(result)
        return result
    except Exception:
        return {}
