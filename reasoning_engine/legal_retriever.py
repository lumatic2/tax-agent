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

from agent.law_client import search_admin_rules, search_precedents

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


def retrieve(
    query: str,
    issue_id: str | None = None,
    k_precedents: int = 3,
    k_admin_rules: int = 2,
) -> dict[str, list[dict[str, Any]]]:
    """판례 + 행정규칙 동시 검색. reasoner 입력으로 쓰는 통합 인터페이스."""
    return {
        'precedents': retrieve_precedents(query, issue_id, k=k_precedents),
        'admin_rules': retrieve_admin_rules(query, issue_id, k=k_admin_rules),
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
