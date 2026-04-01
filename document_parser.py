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
    "근로소득": r"근로\s*소득[^\d]*([\d,]+)",
    "사업소득": r"사업\s*소득[^\d]*([\d,]+)",
    "기타소득": r"기타\s*소득[^\d]*([\d,]+)",
    "이자소득": r"이자\s*소득[^\d]*([\d,]+)",
    "배당소득": r"배당\s*소득[^\d]*([\d,]+)",
    "의료비": r"의료비[^\d]*([\d,]+)",
    "교육비": r"교육비[^\d]*([\d,]+)",
    "연금저축": r"연금\s*저축[^\d]*([\d,]+)",
    "IRP": r"IRP[^\d]*([\d,]+)",
    "기부금": r"기부금[^\d]*([\d,]+)",
    "신용카드": r"신용\s*카드[^\d]*([\d,]+)",
    "체크카드": r"직불(?:카드)?[^\d]*([\d,]+)",
    "월세": r"월세[^\d]*([\d,]+)",
    "주택청약": r"주택\s*청약[^\d]*([\d,]+)",
}

_DOC_TYPE_KEYWORDS = {
    "payslip": ["근로소득", "원천징수", "급여"],
    "business_income": ["사업소득", "사업자", "프리랜서"],
    "deduction_cert": ["소득공제", "세액공제", "연말정산 간소화"],
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
    """텍스트에서 항목별 금액 추출."""
    amounts = {}
    for label, pattern in _PATTERNS.items():
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
                "debit_card": amt("체크카드"),
                "traditional_market": _extract_first_int(raw_text, [r"전통\s*시장[^\d]*([\d,]+)"]),
                "public_transit": _extract_first_int(raw_text, [r"대중\s*교통[^\d]*([\d,]+)"]),
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
