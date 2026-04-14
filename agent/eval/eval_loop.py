"""
Track B — 평가 루프: Claude vs 로컬 모델 일치율 측정

로컬 qwen3:32b를 tax-agent 시나리오 7개로 실행하고
Domain Verifier로 정확도를 측정한다.

Usage (tax-agent 루트에서 실행):
    python -m agent.eval.eval_loop
    python -m agent.eval.eval_loop --model qwen3:14b
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from agent.llm import get_llm
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from typing import TypedDict, Annotated
import operator

import tax_calculator as tc
import strategy_engine as se
from agent.eval.tax_verifier import TaxVerifier

# ── 평가 시나리오 정의 ─────────────────────────────────────────────────────────
# 각 시나리오: (label, query, verify_params)
SCENARIOS = [
    {
        'id': 'S1',
        'label': '근로자 연봉 3천만원',
        'query': '총급여 3000만원인 직장인의 2024년 귀속 소득세(산출세액, 지방소득세, 총납부예상, 실효세율)를 계산해주세요.',
        'gross_salary': 30_000_000,
    },
    {
        'id': 'S2',
        'label': '근로자 연봉 5천만원',
        'query': '총급여 5000만원인 직장인의 2024년 귀속 소득세(산출세액, 지방소득세, 총납부예상, 실효세율)를 계산해주세요.',
        'gross_salary': 50_000_000,
    },
    {
        'id': 'S3',
        'label': '근로자 연봉 8천만원',
        'query': '총급여 8000만원인 직장인의 2024년 귀속 소득세(산출세액, 지방소득세, 총납부예상, 실효세율)를 계산해주세요.',
        'gross_salary': 80_000_000,
    },
    {
        'id': 'S4',
        'label': '근로자 연봉 1억원',
        'query': '총급여 1억원인 직장인의 2024년 귀속 소득세(산출세액, 지방소득세, 총납부예상, 실효세율)를 계산해주세요.',
        'gross_salary': 100_000_000,
    },
    {
        'id': 'S5',
        'label': '연봉 5천만원 + 국민연금',
        'query': '총급여 5000만원, 국민연금 225만원 납부한 직장인의 2024년 귀속 소득세를 계산해주세요.',
        'gross_salary': 50_000_000,
        'national_pension': 2_250_000,
    },
    {
        'id': 'S6',
        'label': '최저 구간 (연봉 1400만원)',
        'query': '총급여 1400만원인 직장인의 2024년 귀속 소득세(산출세액, 지방소득세, 총납부예상, 실효세율)를 계산해주세요.',
        'gross_salary': 14_000_000,
    },
    {
        'id': 'S7',
        'label': '최고 구간 (연봉 2억원)',
        'query': '총급여 2억원인 직장인의 2024년 귀속 소득세(산출세액, 지방소득세, 총납부예상, 실효세율)를 계산해주세요.',
        'gross_salary': 200_000_000,
    },
]


# ── LangGraph Agent 구성 ──────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list, operator.add]


def build_agent(model: str):
    llm = get_llm(model, temperature=0, num_predict=1024)

    @tool
    def calculate_income_tax(gross_salary: int, national_pension: int = 0,
                              health_insurance: int = 0) -> dict:
        """근로소득세를 계산합니다 (소득세법 제47조, 제50조, 제55조).
        Args:
            gross_salary: 총급여 (원)
            national_pension: 국민연금 보험료 (원)
            health_insurance: 건강보험료 (원)
        """
        extra = {}
        if national_pension:
            extra['국민연금'] = national_pension
        if health_insurance:
            extra['건강보험'] = health_insurance
        r = tc.calculate_wage_income_tax(gross_salary, extra)
        return {
            'gross_salary':         r['총급여'],
            'employment_deduction': r['근로소득공제'],
            'taxable_income':       r['과세표준'],
            'income_tax':           r['산출세액'],
            'marginal_rate':        r['적용세율'],
            'local_tax':            r['지방소득세'],
            'total_tax':            r['총납부예상'],
            'effective_rate_pct':   round(r['총납부예상'] / max(r['총급여'], 1) * 100, 2),
        }

    tools_list = [calculate_income_tax]
    llm_with_tools = llm.bind_tools(tools_list)

    system = """당신은 대한민국 세무 전문가 AI입니다. 귀속연도: 2024년.

【필수 규칙】
1. 세액 계산은 반드시 calculate_income_tax 도구를 사용하세요. 직접 계산 절대 금지.
2. 도구 파라미터 규칙:
   - gross_salary: 사용자가 명시한 총급여만 입력 (원 단위 정수, 예: "1400만원" → 14000000)
   - 한국어 금액 변환 규칙: N만원 = N × 10,000 (예: 1400만 = 14,000,000 / 800만 = 8,000,000)
   - national_pension / health_insurance: 사용자가 명시한 경우에만 입력, 미명시 시 반드시 0
   - 사용자가 언급하지 않은 값을 추정하거나 임의로 입력 금지
3. 도구가 반환한 숫자를 그대로 사용하세요. 수정·재계산 절대 금지.
4. 답변에 반드시 아래 항목을 "항목명: 숫자원" 형식으로 명시하세요 (쉼표 구분, 원 단위):
   - 총급여: X,XXX,XXX원
   - 근로소득공제: X,XXX,XXX원
   - 과세표준: X,XXX,XXX원
   - 산출세액: X,XXX,XXX원
   - 지방소득세: X,XXX,XXX원
   - 총납부예상: X,XXX,XXX원
   - 실효세율: X.XX%"""

    def agent_node(state: AgentState):
        msgs = [SystemMessage(content=system)] + state['messages']
        return {'messages': [llm_with_tools.invoke(msgs)]}

    graph = StateGraph(AgentState)
    graph.add_node('agent', agent_node)
    graph.add_node('tools', ToolNode(tools_list))
    graph.set_entry_point('agent')
    graph.add_conditional_edges('agent', tools_condition)
    graph.add_edge('tools', 'agent')
    return graph.compile()


# ── 평가 실행 ─────────────────────────────────────────────────────────────────

@dataclass
class ScenarioResult:
    id: str
    label: str
    passed: bool
    violations: list[str]
    tool_called: bool
    answer_preview: str


def run_eval(model: str) -> list[ScenarioResult]:
    print(f'\n{"="*60}')
    print(f'평가 모델: {model}')
    print(f'시나리오 수: {len(SCENARIOS)}')
    print('='*60)

    agent = build_agent(model)
    verifier = TaxVerifier()
    results = []

    for sc in SCENARIOS:
        print(f'\n[{sc["id"]}] {sc["label"]}')
        try:
            state = agent.invoke({'messages': [HumanMessage(content=sc['query'])]})
            answer = state['messages'][-1].content

            # tool 호출 여부
            tool_called = any(
                hasattr(m, 'tool_calls') and m.tool_calls
                for m in state['messages']
            )

            # 검증
            v_result = verifier.verify(
                answer,
                gross_salary=sc['gross_salary'],
                national_pension=sc.get('national_pension', 0),
                health_insurance=sc.get('health_insurance', 0),
            )

            status = '✅ PASS' if v_result.passed else '❌ FAIL'
            tool_status = '🔧 tool_called' if tool_called else '⚠️  no_tool'
            print(f'  {status} | {tool_status}')
            for viol in v_result.violations:
                print(f'    - {viol}')

            results.append(ScenarioResult(
                id=sc['id'],
                label=sc['label'],
                passed=v_result.passed,
                violations=[str(v) for v in v_result.violations],
                tool_called=tool_called,
                answer_preview=answer[:200],
            ))
        except Exception as e:
            print(f'  ❌ ERROR: {e}')
            results.append(ScenarioResult(
                id=sc['id'], label=sc['label'],
                passed=False, violations=[str(e)],
                tool_called=False, answer_preview='',
            ))

    return results


def print_summary(model: str, results: list[ScenarioResult]):
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    tool_used = sum(1 for r in results if r.tool_called)
    pass_rate = passed / total * 100 if total else 0

    print(f'\n{"="*60}')
    print(f'📊 평가 요약 — {model}')
    print(f'{"="*60}')
    print(f'  PASS: {passed}/{total} ({pass_rate:.0f}%)')
    print(f'  Tool 호출: {tool_used}/{total}')
    print()
    for r in results:
        status = '✅' if r.passed else '❌'
        tool   = '🔧' if r.tool_called else '⚠️ '
        print(f'  {status} {tool} [{r.id}] {r.label}')
        for v in r.violations:
            print(f'       ↳ {v}')




def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='qwen3:32b', help='Ollama 모델 이름')
    parser.add_argument('--tag', default='v2', help='결과 파일 태그 (예: v1_baseline, v2_prompt)')
    args = parser.parse_args()

    results = run_eval(args.model)
    print_summary(args.model, results)

    # 태그를 파일명에 포함
    out_dir = Path(__file__).parent / 'reports'
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_model = args.model.replace(':', '_').replace('/', '_')
    out_path = out_dir / f'eval_{safe_model}_{args.tag}.json'
    data = {
        'model': args.model, 'tag': args.tag,
        'total': len(results),
        'passed': sum(1 for r in results if r.passed),
        'results': [asdict(r) for r in results],
    }
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n  결과 저장: {out_path}')


if __name__ == '__main__':
    main()
