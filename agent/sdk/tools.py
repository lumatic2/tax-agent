"""Phase 9-2: Claude Agent SDK용 세무 tool 모음.

기존 LangGraph POC(`agent/track_b_poc.py`)의 6개 tool을 Agent SDK @tool로 재포장하고,
법령 RAG 검색 tool을 1개 추가한다. 선택 파라미터는 '0/False/"" = 미지정'으로 약속.
"""

from __future__ import annotations

import tax_calculator as tc
from agent import law_client
from strategy_engine import orchestrator as se

try:
    from agent.rag import retriever as rag_retriever  # optional (index 필요)
    _RAG_AVAILABLE = True
except Exception:
    _RAG_AVAILABLE = False

from claude_agent_sdk import tool


def _text(payload) -> dict:
    import json

    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}]}


def _format_candidates(candidates: list) -> list[dict]:
    out = []
    for c in candidates:
        rule = c["rule"]
        legal = " / ".join(
            f"{lb.get('law', '')} {lb.get('article', '')}".strip()
            for lb in (rule.legal_basis or [])
        )
        out.append(
            {
                "name": rule.name,
                "priority": rule.priority,
                "saving": int(c.get("saving", 0)),
                "condition": rule.diagnosis or "",
                "legal_ref": legal,
                "risk": (c.get("risk") or {}).get("level", "low"),
            }
        )
    return out


# ── 1. 근로소득세 계산 ────────────────────────────────────────────────────────
@tool(
    "calculate_income_tax",
    "근로소득세를 계산한다 (소득세법 §47·§50·§55). "
    "gross_salary는 비과세 제외 총급여(원). national_pension/health_insurance는 납부액(원, 0=미지정). "
    "반환: 과세표준·산출세액·지방소득세·총납부예상·실효세율.",
    {"gross_salary": int, "national_pension": int, "health_insurance": int},
)
async def calculate_income_tax(args):
    extra = {}
    if args["national_pension"]:
        extra["국민연금"] = args["national_pension"]
    if args["health_insurance"]:
        extra["건강보험"] = args["health_insurance"]
    r = tc.calculate_wage_income_tax(args["gross_salary"], extra)
    return _text(
        {
            "gross_salary": r["총급여"],
            "employment_deduction": r["근로소득공제"],
            "taxable_income": r["과세표준"],
            "income_tax": r["산출세액"],
            "marginal_rate": r["적용세율"],
            "local_tax": r["지방소득세"],
            "total_tax": r["총납부예상"],
            "effective_rate_pct": round(
                r["총납부예상"] / max(args["gross_salary"], 1) * 100, 2
            ),
        }
    )


# ── 2. 소득세 절세 전략 ───────────────────────────────────────────────────────
@tool(
    "get_income_tax_strategies",
    "근로소득자 대상 절세 전략을 우선순위 순으로 반환한다. "
    "monthly_rent=월세(원, 0=없음). has_irp=True면 IRP/연금저축 제외. "
    "is_sme_worker=중소기업취업자 감면 해당 여부. num_dependents=소득요건 충족 부양가족 수.",
    {
        "gross_salary": int,
        "monthly_rent": int,
        "has_irp": bool,
        "is_sme_worker": bool,
        "num_dependents": int,
    },
)
async def get_income_tax_strategies(args):
    user_data = {
        "income": {"근로소득": args["gross_salary"]},
        "monthly_rent": args["monthly_rent"],
        "dependents_total": args["num_dependents"],
        "flags": {
            "월세지출": args["monthly_rent"] > 0,
            "중소기업취업": args["is_sme_worker"],
            "부양가족수": args["num_dependents"],
        },
    }
    tax_result = {"적용세율": 0.165 if args["gross_salary"] <= 55_000_000 else 0.132}
    try:
        import strategy_engine_legacy as legacy

        strategies = legacy.generate_strategy(user_data, tax_result)
    except Exception:
        strategies = []
    if args["has_irp"]:
        strategies = [s for s in strategies if s.get("항목") not in ("IRP추가납입", "연금저축")]
    return _text(
        [
            {
                "name": s.get("항목"),
                "saving": s.get("예상절세액"),
                "condition": s.get("조건"),
                "legal_ref": s.get("법령조항"),
            }
            for s in strategies
        ]
    )


# ── 3. 법령 조문 검색 (법제처) ────────────────────────────────────────────────
@tool(
    "search_tax_law",
    "법제처 Open API 기반 세법 조문 검색. 소득세법·조특법·부가세법·법인세법·지방세법. "
    "예: '월세 세액공제', 'IRP 연금저축'.",
    {"query": str},
)
async def search_tax_law(args):
    try:
        hits = law_client.search_tax_articles(args["query"], limit=3)
        if not hits:
            return _text([{"info": "매칭 조문 없음"}])
        return _text(hits)
    except Exception as e:
        return _text([{"error": f"법령 조회 실패: {e}"}])


# ── 4. 법인세 전략 ────────────────────────────────────────────────────────────
@tool(
    "get_corporate_tax_strategies",
    "법인세 절세·리스크 전략 조회. 각 금액 0=해당 항목 미지정.",
    {
        "corp_taxable_income": int,
        "is_sme": bool,
        "entertainment_paid": int,
        "entertainment_limit": int,
        "executive_bonus_paid": int,
        "executive_bonus_resolution_amount": int,
        "donation_paid": int,
        "donation_limit": int,
        "loss_carryforward_available": int,
    },
)
async def get_corporate_tax_strategies(args):
    profile = {
        "is_corporation": True,
        "is_sme_corporation": args["is_sme"],
        "corp_taxable_income": args["corp_taxable_income"],
        "entertainment_paid": args["entertainment_paid"],
        "entertainment_limit": args["entertainment_limit"],
        "executive_bonus_paid": args["executive_bonus_paid"],
        "executive_bonus_resolution_amount": args["executive_bonus_resolution_amount"],
        "donation_paid": args["donation_paid"],
        "donation_limit": args["donation_limit"],
        "loss_carryforward_available": args["loss_carryforward_available"],
    }
    return _text(_format_candidates(se.run(profile).get("candidates", [])))


# ── 5. 상속세 전략 ────────────────────────────────────────────────────────────
@tool(
    "get_inheritance_strategies",
    "상속세 절세 전략 조회.",
    {
        "inheritance_total": int,
        "spouse_exists": bool,
        "spouse_inherit_amount": int,
        "spouse_legal_share": int,
        "inheritance_tax_payable": int,
    },
)
async def get_inheritance_strategies(args):
    profile = {
        "is_inheritance_case": True,
        "inheritance_total": args["inheritance_total"],
        "spouse_exists": args["spouse_exists"],
        "spouse_inherit_amount": args["spouse_inherit_amount"],
        "spouse_legal_share": args["spouse_legal_share"],
        "inheritance_tax_payable": args["inheritance_tax_payable"],
    }
    return _text(_format_candidates(se.run(profile).get("candidates", [])))


# ── 6. 증여세 전략 ────────────────────────────────────────────────────────────
@tool(
    "get_gift_strategies",
    "증여세 절세 전략 조회. low_value_asset_* 는 저가양수 관련(해당 없으면 0).",
    {
        "gift_planned_amount": int,
        "gift_prior_10yr_amount": int,
        "gift_exemption_limit": int,
        "low_value_asset_fair_price": int,
        "low_value_asset_expected_price": int,
    },
)
async def get_gift_strategies(args):
    profile = {
        "is_gift_case": True,
        "gift_planned_amount": args["gift_planned_amount"],
        "gift_prior_10yr_amount": args["gift_prior_10yr_amount"],
        "gift_exemption_limit": args["gift_exemption_limit"],
        "low_value_asset_fair_price": args["low_value_asset_fair_price"],
        "low_value_asset_expected_price": args["low_value_asset_expected_price"],
    }
    return _text(_format_candidates(se.run(profile).get("candidates", [])))


# ── 7. 법령·판례 RAG 검색 (decisive_sources 포함) ─────────────────────────────
@tool(
    "retrieve_legal_sources",
    "로컬 RAG로 법령·판례·decisive_sources 핀을 검색한다. 회색지대 이슈 판단 근거 확보용.",
    {"query": str, "top_k": int},
)
async def retrieve_legal_sources(args):
    if not _RAG_AVAILABLE:
        return _text([{"error": "RAG 인덱스 미구축. agent/rag/build_index.py 실행 필요."}])
    try:
        top_k = args["top_k"] or 5
        hits = rag_retriever.search(args["query"], top_k=top_k)
        return _text(hits)
    except Exception as e:
        return _text([{"error": f"RAG 조회 실패: {e}"}])


ALL_TOOLS = [
    calculate_income_tax,
    get_income_tax_strategies,
    search_tax_law,
    get_corporate_tax_strategies,
    get_inheritance_strategies,
    get_gift_strategies,
    retrieve_legal_sources,
]

ALLOWED_TOOL_NAMES = [f"mcp__tax__{t.name}" for t in ALL_TOOLS]
