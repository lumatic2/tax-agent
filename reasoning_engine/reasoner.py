"""Reasoner — LLM이 판례·행정규칙 근거로 회색지대 판단을 생성.

입력:
  issue              reasoning_engine/issues/income_tax_gray.yaml의 한 항목
  profile            납세자 프로필 (flat dict, strategy_engine과 호환)
  retrieved_legal    legal_retriever.retrieve() 출력 {precedents, admin_rules}

출력 JSON:
  {
    "ruling":          str   (issue.ruling_spectrum 중 하나)
    "confidence":      float (0.0~1.0)
    "reasoning":       str   (한국어 판단 근거 설명)
    "cited_sources":   list  (retrieved_legal에 있는 것만 허용)
    "caveats":         list  (주의사항·추가 검토 지점)
  }

핵심 원칙:
  - cited_sources는 retrieved_legal 화이트리스트 강제. 외부 판례 인용 금지.
  - 결과 파싱 실패 시 confidence=0으로 raw text만 반환 (상위에서 재시도 판단).
"""
from __future__ import annotations

import json
import re
from typing import Any

from agent.llm.adapter import get_llm

PROMPT_V5 = """\
당신은 대한민국 세무 전문가다. 아래 회색지대 이슈에 대해 주어진 판례·행정규칙만을 근거로 판단하라.

## 회색지대 이슈
- ID: {issue_id}
- 제목: {title}
- 설명: {description}
- 가능한 판단 결과(ruling_spectrum): {spectrum}
- 관련 조문: {statutes}

## 납세자 프로필
{profile_json}

## 검색된 판례 (화이트리스트 — 이 목록 밖의 판례 인용 금지)
{precedents_text}

## 검색된 행정규칙 (화이트리스트)
{admin_rules_text}

## 지시
0. **[결정판례]** 마크된 판례가 있다면 그 판결요지를 **최우선 기준**으로 삼아라.
   결정판례의 쟁점이 본 사안과 동일하면 동일 결론을 따라야 한다. 일반 검색 판례나
   보수적 해석을 앞세워 결정판례를 거스르지 말 것.
1. ruling_spectrum 중 하나를 선택하라. 새 결과 만들지 말 것.
2. reasoning은 한국어로 3~5문장. 프로필의 구체 수치·사실관계와 판례·행정규칙을 연결하라.
3. cited_sources는 반드시 위 화이트리스트에서만 인용하라. 각 항목 형식:
   - 판례: {{"type": "precedent", "사건번호": "...", "사건명": "..."}}
   - 행정규칙: {{"type": "admin_rule", "rule_id": "...", "행정규칙명": "..."}}
   - 조문: {{"type": "statute", "law": "...", "article": "..."}}
4. confidence는 증거의 직접성·판례 일관성·프로필 사실관계의 명확성 기반 0.0~1.0.
5. caveats에는 추가 확인 필요한 사실관계나 반대 해석 가능성을 적어라.

## 출력 형식 (JSON만, 다른 텍스트 금지)
{{
  "ruling": "...",
  "confidence": 0.0,
  "reasoning": "...",
  "cited_sources": [...],
  "caveats": [...]
}}
"""


def _format_precedents(precedents: list[dict[str, Any]]) -> str:
    if not precedents:
        return '(해당 이슈에 매칭된 판례 없음)'
    lines = []
    for p in precedents:
        marker = '**[결정판례]**' if p.get('_pinned') else '-'
        header = (
            f"{marker} 사건번호: {p.get('사건번호', '?')} / 선고일자: {p.get('선고일자', '?')}\n"
            f"  사건명: {p.get('사건명', '')}"
        )
        holding = p.get('판결요지') or p.get('판시사항')
        if holding:
            holding_short = str(holding).strip().replace('\n', ' ')[:300]
            header += f"\n  판결요지: {holding_short}"
        lines.append(header)
    return '\n'.join(lines)


def _format_admin_rules(rules: list[dict[str, Any]]) -> str:
    if not rules:
        return '(해당 이슈에 매칭된 행정규칙 없음)'
    lines = []
    for r in rules:
        name = r.get('행정규칙명', '?')
        rid = r.get('rule_id', '?')
        articles = r.get('조문내용') or []
        excerpt = ''
        if articles:
            joined = ' '.join(articles)
            excerpt = joined[:400] + ('...' if len(joined) > 400 else '')
        lines.append(f"- rule_id: {rid} / 명칭: {name}\n  조문발췌: {excerpt or '(전문 미캐싱)'}")
    return '\n'.join(lines)


def _parse_json(text: str) -> dict[str, Any] | None:
    """LLM 출력에서 첫 번째 JSON 객체 추출."""
    # 코드블록 제거
    text = re.sub(r'```(?:json)?\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    # 최외곽 중괄호 범위 추출
    start = text.find('{')
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    return None
    return None


def _validate_sources(
    cited: list[dict[str, Any]],
    retrieved: dict[str, list[dict[str, Any]]],
    issue_statutes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """cited_sources 중 retrieved_legal/issue.statutes 화이트리스트에 있는 것만 통과."""
    allowed_prec_ids = {p.get('사건번호') for p in retrieved.get('precedents', [])}
    allowed_rule_ids = {r.get('rule_id') for r in retrieved.get('admin_rules', [])}
    allowed_statute_keys = {(s.get('law'), s.get('article')) for s in issue_statutes or []}

    valid: list[dict[str, Any]] = []
    rejected: list[str] = []
    for src in cited or []:
        t = src.get('type')
        if t == 'precedent':
            if src.get('사건번호') in allowed_prec_ids:
                valid.append(src)
            else:
                rejected.append(f"precedent:{src.get('사건번호')}")
        elif t == 'admin_rule':
            if src.get('rule_id') in allowed_rule_ids:
                valid.append(src)
            else:
                rejected.append(f"admin_rule:{src.get('rule_id')}")
        elif t == 'statute':
            key = (src.get('law'), src.get('article'))
            if key in allowed_statute_keys:
                valid.append(src)
            else:
                rejected.append(f"statute:{key}")
        else:
            rejected.append(f"unknown:{src}")
    return valid, rejected


def reason(
    issue: dict[str, Any],
    profile: dict[str, Any],
    retrieved: dict[str, list[dict[str, Any]]],
    model: str | None = None,
) -> dict[str, Any]:
    """LLM 판단. 화이트리스트 검증 포함."""
    # 판단 JSON은 기본 1024 토큰 초과 케이스 다수 → 2048로 확장
    llm = get_llm(model, num_predict=2048)
    statutes_text = '; '.join(
        f"{s.get('law', '?')} {s.get('article', '?')}"
        for s in (issue.get('statutes') or [])
    ) or '(없음)'
    # adversary critique이 있으면 프롬프트 말미에 주입 (재판단 경로)
    critique = profile.get('__adversary_critique__') if isinstance(profile, dict) else None
    profile_for_prompt = {k: v for k, v in profile.items() if k != '__adversary_critique__'} if isinstance(profile, dict) else profile
    prompt = PROMPT_V5.format(
        issue_id=issue.get('id', '?'),
        title=issue.get('title', '?'),
        description=issue.get('description', '?').strip(),
        spectrum=', '.join(issue.get('ruling_spectrum') or []),
        statutes=statutes_text,
        profile_json=json.dumps(profile_for_prompt, ensure_ascii=False, indent=2),
        precedents_text=_format_precedents(retrieved.get('precedents') or []),
        admin_rules_text=_format_admin_rules(retrieved.get('admin_rules') or []),
    )
    if critique:
        prompt = prompt + '\n' + critique
    resp = llm.invoke(prompt)
    raw = resp.content if hasattr(resp, 'content') else str(resp)
    parsed = _parse_json(raw)
    if parsed is None:
        return {
            'ruling': None,
            'confidence': 0.0,
            'reasoning': '(JSON parse failed)',
            'cited_sources': [],
            'caveats': ['LLM output parsing failed'],
            '_raw': raw,
        }
    # 화이트리스트 검증
    valid, rejected = _validate_sources(
        parsed.get('cited_sources') or [],
        retrieved,
        issue.get('statutes') or [],
    )
    parsed['cited_sources'] = valid
    if rejected:
        caveats = list(parsed.get('caveats') or [])
        caveats.append(f"rejected_non_whitelist_sources: {rejected}")
        parsed['caveats'] = caveats
        # 화이트리스트 위반이 있으면 confidence 감쇠
        parsed['confidence'] = round(min(parsed.get('confidence', 0) * 0.7, 0.6), 2)
    return parsed
