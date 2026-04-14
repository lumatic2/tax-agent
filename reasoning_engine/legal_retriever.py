"""판례·행정규칙 하이브리드 RAG — 로컬 코퍼스 우선, law-mcp on-demand 폴백.

설계 요지:
  1. scripts/build_precedent_corpus.py가 만든 JSON 코퍼스를 메모리 로드
  2. 판례는 사건명, 행정규칙은 행정규칙명+조문내용을 검색대상 텍스트로
  3. 쿼리 토큰이 검색대상에 얼마나 등장하는지 가중치 합산(title-boost + TF)
  4. 로컬 top-K 결과가 부족하거나 issue_id 매칭이 없을 때 law-mcp 실시간 검색
  5. 결과는 reasoner 프롬프트에 화이트리스트로 주입 — retrieved_legal에 없는
     판례번호 인용은 reasoner가 금지 (할루시네이션 방지)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agent.law_client import get_admin_rule, get_precedent, search_admin_rules, search_precedents

ROOT = Path(__file__).parents[1]
PRECEDENT_FILE = ROOT / 'data' / 'precedent_corpus.json'
ADMIN_RULE_FILE = ROOT / 'data' / 'admin_rule_corpus.json'

_PREC_CACHE: list[dict[str, Any]] | None = None
_ADMIN_CACHE: list[dict[str, Any]] | None = None


def _load_precedents() -> list[dict[str, Any]]:
    global _PREC_CACHE
    if _PREC_CACHE is None:
        if PRECEDENT_FILE.exists():
            _PREC_CACHE = json.loads(PRECEDENT_FILE.read_text(encoding='utf-8'))
        else:
            _PREC_CACHE = []
    return _PREC_CACHE


def _load_admin_rules() -> list[dict[str, Any]]:
    global _ADMIN_CACHE
    if _ADMIN_CACHE is None:
        if ADMIN_RULE_FILE.exists():
            _ADMIN_CACHE = json.loads(ADMIN_RULE_FILE.read_text(encoding='utf-8'))
        else:
            _ADMIN_CACHE = []
    return _ADMIN_CACHE


_TOKEN_RE = re.compile(r'[가-힣A-Za-z0-9]+')


def _tokens(q: str) -> list[str]:
    return [w for w in _TOKEN_RE.findall(q) if len(w) >= 2]


def _score(haystack: str, tokens: list[str], title: str = '') -> float:
    score = 0.0
    for t in tokens:
        if not t:
            continue
        if title and t in title:
            score += 5.0
        score += haystack.count(t) * 1.0
    return score


def retrieve_precedents(
    query: str,
    issue_id: str | None = None,
    k: int = 3,
    fallback: bool = True,
) -> list[dict[str, Any]]:
    """로컬 코퍼스에서 판례 top-K. 부족 시 law-mcp 실시간 검색 폴백."""
    tokens = _tokens(query)
    corpus = _load_precedents()

    # issue_id 우선 필터 — 같은 이슈로 라벨된 판례가 있으면 우선순위
    pool = corpus
    if issue_id:
        issue_tagged = [c for c in corpus if issue_id in (c.get('issue_ids') or [])]
        if issue_tagged:
            pool = issue_tagged

    scored: list[tuple[float, dict[str, Any]]] = []
    for c in pool:
        title = c.get('사건명') or ''
        hay = f"{title} {c.get('사건번호', '')}"
        s = _score(hay, tokens, title=title)
        # goldset authoritative는 의도적 선별이므로 가산
        if c.get('goldset_authoritative'):
            s += 3.0
        if s > 0:
            scored.append((s, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = [dict(c, _score=round(s, 2)) for s, c in scored[:k]]

    if fallback and len(out) < k:
        try:
            live = search_precedents(query, limit=k)
        except Exception:
            live = []
        seen = {c['precedent_id'] for c in out}
        for h in live:
            if h.get('precedent_id') in seen:
                continue
            out.append(dict(h, _source='live_fallback'))
            if len(out) >= k:
                break
    return out


def retrieve_admin_rules(
    query: str,
    issue_id: str | None = None,
    k: int = 2,
    fallback: bool = True,
) -> list[dict[str, Any]]:
    tokens = _tokens(query)
    corpus = _load_admin_rules()

    pool = corpus
    if issue_id:
        issue_tagged = [c for c in corpus if issue_id in (c.get('issue_ids') or [])]
        if issue_tagged:
            pool = issue_tagged

    scored: list[tuple[float, dict[str, Any]]] = []
    for c in pool:
        title = c.get('행정규칙명') or ''
        body = ' '.join(c.get('조문내용') or [])
        s = _score(f"{title} {body}", tokens, title=title)
        if c.get('goldset_authoritative'):
            s += 3.0
        if s > 0:
            scored.append((s, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = [dict(c, _score=round(s, 2)) for s, c in scored[:k]]

    if fallback and len(out) < k:
        try:
            live = search_admin_rules(query, limit=k)
        except Exception:
            live = []
        seen = {c.get('rule_id') for c in out}
        for h in live:
            if h.get('rule_id') in seen:
                continue
            out.append(dict(h, _source='live_fallback'))
            if len(out) >= k:
                break
    return out


def _resolve_decisive_precedent(pid: str) -> dict[str, Any] | None:
    """로컬 corpus 우선, 없으면 law-mcp로 단건 조회."""
    for c in _load_precedents():
        if str(c.get('precedent_id')) == str(pid):
            return dict(c, _pinned=True)
    try:
        data = get_precedent(str(pid))
    except Exception:
        return None
    if not data:
        return None
    return dict(data, _pinned=True, _source='live_fetch')


def _resolve_decisive_admin_rule(rid: str) -> dict[str, Any] | None:
    for c in _load_admin_rules():
        if str(c.get('rule_id')) == str(rid):
            return dict(c, _pinned=True)
    try:
        data = get_admin_rule(str(rid))
    except Exception:
        return None
    if not data:
        return None
    return dict(data, _pinned=True, _source='live_fetch')


def _pin_decisive(
    decisive: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """decisive_sources를 precedent/admin_rule로 분리하여 실자료로 해석.

    해석 순서 (merge 전략):
      1) 로컬 corpus에서 ID 매칭 → base dict
      2) law-mcp 단건 조회 (live_fetch) → base dict
      3) 둘 다 없으면 빈 base
      → issue yaml의 decisive_source 메타(판결요지·사건명 등)를 base에 merge-on-top.
        yaml 메타가 corpus 빈 필드를 보강하고, 서로 값이 있으면 yaml 우선.
    """
    prec_out: list[dict[str, Any]] = []
    adm_out: list[dict[str, Any]] = []
    for d in decisive or []:
        t = d.get('type')
        if t == 'precedent' and d.get('precedent_id'):
            base = _resolve_decisive_precedent(d['precedent_id']) or {}
            merged = {**base, **{k: v for k, v in d.items() if v not in (None, '')}}
            merged['_pinned'] = True
            if '_source' not in merged:
                merged['_source'] = 'issue_yaml'
            prec_out.append(merged)
        elif t == 'admin_rule' and d.get('rule_id'):
            base = _resolve_decisive_admin_rule(d['rule_id']) or {}
            merged = {**base, **{k: v for k, v in d.items() if v not in (None, '')}}
            merged['_pinned'] = True
            if '_source' not in merged:
                merged['_source'] = 'issue_yaml'
            adm_out.append(merged)
    return prec_out, adm_out


def retrieve(
    query: str,
    issue_id: str | None = None,
    k_precedents: int = 3,
    k_admin_rules: int = 2,
    decisive_sources: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """판례 + 행정규칙 동시 검색. decisive_sources가 주어지면 top에 강제 주입.

    decisive_sources 스키마: [{type: precedent, precedent_id: "..."}, ...]
    핀된 자료는 검색 스코어와 무관하게 반환의 맨 앞에 배치되어 reasoner가
    반드시 보게 된다. 핀된 개수만큼 일반 검색 k를 차감.
    """
    pinned_prec, pinned_adm = _pin_decisive(decisive_sources)
    pinned_prec_ids = {str(p.get('precedent_id')) for p in pinned_prec}
    pinned_adm_ids = {str(p.get('rule_id')) for p in pinned_adm}

    prec_k = max(0, k_precedents - len(pinned_prec))
    adm_k = max(0, k_admin_rules - len(pinned_adm))

    prec = retrieve_precedents(query, issue_id, k=prec_k) if prec_k else []
    prec = [p for p in prec if str(p.get('precedent_id')) not in pinned_prec_ids]

    adm = retrieve_admin_rules(query, issue_id, k=adm_k) if adm_k else []
    adm = [a for a in adm if str(a.get('rule_id')) not in pinned_adm_ids]

    return {
        'precedents': pinned_prec + prec,
        'admin_rules': pinned_adm + adm,
    }


if __name__ == '__main__':
    import sys
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    for q, iid in [
        ('지정기부금 엄격해석', 'GRAY_DONATION_ELIGIBILITY'),
        ('업무용승용차 운행기록', 'GRAY_CAR_BUSINESS_RATIO'),
        ('오피스텔 레지던스업', 'GRAY_RENTAL_VS_BUSINESS'),
    ]:
        print(f'\n=== [{iid}] {q} ===')
        res = retrieve(q, issue_id=iid)
        for p in res['precedents']:
            print(f"  [prec {p.get('_score', '?')}] {p.get('사건번호')}: {p.get('사건명', '')[:60]}...")
        for a in res['admin_rules']:
            print(f"  [adm  {a.get('_score', '?')}] {a.get('행정규칙명', '')[:60]}")
