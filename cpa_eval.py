"""cpa_eval.py — CPA 2차 소득세 계산 문제 정확도 측정.

plain LLM vs tax calculator + law-mcp 시스템 비교.

사용법:
    python cpa_eval.py                          # 전체 (2024+2025, A+B 모두)
    python cpa_eval.py --problem 2024           # 2024년만
    python cpa_eval.py --mode plain             # 조건A (순수 LLM)만
    python cpa_eval.py --mode tools             # 조건B (도구 포함)만
    python cpa_eval.py --dry-run                # 호출 없이 구조·채점항목 확인
    python cpa_eval.py --output data/exam/results/cpa2_eval.json
"""
import sys
import json
import re
import subprocess
import argparse
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


def _utf8():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


PARSED_DIR = Path("data/exam/parsed")
RESULTS_DIR = Path("data/exam/results")
DEFAULT_MODEL = "claude-sonnet-4-6"

# ±이 범위 이내면 '근사(close)' 처리
TOLERANCE = 100  # 원


# ─── 로딩 ──────────────────────────────────────────────────────────────────────

def load_exam(year: int) -> dict:
    """CPA 2차 세법 Q1(소득세법) 문제 + 정답 로드."""
    q_path = PARSED_DIR / f"CPA_2차_세법_{year}_문제.json"
    a_path = PARSED_DIR / f"CPA_2차_세법_{year}_정답.json"

    with open(q_path, encoding="utf-8") as f:
        q_data = json.load(f)
    with open(a_path, encoding="utf-8") as f:
        a_data = json.load(f)

    q1 = next(q for q in q_data["문제"] if q["번호"] == 1)
    a1 = next(q for q in a_data["문제"] if q["번호"] == 1)

    return {
        "year": year,
        "text": q1["내용"],
        "scoring": a1["물음"],  # [{번호, 내용, 요구사항: [{번호, 항목: {키: 값}}]}]
    }


# ─── 프롬프트 ─────────────────────────────────────────────────────────────────

SYSTEM_PLAIN = """당신은 대한민국 세법 전문가입니다.
CPA 2차 시험 소득세 계산 문제(물음 하나)를 풀어야 합니다.
- 계산 근거를 단계별로 제시하시오.
- 계산이 끝나면 마지막에 반드시 ```json 코드블록으로 답안을 요약하시오.
- 금액은 원 단위 정수로 기입하시오 (콤마·원 표시 없음).
"""

SYSTEM_TOOLS = """당신은 대한민국 세법 전문가입니다.
CPA 2차 시험 소득세 계산 문제(물음 하나)를 풀어야 합니다.
- 계산 근거를 단계별로 제시하시오.
- 계산 검증에 Bash를 통해 다음 명령을 사용할 수 있습니다:
    python tax_calc_cli.py earned-deduction --salary <총급여>
    python tax_calc_cli.py income-tax --taxable <과세표준>
    python tax_calc_cli.py retirement-tax --pay <퇴직급여> --years <근속연수>
    python tax_calc_cli.py transfer-tax --price <양도가> --acq-price <취득가> --held-years <보유연수>
    python tax_calc_cli.py withholding --amount <금액> --type <이자|배당|사업|기타>
- 법령 조문 확인에 law-mcp 도구(get_law_article, search_law 등)를 사용할 수 있습니다.
- 계산이 끝나면 마지막에 반드시 ```json 코드블록으로 답안을 요약하시오.
- 금액은 원 단위 정수로 기입하시오 (콤마·원 표시 없음).
"""


def build_sub_schema(sub: dict) -> str:
    """물음 하나의 요구사항 JSON 스키마 생성."""
    schema: dict = {}
    for req in sub.get("요구사항", []):
        req_key = f"요구사항{req['번호']}"
        schema[req_key] = {k: "?" for k in req["항목"]}
    return json.dumps(schema, ensure_ascii=False, indent=2)


def build_sub_prompt(full_text: str, sub: dict) -> str:
    """물음 하나에 대한 프롬프트 생성."""
    sub_num = sub["번호"]
    label = sub.get("내용", f"물음{sub_num}")
    schema = build_sub_schema(sub)
    return (
        full_text
        + f"\n\n---\n"
        f"위 문제 중 **물음{sub_num}** ({label})에 대해서만 답하라.\n"
        "계산 근거를 단계별로 기술한 뒤,\n"
        "아래 JSON 형식으로 최종 답안을 제시하라.\n"
        "( ? 자리에 계산 결과를 원 단위 정수로 채울 것 )\n\n"
        "```json\n"
        f"{schema}\n"
        "```\n"
    )


# 하위 호환: 전체 문제용 스키마 (dry-run 출력에 사용)
def build_answer_schema(scoring: list[dict]) -> str:
    schema: dict = {}
    for sub in scoring:
        sub_key = f"물음{sub['번호']}"
        schema[sub_key] = {}
        for req in sub.get("요구사항", []):
            req_key = f"요구사항{req['번호']}"
            schema[sub_key][req_key] = {k: "?" for k in req["항목"]}
    return json.dumps(schema, ensure_ascii=False, indent=2)


# ─── Claude 호출 ──────────────────────────────────────────────────────────────

TIMEOUT_PLAIN = 900   # 물음 하나 기준 (plain: 15분)
TIMEOUT_TOOLS = 1200  # 물음 하나 기준 (tools: 20분)


def ask_plain(prompt: str, system: str, model: str) -> tuple[str, float]:
    t0 = time.time()
    result = subprocess.run(
        ["claude", "-p", "--system-prompt", system, "--model", model],
        input=prompt.encode("utf-8"),
        capture_output=True,
        timeout=TIMEOUT_PLAIN,
    )
    raw = result.stdout.decode("utf-8", errors="replace")
    if result.stderr:
        err = result.stderr.decode("utf-8", errors="replace").strip()
        if err:
            print(f"  [stderr] {err[:120]}", file=sys.stderr)
    return raw, time.time() - t0


def ask_tools(prompt: str, system: str, model: str) -> tuple[str, float]:
    t0 = time.time()
    result = subprocess.run(
        [
            "claude", "-p",
            "--tools", "Bash",
            "--dangerously-skip-permissions",
            "--system-prompt", system,
            "--model", model,
        ],
        input=prompt.encode("utf-8"),
        capture_output=True,
        timeout=TIMEOUT_TOOLS,
    )
    raw = result.stdout.decode("utf-8", errors="replace")
    if result.stderr:
        err = result.stderr.decode("utf-8", errors="replace").strip()
        if err:
            print(f"  [stderr] {err[:120]}", file=sys.stderr)
    return raw, time.time() - t0


# ─── JSON 추출 ────────────────────────────────────────────────────────────────

def extract_json(text: str) -> Optional[dict]:
    """응답에서 마지막 ```json 블록을 추출. 없으면 최후 { } 블록 시도."""
    # ```json ... ``` 패턴 (마지막 것 우선)
    blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    for raw in reversed(blocks):
        try:
            d = json.loads(raw)
            if any(f"물음{i}" in d for i in range(1, 5)):
                return d
        except json.JSONDecodeError:
            pass

    # 폴백: 가장 큰 { } 블록
    best: Optional[dict] = None
    for m in re.finditer(r"\{", text):
        depth, i = 0, m.start()
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    snippet = text[m.start(): i + 1]
                    try:
                        d = json.loads(snippet)
                        if any(f"물음{n}" in d for n in range(1, 5)):
                            if best is None or len(snippet) > len(json.dumps(best)):
                                best = d
                    except json.JSONDecodeError:
                        pass
                    break
            i += 1
    return best


# ─── 채점 ─────────────────────────────────────────────────────────────────────

@dataclass
class ItemScore:
    label: str          # "물음1.요구사항2.배당가산액"
    expected: int
    predicted: Optional[int]

    @property
    def exact(self) -> bool:
        return self.predicted is not None and self.predicted == self.expected

    @property
    def close(self) -> bool:
        return (
            self.predicted is not None
            and not self.exact
            and abs(self.predicted - self.expected) <= TOLERANCE
        )

    def fmt(self) -> str:
        if self.exact:
            mark = "✓"
        elif self.close:
            mark = "≈"
        else:
            mark = "✗"
        pred_str = f"{self.predicted:,}" if self.predicted is not None else "N/A"
        return f"  {mark}  {self.label:<45}  정답={self.expected:>15,}  예측={pred_str:>15}"


def score(scoring: list[dict], predicted: Optional[dict]) -> list[ItemScore]:
    items: list[ItemScore] = []
    for sub in scoring:
        sub_key = f"물음{sub['번호']}"
        for req in sub.get("요구사항", []):
            req_key = f"요구사항{req['번호']}"
            for item_key, expected in req["항목"].items():
                label = f"{sub_key}.{req_key}.{item_key}"
                pred_val: Optional[int] = None
                if predicted:
                    raw = predicted.get(sub_key, {}).get(req_key, {}).get(item_key)
                    if raw is not None and str(raw) != "?":
                        try:
                            pred_val = int(str(raw).replace(",", "").replace("원", "").strip())
                        except (ValueError, AttributeError):
                            pass
                items.append(ItemScore(label=label, expected=expected, predicted=pred_val))
    return items


# ─── 물음 하나 실행 ──────────────────────────────────────────────────────────

def run_sub(year: int, sub: dict, full_text: str, mode: str, model: str) -> dict:
    """물음 하나(sub)를 조건에 따라 실행하고 채점 결과 반환."""
    sub_num = sub["번호"]
    label = sub.get("내용", f"물음{sub_num}")
    system = SYSTEM_PLAIN if mode == "plain" else SYSTEM_TOOLS
    prompt = build_sub_prompt(full_text, sub)
    timeout_str = f"{TIMEOUT_TOOLS}s" if mode == "tools" else f"{TIMEOUT_PLAIN}s"

    print(f"  물음{sub_num} ({label}) — 호출 중 (타임아웃 {timeout_str})")

    try:
        if mode == "plain":
            raw, elapsed = ask_plain(prompt, system, model)
        else:
            raw, elapsed = ask_tools(prompt, system, model)
    except subprocess.TimeoutExpired:
        print(f"  물음{sub_num} — 타임아웃!")
        return {
            "sub_num": sub_num, "label": label,
            "elapsed_s": None, "json_ok": False,
            "error": "timeout",
            "items": [
                {"label": f"요구사항{r['번호']}.{k}", "expected": v,
                 "predicted": None, "exact": False, "close": False}
                for r in sub.get("요구사항", [])
                for k, v in r["항목"].items()
            ],
        }

    print(f"  물음{sub_num} — 응답 ({elapsed:.1f}s, {len(raw):,}자)")

    # 물음 단위 응답에서 JSON 추출 (sub-schema 구조)
    predicted_sub = extract_sub_json(raw, sub)

    # 채점 (물음 단위 scoring)
    items = score_sub(sub, predicted_sub)
    exact = sum(1 for i in items if i.exact)
    close = sum(1 for i in items if i.close)
    total = len(items)

    for item in items:
        print(item.fmt())
    print(f"  → exact={exact}/{total}  근사={close}/{total}")

    return {
        "sub_num": sub_num,
        "label": label,
        "elapsed_s": round(elapsed, 1),
        "json_ok": predicted_sub is not None,
        "exact": exact,
        "close": close,
        "total": total,
        "items": [
            {"label": i.label, "expected": i.expected,
             "predicted": i.predicted, "exact": i.exact, "close": i.close}
            for i in items
        ],
        "response": raw,
    }


def extract_sub_json(text: str, sub: dict) -> Optional[dict]:
    """물음 단위 응답에서 요구사항N 키를 가진 JSON 추출."""
    req_keys = {f"요구사항{r['번호']}" for r in sub.get("요구사항", [])}

    blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    for raw in reversed(blocks):
        try:
            d = json.loads(raw)
            if any(k in d for k in req_keys):
                return d
        except json.JSONDecodeError:
            pass

    # 폴백: 가장 큰 매칭 블록
    best: Optional[dict] = None
    for m in re.finditer(r"\{", text):
        depth, i = 0, m.start()
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    snippet = text[m.start(): i + 1]
                    try:
                        d = json.loads(snippet)
                        if any(k in d for k in req_keys):
                            if best is None or len(snippet) > len(json.dumps(best)):
                                best = d
                    except json.JSONDecodeError:
                        pass
                    break
            i += 1
    return best


def score_sub(sub: dict, predicted: Optional[dict]) -> list[ItemScore]:
    """물음 하나의 요구사항을 채점."""
    items: list[ItemScore] = []
    for req in sub.get("요구사항", []):
        req_key = f"요구사항{req['번호']}"
        for item_key, expected in req["항목"].items():
            label = f"요구사항{req['번호']}.{item_key}"
            pred_val: Optional[int] = None
            if predicted:
                raw = predicted.get(req_key, {}).get(item_key)
                if raw is not None and str(raw) != "?":
                    try:
                        pred_val = int(str(raw).replace(",", "").replace("원", "").strip())
                    except (ValueError, AttributeError):
                        pass
            items.append(ItemScore(label=label, expected=expected, predicted=pred_val))
    return items


# ─── 단일 실험 실행 ───────────────────────────────────────────────────────────

def run_one(year: int, mode: str, model: str, dry_run: bool) -> dict:
    exam = load_exam(year)
    system = SYSTEM_PLAIN if mode == "plain" else SYSTEM_TOOLS

    total_items = sum(
        len(req["항목"])
        for sub in exam["scoring"]
        for req in sub.get("요구사항", [])
    )

    cond_label = "A (plain LLM)" if mode == "plain" else "B (tools: tax_calc + law-mcp)"
    print(f"\n{'─'*65}")
    print(f"CPA 2차 {year} Q1 소득세  |  조건 {cond_label}")
    print(f"채점 항목 {total_items}개  |  모델 {model}")
    print(f"{'─'*65}")

    if dry_run:
        print("[드라이런] 답안 스키마:")
        print(build_answer_schema(exam["scoring"]))
        return {"year": year, "mode": mode, "dry_run": True, "total": total_items}

    sub_results = []
    for sub in exam["scoring"]:
        sr = run_sub(year, sub, exam["text"], mode, model)
        sub_results.append(sr)

    # 전체 집계
    exact = sum(sr.get("exact", 0) for sr in sub_results)
    close = sum(sr.get("close", 0) for sr in sub_results)
    total = sum(sr.get("total", 0) for sr in sub_results)
    elapsed = sum(sr["elapsed_s"] for sr in sub_results if sr.get("elapsed_s"))

    print(f"\n  ▶ 소계: exact={exact}/{total}  근사={close}/{total}  elapsed={elapsed:.1f}s")

    return {
        "year": year,
        "mode": mode,
        "model": model,
        "elapsed_s": round(elapsed, 1),
        "exact": exact,
        "close": close,
        "total": total,
        "pct_exact": round(100 * exact / total, 1) if total else 0,
        "pct_close": round(100 * (exact + close) / total, 1) if total else 0,
        "sub_results": [{k: v for k, v in sr.items() if k != "response"} for sr in sub_results],
        "responses": {f"물음{sr['sub_num']}": sr.get("response", "") for sr in sub_results},
    }


# ─── 메인 ────────────────────────────────────────────────────────────────────

def main():
    _utf8()

    parser = argparse.ArgumentParser(description="CPA 2차 소득세 계산 정확도 측정")
    parser.add_argument("--problem", choices=["2024", "2025", "both"], default="both",
                        help="평가 연도 (기본: both)")
    parser.add_argument("--mode", choices=["plain", "tools", "both"], default="both",
                        help="plain=순수LLM / tools=도구포함 / both=둘다")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Claude 모델 (기본: {DEFAULT_MODEL})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Claude 호출 없이 채점 구조만 확인")
    parser.add_argument("--output", default="",
                        help="결과 저장 경로 (.json)")
    args = parser.parse_args()

    years = [2024, 2025] if args.problem == "both" else [int(args.problem)]
    modes = ["plain", "tools"] if args.mode == "both" else [args.mode]

    print("\n" + "=" * 65)
    print("CPA 2차 소득세 계산 정확도 측정  |  plain LLM vs tax system")
    print("=" * 65)
    print(f"모델: {args.model}  |  연도: {years}  |  조건: {modes}")

    all_results = []
    for year in years:
        for mode in modes:
            r = run_one(year, mode, args.model, args.dry_run)
            all_results.append(r)

    # 요약 테이블
    if not args.dry_run:
        valid = [r for r in all_results if "error" not in r and not r.get("dry_run")]
        if valid:
            print("\n" + "=" * 65)
            print("최종 요약")
            print("=" * 65)
            hdr = f"{'연도':<6} {'조건':<8} {'exact':>8} {'±100원':>8} {'소요시간':>10}"
            print(hdr)
            print("-" * 55)
            for r in valid:
                cond = "A plain" if r["mode"] == "plain" else "B tools"
                print(
                    f"{r['year']:<6} {cond:<8} "
                    f"{r['exact']:>3}/{r['total']} ({r['pct_exact']:>5.1f}%)  "
                    f"{r['exact']+r['close']:>3}/{r['total']} ({r['pct_close']:>5.1f}%)  "
                    f"{r['elapsed_s']:>8.1f}s"
                )

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        # 응답 원문은 별도 폴더에 저장
        resp_dir = out.with_suffix("")
        lite = []
        for r in all_results:
            rc = {k: v for k, v in r.items() if k != "responses"}
            lite.append(rc)
            if "responses" in r:
                resp_dir.mkdir(parents=True, exist_ok=True)
                for sub_label, text in r["responses"].items():
                    fname = resp_dir / f"{r['year']}_{r['mode']}_{sub_label}.txt"
                    with open(fname, "w", encoding="utf-8") as f:
                        f.write(text)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(lite, f, ensure_ascii=False, indent=2)
        print(f"\n결과 저장: {out}")


if __name__ == "__main__":
    main()
