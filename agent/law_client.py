"""법제처 Open API 경량 클라이언트 — LangGraph 세무 에이전트용.

law-mcp(https://github.com/.../law-mcp)와 동일한 `law.go.kr/DRF` 엔드포인트를
직접 호출한다. 로컬 Qdrant/BM25 인덱스를 빌드하지 않아도 세법 조문을 검색·조회
할 수 있도록, 대상 세법(소득세법·조세특례제한법)의 조문 코퍼스를 첫 호출 시
수집해 JSON 파일로 캐시하고 in-process로 키워드 스코어링을 수행한다.

외부 인터페이스:
    search_law(query, limit)           — law-mcp search_law 호환 (법령 단위 검색)
    get_law_article(law_id, article_no) — law-mcp get_law_article 호환 (조문 조회)
    search_tax_articles(query, limit)  — 세법 allowlist 내 조문 키워드 검색 (LLM 툴용)
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from agent.rag.corpus import (
    TARGET_LAWS,
    _to_str,
    collect_corpus,
)

_ROOT = Path(__file__).parents[1]
_ENV = _ROOT / '.env'
if _ENV.exists():
    load_dotenv(_ENV)

OC = os.getenv('LAW_API_OC', '8307').strip()
BASE_URL = 'https://www.law.go.kr/DRF'

CACHE_FILE = _ROOT / 'data' / 'tax_law_corpus.json'
TAX_ALLOWLIST = ('소득세법', '조세특례제한법', '부가가치세법', '법인세법', '지방세법')

_CORPUS: list[dict[str, Any]] | None = None


# ── 코퍼스 로딩 (첫 호출 시 수집·디스크 캐시) ────────────────────────────────

def load_tax_corpus(force: bool = False) -> list[dict[str, Any]]:
    """대상 세법(TARGET_LAWS) 조문 전체를 로드. 캐시 우선."""
    global _CORPUS
    if _CORPUS is not None and not force:
        return _CORPUS
    if CACHE_FILE.exists() and not force:
        try:
            _CORPUS = json.loads(CACHE_FILE.read_text(encoding='utf-8'))
            return _CORPUS
        except Exception:
            pass
    _CORPUS = collect_corpus()
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps(_CORPUS, ensure_ascii=False, indent=0),
        encoding='utf-8',
    )
    return _CORPUS


# ── law-mcp 호환 API ─────────────────────────────────────────────────────────

def search_law(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """법령 검색(법령 단위). 법제처 `lawSearch.do` 호출."""
    params = {
        'OC': OC,
        'target': 'law',
        'query': query,
        'type': 'JSON',
        'display': str(limit),
    }
    r = httpx.get(f'{BASE_URL}/lawSearch.do', params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    body = data.get('LawSearch', data) or {}
    rows = body.get('law', [])
    if isinstance(rows, dict):
        rows = [rows]
    out: list[dict[str, Any]] = []
    for row in rows[:limit]:
        out.append({
            'law_id': _to_str(row.get('법령일련번호') or row.get('법령ID')),
            'law_name': _to_str(row.get('법령명한글') or row.get('법령명')),
            'effective_date': _to_str(row.get('시행일자')) or None,
            'law_mst': _to_str(row.get('법령일련번호')) or None,
        })
    return out


def get_law_article(law_id: str, article_no: str) -> dict[str, Any]:
    """특정 법령의 조문 본문 반환. 로컬 코퍼스에서 검색.

    law_id는 MST(법령일련번호) 또는 법령명 문자열 모두 허용.
    """
    corpus = load_tax_corpus()
    for c in corpus:
        matches_id = c['law_id'] == law_id or c['law_name'] == law_id
        if matches_id and c['article_no'] == article_no:
            return {
                'law_id': c['law_id'],
                'law_name': c['law_name'],
                'article_no': c['article_no'],
                'content': c['text'],
            }
    return {
        'law_id': law_id,
        'article_no': article_no,
        'content': '',
        'warnings': ['조문을 찾지 못함 — 코퍼스 재수집 또는 대상 법령 확인 필요'],
    }


# ── 세법 특화 조문 키워드 검색 (LLM 툴에서 사용) ─────────────────────────────

_TITLE_RE = re.compile(r'^(제\d+조(?:의\d+)?\([^)]*\))')


def _split_title_body(text: str) -> tuple[str, str]:
    """조문 텍스트에서 제목(제N조(제목))과 본문을 분리."""
    m = _TITLE_RE.match(text)
    if m:
        title = m.group(1)
        body = text[len(title):]
        return title, body
    nl = text.find('\n')
    if nl > 0:
        return text[:nl], text[nl:]
    return text[:80], text[80:]


# 세법 개념 어휘 — 한국어 복합명사 쿼리를 의미 단위로 분해하기 위한 사전.
# 이 어휘로 쪼개면 "월세세액공제" → ["월세", "세액공제"] 처럼 분리돼
# 각 개념이 독립적으로 매칭·스코어링된다.
_TAX_CONCEPTS: tuple[str, ...] = (
    # 세목/소득
    '근로소득', '종합소득', '사업소득', '양도소득', '퇴직소득', '연금소득',
    '이자소득', '배당소득', '기타소득',
    # 공제/세액계산
    '세액공제', '소득공제', '특별공제', '표준공제', '과세표준',
    '근로소득공제', '세액감면', '세액감면액',
    # 납부/신고
    '원천징수', '연말정산', '확정신고',
    # 상품/공제대상
    '연금계좌', '연금저축', 'IRP', '퇴직연금', '주택청약',
    '월세', '월세액', '주택임차', '기부금', '의료비', '교육비',
    '보험료', '국민연금', '건강보험', '고용보험',
    # 인적/기업
    '부양가족', '경로우대', '중소기업', '장기집합', '장기집합투자',
)


def _decompose(word: str) -> list[tuple[str, float]]:
    """단어를 세법 개념 어휘로 분할. (토큰, 가중치) 쌍 반환.

    - 원본 단어는 항상 포함 (weight 2.0)
    - 매칭된 개념은 풀 가중치(2.0)로 추가
    - 개념을 떼낸 나머지 조각이 2글자 이상이면 잔여 가중치(1.5)로 추가
    """
    out: dict[str, float] = {word: 2.0}
    for concept in _TAX_CONCEPTS:
        if concept == word or len(concept) > len(word):
            continue
        idx = word.find(concept)
        if idx < 0:
            continue
        out[concept] = max(out.get(concept, 0.0), 2.0)
        prefix = word[:idx]
        suffix = word[idx + len(concept):]
        if len(prefix) >= 2:
            out[prefix] = max(out.get(prefix, 0.0), 1.5)
        if len(suffix) >= 2:
            out[suffix] = max(out.get(suffix, 0.0), 1.5)
    return list(out.items())


def _tokenize(q: str) -> list[tuple[str, float]]:
    """쿼리를 (토큰, 가중치) 쌍으로 분해.

    1) 공백 분리 → 각 단어를 세법 개념 사전으로 의미 분할
    2) 긴 미매칭 단어는 2~3-gram subword 백업 (낮은 가중치)
    """
    words = re.findall(r'[가-힣A-Za-z0-9]+', q)
    out: dict[str, float] = {}
    for w in words:
        if len(w) < 2:
            continue
        for token, weight in _decompose(w):
            out[token] = max(out.get(token, 0.0), weight)
        if len(w) > 4:
            for n in (3, 2):
                for i in range(len(w) - n + 1):
                    sub = w[i:i + n]
                    if sub not in out:
                        out[sub] = 0.4 if n == 3 else 0.2
    return list(out.items())


def _score(article: dict[str, Any], weighted_tokens: list[tuple[str, float]]) -> float:
    """조문 제목에 매칭되면 큰 부스트. 본문 매칭은 TF 포화+길이 정규화."""
    text = article['text']
    first_line, body = _split_title_body(text)
    body_len = max(len(body), 1)
    name = article['law_name']
    art_no = article.get('article_no', '')

    TITLE_BOOST = 10.0
    BODY_NORM_K = 500.0  # 본문 길이 정규화 상수 (짧은 조문 부스트)

    hits = 0.0
    for token, weight in weighted_tokens:
        title_count = first_line.count(token)
        if title_count:
            hits += weight * title_count * TITLE_BOOST

        body_count = body.count(token)
        if body_count:
            tf = body_count ** 0.5
            norm = BODY_NORM_K / (BODY_NORM_K + body_len)
            hits += weight * tf * norm * 3.0

        if token in art_no:
            hits += 3 * weight
        if token in name:
            hits += 0.3 * weight
    return hits


def search_tax_articles(query: str, limit: int = 3) -> list[dict[str, Any]]:
    """세법 allowlist 조문 중 쿼리와 매칭되는 상위 N건."""
    corpus = load_tax_corpus()
    allowed = [c for c in corpus if c['law_name'] in TAX_ALLOWLIST]
    weighted = _tokenize(query)
    if not weighted:
        return []
    ranked = sorted(
        ((_score(c, weighted), c) for c in allowed),
        key=lambda x: x[0],
        reverse=True,
    )
    out: list[dict[str, Any]] = []
    for score, c in ranked:
        if score <= 0:
            break
        out.append({
            'law_name': c['law_name'],
            'article_no': c['article_no'],
            'excerpt': c['text'][:600],
            'score': round(float(score), 2),
        })
        if len(out) >= limit:
            break
    return out


# ── 판례·행정규칙 검색 (Phase 6 reasoning_engine 용) ─────────────────────────
#
# 주의: law.go.kr DRF가 반환하는 precedent_id는 국세법령정보시스템 판례 저장소를
# 가리키며, lawService.do?target=prec&ID=...로 직접 조회하면 404에 가까운
# "일치하는 판례 없음" 응답이 자주 반환된다(저장소 분리 이슈). 이 때문에 판례는
# 본문 대신 메타데이터(사건명·사건번호·선고일자)만 저장하고, 사건명이 판결
# 요지를 담고 있다는 성질을 이용해 RAG를 구성한다. 행정규칙(고시·훈령 등)은
# get_admin_rule이 정상 동작해 전문 저장 가능.

def search_precedents(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """판례 검색 (law.go.kr DRF lawSearch.do target=prec).

    반환: [{precedent_id, 사건번호, 사건명, 선고일자, 법원명, 사건종류명, 데이터출처명}]
    """
    params = {
        'OC': OC, 'target': 'prec', 'query': query,
        'type': 'JSON', 'display': str(limit),
    }
    r = httpx.get(f'{BASE_URL}/lawSearch.do', params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    body = data.get('PrecSearch', data) or {}
    rows = body.get('prec', [])
    if isinstance(rows, dict):
        rows = [rows]
    out: list[dict[str, Any]] = []
    for row in rows[:limit]:
        out.append({
            'precedent_id': _to_str(row.get('판례일련번호') or row.get('ID')),
            '사건번호': _to_str(row.get('사건번호')),
            '사건명': _to_str(row.get('사건명')),
            '선고일자': _to_str(row.get('선고일자')),
            '법원명': _to_str(row.get('법원명')) or None,
            '사건종류명': _to_str(row.get('사건종류명')) or None,
            '데이터출처명': _to_str(row.get('데이터출처명')) or None,
        })
    return out


def search_admin_rules(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """행정규칙 검색 (고시·훈령·예규 등) — lawSearch.do target=admrul."""
    params = {
        'OC': OC, 'target': 'admrul', 'query': query,
        'type': 'JSON', 'display': str(limit),
    }
    r = httpx.get(f'{BASE_URL}/lawSearch.do', params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    body = data.get('AdmRulSearch', data) or {}
    rows = body.get('admrul', [])
    if isinstance(rows, dict):
        rows = [rows]
    out: list[dict[str, Any]] = []
    for row in rows[:limit]:
        out.append({
            'rule_id': _to_str(row.get('행정규칙일련번호') or row.get('ID')),
            '행정규칙ID': _to_str(row.get('행정규칙ID')),
            '행정규칙명': _to_str(row.get('행정규칙명')),
            '행정규칙종류': _to_str(row.get('행정규칙종류')) or None,
            '소관부처명': _to_str(row.get('소관부처명')) or None,
            '발령일자': _to_str(row.get('발령일자')) or None,
            '시행일자': _to_str(row.get('시행일자')) or None,
            '현행연혁구분': _to_str(row.get('현행연혁구분')) or None,
        })
    return out


def get_precedent(precedent_id: str) -> dict[str, Any]:
    """판례 단건 조회 — lawService.do target=prec.

    반환 필드는 search_precedents와 호환되도록 매핑.
    """
    params = {'OC': OC, 'target': 'prec', 'ID': precedent_id, 'type': 'JSON'}
    r = httpx.get(f'{BASE_URL}/lawService.do', params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    body = data.get('PrecService', data) or {}
    return {
        'precedent_id': precedent_id,
        '사건번호': _to_str(body.get('사건번호')),
        '사건명': _to_str(body.get('사건명')),
        '선고일자': _to_str(body.get('선고일자')),
        '법원명': _to_str(body.get('법원명')) or None,
        '판시사항': _to_str(body.get('판시사항')) or None,
        '판결요지': _to_str(body.get('판결요지')) or None,
    }


def get_admin_rule(rule_id: str) -> dict[str, Any]:
    """행정규칙 본문 조회 — lawService.do target=admrul.

    DRF 응답 구조: AdmRulService { 행정규칙기본정보{...}, 조문내용: [...] }.
    """
    params = {'OC': OC, 'target': 'admrul', 'ID': rule_id, 'type': 'JSON'}
    r = httpx.get(f'{BASE_URL}/lawService.do', params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    body = data.get('AdmRulService', data) or {}
    base = body.get('행정규칙기본정보') or {}
    articles = body.get('조문내용') or []
    if isinstance(articles, str):
        articles = [articles]
    return {
        'rule_id': rule_id,
        '행정규칙명': _to_str(base.get('행정규칙명')),
        '행정규칙종류': _to_str(base.get('행정규칙종류')) or None,
        '소관부처명': _to_str(base.get('담당부서기관명') or base.get('소관부처명')) or None,
        '발령일자': _to_str(base.get('발령일자')) or None,
        '시행일자': _to_str(base.get('시행일자')) or None,
        '조문내용': [_to_str(a) for a in articles if a],
    }


if __name__ == '__main__':
    import sys as _sys
    if _sys.stdout.encoding.lower() != 'utf-8':
        _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print(f'[load] OC={OC}, cache={CACHE_FILE}')
    corpus = load_tax_corpus()
    print(f'[load] 조문 {len(corpus)}개')
    for q in ('월세세액공제', '근로소득공제', 'IRP 연금저축'):
        print(f'\n[query] {q}')
        for hit in search_tax_articles(q, 3):
            print(f"  {hit['law_name']} {hit['article_no']} (score {hit['score']})")
            print(f"    {hit['excerpt'][:120]}...")
