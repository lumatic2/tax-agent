"""Ollama 로컬 모델 기반 규칙 발동 회귀 하네스.

목적:
  자연어 프로파일 설명 → LLM이 flat profile JSON 추출 → strategy_engine 실행 →
  발동된 규칙 id 집합을 골드셋과 비교.

설계 원칙 (메모리 반영):
  - 순차 1건씩 실행. 병렬·subprocess 파싱 버그 회피.
  - 원문 응답을 디스크 저장 (`data/eval/ollama_runs/<scenario>_<model>_<ts>.json`).
  - JSON fence 강제 프롬프트. 실패 시 raw output 보존 후 skip.
  - `--run` 플래그 없으면 dry-run: 프롬프트·골드셋 구조만 확인.

사용:
  # dry-run (기본) — 모델 호출 없이 구조만 확인
  python eval_ollama_rule_firing.py

  # 실제 실행 (qwen3:32b 가 pull 되어 있어야 함)
  python eval_ollama_rule_firing.py --run --model qwen3:32b

  # 특정 시나리오만
  python eval_ollama_rule_firing.py --run --scenario one_house_exempt

전제:
  - `ollama --version` 정상. `ollama pull qwen3:32b` 완료.
  - Phase 2 이전에는 실험 용도. 통과율이 낮으면 프롬프트 튜닝·모델 교체 검토.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from strategy_engine import run as strategy_run

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


PROMPT_TEMPLATE = """다음 한국 세법 상담 설명에서 flat JSON 프로파일을 추출하라.

출력 규칙:
- ```json 과 ``` 로 감싼 한 개의 JSON 객체만 출력 (thinking 금지).
- 설명에 명시된 내용만. 추측·가정 금지.

통화 변환 (정확히):
- "1억" = 100000000 (0이 8개)
- "8억" = 800000000
- "12억" = 1200000000
- "3천만" = 30000000

양도소득 필드 사전 (해당하는 것만 사용):
- has_transfer_income (bool) — 양도거래 존재
- is_one_house (bool) — 1세대 1주택
- has_temp_two_house (bool) — 일시적 2주택
- has_inherited_house (bool) — 상속주택 보유
- is_unregistered_transfer (bool) — 미등기 자산 양도
- is_multi_house_heavy_zone (bool) — 조정대상지역 다주택
- is_self_cultivated_farmland (bool) — 농지 소재지 거주 자경
- is_public_expropriation (bool) — 공익사업 수용
- is_post_gift_transfer (bool) — 증여받은 자산 양도
- transfer_gain (int, 원) — 양도차익
- transfer_price (int, 원) — 양도가액
- holding_years (int) — 보유 연수
- holding_months (int) — 보유 개월수
- residence_years (int) — 거주 연수
- self_cultivation_years (int) — 자경 연수
- years_since_gift (int) — 증여 후 경과 연수
- months_since_new_house (int) — 신규주택 취득 후 개월수
- expropriation_compensation_type ("cash"|"bond_3y"|"bond_5y"|"bond_7y")

설명:
{description}
"""


@dataclass
class Scenario:
    id: str
    description: str          # LLM 에 제공할 자연어
    expected_fire: set[str]   # 반드시 포함되어야 할 rule id
    expected_skip: set[str] = field(default_factory=set)


SCENARIOS: list[Scenario] = [
    Scenario(
        id="one_house_exempt",
        description=(
            "서울에 사는 김씨. 유일한 주택 한 채를 7년 전에 8억에 매수해 계속 거주했고, "
            "현재 시세 11억에 매도하려 한다. 양도차익은 3억. 조정대상지역이었다."
        ),
        expected_fire={"TRANSFER_ONE_HOUSE_EXEMPT", "TRANSFER_LTCG_TABLE2_ONE_HOUSE"},
    ),
    Scenario(
        id="temp_two_house",
        description=(
            "이씨는 5년 보유·거주한 종전주택이 있고, 작년(14개월 전) 신규주택을 구입해 이사했다. "
            "이제 종전주택을 3억 양도차익으로 팔려 한다."
        ),
        expected_fire={"TRANSFER_TEMP_TWO_HOUSE"},
    ),
    Scenario(
        id="unregistered",
        description=(
            "박씨는 10년 전 상속받았지만 등기를 하지 않은 토지를 양도하려 한다. "
            "양도차익은 1억 5천만원."
        ),
        expected_fire={"TRANSFER_UNREGISTERED_AVOID"},
    ),
    Scenario(
        id="farmland_8yr",
        description=(
            "최씨는 12년간 농지 소재지에 거주하며 직접 농사지은 논을 양도한다. "
            "양도차익 2억. 근로·사업 소득 없음."
        ),
        expected_fire={"TRANSFER_SELF_CULTIVATED_FARMLAND"},
    ),
    Scenario(
        id="high_value_12eok",
        description=(
            "정씨의 서울 본인 거주 아파트(1세대 1주택, 보유 6년·거주 4년). "
            "양도가 18억, 양도차익 8억."
        ),
        expected_fire={"TRANSFER_HIGH_VALUE_EXCESS_LTCG", "TRANSFER_LTCG_TABLE2_ONE_HOUSE"},
        expected_skip={"TRANSFER_ONE_HOUSE_EXEMPT"},
    ),
]


RUNS_DIR = Path("data/eval/ollama_runs")


def _ollama_call(model: str, prompt: str, timeout: int = 300) -> str:
    """Ollama CLI 호출. 타임아웃 시 예외."""
    proc = subprocess.run(
        ["ollama", "run", model, prompt],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ollama exit {proc.returncode}: {proc.stderr[:500]}")
    return proc.stdout


def _extract_json(raw: str) -> dict[str, Any]:
    """```json ... ``` 블록에서 JSON 추출."""
    start = raw.find("```json")
    if start < 0:
        start = raw.find("```")
    if start < 0:
        raise ValueError("no fenced block")
    start = raw.find("\n", start) + 1
    end = raw.find("```", start)
    if end < 0:
        raise ValueError("unclosed fenced block")
    return json.loads(raw[start:end].strip())


def _score(profile: dict, scenario: Scenario) -> dict:
    """추출된 profile 로 strategy_engine 실행 후 점수 산출."""
    res = strategy_run(profile)
    fired = {c["rule"].id for c in res["candidates"]}
    hit = fired & scenario.expected_fire
    miss = scenario.expected_fire - fired
    wrong_skip = fired & scenario.expected_skip
    precision = len(hit) / len(scenario.expected_fire) if scenario.expected_fire else 1.0
    return {
        "fired": sorted(fired),
        "hit": sorted(hit),
        "miss": sorted(miss),
        "wrong_skip": sorted(wrong_skip),
        "precision": precision,
        "passed": len(miss) == 0 and len(wrong_skip) == 0,
    }


def _run_scenario(scenario: Scenario, model: str, dry_run: bool) -> dict:
    prompt = PROMPT_TEMPLATE.format(description=scenario.description)
    record: dict[str, Any] = {
        "scenario_id": scenario.id,
        "model": model,
        "prompt": prompt,
        "timestamp": int(time.time()),
    }
    if dry_run:
        record["status"] = "dry_run"
        return record

    t0 = time.time()
    try:
        raw = _ollama_call(model, prompt)
        record["elapsed_s"] = round(time.time() - t0, 2)
        record["raw_output"] = raw
        profile = _extract_json(raw)
        record["extracted_profile"] = profile
        record["score"] = _score(profile, scenario)
        record["status"] = "ok"
    except Exception as e:
        record["elapsed_s"] = round(time.time() - t0, 2)
        record["status"] = "error"
        record["error"] = f"{type(e).__name__}: {e}"
    return record


def _save_record(record: dict) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"{record['scenario_id']}_{record['model'].replace(':', '_')}_{record['timestamp']}.json"
    path = RUNS_DIR / fname
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3:32b")
    ap.add_argument("--scenario", help="단일 시나리오 id 선택")
    ap.add_argument("--run", action="store_true", help="실제 Ollama 호출 (기본 dry-run)")
    args = ap.parse_args()

    scenarios = SCENARIOS
    if args.scenario:
        scenarios = [s for s in SCENARIOS if s.id == args.scenario]
        if not scenarios:
            print(f"unknown scenario: {args.scenario}", file=sys.stderr)
            return 1

    dry = not args.run
    mode = "DRY-RUN" if dry else f"MODEL={args.model}"
    print(f"=== Ollama rule-firing eval ({mode}) — {len(scenarios)} 시나리오 ===\n")

    total = len(scenarios)
    passed = 0
    for s in scenarios:
        print(f"--- {s.id} ---")
        print(f"설명: {s.description}")
        print(f"기대 발동: {sorted(s.expected_fire)}")
        if s.expected_skip:
            print(f"기대 비발동: {sorted(s.expected_skip)}")
        record = _run_scenario(s, args.model, dry)
        if dry:
            print("  (dry-run — 프롬프트만 구성)\n")
            continue
        path = _save_record(record)
        print(f"  저장: {path}")
        if record["status"] != "ok":
            print(f"  [ERR] {record.get('error')}")
            continue
        sc = record["score"]
        verdict = "PASS" if sc["passed"] else "FAIL"
        print(f"  [{verdict}] precision={sc['precision']:.2f} hit={sc['hit']} miss={sc['miss']}")
        if sc["passed"]:
            passed += 1
        print()

    if not dry:
        print(f"\n결과: {passed}/{total} 통과")
        return 0 if passed == total else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
