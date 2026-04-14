"""Phase 6 — 판단 품질 골드셋 채점기.

3메트릭:
  ruling_match          expected_ruling과 판단 일치 여부
  source_match          authoritative_sources 중 1건 이상이 cited_sources에 포함
  forbidden_avoided     forbidden_reasoning 키워드가 reasoning에 등장하지 않음

목표: ruling_match ≥ 8/10, source_match ≥ 7/10, forbidden_avoided = 10/10

사용:
  uv run python eval_judgment_v1.py                 # 전체 10케이스
  uv run python eval_judgment_v1.py --cases J001,J003  # 특정 케이스만
  uv run python eval_judgment_v1.py --save-runs     # 상세 결과 저장
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from reasoning_engine.orchestrator import run as orchestrate

ROOT = Path(__file__).parent
GOLDSET_FILE = ROOT / 'data' / 'eval' / 'judgment_goldset_v1.yaml'
RUNS_DIR = ROOT / 'data' / 'eval' / 'judgment_runs'


def _load_cases() -> list[dict[str, Any]]:
    return yaml.safe_load(GOLDSET_FILE.read_text(encoding='utf-8'))


def score_case(case: dict[str, Any], judgment: dict[str, Any]) -> dict[str, Any]:
    expected = case['expected_ruling']
    actual = (judgment.get('ruling') or '').strip()

    # 1. ruling_match: 정확 일치 (향후 유사어 허용 확장 여지)
    ruling_match = actual == expected

    # 2. source_match: authoritative_sources 중 최소 1건이 cited_sources에 포함
    auth = case.get('authoritative_sources') or []
    cited = judgment.get('cited_sources') or []
    source_match = False
    for a in auth:
        t = a.get('type')
        for c in cited:
            if c.get('type') != t:
                continue
            if t == 'precedent' and c.get('사건번호') == a.get('사건번호'):
                source_match = True
            elif t == 'admin_rule' and c.get('rule_id') == a.get('rule_id'):
                source_match = True
            elif t == 'statute' and c.get('law') == a.get('law') and c.get('article') == a.get('article'):
                source_match = True
        if source_match:
            break

    # 3. forbidden_avoided: reasoning에 forbidden 키워드 미등장
    forbidden = case.get('forbidden_reasoning') or []
    reasoning_text = judgment.get('reasoning') or ''
    forbidden_hits = [f for f in forbidden if f in reasoning_text]
    forbidden_avoided = not forbidden_hits

    return {
        'case_id': case['id'],
        'issue_id': case['issue_id'],
        'expected_ruling': expected,
        'actual_ruling': actual,
        'ruling_match': ruling_match,
        'source_match': source_match,
        'forbidden_avoided': forbidden_avoided,
        'forbidden_hits': forbidden_hits,
        'confidence': judgment.get('confidence'),
        'cited_count': len(cited),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', default='', help='comma-separated case id prefixes (J001,J003)')
    ap.add_argument('--model', default=None)
    ap.add_argument('--save-runs', action='store_true')
    args = ap.parse_args()

    cases = _load_cases()
    if args.cases:
        wanted = [w.strip() for w in args.cases.split(',') if w.strip()]
        cases = [c for c in cases if any(c['id'].startswith(w) for w in wanted)]

    results: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    t0 = time.time()
    for i, case in enumerate(cases, 1):
        ts = time.time()
        print(f"[{i}/{len(cases)}] {case['id']} ({case['issue_id']}) ...", flush=True)
        try:
            run = orchestrate(case['issue_id'], case['profile'], model=args.model)
            judgment = run['judgment']
        except Exception as e:
            judgment = {'ruling': None, 'reasoning': f'[ERROR] {e}', 'cited_sources': [], 'confidence': 0.0}
            run = {'error': str(e)}
        score = score_case(case, judgment)
        score['elapsed_s'] = round(time.time() - ts, 1)
        results.append(score)
        flags = []
        flags.append('R✓' if score['ruling_match'] else 'R✗')
        flags.append('S✓' if score['source_match'] else 'S✗')
        flags.append('F✓' if score['forbidden_avoided'] else 'F✗')
        print(
            f"   {' '.join(flags)} "
            f"[{score['actual_ruling']} vs {score['expected_ruling']}] "
            f"cited={score['cited_count']} conf={score['confidence']} "
            f"({score['elapsed_s']}s)",
            flush=True,
        )
        if args.save_runs:
            runs.append({'case_id': case['id'], 'score': score, 'judgment': judgment})

    total = len(results)
    rm = sum(1 for r in results if r['ruling_match'])
    sm = sum(1 for r in results if r['source_match'])
    fa = sum(1 for r in results if r['forbidden_avoided'])
    elapsed = round(time.time() - t0, 1)
    print(f"\n=== Summary ({total} cases, {elapsed}s) ===")
    print(f"ruling_match:     {rm}/{total} (target ≥ 8)")
    print(f"source_match:     {sm}/{total} (target ≥ 7)")
    print(f"forbidden_avoid:  {fa}/{total} (target = 10)")

    if args.save_runs:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        out = RUNS_DIR / f'judgment_{stamp}.json'
        out.write_text(
            json.dumps({'summary': {'total': total, 'rm': rm, 'sm': sm, 'fa': fa, 'elapsed_s': elapsed},
                        'runs': runs}, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        print(f"[saved] {out}")


if __name__ == '__main__':
    import sys
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
