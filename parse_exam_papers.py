"""시험 기출문제 PDF 파서 (parse_exam_papers.py)

data/exam/ 아래 PDF/HWP 파일을 파싱해서
data/exam/parsed/ 에 구조화된 텍스트로 저장한다.

출력 형식: JSON (문제 리스트 + 메타데이터)
  {
    "시험": "CPA_2차_세법" | "CPA_1차_세법" | "세무사_1차_세법학개론" | "세무사_2차_세법학",
    "연도": 2024,
    "구분": "문제" | "해설",
    "문제": [
      {
        "번호": 1,
        "유형": "주관식" | "객관식",
        "내용": "...",
        "보기": ["①...", "②...", ...],   # 객관식만
        "소재": ["소득세", "법인세", ...],  # 추정 세목 태그
        "배점": 20,
        "답": "...",                      # 해설 파일에서 추출
      }
    ],
    "원본_파일": "...",
    "파싱_날짜": "2026-04-11",
    "총_문제수": 10,
  }

실행:
  uv run python parse_exam_papers.py
  uv run python parse_exam_papers.py --file data/exam/cpa_2차/문제/CPA_2차_세법_2024.pdf
"""

from __future__ import annotations
import argparse
import json
import re
import sys
import zipfile
from datetime import date
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("pdfplumber 없음: uv add pdfplumber")
    sys.exit(1)

try:
    import fitz as pymupdf  # PyMuPDF fallback
    _HAS_PYMUPDF = True
except ImportError:
    _HAS_PYMUPDF = False

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "exam"
PARSED_DIR = DATA / "parsed"
PARSED_DIR.mkdir(parents=True, exist_ok=True)

TODAY = date.today().isoformat()

# ── 세목 키워드 태깅 ─────────────────────────────────────────────────────────
TAX_KEYWORDS = {
    "소득세": ["소득세", "근로소득", "사업소득", "양도소득", "퇴직소득", "연금소득", "종합소득", "세액공제"],
    "법인세": ["법인세", "각사업연도", "소득처분", "세무조정", "이월결손금", "최저한세"],
    "부가가치세": ["부가가치세", "매입세액", "매출세액", "영세율", "면세", "간이과세"],
    "상속·증여세": ["상속세", "증여세", "상속재산", "증여재산", "피상속인"],
    "국세기본법": ["국세기본법", "납세의무", "경정청구", "가산세", "부과제척기간", "조세불복"],
    "조세특례제한법": ["조세특례", "조특법", "중소기업", "세액감면"],
    "지방세": ["지방세", "취득세", "재산세", "지방소득세"],
    "개별소비세": ["개별소비세"],
}


def tag_tax_subjects(text: str) -> list[str]:
    """텍스트에서 관련 세목을 추정해서 반환."""
    found = []
    for subject, keywords in TAX_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            found.append(subject)
    return found or ["미분류"]


# ── PDF 파싱 ────────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: Path, prefer_pymupdf: bool = False) -> str:
    """PDF 텍스트 추출. prefer_pymupdf=True면 PyMuPDF 우선(다단 레이아웃에 유리)."""
    if prefer_pymupdf and _HAS_PYMUPDF:
        try:
            doc = pymupdf.open(str(pdf_path))
            parts = [page.get_text() for page in doc]
            text = "\n".join(p for p in parts if p.strip())
            if text.strip():
                return text
        except Exception as e:
            print(f"    [WARN] PyMuPDF 실패: {e}")

    text_parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n".join(text_parts)
    except Exception as e:
        print(f"    [WARN] pdfplumber 실패: {e}")
        if _HAS_PYMUPDF and not prefer_pymupdf:
            print(f"    PyMuPDF로 재시도...")
            try:
                doc = pymupdf.open(str(pdf_path))
                parts = [page.get_text() for page in doc]
                return "\n".join(p for p in parts if p.strip())
            except Exception as e2:
                print(f"    [WARN] PyMuPDF도 실패: {e2}")
        return ""


def extract_text_from_hwpx(hwpx_path: Path) -> str:
    """HWPX(HWP XML) 파일에서 텍스트 추출. HWPX는 ZIP 컨테이너 내 XML."""
    import xml.etree.ElementTree as ET
    text_parts = []
    try:
        with zipfile.ZipFile(hwpx_path) as zf:
            # section XML 파일들 추출
            for name in sorted(zf.namelist()):
                if re.match(r'Contents/section\d+\.xml', name):
                    with zf.open(name) as f:
                        data = f.read().decode('utf-8', errors='replace')
                    # hp:t 태그에서 텍스트 추출
                    texts = re.findall(r'<hp:t[^>]*>([^<]+)</hp:t>', data)
                    text_parts.extend(texts)
    except Exception as e:
        print(f"    [WARN] HWPX 파싱 오류: {e}")
    return ' '.join(text_parts)


def extract_text_from_zip(zip_path: Path) -> dict[str, str]:
    """ZIP 내 PDF 파일 텍스트 추출. {파일명: 텍스트}"""
    results = {}
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.lower().endswith(".pdf"):
                with zf.open(name) as f:
                    import io
                    data = f.read()
                    with pdfplumber.open(io.BytesIO(data)) as pdf:
                        parts = []
                        for page in pdf.pages:
                            t = page.extract_text()
                            if t:
                                parts.append(t)
                        results[name] = "\n".join(parts)
    return results


# ── 문제 파싱 ────────────────────────────────────────────────────────────────

def parse_cpa_2차_세법(text: str) -> list[dict]:
    """
    CPA 2차 세법 주관식 문제 파싱.
    패턴: [문제 X] / <문제 1> / 문제1】(25점) 등
    """
    problems = []
    pattern = re.compile(
        r'(?:\[문제\s*(\d+)\]|<문제\s*(\d+)>|문제\s*(\d+)\s*[】\.\)])\s*'
        r'(?:\((\d+)점\))?',
        re.MULTILINE,
    )
    splits = list(pattern.finditer(text))
    if not splits:
        # 단순 분할 불가 시 전체를 하나의 문제로
        return [{"번호": 1, "유형": "주관식", "내용": text.strip(), "배점": None, "소재": tag_tax_subjects(text)}]

    for i, m in enumerate(splits):
        num = int(m.group(1) or m.group(2) or m.group(3) or i + 1)
        pts = int(m.group(4)) if m.group(4) else None
        start = m.end()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
        content = text[start:end].strip()
        problems.append({
            "번호": num,
            "유형": "주관식",
            "내용": content,
            "배점": pts,
            "소재": tag_tax_subjects(content),
        })
    return problems


def parse_세무사_1차_세법(text: str) -> list[dict]:
    """
    세무사 1차 객관식 세법학개론 파싱.
    패턴: 숫자. 또는 숫자.①~⑤
    """
    problems = []
    # 객관식: "1. 소득세법상..." 패턴
    pattern = re.compile(r'^(\d{1,3})\.\s+', re.MULTILINE)
    splits = list(pattern.finditer(text))
    if not splits:
        return [{"번호": 1, "유형": "객관식", "내용": text.strip(), "소재": tag_tax_subjects(text)}]

    for i, m in enumerate(splits):
        num = int(m.group(1))
        start = m.end()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
        content = text[start:end].strip()

        # 보기 추출 (①②③④⑤): 원형 기호 사이의 텍스트를 모두 수집 (개행 포함)
        choice_positions = [m.start() for m in re.finditer(r'[①②③④⑤]', content)]
        choices = []
        for ci, cstart in enumerate(choice_positions):
            cend = choice_positions[ci + 1] if ci + 1 < len(choice_positions) else len(content)
            choice_text = content[cstart:cend].strip()
            choice_text = re.sub(r'\s+', ' ', choice_text)  # 개행·공백 정규화
            if len(choice_text) >= 2:
                choices.append(choice_text)
        # 정답 (별도 정답 파일이 있으면 매핑)
        body = re.split(r'[①②③④⑤]', content)[0].strip()

        problems.append({
            "번호": num,
            "유형": "객관식",
            "내용": body,
            "보기": choices,
            "소재": tag_tax_subjects(body),
        })
    return problems


def parse_세무사_2차_세법(text: str) -> list[dict]:
    """세무사 2차 세법학 1부/2부 주관식 파싱."""
    return parse_cpa_2차_세법(text)  # 문제 구조 유사


# ── 파일 → 구조화 JSON ────────────────────────────────────────────────────────

def detect_exam_type(path: Path) -> tuple[str, int, str]:
    """
    파일명에서 (시험종류, 연도, 구분) 추출.
    예: CPA_2차_세법_2024.pdf → ("CPA_2차_세법", 2024, "문제")
    """
    name = path.stem
    year_m = re.search(r'(20\d{2})', name)
    year = int(year_m.group(1)) if year_m else 0
    구분 = "해설" if "해설" in name or "답안" in name or "정답" in name else "문제"
    if "CPA_2차" in name or "cpa_2차" in name.lower() or "세무회계" in name:
        return "CPA_2차_세법", year, 구분
    if "CPA_1차" in name or "cpa_1차" in name.lower() or "회계사" in name:
        return "CPA_1차_세법", year, 구분
    if "세무사_2차" in name or "세법학1부" in name or "세법학2부" in name:
        # 1부/2부 구분
        부 = "1부" if "1부" in name else ("2부" if "2부" in name else "")
        return f"세무사_2차_세법학{부}", year, 구분
    if "세무사_1차" in name or "세법학개론" in name:
        return "세무사_1차_세법학개론", year, 구분
    return "미분류", year, 구분


def parse_file(pdf_path: Path) -> dict | None:
    """단일 PDF/HWPX/ZIP 파일을 파싱해서 구조화된 dict 반환."""
    suffix = pdf_path.suffix.lower()
    if suffix not in (".pdf", ".zip", ".hwp", ".hwpx"):
        return None

    print(f"  파싱: {pdf_path.name}")

    exam_type, year, 구분 = detect_exam_type(pdf_path)

    if suffix == ".zip":
        # ZIP이 HWPX 컨테이너인지 확인 (mimetype 파일 존재)
        try:
            with zipfile.ZipFile(pdf_path) as zf:
                names = zf.namelist()
            if 'mimetype' in names and any('section' in n for n in names):
                # HWPX 컨테이너 형식
                text = extract_text_from_hwpx(pdf_path)
                print(f"    HWPX 형식 감지, 텍스트 {len(text)}자 추출")
            else:
                texts = extract_text_from_zip(pdf_path)
                # CPA 1차: 세법 과목만 추출
                세법_key = next((k for k in texts if "세법" in k), None)
                if 세법_key:
                    text = texts[세법_key]
                    print(f"    ZIP 내 세법 파일: {세법_key}")
                else:
                    text = "\n\n".join(f"[{k}]\n{v}" for k, v in texts.items())
        except Exception as e:
            print(f"    [WARN] ZIP 처리 오류: {e}")
            return None
    elif suffix in (".hwp", ".hwpx"):
        print(f"    [WARN] HWP 파일은 자동 파싱 불가. PDF 버전을 사용하세요.")
        return None
    else:
        # CPA 2차/세무사 2차 주관식은 다단 레이아웃 → PyMuPDF 우선
        prefer_mupdf = exam_type in ("CPA_2차_세법",) or exam_type.startswith("세무사_2차_세법학")
        text = extract_text_from_pdf(pdf_path, prefer_pymupdf=prefer_mupdf)
        # CPA 1차 2교시 = 기업법+세법개론 합본 → 세법개론 부분만 추출
        if exam_type == "CPA_1차_세법" and "세법개론" in text:
            idx = text.find("세법개론")
            if idx > 0:
                text = text[idx:]
                print(f"    기업법+세법개론 합본 감지, 세법개론 부분 추출 (offset={idx})")
        # 세무사 1차 1교시 원본 = 재정학+세법학개론 합본 → 세법학개론 부분만 추출
        if exam_type == "세무사_1차_세법학개론" and "세법학개론" in text:
            idx = text.find("세법학개론")
            if idx > 0:
                text = text[idx:]
                print(f"    재정학+세법학개론 합본 감지, 세법학개론 부분 추출 (offset={idx})")

    if not text.strip():
        print(f"    [WARN] 텍스트 추출 실패 (스캔 이미지일 수 있음)")
        return {"시험": exam_type, "연도": year, "구분": 구분,
                "원본_파일": str(pdf_path.relative_to(ROOT)),
                "파싱_날짜": TODAY, "총_문제수": 0,
                "오류": "텍스트 추출 실패 (OCR 필요)", "원본_텍스트": ""}

    # 문제 파싱
    if exam_type == "CPA_2차_세법" or exam_type.startswith("세무사_2차_세법학"):
        problems = parse_cpa_2차_세법(text)
    elif exam_type in ("CPA_1차_세법", "세무사_1차_세법학개론"):
        problems = parse_세무사_1차_세법(text)
    else:
        problems = parse_세무사_1차_세법(text)

    return {
        "시험": exam_type,
        "연도": year,
        "구분": 구분,
        "원본_파일": str(pdf_path.relative_to(ROOT)),
        "파싱_날짜": TODAY,
        "총_문제수": len(problems),
        "문제": problems,
        "원본_텍스트": text[:500] + "..." if len(text) > 500 else text,
    }


# ── 정답 파싱 ────────────────────────────────────────────────────────────────

# ①②③④⑤ → 1~5 변환
_CIRCLE = {"①": 1, "②": 2, "③": 3, "④": 4, "⑤": 5}


def _circle_to_int(s: str) -> int | None:
    return _CIRCLE.get(s.strip())


def parse_answer_key_cpa_1차(text: str, year: int) -> dict:
    """
    CPA 1차 확정답안 PDF 파싱 → 세법개론 ①형 정답 dict.
    출력: {"1": 2, "2": 1, ..., "40": 4}
    형식 A: "1 ② ①" (원형 기호)
    형식 B: "1 2 1"  (숫자 1~5)
    """
    # 세법개론 섹션 추출
    idx = text.find("세법개론정답")
    if idx < 0:
        return {}
    section = text[idx:]
    # 다음 과목 섹션에서 잘라냄
    next_sec = re.search(r'[가-힣]+정답', section[7:])
    if next_sec:
        section = section[:next_sec.start() + 7]

    answers = {}

    # 형식 A: 원형 기호 — 복수정답 포함 (예: ②,③,⑤)
    # 패턴: 문항번호 + ①형정답(복수가능) + ②형정답(복수가능)
    circle_pat = r'[①②③④⑤](?:,[①②③④⑤])*'
    rows_circle = re.findall(rf'(\d{{1,2}})\s+({circle_pat})\s+({circle_pat})', section)
    if rows_circle:
        for num, form1, _form2 in rows_circle:
            # 복수정답: 리스트로 저장. 단일이면 int
            vals = [_circle_to_int(c) for c in re.findall(r'[①②③④⑤]', form1) if _circle_to_int(c)]
            if vals:
                answers[num] = vals[0] if len(vals) == 1 else vals
        return answers

    # 형식 B: 숫자 1~5 (문항번호 + ①형정답 + ②형정답)
    # "1\n2\n1\n" 또는 "1 2 1" 패턴 → 문항번호, 정답1, 정답2 순서
    rows_num = re.findall(r'^(\d{1,2})\s+([1-5])\s+([1-5])', section, re.MULTILINE)
    for num, ans1, _ans2 in rows_num:
        n = int(num)
        if 1 <= n <= 40:
            answers[num] = int(ans1)

    return answers


def parse_answer_key_세무사_1차(text: str, year: int) -> dict:
    """
    세무사 1차 정답 PDF 파싱 → 세법학개론 ①형(A형) 정답 dict.
    출력: {"1": 2, "2": 3, ..., "40": 1}  (문항 41~80 → 상대번호 1~40)
    """
    # 세법학개론 섹션 찾기
    idx = text.find("세법학개론")
    if idx < 0:
        return {}
    section = text[idx:]

    answers = {}

    # 2025 형식: "41\n1\n42\n3\n..." 또는 "41 1\n42 3\n..."
    # 숫자쌍 추출 (문항번호 + 정답)
    pairs = re.findall(r'(\d{2,3})\s+([1-5])', section)
    if pairs:
        for num_str, ans_str in pairs:
            num = int(num_str)
            if 41 <= num <= 80:  # 세법학개론 범위 (1교시 41~80번)
                answers[str(num - 40)] = int(ans_str)  # 1~40으로 정규화
        if answers:
            return answers

    # 원형 기호 형식 (①②③④⑤)
    pairs_circle = re.findall(r'(\d{2,3})\s+([①②③④⑤])', section)
    for num_str, circle in pairs_circle:
        num = int(num_str)
        if 41 <= num <= 80:
            val = _circle_to_int(circle)
            if val:
                answers[str(num - 40)] = val

    return answers


def parse_answer_key(pdf_path: Path) -> dict | None:
    """정답 PDF를 파싱해서 구조화된 정답 dict 반환."""
    text = extract_text_from_pdf(pdf_path, prefer_pymupdf=True)
    if not text.strip():
        print(f"    [WARN] 정답 파일 텍스트 추출 실패 (스캔본?): {pdf_path.name}")
        return None

    exam_type, year, _ = detect_exam_type(pdf_path)

    if exam_type == "CPA_1차_세법":
        answers = parse_answer_key_cpa_1차(text, year)
        책형 = "①형"
    elif exam_type == "세무사_1차_세법학개론":
        answers = parse_answer_key_세무사_1차(text, year)
        책형 = "A형"
    else:
        # 2차 주관식 — 서술형 정답 전문 저장
        answers = {}
        책형 = None

    if not answers:
        print(f"    [WARN] 정답 추출 실패: {pdf_path.name}")
        return None

    return {
        "시험": exam_type,
        "연도": year,
        "구분": "정답",
        "책형": 책형,
        "정답": answers,   # {"1": 2, "2": 1, ...}
        "총_문항수": len(answers),
        "원본_파일": str(pdf_path.relative_to(ROOT)),
        "파싱_날짜": TODAY,
    }


def parse_all(data_dir: Path = DATA) -> None:
    """data/exam/ 전체 PDF 파싱."""
    pdfs = sorted(data_dir.rglob("*.pdf")) + sorted(data_dir.rglob("*.zip"))
    if not pdfs:
        print("파싱할 파일이 없습니다. 먼저 download_exam_papers.py를 실행하세요.")
        return

    results = []
    for pdf_path in pdfs:
        if "parsed" in str(pdf_path):
            continue

        # 정답 파일 여부 판단
        name = pdf_path.stem
        is_answer = any(k in name for k in ["정답", "답안", "확정답안", "가답안"])

        if is_answer:
            print(f"  정답파싱: {pdf_path.name}")
            result = parse_answer_key(pdf_path)
            if result:
                results.append(result)
                out_name = f"{result['시험']}_{result['연도']}_정답.json"
                out_path = PARSED_DIR / out_name
                out_path.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"    → {out_path.relative_to(ROOT)} (정답 {result['총_문항수']}개)")
        else:
            result = parse_file(pdf_path)
            if result:
                results.append(result)
                out_name = f"{result['시험']}_{result['연도']}_{result['구분']}.json"
                out_path = PARSED_DIR / out_name
                out_path.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"    → {out_path.relative_to(ROOT)} (문제 {result['총_문제수']}개)")

    # 전체 요약
    summary_path = PARSED_DIR / "index.json"
    summary = []
    for r in results:
        if r.get("구분") == "정답":
            summary.append({
                "파일": r["원본_파일"],
                "시험": r["시험"],
                "연도": r["연도"],
                "구분": "정답",
                "총_문항수": r.get("총_문항수", 0),
            })
        else:
            summary.append({
                "파일": r["원본_파일"],
                "시험": r["시험"],
                "연도": r["연도"],
                "구분": r["구분"],
                "총_문제수": r["총_문제수"],
            })
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n총 {len(results)}개 파일 파싱 완료 → {PARSED_DIR.relative_to(ROOT)}/")
    print(f"인덱스: {summary_path.relative_to(ROOT)}")


def main():
    parser = argparse.ArgumentParser(description="시험 기출문제 PDF 파서")
    parser.add_argument("--file", help="단일 파일 파싱")
    args = parser.parse_args()

    if args.file:
        result = parse_file(Path(args.file))
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parse_all()


if __name__ == "__main__":
    main()
