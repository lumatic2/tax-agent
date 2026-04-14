"""Adversary — 국세청 조사관 페르소나로 reasoner 출력을 반박.

입력:
  issue, profile, retrieved_legal, judgment (reasoner 출력)

출력 JSON:
  {
    "counterargument":   str   (반박 논리 3~5문장)
    "probe_questions":   list  (사실관계 추가 질문)
    "required_evidence": list  (입증 필요 증빙)
    "risk_escalation":   str   (low/medium/high)
    "severity":          float (0.0~1.0 — 원 판단이 흔들릴 정도)
    "flaw_detected":     str | None  (원 판단의 핵심 오류, 없으면 null)
  }

활용:
  - severity < 0.4: 단순 주의사항 추가, 판단 유지
  - severity ≥ 0.4: reasoner에 adversary critique 주입해 재판단 1회
  - 재판단 후에도 adversary가 동일 오류 지적하면 confidence cap
"""
from __future__ import annotations

import json
from typing import Any

from agent.llm.adapter import get_llm
from reasoning_engine.reasoner import _format_admin_rules, _format_precedents, _parse_json

ADVERSARY_PROMPT = """\
당신은 대한민국 국세청 조사4국 조사관이다. 납세자 측 세무대리인이 아래와 같이 판단했다.
당신의 역할은 그 판단을 **엄격히 반박**해 과세 가능성을 최대한 끌어올리는 것이다.
단순 동조(yes-man) 금지. 반드시 반박 논거를 찾아내라.

## 쟁점
- 이슈: {issue_id} — {title}
- 상황 설명: {description}
- 납세자 프로필: {profile_json}

## 납세자 측 판단(반박 대상)
- ruling: {ruling}
- reasoning: {reasoning}
- cited_sources: {cited_sources}
- confidence: {confidence}

## 참고 판례·행정규칙
{precedents_text}

{admin_rules_text}

## 반박 지시
1. **핵심 오류(flaw_detected)**: 납세자 측 판단에 논리적 오류·누락된 요건·잘못 적용된 조문이
   있다면 한 문장으로 지적하라. 없으면 null로 두라.
2. **counterargument**: 판단을 뒤집거나 약화시킬 논거 3~5문장. 조문·판례·예규 근거 포함.
3. **probe_questions**: 세무조사 시 납세자에게 물어야 할 사실관계 질문 3~5개.
4. **required_evidence**: 납세자가 자기 주장을 입증하려면 제출해야 할 증빙 목록.
5. **risk_escalation**: low/medium/high — 부과처분 가능성.
6. **severity**: 원 판단이 흔들릴 정도 0.0~1.0.
   - 0.0~0.3: 사소한 보강 필요
   - 0.4~0.6: 판단 재검토 필요 (동일 결론 가능성 있으나 근거 보강)
   - 0.7~1.0: 판단 결론 자체가 틀릴 가능성 큼

## 출력 (JSON만)
{{
  "flaw_detected": "..." or null,
  "counterargument": "...",
  "probe_questions": [...],
  "required_evidence": [...],
  "risk_escalation": "low|medium|high",
  "severity": 0.0
}}
"""


def challenge(
    issue: dict[str, Any],
    profile: dict[str, Any],
    retrieved: dict[str, list[dict[str, Any]]],
    judgment: dict[str, Any],
    *,
    model: str | None = None,
) -> dict[str, Any]:
    llm = get_llm(model, num_predict=1536)
    prompt = ADVERSARY_PROMPT.format(
        issue_id=issue.get('id', '?'),
        title=issue.get('title', '?'),
        description=issue.get('description', '?').strip(),
        profile_json=json.dumps(profile, ensure_ascii=False, indent=2),
        ruling=judgment.get('ruling'),
        reasoning=judgment.get('reasoning'),
        cited_sources=json.dumps(judgment.get('cited_sources') or [], ensure_ascii=False),
        confidence=judgment.get('confidence'),
        precedents_text=_format_precedents(retrieved.get('precedents') or []),
        admin_rules_text=_format_admin_rules(retrieved.get('admin_rules') or []),
    )
    resp = llm.invoke(prompt)
    raw = resp.content if hasattr(resp, 'content') else str(resp)
    parsed = _parse_json(raw) or {
        'flaw_detected': None,
        'counterargument': '(parse failed)',
        'probe_questions': [],
        'required_evidence': [],
        'risk_escalation': 'low',
        'severity': 0.0,
    }
    try:
        parsed['severity'] = float(parsed.get('severity', 0.0))
    except Exception:
        parsed['severity'] = 0.0
    return parsed
