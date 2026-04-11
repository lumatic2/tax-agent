"""시험 기출문제 PDF 다운로더 (download_exam_papers.py)

공개된 공식 소스에서 세무사·공인회계사 기출문제를 자동 다운로드한다.

소스 구분:
  A. cpa.fss.or.kr  — 금융감독원 공인회계사시험 (공개, 로그인 불필요)
  B. 0gichul.com    — 공기출 세무사 1차 (공개, 세션 SID 추출 후 다운로드)

수동 다운로드 필요 항목:
  - 세무사 2차 문제:  namucpa.com (로그인 필요, ZIP 파일)
  - 세무사 2차 해설:  barun-edu.com (JavaScript 파일 번호 필요)
  - 우리CPA 해설:     uricpa.com (로그인 필요)

실행:
  uv run python download_exam_papers.py          # 자동 다운로드
  uv run python download_exam_papers.py --check  # URL 확인만
"""

from __future__ import annotations
import argparse
import re
import sys
import time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "exam"

# ── 헤더 (공공 사이트 크롤링 기준) ──────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Referer": "https://cpa.fss.or.kr/",
}

# ── A. 금융감독원 CPA 기출문제 URL 맵 ────────────────────────────────────────
# URL 패턴: https://cpa.fss.or.kr/cpa/cmmn/file/fileDown.do?menuNo=&atchFileId=ID&fileSn=N&bbsId=B0000368
# 세법 = fileSn=1 (2차 HWP), fileSn=1 → PDF는 시험마다 다름
# 아래 표는 수동 확인한 값:
#   2차: 1-1 세법문제(HWP=fileSn1,PDF=+5), 각 연도 atchFileId 확인 완료

FSS_BASE = "https://cpa.fss.or.kr/cpa/cmmn/file/fileDown.do"
FSS_BBS = "B0000368"

CPA_2차_FILES = {
    2023: {
        "atchFileId": "a21c273dc87f45db9422820f65f3cf96",
        "세법_hwp": 1,   # 1-1 세법 문제(2023-2).hwp
        "세법_pdf": None,  # 2023 2차는 HWP만 제공 (PDF 버전은 nttId=128479)
        "nttId_pdf": 128479,  # PDF 버전 게시글 (별도 atchFileId 필요)
    },
    2024: {
        "atchFileId": "daf1c7c3dab84b3a971b3e7b89122f85",
        "세법_hwp": 6,   # 1-1 세법 문제(2024-2).hwp  (fileSn=6)
        "세법_pdf": 1,   # 1-1 세법 문제(2024-2).pdf  (fileSn=1)
    },
    2025: {
        "atchFileId": "4f4d31d5ed8a4d2da0566afeefd3129e",
        "세법_hwp": 1,   # 1-1 세법 문제(2025-2).hwp  (fileSn=1)
        "세법_pdf": 7,   # 1-1 세법 문제(2025-2).pdf  (fileSn=7)
    },
}

# CPA 1차 전체 ZIP (세법 포함) — 압축 해제 후 세법 파일 추출 필요
CPA_1차_FILES = {
    2024: {
        "atchFileId": "4a3f5d4278834903b7413ff41ba8da68",
        "파일형식": "zip",
        "파일명": "24년도 공인회계사 제1차시험 문제.zip",
        "정답_fileSn": 2,   # 확정답안_2024.pdf
    },
    # 2023, 2025, 2026: atchFileId 별도 확인 필요 (아래 nttId로 조회)
    2023: {"nttId": 66123,  "상태": "atchFileId 조회 필요"},
    2025: {
        "atchFileId": "3829390e2dc50d21e862899048e2db59",
        "파일형식": "pdf",
        "세법_pdf": 4,      # 2교시 기업법 세법개론(1형)_문제_2025.pdf
        "정답_fileSn": 7,   # 정답_2025.pdf
    },
    2026: {
        "atchFileId": "529b84f1e3eb4f65a6b40595c4e0fca1",
        "파일형식": "pdf",
        "세법_pdf": 4,      # 2교시 기업법 세법개론(1형)_문제(최종)_2026.pdf
        "정답_fileSn": 7,   # 최종정답확정_2026.pdf
    },
}

# ── B. 공기출(0gichul.com) 세무사 1차 세법학개론 ──────────────────────────────
# URL 패턴: https://0gichul.com/?module=file&act=procFileDownload&file_srl=XXXX
# SID는 페이지에서 동적 추출 필요
GICHUL_BASE = "https://0gichul.com"
GICHUL_PAGES = {
    2023: "https://0gichul.com/y2023/106694537",   # 세무사 1차 세법학개론
    2024: "https://0gichul.com/y2024/130891915",
    2025: "https://0gichul.com/y2025/130904399",
}
# file_srl 값 (페이지에서 확인)
GICHUL_FILE_SRLS = {
    2023: {"문제": 106694538, "정답": 111581315},
    2024: {"문제": 130891916, "정답": 130891891},
    2025: {"문제": 130904400, "정답": 130904373},
}


def fss_url(atch_file_id: str, file_sn: int) -> str:
    return (
        f"{FSS_BASE}?menuNo=&atchFileId={atch_file_id}"
        f"&fileSn={file_sn}&bbsId={FSS_BBS}"
    )


def extract_gichul_sid(year: int, session: requests.Session) -> dict[str, str]:
    """공기출 페이지에서 file_srl별 SID 추출."""
    page_url = GICHUL_PAGES[year]
    resp = session.get(page_url, headers={**HEADERS, "Referer": GICHUL_BASE}, timeout=15)
    resp.raise_for_status()
    sids = {}
    for m in re.finditer(
        r"file_srl=(\d+)&(?:amp;)?sid=([0-9a-f]+)", resp.text
    ):
        srl, sid = m.group(1), m.group(2)
        sids[srl] = sid
    return sids


def download_file(
    session: requests.Session,
    url: str,
    dest: Path,
    label: str,
    dry_run: bool = False,
) -> bool:
    if dest.exists():
        print(f"  [skip] {label} — 이미 존재: {dest.name}")
        return True
    if dry_run:
        print(f"  [check] {label}")
        print(f"          URL: {url}")
        return True
    try:
        resp = session.get(url, headers=HEADERS, timeout=30, stream=True)
        resp.raise_for_status()
        ctype = resp.headers.get("Content-Type", "")
        if "html" in ctype and len(resp.content) < 50_000:
            # 로그인 페이지로 리다이렉트된 경우
            print(f"  [WARN] {label} — HTML 응답 (로그인 필요?): {url}")
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        size_kb = dest.stat().st_size // 1024
        print(f"  [ok]   {label} — {size_kb}KB → {dest.relative_to(ROOT)}")
        time.sleep(0.5)  # 서버 부하 방지
        return True
    except Exception as e:
        print(f"  [ERR]  {label} — {e}")
        return False


def download_cpa_2차(session: requests.Session, dry_run: bool) -> None:
    print("\n[CPA 2차 세법 문제] 금융감독원 공식 자료")
    for year, info in CPA_2차_FILES.items():
        aid = info["atchFileId"]
        # PDF 우선, 없으면 HWP
        if info.get("세법_pdf"):
            url = fss_url(aid, info["세법_pdf"])
            dest = DATA / "cpa_2차" / "문제" / f"CPA_2차_세법_{year}.pdf"
            download_file(session, url, dest, f"CPA 2차 세법 문제 {year} (PDF)", dry_run)
        elif info.get("세법_hwp"):
            url = fss_url(aid, info["세법_hwp"])
            dest = DATA / "cpa_2차" / "문제" / f"CPA_2차_세법_{year}.hwp"
            download_file(session, url, dest, f"CPA 2차 세법 문제 {year} (HWP)", dry_run)
        else:
            print(f"  [TODO] CPA 2차 세법 {year} — atchFileId 별도 확인 필요 (nttId={info.get('nttId_pdf')})")


def download_cpa_1차(session: requests.Session, dry_run: bool) -> None:
    print("\n[CPA 1차 전체 ZIP] 금융감독원 공식 자료 (세법 포함)")
    for year, info in CPA_1차_FILES.items():
        if "atchFileId" not in info:
            print(f"  [TODO] CPA 1차 {year} — atchFileId 조회 필요 (nttId={info['nttId']})")
            print(f"         페이지: https://cpa.fss.or.kr/cpa/bbs/B0000368/view.do?nttId={info['nttId']}&menuNo=1200078")
            continue
        aid = info["atchFileId"]
        # 세법_pdf가 있으면 개별 PDF 다운로드, 없으면 fileSn=1 ZIP
        if info.get("세법_pdf"):
            sn = info["세법_pdf"]
            url_q = fss_url(aid, sn)
            ext = "hwpx" if info.get("파일형식") == "hwpx" else "pdf"
            dest_q = DATA / "cpa_1차" / "문제" / f"CPA_1차_{year}_세법.{ext}"
            download_file(session, url_q, dest_q, f"CPA 1차 세법 {year} (PDF, fileSn={sn})", dry_run)
        else:
            url_q = fss_url(aid, 1)
            dest_q = DATA / "cpa_1차" / "문제" / f"CPA_1차_{year}_전체.zip"
            download_file(session, url_q, dest_q, f"CPA 1차 문제 {year} (ZIP)", dry_run)
        # 확정답안 PDF
        if info.get("정답_fileSn"):
            url_a = fss_url(aid, info["정답_fileSn"])
            dest_a = DATA / "cpa_1차" / "해설" / f"CPA_1차_{year}_확정답안.pdf"
            download_file(session, url_a, dest_a, f"CPA 1차 확정답안 {year}", dry_run)


def download_세무사_1차(session: requests.Session, dry_run: bool) -> None:
    print("\n[세무사 1차 세법학개론] 공기출(0gichul.com)")
    for year, srls in GICHUL_FILE_SRLS.items():
        # SID 추출
        if not dry_run:
            try:
                sids = extract_gichul_sid(year, session)
            except Exception as e:
                print(f"  [WARN] {year}년 SID 추출 실패: {e}")
                sids = {}

        for kind, srl in srls.items():
            if dry_run:
                url = f"{GICHUL_BASE}/?module=file&act=procFileDownload&file_srl={srl}"
                dest = DATA / "세무사_1차" / ("문제" if kind == "문제" else "해설") / f"세무사_1차_세법_{year}_{kind}.pdf"
                download_file(session, url, dest, f"세무사 1차 세법 {year} {kind}", dry_run)
            else:
                sid = sids.get(str(srl), "")
                if not sid:
                    print(f"  [WARN] 세무사 1차 {year} {kind} — SID 없음 (file_srl={srl})")
                    continue
                url = f"{GICHUL_BASE}/?module=file&act=procFileDownload&file_srl={srl}&sid={sid}"
                dest = DATA / "세무사_1차" / ("문제" if kind == "문제" else "해설") / f"세무사_1차_세법_{year}_{kind}.pdf"
                download_file(session, url, dest, f"세무사 1차 세법 {year} {kind}")


def print_manual_guide() -> None:
    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
수동 다운로드 필요 항목
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[세무사 2차 세법학 1부·2부 — 문제지]
  2023: https://www.namucpa.com/customer/board_noticeView.asp?bIDX=414983
  2024: https://namucpa.com/customer/board_noticeView.asp?bIDX=494717
  2025: https://www.uricpa.com/GContents/CTA/InfoCenter/PreQuestion/Index.asp?B_Idx=750469
  → 저장 위치: data/exam/세무사_2차/문제/세무사_2차_세법학_[연도].pdf

[세무사 2차 세법학 해설·답안]
  2025 (바른생각): https://barun-edu.com/cs/inotice/dtl/60127
  2025 (우리CPA):  https://www.uricpa.com/GContents/CTA/InfoCenter/ExamData/Index.asp?B_Idx=750469
  2024 (우리CPA):  https://www.uricpa.com/GContents/CTA/InfoCenter/ExamData/Index.asp?B_Idx=666158
  → 저장 위치: data/exam/세무사_2차/해설/세무사_2차_세법학_[연도]_해설.pdf

[CPA 1차 — atchFileId 조회 필요 (현재 자동 다운로드 불가)]
  2023: https://cpa.fss.or.kr/cpa/bbs/B0000368/view.do?nttId=66123&menuNo=1200078
  2025: https://cpa.fss.or.kr/cpa/bbs/B0000368/view.do?nttId=191846&menuNo=1200078
  2026: https://cpa.fss.or.kr/cpa/bbs/B0000368/view.do?nttId=215021&menuNo=1200078

[CPA 2차 세법 해설]
  2024: https://www.uricpa.com/GContents/CTA/InfoCenter/ExamData/Index.asp?B_Idx=658975
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


def main():
    parser = argparse.ArgumentParser(description="시험 기출문제 PDF 다운로더")
    parser.add_argument("--check", action="store_true", help="URL 확인만 (다운로드 안 함)")
    args = parser.parse_args()

    dry_run = args.check
    action = "URL 확인" if dry_run else "다운로드"
    print(f"=== 시험 기출문제 {action} ===")

    session = requests.Session()

    download_cpa_2차(session, dry_run)
    download_cpa_1차(session, dry_run)
    download_세무사_1차(session, dry_run)
    print_manual_guide()

    print("\n완료. data/exam/ 디렉토리를 확인하세요.")
    print("파싱: uv run python parse_exam_papers.py")


if __name__ == "__main__":
    main()
