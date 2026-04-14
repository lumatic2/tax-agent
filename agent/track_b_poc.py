"""
Track B — Tax Agent 로컬화 PoC v2
LangGraph + Ollama tool calling + tax-agent 실제 연동
"""
import json
import sys

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from langchain_core.tools import tool
from agent.llm import default_model, get_llm
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from typing import TypedDict, Annotated
import operator

MODEL = default_model()

try:
    import tax_calculator as tc
    import strategy_engine as se
    TAX_AVAILABLE = True
except ImportError as e:
    print(f'tax-agent 모듈 없음 ({e}) — 더미 툴로 대체')
    TAX_AVAILABLE = False

try:
    from agent.law_client import search_tax_articles
    LAW_CLIENT_AVAILABLE = True
except ImportError as e:
    print(f'law_client 로드 실패 ({e}) — 법령 조회 비활성')
    LAW_CLIENT_AVAILABLE = False


# ── Tool 1: 근로소득세 계산 ───────────────────────────────────────────────────
@tool
def calculate_income_tax(gross_salary: int, national_pension: int = 0,
                          health_insurance: int = 0) -> dict:
    """근로소득세를 계산합니다 (소득세법 제47조, 제50조, 제55조).

    Args:
        gross_salary: 총급여 (원) — 비과세 제외한 연봉
        national_pension: 납부한 국민연금 보험료 (원, 기본값 0)
        health_insurance: 납부한 건강보험료 (원, 기본값 0)

    Returns:
        총급여, 근로소득공제, 과세표준, 산출세액, 지방소득세, 총납부예상, 실효세율
    """
    if TAX_AVAILABLE:
        extra = {}
        if national_pension:
            extra['국민연금'] = national_pension
        if health_insurance:
            extra['건강보험'] = health_insurance
        r = tc.calculate_wage_income_tax(gross_salary, extra)
        return {
            'gross_salary':        r['총급여'],
            'employment_deduction': r['근로소득공제'],
            'taxable_income':      r['과세표준'],
            'income_tax':          r['산출세액'],
            'marginal_rate':       r['적용세율'],
            'local_tax':           r['지방소득세'],
            'total_tax':           r['총납부예상'],
            'effective_rate_pct':  round(r['총납부예상'] / max(gross_salary, 1) * 100, 2),
        }
    else:
        taxable = max(0, gross_salary - int(gross_salary * 0.3))
        rate = 0.15 if taxable < 50_000_000 else 0.24
        income_tax = int(taxable * rate)
        local_tax = int(income_tax * 0.1)
        return {
            'gross_salary': gross_salary,
            'taxable_income': taxable,
            'income_tax': income_tax,
            'marginal_rate': rate,
            'local_tax': local_tax,
            'total_tax': income_tax + local_tax,
            'effective_rate_pct': round((income_tax + local_tax) / max(gross_salary, 1) * 100, 2),
        }


# ── Tool 2: 절세 전략 조회 ────────────────────────────────────────────────────
@tool
def get_tax_saving_strategies(gross_salary: int, monthly_rent: int = 0,
                               has_irp: bool = False, is_sme_worker: bool = False,
                               num_dependents: int = 0) -> list:
    """활용 가능한 절세 전략을 우선순위 순으로 조회합니다.

    Args:
        gross_salary: 총급여 (원)
        monthly_rent: 월세 납부액 (원, 0이면 월세 없음)
        has_irp: IRP/연금저축 이미 최대 납입 여부 (True면 추가 납입 불가)
        is_sme_worker: 중소기업 취업자 감면 해당 여부
        num_dependents: 부양가족 수 (소득요건 충족 기준)

    Returns:
        절세 전략 리스트 (항목명, 예상절세액, 조건, 법령조항)
    """
    if TAX_AVAILABLE:
        user_data = {
            'income': {'근로소득': gross_salary},
            'monthly_rent': monthly_rent,
            'dependents_total': num_dependents,
            'flags': {
                '월세지출': monthly_rent > 0,
                '중소기업취업': is_sme_worker,
                '부양가족수': num_dependents,
            },
        }
        # tax_result에 한계세율 포함 — strategy_engine이 활용
        tax_result = {'적용세율': 0.165 if gross_salary <= 55_000_000 else 0.132}
        strategies = se.generate_strategy(user_data, tax_result)

        # IRP 이미 최대 납입 시 제외
        if has_irp:
            strategies = [s for s in strategies
                          if s['항목'] not in ('IRP추가납입', '연금저축')]

        return [
            {
                'name':    s['항목'],
                'saving':  s['예상절세액'],
                'condition': s['조건'],
                'legal_ref': s['법령조항'],
            }
            for s in strategies
        ]
    else:
        # 더미
        out = []
        rate = 0.165 if gross_salary <= 55_000_000 else 0.132
        if not has_irp:
            out.append({'name': 'IRP추가납입', 'saving': int(9_000_000 * rate),
                        'condition': '연 900만원 한도', 'legal_ref': '조세특례제한법'})
        if monthly_rent:
            out.append({'name': '월세세액공제', 'saving': int(monthly_rent * 12 * 0.17),
                        'condition': '무주택 세대주', 'legal_ref': '조세특례제한법 제95조의2'})
        return out


# ── Tool 3: 세법 검색 ─────────────────────────────────────────────────────────
@tool
def search_tax_law(query: str) -> list:
    """법제처 Open API 기반으로 세법 조문을 검색합니다.

    소득세법·조세특례제한법·부가가치세법·법인세법·지방세법 allowlist 내에서
    쿼리와 매칭되는 상위 조문을 반환합니다.

    Args:
        query: 검색어 (예: "월세 세액공제", "IRP 연금저축 세액공제")

    Returns:
        관련 조문 목록 (law_name, article_no, excerpt, score)
    """
    if LAW_CLIENT_AVAILABLE:
        try:
            hits = search_tax_articles(query, limit=3)
            if hits:
                return hits
            return [{'law_name': '-', 'article_no': '-', 'excerpt': '매칭 조문 없음', 'score': 0}]
        except Exception as e:
            return [{'law_name': '-', 'article_no': '-', 'excerpt': f'법령 조회 실패: {e}', 'score': 0}]
    return [{'law_name': '소득세법', 'excerpt': 'law_client 미연동 — 더미 결과', 'score': 0}]


# ── Tool 4/5/6: 법인세 · 상속세 · 증여세 전략 (strategy_engine 직접) ──────────
def _format_candidates(candidates: list) -> list:
    out = []
    for c in candidates:
        rule = c['rule']
        legal_parts = [
            f"{lb.get('law','')} {lb.get('article','')}".strip()
            for lb in (rule.legal_basis or [])
        ]
        out.append({
            'name': rule.name,
            'priority': rule.priority,
            'saving': int(c.get('saving', 0)),
            'condition': rule.diagnosis or '',
            'legal_ref': ' / '.join(p for p in legal_parts if p),
            'risk': (c.get('risk') or {}).get('level', 'low'),
        })
    return out


@tool
def get_corporate_tax_strategies(
    corp_taxable_income: int,
    is_sme: bool = True,
    entertainment_paid: int = 0,
    entertainment_limit: int = 0,
    executive_bonus_paid: int = 0,
    executive_bonus_resolution_amount: int = 0,
    donation_paid: int = 0,
    donation_limit: int = 0,
    loss_carryforward_available: int = 0,
) -> list:
    """법인세 절세·리스크 전략을 조회합니다 (strategy_engine 직접 호출).

    Args:
        corp_taxable_income: 과세표준 (원)
        is_sme: 중소기업 해당 여부
        entertainment_paid/limit: 접대비 사용액/한도 (원)
        executive_bonus_paid/resolution_amount: 임원상여금 지급액/결의 한도 (원)
        donation_paid/limit: 기부금 지급액/한도 (원)
        loss_carryforward_available: 이월결손금 (원)

    Returns: 전략 목록 (name, priority, saving, condition, legal_ref, risk)
    """
    if not TAX_AVAILABLE:
        return []
    profile = {
        'is_corporation': True,
        'is_sme_corporation': is_sme,
        'corp_taxable_income': corp_taxable_income,
        'entertainment_paid': entertainment_paid,
        'entertainment_limit': entertainment_limit,
        'executive_bonus_paid': executive_bonus_paid,
        'executive_bonus_resolution_amount': executive_bonus_resolution_amount,
        'donation_paid': donation_paid,
        'donation_limit': donation_limit,
        'loss_carryforward_available': loss_carryforward_available,
    }
    return _format_candidates(se.run(profile).get('candidates', []))


@tool
def get_inheritance_strategies(
    inheritance_total: int,
    spouse_exists: bool = False,
    spouse_inherit_amount: int = 0,
    spouse_legal_share: int = 0,
    inheritance_tax_payable: int = 0,
) -> list:
    """상속세 절세 전략을 조회합니다.

    Args:
        inheritance_total: 상속재산 총액 (원)
        spouse_exists: 배우자 생존 여부
        spouse_inherit_amount: 배우자 실제 상속액 (원)
        spouse_legal_share: 배우자 법정 상속분 (원)
        inheritance_tax_payable: 예상 상속세액 (원)
    """
    if not TAX_AVAILABLE:
        return []
    profile = {
        'is_inheritance_case': True,
        'inheritance_total': inheritance_total,
        'spouse_exists': spouse_exists,
        'spouse_inherit_amount': spouse_inherit_amount,
        'spouse_legal_share': spouse_legal_share,
        'inheritance_tax_payable': inheritance_tax_payable,
    }
    return _format_candidates(se.run(profile).get('candidates', []))


@tool
def get_gift_strategies(
    gift_planned_amount: int,
    gift_prior_10yr_amount: int = 0,
    gift_exemption_limit: int = 0,
    low_value_asset_fair_price: int = 0,
    low_value_asset_expected_price: int = 0,
) -> list:
    """증여세 절세 전략을 조회합니다.

    Args:
        gift_planned_amount: 증여 예정액 (원)
        gift_prior_10yr_amount: 10년 이내 기증여액 (원)
        gift_exemption_limit: 증여 공제 한도 (원)
        low_value_asset_fair_price: 저가 양수 시가 (원, 해당시)
        low_value_asset_expected_price: 저가 양수 예정가 (원, 해당시)
    """
    if not TAX_AVAILABLE:
        return []
    profile = {
        'is_gift_case': True,
        'gift_planned_amount': gift_planned_amount,
        'gift_prior_10yr_amount': gift_prior_10yr_amount,
        'gift_exemption_limit': gift_exemption_limit,
        'low_value_asset_fair_price': low_value_asset_fair_price,
        'low_value_asset_expected_price': low_value_asset_expected_price,
    }
    return _format_candidates(se.run(profile).get('candidates', []))


# ── LangGraph 상태 정의 ──────────────────────────────────────────────────────
class TaxAgentState(TypedDict):
    messages: Annotated[list, operator.add]


tools = [
    calculate_income_tax,
    get_tax_saving_strategies,
    search_tax_law,
    get_corporate_tax_strategies,
    get_inheritance_strategies,
    get_gift_strategies,
]

SYSTEM_PROMPT = """당신은 대한민국 세무 전문가 AI입니다.
사용자의 세무 질문에 제공된 도구를 활용해 정확한 세액을 계산하고 절세 전략을 제안합니다.

원칙:
- 세액 계산은 반드시 calculate_income_tax 도구 사용. 직접 계산 금지.
- 절세 전략은 get_tax_saving_strategies 도구 사용.
- 법령 조문이 필요하면 search_tax_law 도구 사용.
- 모든 응답은 한국어로, 금액은 만원 단위로 표시.
- 귀속연도는 2024년 기준임을 명시."""


# ── 그래프 구성 (모델 런타임 지정) ────────────────────────────────────────────
def build_graph(model: str = MODEL):
    llm = get_llm(model, temperature=0, num_predict=2048)
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: TaxAgentState):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state['messages']
        return {'messages': [llm_with_tools.invoke(messages)]}

    graph = StateGraph(TaxAgentState)
    graph.add_node('agent', agent_node)
    graph.add_node('tools', ToolNode(tools))
    graph.set_entry_point('agent')
    graph.add_conditional_edges('agent', tools_condition)
    graph.add_edge('tools', 'agent')
    return graph.compile()


# ── 테스트 실행 ──────────────────────────────────────────────────────────────
def run_scenario(app, label: str, query: str):
    print(f'\n{"="*60}')
    print(f'[시나리오] {label}')
    print(f'[질문] {query.strip()}')
    print('[처리 중...]')

    result = app.invoke({'messages': [HumanMessage(content=query)]})
    final_message = result['messages'][-1].content
    print(f'\n[답변]\n{final_message}')

    tool_calls = [m for m in result['messages']
                  if hasattr(m, 'tool_calls') and m.tool_calls]
    print(f'\n[도구 호출 내역]')
    for msg in tool_calls:
        for tc_item in msg.tool_calls:
            print(f'  - {tc_item["name"]}({json.dumps(tc_item["args"], ensure_ascii=False)})')

    return result


def run_test():
    print(f'Track B PoC v2 — LangGraph + {MODEL}')
    app = build_graph()

    # 시나리오 1: 연봉 5천만원 직장인, 세액 + 절세 전략
    run_scenario(
        app,
        label='직장인 연봉 5000만원 — 세액 계산 + 절세 전략',
        query="""제 연봉은 5000만원입니다 (비과세 없음).
1) 2024년 귀속 소득세는 얼마인가요?
2) 절세 방법이 있나요? IRP 없고, 월세 60만원 납부 중입니다.""",
    )

    # 시나리오 2: 월세세액공제 법령 근거 확인
    run_scenario(
        app,
        label='월세세액공제 법령 조문 확인',
        query='월세세액공제의 법령 근거(조문)를 검색해서 알려주세요.',
    )


if __name__ == '__main__':
    run_test()
