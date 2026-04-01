"""법제처 Open API 클라이언트

엔드포인트:
  lawSearch.do  - 법령 검색 / 국세청 법령해석례 검색
  lawService.do - 법령 본문 조회

OC값(인증키)은 환경변수 LAW_API_OC에서 읽음.
"""

import os

import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BASE_URL = "https://www.law.go.kr/DRF"


class LegalSearchError(Exception):
    pass


def _get_oc():
    oc = os.getenv("LAW_API_OC", "").strip()
    if not oc:
        raise LegalSearchError("환경변수 LAW_API_OC가 비어 있습니다. .env를 설정해 주세요.")
    return oc


def _request(endpoint, params):
    url = f"{BASE_URL}/{endpoint}"
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            ct = resp.headers.get("content-type", "")
            if "json" not in ct.lower():
                return {"raw": resp.text}
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise LegalSearchError(f"법제처 API 오류: {e.response.status_code} {e.response.text}") from e
    except httpx.RequestError as e:
        raise LegalSearchError(f"법제처 API 통신 오류: {e}") from e


def search_law(query, display=20, page=1, search=1):
    """법령명으로 검색. 법령 목록 dict 반환."""
    oc = _get_oc()
    params = {
        "OC": oc,
        "target": "law",
        "type": "JSON",
        "search": int(search),
        "query": query,
        "display": int(display),
        "page": int(page),
    }
    return _request("lawSearch.do", params)


def get_law_content(law_id):
    """MST(법령ID)로 법령 본문 조회."""
    oc = _get_oc()
    params = {
        "OC": oc,
        "target": "law",
        "type": "JSON",
        "MST": str(law_id),
    }
    return _request("lawService.do", params)


def search_nts_interpretation(query, display=20, page=1, search=1):
    """국세청 법령해석례(예규·해석) 검색."""
    oc = _get_oc()
    params = {
        "OC": oc,
        "target": "ntsCgmExpc",
        "type": "JSON",
        "search": int(search),
        "query": query,
        "display": int(display),
        "page": int(page),
    }
    return _request("lawSearch.do", params)
