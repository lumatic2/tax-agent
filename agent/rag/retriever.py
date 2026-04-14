"""
Hybrid RAG 검색 — Qdrant(벡터) + BM25(키워드) + RRF 결합
"""
import pickle
from pathlib import Path

from langchain_ollama import OllamaEmbeddings
from qdrant_client import QdrantClient

from .indexer import EMBED_MODEL, COLLECTION, QDRANT_PATH, BM25_PATH, _bigrams

_embedder = None
_client   = None
_bm25_data = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = OllamaEmbeddings(model=EMBED_MODEL)
    return _embedder


def _get_client():
    global _client
    if _client is None:
        _client = QdrantClient(path=QDRANT_PATH)
    return _client


def _get_bm25():
    global _bm25_data
    if _bm25_data is None:
        with open(BM25_PATH, 'rb') as f:
            _bm25_data = pickle.load(f)
    return _bm25_data['bm25'], _bm25_data['chunks']


def _rrf(rankings: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion: 여러 랭킹 리스트 → (doc_idx, score) 통합"""
    scores: dict[int, float] = {}
    for ranked in rankings:
        for rank, idx in enumerate(ranked):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def search(query: str, top_k: int = 5) -> list[dict]:
    """
    Hybrid RAG 검색.

    Args:
        query:  자연어 쿼리 (예: "월세 세액공제 요건")
        top_k:  반환할 상위 결과 수

    Returns:
        [{'doc_id', 'law_name', 'article_no', 'text', 'score'}, ...]
    """
    fetch_k = top_k * 4   # RRF 후보 폭

    # ── 1. 벡터 검색 ─────────────────────────────────────────────────────────
    q_vec = _get_embedder().embed_query(query)
    hits = _get_client().query_points(
        collection_name=COLLECTION,
        query=q_vec,
        limit=fetch_k,
        with_payload=False,
    )
    vec_ranking = [h.id for h in hits.points]

    # ── 2. BM25 검색 ─────────────────────────────────────────────────────────
    bm25, chunks = _get_bm25()
    bm25_scores = bm25.get_scores(_bigrams(query))
    bm25_ranking = sorted(range(len(bm25_scores)),
                          key=lambda i: bm25_scores[i], reverse=True)[:fetch_k]

    # ── 3. RRF 결합 ──────────────────────────────────────────────────────────
    fused = _rrf([vec_ranking, bm25_ranking])

    # ── 4. 결과 조립 ─────────────────────────────────────────────────────────
    results = []
    for idx, score in fused[:top_k]:
        chunk = chunks[idx]
        results.append({
            'doc_id':     chunk['doc_id'],
            'law_name':   chunk['law_name'],
            'article_no': chunk['article_no'],
            'text':       chunk['text'],
            'score':      round(score, 4),
        })

    return results
