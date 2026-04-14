"""
세법 RAG 인덱스 빌드 스크립트

Usage:
    python -m agent.rag.build_index          # 인덱스 없으면 구축
    python -m agent.rag.build_index --force  # 강제 재구축
"""
import sys
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from agent.rag.corpus import collect_corpus
from agent.rag.indexer import build_index, BM25_PATH, QDRANT_PATH
from agent.rag.retriever import search

TEST_QUERIES = [
    '월세 세액공제',
    'IRP 연금저축 세액공제',
    '근로소득공제',
    '중소기업 취업자 감면',
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='강제 재구축')
    args = parser.parse_args()

    bm25_exists   = Path(BM25_PATH).exists()
    qdrant_exists = Path(QDRANT_PATH).exists()

    if bm25_exists and qdrant_exists and not args.force:
        print('인덱스가 이미 존재합니다. --force 옵션으로 재구축 가능.')
    else:
        print('=== 세법 코퍼스 수집 ===')
        chunks = collect_corpus()
        print(f'총 조문 수: {len(chunks)}개')

        if not chunks:
            print('조문 수집 실패. 종료.')
            sys.exit(1)

        print('\n=== 인덱스 구축 ===')
        build_index(chunks)
        print('인덱스 구축 완료.')

    print('\n=== 검색 테스트 ===')
    for query in TEST_QUERIES:
        print(f'\n[쿼리] {query}')
        results = search(query, top_k=3)
        for i, r in enumerate(results, 1):
            print(f'  {i}. {r["law_name"]} {r["article_no"]} (score={r["score"]})')
            print(f'     {r["text"][:100].replace(chr(10), " ")}...')


if __name__ == '__main__':
    main()
