"""
세법 코퍼스 수집 — 법제처 API에서 조문 단위로 청킹
"""
import sys
import re
import json
from pathlib import Path
import httpx
from dotenv import load_dotenv
import os

TAX_AGENT_PATH = Path(__file__).parent.parent.parent.parent / 'tax-agent'
load_dotenv(TAX_AGENT_PATH / '.env')

OC = os.getenv('LAW_API_OC', '').strip()
BASE_URL = 'https://www.law.go.kr/DRF'

# 수집 대상 법령 (법령명, 법령ID)
TARGET_LAWS = [
    ('소득세법',       '276127'),   # MST=법령일련번호 (법령ID: 001565)
    ('조세특례제한법', '280409'),   # MST=법령일련번호 (법령ID: 001584)
]


def _fetch_law(mst: str) -> dict:
    resp = httpx.get(f'{BASE_URL}/lawService.do', params={
        'OC': OC, 'target': 'law', 'MST': mst, 'type': 'JSON'
    }, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _article_key_to_no(조문키: str) -> str:
    """'0095021' → '제95조의2', '0001000' → '제1조' 형태로 변환
    조문키 구조: 4자리(조번호) + 2자리(의N, 00=없음) + 1자리(순번)
    """
    try:
        main = int(조문키[:4])       # 앞 4자리: 조번호
        의num = int(조문키[4:6])     # 5~6번째: 의N 번호 (0=없음)
        result = f'제{main}조'
        if 의num > 0:
            result += f'의{의num}'
        return result
    except Exception:
        return 조문키


def _extract_article_no(article: dict) -> str:
    """조문내용에서 '제N조' 또는 '제N조의M' 패턴을 추출. 실패 시 조문키로 폴백."""
    content = _to_str(article.get('조문내용')).strip()
    m = re.match(r'^(제\d+조(?:의\d+)?)', content)
    if m:
        return m.group(1)
    return _article_key_to_no(article.get('조문키', ''))


def _to_str(val) -> str:
    """API 응답값을 안전하게 문자열로 변환 (리스트이면 join)"""
    if val is None:
        return ''
    if isinstance(val, list):
        return ' '.join(str(v) for v in val if v)
    return str(val)


def _build_article_text(article: dict) -> str:
    """조문 dict → 본문 텍스트 (항·호 포함)"""
    parts = []

    content = _to_str(article.get('조문내용')).strip()
    if content:
        parts.append(content)

    # 항 (①②③...) — 리스트 또는 단일 dict 모두 처리
    항목록 = article.get('항', [])
    if isinstance(항목록, dict):
        항목록 = [항목록]
    elif not isinstance(항목록, list):
        항목록 = []

    for 항 in 항목록:
        if not isinstance(항, dict):
            continue
        항내용 = _to_str(항.get('항내용')).strip()
        if 항내용:
            parts.append(항내용)

        # 호 (1. 2. ...) — 리스트 또는 단일 dict 모두 처리
        호목록 = 항.get('호', [])
        if isinstance(호목록, dict):
            호목록 = [호목록]
        elif not isinstance(호목록, list):
            호목록 = []

        for 호 in 호목록:
            if not isinstance(호, dict):
                continue
            호내용 = _to_str(호.get('호내용')).strip()
            if 호내용:
                parts.append('  ' + 호내용)

    return '\n'.join(parts)


def collect_corpus() -> list[dict]:
    """법령 조문을 수집해 청크 리스트로 반환"""
    chunks = []

    for law_name, mst in TARGET_LAWS:
        print(f'  [{law_name}] 수집 중...')
        try:
            data = _fetch_law(mst)
        except Exception as e:
            print(f'  [{law_name}] 오류: {e}')
            continue

        법령 = data.get('법령', {})
        기본 = 법령.get('기본정보', {})
        시행일자 = 기본.get('시행일자', '')
        조문단위 = 법령.get('조문', {}).get('조문단위', [])

        if not isinstance(조문단위, list):
            조문단위 = [조문단위]

        for article in 조문단위:
            조문키 = article.get('조문키', '')
            조문여부 = article.get('조문여부', '')

            # 장·절 제목(편장절관) 등 비조문 항목 제외
            if 조문여부 not in ('조문', '전문'):
                continue

            text = _build_article_text(article)
            if not text or len(text.strip()) < 10:
                continue

            # 제목이 "제X조 삭제" 이면 제외
            if re.search(r'삭\s*제', text):
                continue

            article_no = _extract_article_no(article)

            chunks.append({
                'doc_id':           f'{law_name}_{조문키}',
                'law_name':         law_name,
                'law_id':           mst,
                'article_no':       article_no,
                'enforcement_date': 시행일자,
                'text':             text.strip(),
            })

        print(f'  [{law_name}] 조문 {len([c for c in chunks if c["law_id"] == mst])}개')

    return chunks
