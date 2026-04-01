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


def parse_pdf(file_path):
    """PDF 파일 파싱.

    Returns:
        {"doc_type": str, "raw_text": str, "amounts": dict}
    """
    if not _PDF_AVAILABLE:
        raise ImportError("pdfplumber가 설치되지 않았습니다. 'uv sync'를 실행해 주세요.")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    raw_text = "\n".join(pages)

    return {
        "doc_type": _classify_doc_type(raw_text),
        "raw_text": raw_text,
        "amounts": _parse_amounts(raw_text),
    }


def parse_text(text):
    """텍스트 직접 파싱 (PDF 없이 붙여넣기 입력 지원).

    Returns:
        {"doc_type": str, "raw_text": str, "amounts": dict}
    """
    return {
        "doc_type": _classify_doc_type(text),
        "raw_text": text,
        "amounts": _parse_amounts(text),
    }
