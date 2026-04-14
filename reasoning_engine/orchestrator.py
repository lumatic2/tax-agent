"""4단계 파이프라인 오케스트레이터.

흐름:
  1) issue 선택 (issue_id 또는 profile 기반 추출)
  2) 검색쿼리 생성 (issue.search_queries + 제목)
  3) legal_retriever.retrieve()로 판례·행정규칙 수집
  4) reasoner.reason()로 판단 생성

adversary는 6-D에서 후단에 추가됨.

CLI:
  python -m reasoning_engine.orchestrator --case J001_car_business_ratio_weak_log
  python -m reasoning_engine.orchestrator --issue GRAY_CAR_BUSINESS_RATIO --profile-json '{...}'
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from reasoning_engine.adversary import challenge
from reasoning_engine.legal_retriever import retrieve
from reasoning_engine.reasoner import reason

ROOT = Path(__file__).parents[1]
ISSUES_DIR = ROOT / 'reasoning_engine' / 'issues'
GOLDSET_DIR = ROOT / 'data' / 'eval'
GOLDSET_GLOB = 'judgment_goldset_*.yaml'


def _load_issues() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in sorted(ISSUES_DIR.glob('*.yaml')):
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
        if data:
            out.extend(data)
    return out


def _load_cases() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in sorted(GOLDSET_DIR.glob(GOLDSET_GLOB)):
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
        if data:
            out.extend(data)
    return out


def _find_issue(issue_id: str) -> dict[str, Any]:
    for i in _load_issues():
        if i['id'] == issue_id:
            return i
    raise ValueError(f"issue not found: {issue_id}")


def _find_case(case_id: str) -> dict[str, Any]:
    for c in _load_cases():
        if c['id'] == case_id:
            return c
    raise ValueError(f"case not found: {case_id}")


def run(
    issue_id: str,
    profile: dict[str, Any],
    *,
    model: str | None = None,
    k_precedents: int = 3,
    k_admin_rules: int = 2,
    use_adversary: bool = True,
    adversary_rewrites: bool = False,
    severity_threshold: float = 0.4,
) -> dict[str, Any]:
    """end-to-end 파이프라인 실행.

    파이프라인:
      1. retrieve (판례·행정규칙)
      2. reason v1 (초기 판단)
      3. adversary challenge — 반박·probe_questions·required_evidence 생성
      4. (adversary_rewrites=True일 때만) severity ≥ threshold이면 reason v2

    기본값 adversary_rewrites=False: adversary는 annotation-only.
    측정 결과 adversary critique이 재판단에 LLM 환각을 주입해 정답률이
    오히려 떨어지는 현상 관찰(10케이스 기준 8→4). 재판단은 명시적 opt-in.
    """
    issue = _find_issue(issue_id)
    query = ' '.join(issue.get('search_queries') or [issue.get('title', '')])
    retrieved = retrieve(
        query,
        issue_id=issue_id,
        k_precedents=k_precedents,
        k_admin_rules=k_admin_rules,
    )
    judgment_v1 = reason(issue, profile, retrieved, model=model)
    out: dict[str, Any] = {
        'issue_id': issue_id,
        'query': query,
        'retrieved': retrieved,
        'judgment': judgment_v1,
    }
    if not use_adversary:
        return out

    adv = challenge(issue, profile, retrieved, judgment_v1, model=model)
    out['adversary'] = adv

    # adversary가 고severity이면 판단의 confidence 감쇠 + caveats 주입 (재판단 X)
    if adv.get('severity', 0.0) >= severity_threshold:
        judgment_v1['confidence'] = min(judgment_v1.get('confidence', 0) or 0, 0.6)
        caveats = list(judgment_v1.get('caveats') or [])
        caveats.append(
            f"adversary_flagged[severity={adv.get('severity'):.1f}]: "
            f"{adv.get('flaw_detected') or (adv.get('counterargument') or '')[:120]}"
        )
        judgment_v1['caveats'] = caveats

    if adversary_rewrites and adv.get('severity', 0.0) >= severity_threshold:
        # 재판단: adversary critique을 reasoner에 추가 컨텍스트로 주입
        critique_block = (
            "\n\n## 조사관 측 반박 (재검토 필수)\n"
            f"- 지적된 오류: {adv.get('flaw_detected') or '(명시 없음)'}\n"
            f"- 반박 논거: {adv.get('counterargument')}\n"
            f"- 필요 증빙: {adv.get('required_evidence')}\n"
            "위 반박을 정면으로 반영해 판단을 재작성하라. 반박이 타당하면 ruling을 바꾸고,\n"
            "부당하면 왜 부당한지 reasoning에 명시하라.\n"
        )
        # reason()에 critique을 넘기는 간편 경로: profile에 임시 필드 추가
        augmented_profile = dict(profile)
        augmented_profile['__adversary_critique__'] = critique_block
        judgment_v2 = reason(issue, augmented_profile, retrieved, model=model)
        out['judgment'] = judgment_v2
        out['judgment_v1_before_adversary'] = judgment_v1

        # v2에 대한 재검증 — severity 여전히 높으면 confidence cap
        adv2 = challenge(issue, profile, retrieved, judgment_v2, model=model)
        out['adversary_v2'] = adv2
        if adv2.get('severity', 0.0) >= severity_threshold:
            judgment_v2['confidence'] = min(judgment_v2.get('confidence', 0) or 0, 0.6)
            caveats = list(judgment_v2.get('caveats') or [])
            caveats.append(
                f"adversary_persistent_flaw: {adv2.get('flaw_detected') or adv2.get('counterargument','')[:100]}"
            )
            judgment_v2['caveats'] = caveats
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', help='goldset case id (e.g. J001_car_business_ratio_weak_log)')
    ap.add_argument('--issue', help='issue id (e.g. GRAY_CAR_BUSINESS_RATIO)')
    ap.add_argument('--profile-json', help='profile as JSON string', default=None)
    ap.add_argument('--model', default=None)
    args = ap.parse_args()

    if args.case:
        case = _find_case(args.case)
        issue_id = case['issue_id']
        profile = case['profile']
    elif args.issue:
        issue_id = args.issue
        profile = json.loads(args.profile_json) if args.profile_json else {}
    else:
        ap.error('--case or --issue required')

    out = run(issue_id, profile, model=args.model)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    import sys
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
