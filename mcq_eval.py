"""mcq_eval.py — 세무사·CPA 1차 객관식(MCQ) 정확도 평가.

Claude API(claude-haiku-4-5)를 사용해 세법 객관식 문제를 풀고
기출 정답과 비교하여 정확도를 측정한다.

사용법:
    python mcq_eval.py                          # 전체 (세무사 1차 3개 연도)
    python mcq_eval.py --exam cta1 --year 2024  # 특정 시험·연도
    python mcq_eval.py --limit 10               # 최대 10문항
    python mcq_eval.py --dry-run                # API 호출 없이 구조만 확인

전제 조건:
    .env 에 ANTHROPIC_API_KEY= 설정 필요
    uv add anthropic  (또는 pip install anthropic)
"""
import sys
import json
import time
import argparse
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


def _utf8():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


# ─── 시험 메타데이터 ──────────────────────────────────────────────────────────

EXAM_CONFIG = {
    "cta1": {
        "name": "세무사_1차_세법학개론",
        "years": [2023, 2024, 2025],
        "q_file": "세무사_1차_세법학개론_{year}_문제.json",
        "a_file": "세무사_1차_세법학개론_{year}_정답.json",
        # 세무사 1차 세법학개론: 문제 번호 41~80, 정답 키 1~40 (오프셋 40)
        "answer_offset": 40,
    },
    "cpa1": {
        "name": "CPA_1차_세법",
        "years": [2024, 2025, 2026],
        "q_file": "CPA_1차_세법_{year}_문제.json",
        "a_file": "CPA_1차_세법_{year}_정답.json",
        # CPA 1차 세법: 문제 번호 = 정답 키 (오프셋 0)
        "answer_offset": 0,
    },
}

PARSED_DIR = Path("data/exam/parsed")


# ─── 문제·정답 로딩 ───────────────────────────────────────────────────────────

@dataclass
class Question:
    exam: str
    year: int
    number: int          # 원본 문제 번호 (예: 41)
    answer_key: int      # 정답 키 번호 (예: 1)
    content: str         # 문제 지문
    choices: list[str]   # 선택지 리스트
    subject: list[str]   # 세목 (소재)
    correct: int         # 정답 번호 (1~5)


def load_questions(exam: str, year: int) -> list[Question]:
    cfg = EXAM_CONFIG[exam]
    q_path = PARSED_DIR / cfg["q_file"].format(year=year)
    a_path = PARSED_DIR / cfg["a_file"].format(year=year)

    if not q_path.exists():
        print(f"  ! 문제 파일 없음: {q_path}")
        return []
    if not a_path.exists():
        print(f"  ! 정답 파일 없음: {a_path}")
        return []

    with open(q_path, encoding="utf-8") as f:
        q_data = json.load(f)
    with open(a_path, encoding="utf-8") as f:
        a_data = json.load(f)

    answers = {int(k): v for k, v in a_data.get("정답", {}).items()}
    offset = cfg["answer_offset"]
    questions = []

    for q in q_data.get("문제", []):
        num = int(q["번호"])
        key = num - offset  # 정답 키로 변환
        if key not in answers:
            continue
        questions.append(Question(
            exam=exam,
            year=year,
            number=num,
            answer_key=key,
            content=q.get("내용", ""),
            choices=q.get("보기", []),
            subject=q.get("소재", []),
            correct=answers[key],
        ))

    return questions


# ─── Claude API 호출 ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """당신은 대한민국 세법 전문가입니다.
주어진 객관식 문제를 읽고 정답 번호(1~5 중 하나)만 숫자로 답하세요.
설명 없이 숫자 하나만 출력하세요."""


def build_user_prompt(q: Question) -> str:
    choices_text = "\n".join(q.choices)
    subject_text = " / ".join(q.subject) if q.subject else "세법"
    return f"""[{subject_text}]

{q.content}

{choices_text}

정답 번호:"""


def ask_claude(client, q: Question, model: str = "claude-haiku-4-5-20251001") -> Optional[int]:
    """Claude에게 MCQ 질문을 던지고 정답 번호(int)를 반환. 실패 시 None."""
    try:
        response = client.messages.create(
            model=model,
            max_tokens=10,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_prompt(q)}],
        )
        raw = response.content[0].text.strip()
        # 숫자만 추출
        for ch in raw:
            if ch.isdigit() and ch in "12345":
                return int(ch)
        return None
    except Exception as e:
        print(f"    API 오류: {e}", file=sys.stderr)
        return None


# ─── 결과 집계 ────────────────────────────────────────────────────────────────

@dataclass
class MCQResult:
    q: Question
    predicted: Optional[int]
    correct: int

    @property
    def is_correct(self) -> bool:
        return self.predicted == self.correct

    def summary(self) -> str:
        status = "✓" if self.is_correct else "✗"
        pred_str = str(self.predicted) if self.predicted else "?"
        return (f"  {status} [{self.q.year} Q{self.q.number}] "
                f"정답={self.correct} / 예측={pred_str} "
                f"({'/'.join(self.q.subject)})")


# ─── 드라이런 모드 (API 없이 구조 확인) ─────────────────────────────────────

def dry_run(questions: list[Question]):
    """API 없이 문제 파싱 결과만 출력."""
    print(f"\n  총 {len(questions)}문항 로드됨.")
    for q in questions[:3]:
        print(f"\n  [Q{q.number}] {q.content[:60]}...")
        for c in q.choices[:2]:
            print(f"    {c[:50]}")
        print(f"    정답: {q.correct} | 소재: {q.subject}")
    if len(questions) > 3:
        print(f"  ... 이하 {len(questions) - 3}문항 생략")


# ─── 메인 ────────────────────────────────────────────────────────────────────

def main():
    _utf8()

    parser = argparse.ArgumentParser(description="mcq_eval — 세법 객관식 정확도 측정")
    parser.add_argument("--exam", choices=["cta1", "cpa1", "all"], default="cta1",
                        help="시험 선택 (cta1=세무사1차, cpa1=CPA1차, all=전체)")
    parser.add_argument("--year", type=int, default=0,
                        help="특정 연도 (0=전체)")
    parser.add_argument("--limit", type=int, default=0,
                        help="최대 문항 수 (0=무제한)")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001",
                        help="사용할 Claude 모델")
    parser.add_argument("--dry-run", action="store_true",
                        help="API 호출 없이 문제 파싱 확인만")
    parser.add_argument("--output", default="",
                        help="결과 저장 경로 (JSON)")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="API 호출 간 딜레이(초)")
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("MCQ EVAL — 세법 기출 객관식 정확도 측정")
    print("=" * 70)

    # ── 시험 목록 결정 ──
    exams = list(EXAM_CONFIG.keys()) if args.exam == "all" else [args.exam]

    # ── 문제 수집 ──
    all_questions: list[Question] = []
    for exam in exams:
        cfg = EXAM_CONFIG[exam]
        years = [args.year] if args.year else cfg["years"]
        for year in years:
            qs = load_questions(exam, year)
            print(f"  로드: {cfg['name']} {year} — {len(qs)}문항")
            all_questions.extend(qs)

    if args.limit:
        all_questions = all_questions[:args.limit]

    print(f"\n  평가 대상: 총 {len(all_questions)}문항")

    if args.dry_run:
        print("\n[드라이런 모드 — API 호출 없음]")
        dry_run(all_questions)
        return

    if not all_questions:
        print("평가할 문항 없음.")
        return

    # ── API 클라이언트 초기화 ──
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("\n[오류] ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        print("  .env 파일에 ANTHROPIC_API_KEY=sk-ant-... 를 추가하거나")
        print("  --dry-run 옵션으로 구조만 확인하세요.")
        sys.exit(1)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except ImportError:
        print("\n[오류] anthropic 패키지가 없습니다: uv add anthropic")
        sys.exit(1)

    # ── 평가 실행 ──
    results: list[MCQResult] = []
    print(f"\n[모델: {args.model}]")
    print()

    for i, q in enumerate(all_questions, 1):
        predicted = ask_claude(client, q, model=args.model)
        r = MCQResult(q=q, predicted=predicted, correct=q.correct)
        results.append(r)
        print(r.summary())
        if args.delay and i < len(all_questions):
            time.sleep(args.delay)

    # ── 결과 리포트 ──
    total = len(results)
    correct_count = sum(1 for r in results if r.is_correct)
    accuracy = 100 * correct_count / total if total else 0

    print()
    print("=" * 70)
    print(f"총 {total}문항 | 정답 {correct_count}건 | 오답 {total - correct_count}건")
    print(f"정확도: {accuracy:.1f}%")

    # 세목별 정확도
    by_subject: dict[str, list[bool]] = {}
    for r in results:
        for s in r.q.subject:
            by_subject.setdefault(s, []).append(r.is_correct)

    if len(by_subject) > 1:
        print("\n[세목별 정확도]")
        for subj, bools in sorted(by_subject.items()):
            acc = 100 * sum(bools) / len(bools)
            print(f"  {subj}: {acc:.1f}% ({sum(bools)}/{len(bools)})")

    # ── 결과 저장 ──
    if args.output:
        out_path = Path(args.output)
        out_data = {
            "모델": args.model,
            "총_문항수": total,
            "정답수": correct_count,
            "정확도": round(accuracy, 2),
            "결과": [
                {
                    "시험": r.q.exam,
                    "연도": r.q.year,
                    "번호": r.q.number,
                    "정답": r.q.correct,
                    "예측": r.predicted,
                    "정오": r.is_correct,
                    "소재": r.q.subject,
                }
                for r in results
            ],
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out_data, f, ensure_ascii=False, indent=2)
        print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    main()
