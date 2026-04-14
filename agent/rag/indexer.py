"""
Qdrant(벡터) + BM25(키워드) 인덱스 구축
"""
import pickle
from pathlib import Path

from langchain_ollama import OllamaEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from rank_bm25 import BM25Okapi

EMBED_MODEL  = 'nomic-embed-text'
COLLECTION   = 'tax_law'
QDRANT_PATH  = str(Path(__file__).parent.parent.parent / 'data' / 'qdrant_tax')
BM25_PATH    = Path(__file__).parent.parent.parent / 'data' / 'bm25_tax.pkl'
VECTOR_DIM   = 768   # nomic-embed-text 출력 차원


def _bigrams(text: str) -> list[str]:
    """Character bigram 토크나이저.
    한국어 형태소 경계를 고려: '월세액에' → ['월세', '세액', '액에']
    '월세' 쿼리가 '월세액에' 토큰을 포함한 문서와 매칭 가능.
    """
    # 공백 제거 후 2-gram
    flat = ''.join(text.split())
    return [flat[i:i+2] for i in range(len(flat) - 1)] if len(flat) >= 2 else list(flat)


def build_index(chunks: list[dict]) -> None:
    """청크 리스트로 Qdrant 벡터 인덱스 + BM25 인덱스를 구축한다."""
    embedder = OllamaEmbeddings(model=EMBED_MODEL)

    # ── 1. 벡터 임베딩 ──────────────────────────────────────────────────────
    print('  임베딩 생성 중...')
    texts = [c['text'] for c in chunks]
    vectors = embedder.embed_documents(texts)
    print(f'  벡터 {len(vectors)}개 생성 완료 (dim={len(vectors[0])})')

    # ── 2. Qdrant 적재 ──────────────────────────────────────────────────────
    Path(QDRANT_PATH).mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=QDRANT_PATH)

    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION in existing:
        client.delete_collection(COLLECTION)

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
    )

    points = [
        PointStruct(
            id=i,
            vector=vectors[i],
            payload={k: v for k, v in chunks[i].items() if k != 'text'},
        )
        for i in range(len(chunks))
    ]
    client.upsert(collection_name=COLLECTION, points=points)
    print(f'  Qdrant 적재 완료: {len(points)}개')

    # ── 3. BM25 인덱스 (character bigram) ───────────────────────────────────
    tokenized = [_bigrams(t) for t in texts]
    bm25 = BM25Okapi(tokenized)

    BM25_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BM25_PATH, 'wb') as f:
        pickle.dump({'bm25': bm25, 'chunks': chunks}, f)
    print(f'  BM25 인덱스 저장: {BM25_PATH}')
