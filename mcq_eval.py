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


def ask_claude_cli(q: Question, model: str = "claude-haiku-4-5-20251001") -> Optional[int]:
    """claude -p CLI를 통해 MCQ 질문을 던지고 정답 번호(int)를 반환. 실패 시 None."""
    import subprocess
    try:
        result = subprocess.run(
            ["claude", "-p", "--model", model, "--system-prompt", SYSTEM_PROMPT],
            input=build_user_prompt(q).encode("utf-8"),
            capture_output=True,
            timeout=180,
        )
        raw = result.stdout.decode("utf-8", errors="replace").strip()
        # 원형 숫자 ①~⑤ 우선 확인
        circle_map = {"①": "1", "②": "2", "③": "3", "④": "4", "⑤": "5"}
        for orig, mapped in circle_map.items():
            if orig in raw:
                return int(mapped)
        # 마지막 줄부터 역순으로 1~5 숫자 탐색 (앞쪽 목록 번호 오인 방지)
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        for line in reversed(lines):
            for ch in reversed(line):
                if ch in "12345":
                    return int(ch)
        if result.stderr:
            err = result.stderr.decode("utf-8", errors="replace")
            if err.strip():
                print(f"    [stderr] {err[:80]}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"    CLI 오류: {e}", file=sys.stderr)
        return None


def ask_claude_with_tools(q: Question, model: str) -> Optional[int]:
    import subprocess

    system_prompt = """당신은 대한민국 세법 객관식 문제를 푸는 전문가다.
계산이 필요하면 반드시 현재 저장소의 `python tax_calc_cli.py ...` 명령을 Bash 도구로 호출해 검산한다.
추론은 간결하게 진행하고, 마지막 줄에는 정답 숫자 1~5 중 하나만 남겨라."""
    prompt = build_user_prompt(q)

    try:
        result = subprocess.run(
            [
                "claude",
                "-p",
                "--tools",
                "Bash",
                "--dangerously-skip-permissions",
                "--system-prompt",
                system_prompt,
                "--model",
                model,
            ],
            input=prompt.encode("utf-8"),
            capture_output=True,
            timeout=300,
        )
        raw = result.stdout.decode("utf-8", errors="replace").strip()
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        for line in reversed(lines):
            for ch in line:
                if ch in "12345":
                    return int(ch)
        return None
    except Exception as e:
        print(f"Tools error: {e}", file=sys.stderr)
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
    parser.add_argument("--subject", default="",
                        help="특정 세목 문자열 필터")
    parser.add_argument("--use-tools", action="store_true",
                        help="claude CLI 호출 시 Bash 도구 사용")
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

    if args.subject:
        # 문제 내용의 <법명> 마커를 우선 체크, 없으면 subject 태그로 폴백
        law_marker = f"<{args.subject}법>"
        all_questions = [
            q for q in all_questions
            if law_marker in q.content
            or any(args.subject in s for s in q.subject)
            and f"<" not in q.content  # 마커 없는 문제만 태그 폴백
        ]
        print(f"  subject 필터 후: {len(all_questions)}문항")

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
    use_cli = args.use_tools or not api_key

    if use_cli:
        if args.use_tools:
            print("\n[--use-tools 활성화 — claude CLI + Bash 도구 모드]")
        else:
            print("\n[ANTHROPIC_API_KEY 없음 — claude CLI 폴백 모드]")
        client = None
    else:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            print("\n[경고] anthropic 패키지 없음 — claude CLI 폴백 모드")
            client = None
            use_cli = True

    # ── 평가 실행 ──
    results: list[MCQResult] = []
    print(f"\n[모델: {args.model}]")
    print()

    if use_cli or client is None:
        # 병렬 실행 (CLI 폴백: subprocess overhead를 병렬로 상쇄)
        from concurrent.futures import ThreadPoolExecutor, as_completed
        workers = min(len(all_questions), 10)  # 최대 10 병렬
        print(f"[병렬 모드: {workers} workers]")
        futures = {}
        ask_fn = ask_claude_with_tools if args.use_tools else ask_claude_cli
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for q in all_questions:
                fut = ex.submit(ask_fn, q, args.model)
                futures[fut] = q
            pending = {fut: q for fut, q in futures.items()}
            done_results: dict[int, MCQResult] = {}
            for fut in as_completed(pending):
                q = pending[fut]
                predicted = fut.result()
                r = MCQResult(q=q, predicted=predicted, correct=q.correct)
                done_results[q.number] = r
                print(r.summary())
        results = [done_results[q.number] for q in all_questions]
    else:
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
