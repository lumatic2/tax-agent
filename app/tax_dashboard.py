"""T2 — 세무 통합 UI (Streamlit).

소득세 계산·절세 전략·법령 근거를 Track B LangGraph 에이전트(qwen3:32b)로
한 화면에 돌려주는 독립 대시보드. pywebview로 래핑해 데스크톱 창으로도 실행.

Usage:
    streamlit run infrastructure/tax_dashboard.py --server.port 8502
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ICON_PATH = ROOT / 'assets' / 'icon.ico'

from agent.llm import default_model
MODEL = default_model()

st.set_page_config(
    page_title='Tax Agent',
    page_icon=str(ICON_PATH) if ICON_PATH.exists() else '⚖️',
    layout='wide',
    initial_sidebar_state='collapsed',
)


# ── 지연 import (Streamlit 시작 시 LangGraph 로드 지연 방지) ────────────────

@st.cache_resource(show_spinner='LangGraph 에이전트 로드 중...')
def get_agent() -> Any:
    from agent.track_b_poc import build_graph
    return build_graph(model=MODEL)


@st.cache_resource(show_spinner='세법 코퍼스 준비 중...')
def warm_corpus() -> int:
    from agent.law_client import load_tax_corpus
    return len(load_tax_corpus())


# ── 프롬프트 템플릿 ──────────────────────────────────────────────────────────

def build_prompt(form: dict[str, Any]) -> str:
    gross_man = form['gross_man']
    lines = [f'제 총급여는 {gross_man}만원입니다 (비과세 제외).']

    if form['national_pension']:
        lines.append(f'국민연금 납부액: {form["national_pension"]:,}원')
    if form['health_insurance']:
        lines.append(f'건강보험 납부액: {form["health_insurance"]:,}원')
    if form['monthly_rent']:
        lines.append(f'월세 {form["monthly_rent"]:,}원 납부 중입니다.')
    if form['num_dependents']:
        lines.append(f'부양가족 {form["num_dependents"]}명.')
    if form['has_irp']:
        lines.append('IRP/연금저축은 이미 최대 납입했습니다.')
    if form['is_sme_worker']:
        lines.append('중소기업 취업자 감면 대상자입니다.')

    lines.append('')
    lines.append('1) 2024년 귀속 소득세는 얼마인가요? 반드시 calculate_income_tax 도구를 사용하세요.')
    lines.append('2) 활용 가능한 절세 전략을 get_tax_saving_strategies 도구로 조회해 주세요.')
    lines.append('3) 추천 전략의 법령 근거는 search_tax_law 도구로 확인해 주세요.')

    extra = form.get('free_question', '').strip()
    if extra:
        lines.append('')
        lines.append(f'추가 질문: {extra}')

    return '\n'.join(lines)


# ── 결과 파싱 ────────────────────────────────────────────────────────────────

def parse_result(result: dict[str, Any]) -> dict[str, Any]:
    """LangGraph result에서 UI 섹션별 데이터 추출."""
    messages = result.get('messages', [])

    tool_calls: list[dict[str, Any]] = []
    tool_results: dict[str, list[Any]] = {
        'calculate_income_tax': [],
        'get_tax_saving_strategies': [],
        'search_tax_law': [],
    }

    for msg in messages:
        calls = getattr(msg, 'tool_calls', None) or []
        for call in calls:
            tool_calls.append({'name': call['name'], 'args': call['args']})

        name = getattr(msg, 'name', None)
        content = getattr(msg, 'content', None)
        if name in tool_results and content is not None:
            try:
                payload = json.loads(content) if isinstance(content, str) else content
                tool_results[name].append(payload)
            except Exception:
                tool_results[name].append(content)

    final_content = ''
    for msg in reversed(messages):
        content = getattr(msg, 'content', None)
        if content and not getattr(msg, 'tool_calls', None) and not getattr(msg, 'name', None):
            final_content = content if isinstance(content, str) else str(content)
            break

    return {
        'final': final_content,
        'tool_calls': tool_calls,
        'calc': tool_results['calculate_income_tax'][-1] if tool_results['calculate_income_tax'] else None,
        'strategies': tool_results['get_tax_saving_strategies'][-1] if tool_results['get_tax_saving_strategies'] else None,
        'laws': tool_results['search_tax_law'][-1] if tool_results['search_tax_law'] else None,
    }


# ── 렌더러: 섹션별 ───────────────────────────────────────────────────────────

def _fmt_won(v: Any) -> str:
    """금액을 만원 단위로 컴팩트하게 표시. <만원이면 원 단위 유지."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return '-'
    if abs(v) >= 100_000_000:
        return f'{v / 100_000_000:.2f}억원'.replace('.00억원', '억원')
    if abs(v) >= 10_000:
        s = f'{v / 10_000:,.1f}만원'
        return s.replace('.0만원', '만원')
    return f'{int(v):,}원'


def _fmt_man(saving: Any) -> str:
    try:
        v = float(saving)
    except (TypeError, ValueError):
        return str(saving)
    return _fmt_won(v)


def render_calc_section(calc: Any) -> None:
    st.markdown('#### 계산 결과')
    if not isinstance(calc, dict):
        st.info('계산 결과가 아직 없습니다.')
        return
    row1 = st.columns(3)
    row1[0].metric('과세표준', _fmt_won(calc.get('taxable_income', 0)))
    row1[1].metric('산출세액', _fmt_won(calc.get('income_tax', 0)))
    row1[2].metric('지방소득세', _fmt_won(calc.get('local_tax', 0)))
    row2 = st.columns(2)
    row2[0].metric('총납부예상', _fmt_won(calc.get('total_tax', 0)))
    row2[1].metric('실효세율', f"{float(calc.get('effective_rate_pct', 0)):.2f}%")
    rate = calc.get('marginal_rate')
    if rate is not None:
        st.caption(f'적용 한계세율: {rate}')


def render_strategies_section(strategies: Any) -> None:
    st.markdown('#### 절세 전략')
    if not isinstance(strategies, list) or not strategies:
        st.info('추천 전략이 없습니다.')
        return
    for s in strategies:
        if not isinstance(s, dict):
            continue
        name = s.get('name', '-')
        saving = s.get('saving', 0)
        cond = s.get('condition', '')
        legal = s.get('legal_ref', '')
        with st.container(border=True):
            head_l, head_r = st.columns([3, 1])
            head_l.markdown(f'**{name}**')
            if isinstance(saving, (int, float)):
                head_r.markdown(f':orange[**+{_fmt_man(saving)}**]')
            else:
                head_r.markdown(f':orange[**{saving}**]')
            if cond:
                st.caption(f'조건: {cond}')
            if legal:
                st.caption(f'법령: `{legal}`')


def render_laws_section(laws: Any) -> None:
    st.markdown('#### 법령 근거')
    if not isinstance(laws, list) or not laws:
        st.info('관련 법령 조회 결과가 없습니다.')
        return
    for law in laws:
        if not isinstance(law, dict):
            continue
        head = f"{law.get('law_name', '-')} {law.get('article_no', '')}".strip()
        score = law.get('score')
        with st.container(border=True):
            if score is not None:
                st.markdown(f'**{head}**  :grey[(score {score})]')
            else:
                st.markdown(f'**{head}**')
            excerpt = law.get('excerpt') or law.get('text') or ''
            if excerpt:
                st.markdown(f'> {excerpt}')


def render_tool_trace(tool_calls: list[dict[str, Any]]) -> None:
    if not tool_calls:
        return
    with st.expander(f'도구 호출 내역 ({len(tool_calls)})'):
        for i, call in enumerate(tool_calls, 1):
            args_str = json.dumps(call.get('args', {}), ensure_ascii=False)
            st.code(f'{i}. {call["name"]}({args_str})', language='text')


# ── 헤더 & 상태 체크 ─────────────────────────────────────────────────────────

def _check_ollama() -> tuple[bool, str]:
    try:
        import httpx
        r = httpx.get('http://127.0.0.1:11434/api/tags', timeout=2.0)
        return r.status_code == 200, 'Ollama 연결됨'
    except Exception as e:
        return False, f'Ollama 연결 실패: {e}'


def _check_law_api() -> tuple[bool, str]:
    try:
        import httpx
        r = httpx.get('https://www.law.go.kr/DRF/lawSearch.do',
                      params={'OC': '8307', 'target': 'law',
                              'query': '소득세법', 'type': 'JSON', 'display': '1'},
                      timeout=3.0)
        return r.status_code == 200, 'law.go.kr 정상'
    except Exception as e:
        return False, f'law.go.kr 오류: {e}'


def render_header() -> None:
    st.title('소득세 계산 · 절세 분석')
    st.caption(f'로컬 AI 세무 에이전트 · {MODEL} · 귀속 2024')
    st.divider()


def render_footer() -> None:
    st.divider()
    ollama_ok, ollama_msg = _check_ollama()
    law_ok, law_msg = _check_law_api()
    dot_o = '🟢' if ollama_ok else '🔴'
    dot_l = '🟢' if law_ok else '🔴'
    st.caption(f'{dot_o} {ollama_msg}  ·  {dot_l} {law_msg}')


# ── 탭 구현 ──────────────────────────────────────────────────────────────────

def render_income_tax_tab(corpus_size: int) -> None:
    form_col, result_col = st.columns([2, 3], gap='large')

    with form_col:
        st.markdown('### 입력 정보')
        with st.form('income_tax_form', border=True):
            st.markdown('**기본 소득 정보**')
            gross_man = st.number_input(
                '총급여 (만원)', min_value=0, max_value=100000, value=5000, step=100,
            )
            national_pension = st.number_input(
                '국민연금 납부액 (원)', min_value=0, value=0, step=10000,
            )
            health_insurance = st.number_input(
                '건강보험 납부액 (원)', min_value=0, value=0, step=10000,
            )

            st.divider()
            st.markdown('**공제·상황**')
            monthly_rent = st.number_input(
                '월세 (원/월)', min_value=0, value=0, step=10000,
            )
            num_dependents = st.number_input(
                '부양가족 수', min_value=0, max_value=20, value=0, step=1,
            )
            has_irp = st.checkbox('IRP/연금저축 최대 납입 여부')
            is_sme_worker = st.checkbox('중소기업 취업자 감면 해당')

            st.divider()
            free_question = st.text_area(
                '추가 질문 (선택)',
                placeholder='예: 월세세액공제의 법령 근거는?',
                height=80,
            )

            submitted = st.form_submit_button(
                '분석 시작',
                type='primary',
                use_container_width=True,
            )

        if corpus_size:
            st.caption(f'세법 코퍼스: 조문 {corpus_size:,}개 로드됨')

    with result_col:
        st.markdown('### 분석 결과')
        if not submitted:
            st.info('왼쪽 폼을 작성하고 **분석 시작** 버튼을 눌러주세요.')
            st.caption('첫 실행은 LangGraph 초기화 + 세법 코퍼스 수집으로 1~2분 소요될 수 있습니다.')
            return

        form = {
            'gross_man': int(gross_man),
            'national_pension': int(national_pension),
            'health_insurance': int(health_insurance),
            'monthly_rent': int(monthly_rent),
            'num_dependents': int(num_dependents),
            'has_irp': bool(has_irp),
            'is_sme_worker': bool(is_sme_worker),
            'free_question': free_question or '',
        }
        prompt = build_prompt(form)

        with st.status('LangGraph 실행 중...', expanded=True) as status:
            try:
                st.write(f'• 에이전트 로드 ({MODEL})')
                agent = get_agent()
                from langchain_core.messages import HumanMessage

                st.write(f'• {MODEL} 호출 (도구 사용)')
                t0 = time.time()
                result = agent.invoke({'messages': [HumanMessage(content=prompt)]})
                dt = time.time() - t0
                st.write(f'• 완료 ({dt:.1f}s)')
                status.update(label=f'분석 완료 · {dt:.1f}s', state='complete')
            except Exception as e:
                status.update(label='실행 실패', state='error')
                st.error(f'LangGraph 실행 오류: {e}')
                with st.expander('상세 오류'):
                    st.code(traceback.format_exc())
                return

        parsed = parse_result(result)

        # 계산·전략 섹션은 LLM 툴콜에 의존하지 않고 결정론적 엔진 직접 호출
        # (qwen3:32b이 툴을 건너뛰고 자체 추론으로 답변하는 케이스 보정)
        import tax_calculator as tc
        from strategy_engine import run as run_strategy

        gross_salary = form['gross_man'] * 10_000
        extra = {}
        if form['national_pension']:
            extra['국민연금'] = form['national_pension']
        if form['health_insurance']:
            extra['건강보험'] = form['health_insurance']
        try:
            r = tc.calculate_wage_income_tax(gross_salary, extra)
            calc = {
                'gross_salary': r['총급여'],
                'employment_deduction': r['근로소득공제'],
                'taxable_income': r['과세표준'],
                'income_tax': r['산출세액'],
                'marginal_rate': r['적용세율'],
                'local_tax': r['지방소득세'],
                'total_tax': r['총납부예상'],
                'effective_rate_pct': round(r['총납부예상'] / max(gross_salary, 1) * 100, 2),
            }
        except Exception as e:
            calc = parsed['calc']
            st.warning(f'계산 엔진 실패 — LLM 결과로 폴백: {e}')

        profile = {
            'gross_salary': gross_salary,
            'monthly_rent': form['monthly_rent'],
            'dependents_count': form['num_dependents'],
            'is_homeless_household': form['monthly_rent'] > 0,
            'is_sme_employee': form['is_sme_worker'],
        }
        try:
            res = run_strategy(profile, {'적용세율': calc.get('marginal_rate', 0.15)})
            strategy_candidates = res.get('candidates', [])
            if form['has_irp']:
                strategy_candidates = [
                    c for c in strategy_candidates
                    if c['rule'].name not in ('IRP추가납입', '연금저축', 'IRP 추가납입')
                ]
        except Exception as e:
            strategy_candidates = []
            st.warning(f'전략 엔진 실패: {e}')

        render_calc_section(calc)
        st.markdown('#### 절세 전략')
        _render_strategy_result(strategy_candidates)
        render_laws_section(parsed['laws'])

        if parsed['final']:
            with st.expander('에이전트 최종 답변 (원문)', expanded=False):
                st.markdown(parsed['final'])

        render_tool_trace(parsed['tool_calls'])


def _render_strategy_result(candidates: list) -> None:
    if not candidates:
        st.info('해당 입력으로 매칭된 전략이 없습니다. 트리거 조건을 확인해 주세요.')
        return
    for item in candidates:
        rule = item['rule']
        saving = int(item.get('saving', 0))
        legal_parts = [
            f"{lb.get('law','')} {lb.get('article','')}".strip()
            for lb in (rule.legal_basis or [])
        ]
        legal = ' / '.join(p for p in legal_parts if p)
        with st.container(border=True):
            head_l, head_r = st.columns([3, 1])
            head_l.markdown(f'**{rule.name}**  :grey[({rule.priority})]')
            if saving > 0:
                head_r.markdown(f':orange[**+{_fmt_man(saving)}**]')
            if rule.diagnosis:
                st.caption(f'조건: {rule.diagnosis}')
            detail = (rule.recommendation or {}).get('detail')
            if detail:
                st.caption(f'실행: {detail}')
            if legal:
                st.caption(f'법령: `{legal}`')
            risk = item.get('risk') or {}
            if risk.get('level') and risk['level'] != 'low':
                st.warning(f"⚠ 리스크 {risk.get('level')}: {risk.get('note','')}")


def render_corporate_tax_tab() -> None:
    from strategy_engine import run as run_strategy
    form_col, result_col = st.columns([2, 3], gap='large')

    with form_col:
        st.markdown('### 법인 프로필 입력')
        with st.form('corp_form', border=True):
            taxable = st.number_input('과세표준 (원)', 0, value=500_000_000, step=10_000_000)
            is_sme = st.checkbox('중소기업 해당', value=True)
            st.divider()
            st.markdown('**손금불산입 주요 항목**')
            entertain_paid = st.number_input('접대비 사용액 (원)', 0, value=0, step=1_000_000)
            entertain_limit = st.number_input('접대비 한도 (원)', 0, value=0, step=1_000_000)
            exec_bonus = st.number_input('임원상여금 지급액 (원)', 0, value=0, step=1_000_000)
            exec_bonus_resolved = st.number_input('주총 결의 한도 (원)', 0, value=0, step=1_000_000)
            donation_paid = st.number_input('기부금 지급액 (원)', 0, value=0, step=1_000_000)
            donation_limit = st.number_input('기부금 한도 (원)', 0, value=0, step=1_000_000)
            st.divider()
            loss_cf = st.number_input('이월결손금 (원)', 0, value=0, step=1_000_000)
            submitted = st.form_submit_button('전략 조회', type='primary', use_container_width=True)

    with result_col:
        st.markdown('### 법인세 절세 전략')
        if not submitted:
            st.info('왼쪽 폼을 작성하고 **전략 조회**를 눌러주세요. (LLM 없음 — 규칙 엔진 직접 호출)')
            return
        profile = {
            'is_corporation': True,
            'is_sme_corporation': bool(is_sme),
            'corp_taxable_income': int(taxable),
            'entertainment_paid': int(entertain_paid),
            'entertainment_limit': int(entertain_limit),
            'executive_bonus_paid': int(exec_bonus),
            'executive_bonus_resolution_amount': int(exec_bonus_resolved),
            'donation_paid': int(donation_paid),
            'donation_limit': int(donation_limit),
            'loss_carryforward_available': int(loss_cf),
        }
        try:
            res = run_strategy(profile)
            _render_strategy_result(res.get('candidates', []))
        except Exception as e:
            st.error(f'전략 엔진 오류: {e}')
            with st.expander('상세'):
                st.code(traceback.format_exc())


def render_inheritance_tax_tab() -> None:
    from strategy_engine import run as run_strategy
    form_col, result_col = st.columns([2, 3], gap='large')

    with form_col:
        st.markdown('### 상속 사안 입력')
        with st.form('inh_form', border=True):
            total = st.number_input('상속재산 총액 (원)', 0, value=2_000_000_000, step=50_000_000)
            spouse = st.checkbox('배우자 생존', value=True)
            spouse_amt = st.number_input('배우자 실제 상속액 (원)', 0, value=800_000_000, step=50_000_000)
            spouse_share = st.number_input('배우자 법정 상속분 (원)', 0, value=1_000_000_000, step=50_000_000)
            payable = st.number_input('예상 상속세액 (원)', 0, value=200_000_000, step=10_000_000)
            submitted = st.form_submit_button('전략 조회', type='primary', use_container_width=True)

    with result_col:
        st.markdown('### 상속세 절세 전략')
        if not submitted:
            st.info('왼쪽 폼을 작성하고 **전략 조회**를 눌러주세요.')
            return
        profile = {
            'is_inheritance_case': True,
            'inheritance_total': int(total),
            'spouse_exists': bool(spouse),
            'spouse_inherit_amount': int(spouse_amt),
            'spouse_legal_share': int(spouse_share),
            'inheritance_tax_payable': int(payable),
        }
        try:
            res = run_strategy(profile)
            _render_strategy_result(res.get('candidates', []))
        except Exception as e:
            st.error(f'전략 엔진 오류: {e}')
            with st.expander('상세'):
                st.code(traceback.format_exc())


def render_gift_tax_tab() -> None:
    from strategy_engine import run as run_strategy
    form_col, result_col = st.columns([2, 3], gap='large')

    with form_col:
        st.markdown('### 증여 계획 입력')
        with st.form('gift_form', border=True):
            planned = st.number_input('증여 예정액 (원)', 0, value=100_000_000, step=10_000_000)
            prior_10yr = st.number_input('10년 이내 기증여액 (원)', 0, value=0, step=10_000_000)
            exemption = st.number_input('증여 공제 한도 (원)', 0, value=50_000_000, step=10_000_000)
            st.divider()
            st.markdown('**저가 양수 사안 (선택)**')
            fair = st.number_input('시가 (원)', 0, value=0, step=10_000_000)
            expected = st.number_input('양수 예정가 (원)', 0, value=0, step=10_000_000)
            submitted = st.form_submit_button('전략 조회', type='primary', use_container_width=True)

    with result_col:
        st.markdown('### 증여세 절세 전략')
        if not submitted:
            st.info('왼쪽 폼을 작성하고 **전략 조회**를 눌러주세요.')
            return
        profile = {
            'is_gift_case': True,
            'gift_planned_amount': int(planned),
            'gift_prior_10yr_amount': int(prior_10yr),
            'gift_exemption_limit': int(exemption),
            'low_value_asset_fair_price': int(fair),
            'low_value_asset_expected_price': int(expected),
        }
        try:
            res = run_strategy(profile)
            _render_strategy_result(res.get('candidates', []))
        except Exception as e:
            st.error(f'전략 엔진 오류: {e}')
            with st.expander('상세'):
                st.code(traceback.format_exc())


def render_law_search_tab(corpus_size: int) -> None:
    st.markdown('### 세법 조문 검색')
    st.caption(
        '법제처 Open API 수집 코퍼스(소득세법·조세특례제한법)를 in-process 키워드 검색. '
        'LLM을 거치지 않고 즉시 조문을 찾고 싶을 때 사용.'
    )

    query = st.text_input(
        '검색어',
        placeholder='예: 월세세액공제 · 근로소득공제 · IRP 연금저축',
        key='law_search_query',
    )
    limit = st.slider('결과 개수', min_value=3, max_value=15, value=5, step=1)

    if not query.strip():
        if corpus_size:
            st.caption(f'코퍼스: 조문 {corpus_size:,}개 준비됨. 검색어를 입력하세요.')
        return

    from agent.law_client import search_tax_articles
    try:
        hits = search_tax_articles(query.strip(), limit=limit)
    except Exception as e:
        st.error(f'검색 실패: {e}')
        return

    if not hits:
        st.warning('매칭 조문 없음. 다른 키워드로 검색해 보세요.')
        return

    st.caption(f'{len(hits)}건 검색됨')
    for hit in hits:
        head = f"{hit['law_name']} {hit['article_no']}"
        with st.container(border=True):
            st.markdown(f'**{head}**  :grey[(score {hit["score"]})]')
            st.markdown(f'> {hit["excerpt"]}')


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main() -> None:
    render_header()

    try:
        corpus_size = warm_corpus()
    except Exception as e:
        st.warning(f'세법 코퍼스 로드 실패 — 법령 조회가 제한될 수 있습니다: {e}')
        corpus_size = 0

    tab_income, tab_corp, tab_inh, tab_gift, tab_law = st.tabs([
        '소득세',
        '법인세',
        '상속세',
        '증여세',
        '법령 검색',
    ])

    with tab_income:
        render_income_tax_tab(corpus_size)
    with tab_corp:
        render_corporate_tax_tab()
    with tab_inh:
        render_inheritance_tax_tab()
    with tab_gift:
        render_gift_tax_tab()
    with tab_law:
        render_law_search_tab(corpus_size)

    render_footer()


if __name__ == '__main__':
    main()
else:
    main()
