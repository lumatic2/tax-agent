"""Phase 6-B — 판례·행정규칙 로컬 코퍼스 빌더.

입력:
  reasoning_engine/issues/income_tax_gray.yaml   (각 이슈의 search_queries)
  data/eval/judgment_goldset_v1.yaml             (각 케이스의 authoritative_sources)

출력:
  data/precedent_corpus.json    판례 메타데이터 (사건명·사건번호·선고일자·precedent_id)
  data/admin_rule_corpus.json   행정규칙 전문 (조문내용 포함)

왜 판례는 메타데이터만 저장하는가:
  law.go.kr DRF의 판례 detail endpoint(`lawService.do?target=prec`)는 검색으로
  얻은 precedent_id에 대해 "일치하는 판례 없음"을 자주 반환한다(법제처 본체와
  국세법령정보시스템 DB 분리). 따라서 본문 대신 사건명(판결 요지 요약) 기반으로
  RAG를 구성하는 것이 실무적. 필요 시 사건번호로 대법원 사이트를 별도 조회.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from agent.law_client import (
    get_admin_rule,
    search_admin_rules,
    search_precedents,
)

ROOT = Path(__file__).parents[1]
ISSUES_FILE = ROOT / 'reasoning_engine' / 'issues' / 'income_tax_gray.yaml'
GOLDSET_FILE = ROOT / 'data' / 'eval' / 'judgment_goldset_v1.yaml'
PRECEDENT_OUT = ROOT / 'data' / 'precedent_corpus.json'
ADMIN_RULE_OUT = ROOT / 'data' / 'admin_rule_corpus.json'


def _load_yaml(path: Path) -> list[dict[str, Any]]:
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def collect_precedents() -> dict[str, dict[str, Any]]:
    """이슈 카탈로그의 search_queries로 판례 수집 + goldset authoritative_sources
    에 명시된 판례도 메타데이터로 주입. precedent_id 기준 dedup.
    """
    by_id: dict[str, dict[str, Any]] = {}
    issues = _load_yaml(ISSUES_FILE)
    for issue in issues:
        for q in issue.get('search_queries') or []:
            try:
                hits = search_precedents(q, limit=10)
            except Exception as e:
                print(f'[skip] search_precedents({q!r}) failed: {e}')
                continue
            for h in hits:
                pid = h.get('precedent_id')
                if not pid:
                    continue
                entry = by_id.setdefault(pid, h)
                entry.setdefault('issue_ids', [])
                if issue['id'] not in entry['issue_ids']:
                    entry['issue_ids'].append(issue['id'])
                entry.setdefault('matched_queries', [])
                if q not in entry['matched_queries']:
                    entry['matched_queries'].append(q)

    # goldset에 명시된 authoritative_sources 중 판례는 강제 주입
    cases = _load_yaml(GOLDSET_FILE)
    for case in cases:
        for src in case.get('authoritative_sources') or []:
            if src.get('type') != 'precedent':
                continue
            pid = src.get('precedent_id')
            if not pid:
                continue
            entry = by_id.setdefault(pid, {
                'precedent_id': pid,
                '사건번호': src.get('사건번호'),
                '사건명': src.get('사건명'),
                '선고일자': src.get('선고일자'),
            })
            entry.setdefault('issue_ids', [])
            if case['issue_id'] not in entry['issue_ids']:
                entry['issue_ids'].append(case['issue_id'])
            entry['goldset_authoritative'] = True
    return by_id


def collect_admin_rules() -> dict[str, dict[str, Any]]:
    """이슈 search_queries로 행정규칙 검색 + goldset에서 지정된 rule_id는 전문 fetch."""
    by_id: dict[str, dict[str, Any]] = {}
    issues = _load_yaml(ISSUES_FILE)
    for issue in issues:
        for q in issue.get('search_queries') or []:
            try:
                hits = search_admin_rules(q, limit=5)
            except Exception as e:
                print(f'[skip] search_admin_rules({q!r}) failed: {e}')
                continue
            for h in hits:
                rid = h.get('rule_id')
                if not rid:
                    continue
                entry = by_id.setdefault(rid, h)
                entry.setdefault('issue_ids', [])
                if issue['id'] not in entry['issue_ids']:
                    entry['issue_ids'].append(issue['id'])

    cases = _load_yaml(GOLDSET_FILE)
    must_fetch_full: set[str] = set()
    for case in cases:
        for src in case.get('authoritative_sources') or []:
            if src.get('type') != 'admin_rule':
                continue
            rid = src.get('rule_id')
            if rid:
                must_fetch_full.add(rid)
                by_id.setdefault(rid, {'rule_id': rid})
                by_id[rid]['goldset_authoritative'] = True

    # 전문 fetch: goldset authoritative + 검색 상위 히트 5건
    top_hits = sorted(by_id.keys())[:5]
    for rid in must_fetch_full | set(top_hits):
        try:
            full = get_admin_rule(rid)
        except Exception as e:
            print(f'[skip] get_admin_rule({rid}) failed: {e}')
            continue
        by_id[rid].update(full)
    return by_id


def main() -> None:
    print(f'[build] reading {ISSUES_FILE.name} + {GOLDSET_FILE.name}')
    precedents = collect_precedents()
    admin_rules = collect_admin_rules()
    PRECEDENT_OUT.parent.mkdir(parents=True, exist_ok=True)
    PRECEDENT_OUT.write_text(
        json.dumps(list(precedents.values()), ensure_ascii=False, indent=0),
        encoding='utf-8',
    )
    ADMIN_RULE_OUT.write_text(
        json.dumps(list(admin_rules.values()), ensure_ascii=False, indent=0),
        encoding='utf-8',
    )
    print(f'[build] precedents: {len(precedents)} → {PRECEDENT_OUT}')
    print(f'[build] admin_rules: {len(admin_rules)} → {ADMIN_RULE_OUT}')


if __name__ == '__main__':
    import sys
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
