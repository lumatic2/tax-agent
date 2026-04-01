"""Tax Agent Phase 1 — CLI 진입점

사용법:
    python main.py
    uv run python main.py
"""

import json

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

import document_parser
import legal_search
import strategy_engine
import tax_calculator
import tax_store

console = Console()


def _parse_int(v, default=0):
    if v is None:
        return int(default)
    s = str(v).strip().replace(",", "")
    if s == "":
        return int(default)
    return int(s)


def _fmt(n):
    return f"{int(n):,}원"


def _ask_int(label, default="0"):
    return _parse_int(Prompt.ask(label, default=str(default)))


def _ask_yes_no(label, default=False):
    return bool(Confirm.ask(label, default=bool(default)))


def _ask_dependents():
    console.print("\n[bold]부양가족 목록 입력[/bold] (없으면 0명)")
    count = _ask_int("부양가족 수", default="0")
    if count <= 0:
        return []

    console.print("[dim]각 인원별로 relation/age/disabled/annual_income를 입력합니다.[/dim]")
    deps = []
    for i in range(1, count + 1):
        console.print(f"\n[bold]#{i}[/bold]")
        relation = Prompt.ask(
            "relation",
            choices=["배우자", "직계존속", "직계비속", "형제자매", "위탁아동"],
            default="직계비속",
        )
        age = _ask_int("age (만 나이)", default="0")
        disabled = _ask_yes_no("disabled (장애인인가요?)", default=False)
        annual_income = _ask_int("annual_income (연 소득금액, 원)", default="0")
        wage_only = False
        if relation != "본인" and annual_income > 1_000_000:
            wage_only = _ask_yes_no("연 소득이 '근로소득만'인가요? (예: 급여만)", default=False)

        deps.append(
            {
                "relation": relation,
                "age": age,
                "disabled": disabled,
                "annual_income": annual_income,
                "wage_only": wage_only,
            }
        )
    return deps


def _ask_common_flags():
    console.print("\n[bold]추가 공제/감면 체크(선택)[/bold]")
    return {
        "월세지출": _ask_yes_no("  월세 지출이 있나요?", default=False),
        "중소기업취업": _ask_yes_no("  중소기업 취업자 감면 대상인가요?", default=False),
        "교육비지출": _ask_yes_no("  취학 전 아동 교육비가 있나요?", default=False),
        "의료비지출": _ask_yes_no("  안경/렌즈 구입비가 있나요?", default=False),
        "중도퇴사": _ask_yes_no("  올해 중도 퇴사한 이력이 있나요?", default=False),
        "혼인": _ask_yes_no("  올해 혼인신고를 했나요?", default=False),
        "기부금이월": _ask_yes_no("  이월 기부금이 있나요?", default=False),
        "종교단체기부": _ask_yes_no("  종교단체 기부금이 있나요?", default=False),
    }


def _input_wage_inputs():
    console.print(Panel("근로소득자 입력 플로우", title="근로소득자"))
    gross_salary = _ask_int("총급여액 (원)", default="0")

    national_pension = _ask_int("국민연금 보험료 (원)", default="0")
    health_insurance = _ask_int("건강보험료 (원)", default="0")
    employment_insurance = _ask_int("고용보험료 (원)", default="0")

    medical_expense = _ask_int("의료비 지출액 (원)", default="0")
    education_expense = _ask_int("교육비 지출액 (원)", default="0")
    donation = _ask_int("기부금 (원)", default="0")

    housing_fund = _ask_int("주택자금공제액 (원)", default="0")

    credit_card = _ask_int("신용카드 사용액 (원)", default="0")
    debit_card = _ask_int("체크카드 사용액 (원)", default="0")
    traditional_market = _ask_int("전통시장 사용액 (원)", default="0")
    public_transit = _ask_int("대중교통 사용액 (원)", default="0")

    irp_pension = _ask_int("IRP/연금저축 납입액 (원)", default="0")

    dependents = _ask_dependents()
    prepaid_tax = _ask_int("기납부세액 (원천징수 합계, 원)", default="0")

    return {
        "gross_salary": gross_salary,
        "insurance": {
            "national_pension": national_pension,
            "health_insurance": health_insurance,
            "employment_insurance": employment_insurance,
        },
        "expenses": {
            "medical_expense": medical_expense,
            "education_expense": education_expense,
            "donation": donation,
        },
        "housing_fund": housing_fund,
        "card_usage": {
            "credit_card": credit_card,
            "debit_card": debit_card,
            "traditional_market": traditional_market,
            "public_transit": public_transit,
        },
        "irp_pension": irp_pension,
        "dependents": dependents,
        "prepaid_tax": prepaid_tax,
    }


def _input_business_inputs():
    console.print(Panel("사업소득자 입력 플로우", title="사업소득자"))

    industry_code = Prompt.ask("업종코드").strip()
    revenue = _ask_int("수입금액 (원)", default="0")
    prev_year_revenue = _ask_int("전년도 수입금액 (원) — 단순/기준경비율 판정용", default="0")

    method_label = Prompt.ask(
        "경비 방식",
        choices=["단순경비율", "기준경비율", "장부"],
        default="단순경비율",
    )
    if method_label == "단순경비율":
        method = "단순"
        major_expenses = {}
        actual_expenses = 0
    elif method_label == "기준경비율":
        method = "기준"
        console.print("\n[dim]기준경비율 선택 시 주요경비(매입비용/임차료/인건비)를 입력합니다.[/dim]")
        major_expenses = {
            "매입비용": _ask_int("  매입비용 (원)", default="0"),
            "임차료": _ask_int("  임차료 (원)", default="0"),
            "인건비": _ask_int("  인건비 (원)", default="0"),
        }
        actual_expenses = 0
    else:
        method = "실제"
        major_expenses = {}
        actual_expenses = _ask_int("필요경비 합계 (장부 기준, 원)", default="0")

    prepaid_tax = _ask_int("기납부세액 (중간예납 등, 원)", default="0")
    dependents = _ask_dependents()

    return {
        "industry_code": industry_code,
        "revenue": revenue,
        "prev_year_revenue": prev_year_revenue,
        "method": method,
        "method_label": method_label,
        "major_expenses": major_expenses,
        "actual_expenses": actual_expenses,
        "dependents": dependents,
        "prepaid_tax": prepaid_tax,
    }


def _input_composite_inputs():
    console.print(Panel("복합소득자 입력 플로우", title="복합소득자"))

    console.print("\n[bold]근로소득 입력[/bold]")
    wage = _input_wage_inputs()

    console.print("\n[bold]사업소득 입력[/bold]")
    biz = _input_business_inputs()

    console.print("\n[bold]금융소득 입력[/bold] (이자/배당)")
    interest = _ask_int("이자소득 (원)", default="0")
    dividend = _ask_int("배당소득 (원)", default="0")
    gross_up_eligible_dividend = _ask_int(
        "Gross-up 대상 배당금액 (원, 모르면 배당소득과 동일)",
        default=str(dividend),
    )

    console.print("\n[bold]기타소득 입력[/bold]")
    other_revenue = _ask_int("기타소득 수입금액 합계 (원)", default="0")
    other_items = []
    if other_revenue > 0:
        other_items = [{"종류": "기타", "수입금액": other_revenue}]

    return {
        "wage": wage,
        "business": biz,
        "financial": {
            "interest": interest,
            "dividend": dividend,
            "gross_up_eligible_dividend": gross_up_eligible_dividend,
        },
        "other_income_items": other_items,
    }


# ── 메뉴 1: 내 정보 입력 ─────────────────────────────────────────────────────

def input_user_info():
    console.print(Panel("소득 유형을 선택하고, 해당 유형에 맞는 항목을 단계별로 입력합니다.", title="1. 내 정보 입력"))

    name = Prompt.ask("이름(또는 별칭)", default="나")
    tax_year = int(Prompt.ask("귀속 연도", default="2024"))

    income_type = Prompt.ask(
        "소득 유형",
        choices=["근로소득자", "사업소득자", "복합소득자"],
        default="근로소득자",
    )

    if income_type == "근로소득자":
        inputs = {"type": "근로소득자", "wage": _input_wage_inputs()}
    elif income_type == "사업소득자":
        inputs = {"type": "사업소득자", "business": _input_business_inputs()}
    else:
        inputs = {"type": "복합소득자", "composite": _input_composite_inputs()}

    flags = _ask_common_flags()
    flags["inputs"] = inputs

    tax_store.save_user_profile(
        {
            "name": name,
            "tax_year": tax_year,
            "income_type": [income_type],
            "flags": flags,
        }
    )
    console.print(f"\n[green]저장 완료 — {name}님 ({tax_year}년 귀속, {income_type})[/green]")


# ── 메뉴 2: 자료 업로드 ─────────────────────────────────────────────────────

def upload_document():
    console.print(Panel("세무 자료를 업로드합니다.", title="2. 자료 업로드"))
    console.print("  1) PDF 파일 경로 입력")
    console.print("  2) 텍스트 직접 붙여넣기")
    choice = Prompt.ask("선택", choices=["1", "2"], default="1")

    if choice == "1":
        path = Prompt.ask("PDF 파일 경로").strip().strip('"')
        try:
            result = document_parser.parse_pdf(path)
        except Exception as e:
            console.print(f"[red]파싱 실패: {e}[/red]")
            return
    else:
        console.print("텍스트를 입력하세요. 입력 완료 후 빈 줄에서 Enter 두 번.")
        lines = []
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)
        result = document_parser.parse_text("\n".join(lines))

    console.print(f"\n[bold]문서 유형[/bold]: {result['doc_type']}")
    if result["amounts"]:
        table = Table(title="파싱된 금액 항목")
        table.add_column("항목")
        table.add_column("금액", justify="right")
        for k, v in result["amounts"].items():
            table.add_row(k, _fmt(v))
        console.print(table)
    else:
        console.print("[yellow]자동 파싱된 금액 항목이 없습니다. 직접 확인해 주세요.[/yellow]")

    total = sum(result["amounts"].values()) if result["amounts"] else 0
    tax_store.save_document({
        "doc_type": result["doc_type"],
        "raw_text": result["raw_text"][:2000],
        "parsed_data": result["amounts"],
        "amount": total,
    })
    console.print("[green]자료 저장 완료.[/green]")


# ── 메뉴 3: 세액 계산 ────────────────────────────────────────────────────────

def _build_person_list(dependents):
    persons = [{"relation": "본인", "age": 0, "disabled": False, "annual_income": 0, "wage_only": False}]
    for d in dependents or []:
        persons.append(
            {
                "relation": d.get("relation", ""),
                "age": int(d.get("age", 0) or 0),
                "disabled": bool(d.get("disabled", False)),
                "annual_income": int(d.get("annual_income", 0) or 0),
                "wage_only": bool(d.get("wage_only", False)),
            }
        )
    return persons


def _children_count_from_dependents(dependents):
    count = 0
    for d in dependents or []:
        relation = d.get("relation", "")
        age = int(d.get("age", 0) or 0)
        if relation in {"직계비속", "위탁아동"} and age >= 8:
            count += 1
    return count


def _render_kv_table(title, rows, highlight_key=None):
    table = Table(title=title)
    table.add_column("항목")
    table.add_column("금액", justify="right")
    table.add_column("비고")
    for k, v, note in rows:
        label = k
        value = _fmt(v) if isinstance(v, (int, float)) else str(v)
        if highlight_key and k == highlight_key:
            label = f"[bold]{label}[/bold]"
            value = f"[bold]{value}[/bold]"
        table.add_row(label, value, note or "")
    console.print(table)


def _render_breakdown_tables(result):
    if result.get("warnings"):
        console.print(Panel("\n".join(result["warnings"]), title="주의", style="yellow"))

    _render_kv_table("소득금액 계산 내역", result.get("income_rows", []))
    _render_kv_table("소득공제 내역 (항목별)", result.get("deduction_rows", []), highlight_key="소득공제_합계")
    _render_kv_table("세액공제 내역 (항목별)", result.get("credit_rows", []), highlight_key="세액공제_합계")

    final = result.get("final", {}) or {}
    decision_total = int(final.get("총결정세액", 0) or 0)
    prepaid = int(final.get("기납부세액", 0) or 0)
    diff = int(final.get("차감후", 0) or 0)
    diff_label = "환급액" if diff < 0 else "추납액"
    diff_style = "green" if diff < 0 else "red"

    summary = Table(title="최종")
    summary.add_column("항목")
    summary.add_column("금액", justify="right")
    summary.add_row("결정세액 (소득세+지방소득세)", f"[bold]{_fmt(decision_total)}[/bold]")
    summary.add_row("기납부세액", _fmt(prepaid))
    summary.add_row(f"[bold]{diff_label}[/bold]", f"[bold {diff_style}]{_fmt(abs(diff))}[/bold {diff_style}]")
    console.print(summary)


def _profile_to_strategy_user_data(profile):
    flags = profile.get("flags", {}) or {}
    inputs = flags.get("inputs") or {}
    income_type = ((profile.get("income_type") or [""])[0]) or ""
    income = {}

    try:
        if income_type == "근로소득자":
            wage = inputs.get("wage") or {}
            income["근로소득"] = int(wage.get("gross_salary", 0) or 0)
        elif income_type == "사업소득자":
            biz_inputs = inputs.get("business") or {}
            biz = tax_calculator.calculate_business_income(
                revenue=int(biz_inputs.get("revenue", 0) or 0),
                industry_code=str(biz_inputs.get("industry_code", "") or ""),
                method=str(biz_inputs.get("method", "단순") or "단순"),
                prev_year_revenue=int(biz_inputs.get("prev_year_revenue", 0) or 0),
                major_expenses=biz_inputs.get("major_expenses", {}) or {},
                actual_expenses=int(biz_inputs.get("actual_expenses", 0) or 0),
            )
            income["사업소득"] = int(biz.get("사업소득금액", 0) or 0)
        else:
            comp = inputs.get("composite") or {}
            wage = comp.get("wage") or {}
            biz_inputs = comp.get("business") or {}
            if wage:
                income["근로소득"] = int(wage.get("gross_salary", 0) or 0)
            biz = tax_calculator.calculate_business_income(
                revenue=int(biz_inputs.get("revenue", 0) or 0),
                industry_code=str(biz_inputs.get("industry_code", "") or ""),
                method=str(biz_inputs.get("method", "단순") or "단순"),
                prev_year_revenue=int(biz_inputs.get("prev_year_revenue", 0) or 0),
                major_expenses=biz_inputs.get("major_expenses", {}) or {},
                actual_expenses=int(biz_inputs.get("actual_expenses", 0) or 0),
            )
            income["사업소득"] = int(biz.get("사업소득금액", 0) or 0)
    except Exception:
        pass

    return {
        "income": income,
        "flags": flags,
    }


def _calculate_wage_pipeline(wage_inputs):
    c = _compute_wage_components(wage_inputs)
    gross_salary = c["gross_salary"]
    earned_income = c["earned_income"]
    dependents = c["dependents"]
    prepaid_tax = c["prepaid_tax"]
    irp_pension = c["irp_pension"]
    expenses = c["expenses"]

    taxable_base = max(earned_income - c["total_deductions"], 0)
    tax = tax_calculator.calculate_tax(taxable_base)
    income_tax = int(tax.get("산출세액", 0) or 0)

    earned_credit = tax_calculator.calculate_earned_income_tax_credit(income_tax, gross_salary)
    earned_credit_final = int(earned_credit.get("최종공제액", 0) or 0)

    medical_raw = int(expenses.get("medical_expense", 0) or 0)
    medical_base = max(medical_raw - int(gross_salary * 0.03), 0)
    credits = tax_calculator.calculate_tax_credits(
        {
            "gross_salary": gross_salary,
            "children_count": _children_count_from_dependents(dependents),
            "medical_expense": medical_base,
            "education_expense": int(expenses.get("education_expense", 0) or 0),
            "monthly_rent": 0,
            "irp_pension": irp_pension,
            "total_income": earned_income,
        }
    )
    other_credits_total = int(credits.get("세액공제_합계", 0) or 0)
    total_credits = earned_credit_final + other_credits_total

    decision_income_tax = max(income_tax - total_credits, 0)
    local_tax = tax_calculator.calculate_local_tax(decision_income_tax)
    decision_total = decision_income_tax + local_tax

    final_diff = decision_total - prepaid_tax

    income_rows = c["income_rows"]

    deduction_rows = [
        ("기본공제액", int(c["personal"].get("기본공제액", 0) or 0), f"인원 {c['personal'].get('기본공제_인원', 0)}명"),
    ]
    for k, v in (c["personal"].get("추가공제_내역", {}) or {}).items():
        deduction_rows.append((f"추가공제: {k}", int(v), ""))
    deduction_rows.extend(
        [
            ("보험료공제", int(c["special"].get("보험료공제", 0) or 0), ""),
            ("주택자금공제", int(c["special"].get("주택자금공제", 0) or 0), ""),
            ("기부금공제", int(c["special"].get("기부금공제", 0) or 0), c["special"].get("적용방식", "")),
            ("신용카드 등 공제", c["card_deduction"], f"총사용액 {_fmt(c['card'].get('총사용액', 0) or 0)}"),
            ("소득공제_합계", c["total_deductions"], ""),
        ]
    )

    credit_rows = [
        ("근로소득세액공제", earned_credit_final, f"한도 {_fmt(earned_credit.get('공제한도', 0) or 0)}"),
    ]
    for k, v in credits.items():
        if k == "세액공제_합계":
            continue
        credit_rows.append((k, int(v), ""))
    credit_rows.append(("세액공제_합계", other_credits_total + earned_credit_final, ""))

    return {
        "income_rows": income_rows,
        "deduction_rows": deduction_rows,
        "credit_rows": credit_rows,
        "warnings": c["personal"].get("warnings", []) or [],
        "final": {
            "과세표준": taxable_base,
            "산출세액": income_tax,
            "결정소득세": decision_income_tax,
            "지방소득세": local_tax,
            "총결정세액": decision_total,
            "기납부세액": prepaid_tax,
            "차감후": final_diff,
        },
        "meta": {
            "gross_income": earned_income,
            "total_deductions": c["total_deductions"],
            "taxable_income": taxable_base,
        },
    }


def _compute_wage_components(wage_inputs):
    gross_salary = int(wage_inputs.get("gross_salary", 0) or 0)
    insurance = wage_inputs.get("insurance", {}) or {}
    expenses = wage_inputs.get("expenses", {}) or {}
    housing_fund = int(wage_inputs.get("housing_fund", 0) or 0)
    card_usage = wage_inputs.get("card_usage", {}) or {}
    irp_pension = int(wage_inputs.get("irp_pension", 0) or 0)
    dependents = wage_inputs.get("dependents", []) or []
    prepaid_tax = int(wage_inputs.get("prepaid_tax", 0) or 0)

    emp_deduction = tax_calculator.calculate_employment_income_deduction(gross_salary)
    earned_income = max(gross_salary - emp_deduction, 0)

    personal = tax_calculator.calculate_personal_deductions(_build_person_list(dependents))
    special = tax_calculator.calculate_special_deductions(
        {
            "gross_salary": gross_salary,
            "national_pension": int(insurance.get("national_pension", 0) or 0),
            "health_insurance": int(insurance.get("health_insurance", 0) or 0),
            "employment_insurance": int(insurance.get("employment_insurance", 0) or 0),
            "housing_fund": housing_fund,
            "medical_expense": 0,
            "education_expense": 0,
            "donation": int(expenses.get("donation", 0) or 0),
        }
    )
    card = tax_calculator.calculate_card_deduction(gross_salary, card_usage)
    card_deduction = int(card.get("최종공제액", 0) or 0)

    total_deductions = int(personal.get("인적공제_합계", 0) or 0) + int(special.get("특별공제_합계", 0) or 0) + card_deduction

    income_rows = [
        ("총급여", gross_salary, ""),
        ("근로소득공제", emp_deduction, ""),
        ("근로소득금액", earned_income, ""),
    ]

    return {
        "gross_salary": gross_salary,
        "earned_income": earned_income,
        "personal": personal,
        "special": special,
        "card": card,
        "card_deduction": card_deduction,
        "total_deductions": total_deductions,
        "dependents": dependents,
        "prepaid_tax": prepaid_tax,
        "irp_pension": irp_pension,
        "expenses": expenses,
        "income_rows": income_rows,
    }


def _calculate_business_pipeline(biz_inputs):
    industry_code = str(biz_inputs.get("industry_code", "") or "")
    revenue = int(biz_inputs.get("revenue", 0) or 0)
    prev_year_revenue = int(biz_inputs.get("prev_year_revenue", 0) or 0)
    method = str(biz_inputs.get("method", "단순") or "단순")
    major_expenses = biz_inputs.get("major_expenses", {}) or {}
    actual_expenses = int(biz_inputs.get("actual_expenses", 0) or 0)
    dependents = biz_inputs.get("dependents", []) or []
    prepaid_tax = int(biz_inputs.get("prepaid_tax", 0) or 0)

    biz = tax_calculator.calculate_business_income(
        revenue=revenue,
        industry_code=industry_code,
        method=method,
        prev_year_revenue=prev_year_revenue,
        major_expenses=major_expenses,
        actual_expenses=actual_expenses,
    )
    biz_income = int(biz.get("사업소득금액", 0) or 0)

    personal = tax_calculator.calculate_personal_deductions(_build_person_list(dependents))
    total_deductions = int(personal.get("인적공제_합계", 0) or 0)
    taxable_base = max(biz_income - total_deductions, 0)

    tax = tax_calculator.calculate_tax(taxable_base)
    income_tax = int(tax.get("산출세액", 0) or 0)
    decision_income_tax = income_tax
    local_tax = tax_calculator.calculate_local_tax(decision_income_tax)
    decision_total = decision_income_tax + local_tax
    final_diff = decision_total - prepaid_tax

    income_rows = [
        ("수입금액", int(biz.get("수입금액", 0) or 0), f"업종 {biz.get('업종명', '')} ({biz.get('업종코드', '')})"),
        ("필요경비", int(biz.get("필요경비", 0) or 0), biz.get("적용방법", "")),
        ("사업소득금액", biz_income, f"소득률 {biz.get('소득률', 0.0):.1%}"),
    ]

    deduction_rows = [
        ("기본공제액", int(personal.get("기본공제액", 0) or 0), f"인원 {personal.get('기본공제_인원', 0)}명"),
    ]
    for k, v in (personal.get("추가공제_내역", {}) or {}).items():
        deduction_rows.append((f"추가공제: {k}", int(v), ""))
    deduction_rows.append(("소득공제_합계", total_deductions, ""))

    credit_rows = [("세액공제_합계", 0, "")]

    return {
        "income_rows": income_rows,
        "deduction_rows": deduction_rows,
        "credit_rows": credit_rows,
        "warnings": personal.get("warnings", []) or [],
        "final": {
            "과세표준": taxable_base,
            "산출세액": income_tax,
            "결정소득세": decision_income_tax,
            "지방소득세": local_tax,
            "총결정세액": decision_total,
            "기납부세액": prepaid_tax,
            "차감후": final_diff,
        },
        "meta": {
            "gross_income": biz_income,
            "total_deductions": total_deductions,
            "taxable_income": taxable_base,
        },
    }


def _calculate_composite_pipeline(composite_inputs):
    wage = (composite_inputs.get("wage") or {})
    biz_inputs = (composite_inputs.get("business") or {})
    financial = (composite_inputs.get("financial") or {})
    other_items = composite_inputs.get("other_income_items") or []

    wage_dependents = wage.get("dependents") or []
    biz_dependents = biz_inputs.get("dependents") or []
    dependents_for_personal = wage_dependents or biz_dependents
    wage_for_personal = dict(wage)
    wage_for_personal["dependents"] = dependents_for_personal

    wage_c = _compute_wage_components(wage_for_personal)
    wage_gross_salary = wage_c["gross_salary"]
    wage_earned_income = wage_c["earned_income"]

    biz = tax_calculator.calculate_business_income(
        revenue=int(biz_inputs.get("revenue", 0) or 0),
        industry_code=str(biz_inputs.get("industry_code", "") or ""),
        method=str(biz_inputs.get("method", "단순") or "단순"),
        prev_year_revenue=int(biz_inputs.get("prev_year_revenue", 0) or 0),
        major_expenses=biz_inputs.get("major_expenses", {}) or {},
        actual_expenses=int(biz_inputs.get("actual_expenses", 0) or 0),
    )
    biz_income = int(biz.get("사업소득금액", 0) or 0)

    fin = tax_calculator.calculate_financial_income(
        interest=int(financial.get("interest", 0) or 0),
        dividend=int(financial.get("dividend", 0) or 0),
        gross_up_eligible_dividend=int(financial.get("gross_up_eligible_dividend", 0) or 0),
    )
    fin_separate_tax = 0
    fin_separate_local = 0
    fin_comprehensive_income = int(fin.get("종합과세편입금액", 0) or 0)
    if fin.get("종합과세여부") is False:
        fin_separate_tax = int(fin.get("분리과세세액", 0) or 0)
        fin_separate_local = tax_calculator.calculate_local_tax(fin_separate_tax)

    other = tax_calculator.calculate_other_income(other_items)
    other_comp_income = int(other.get("종합과세편입금액", 0) or 0)
    other_sep_tax = 0
    other_sep_local = 0
    if other_items and other.get("과세방식") == "분리과세선택가능":
        use_separate = Confirm.ask("기타소득 300만원 이하: 분리과세(22%)를 선택할까요?", default=True)
        if use_separate:
            other_sep_tax = int(other.get("분리과세세액(22%)", 0) or 0)
            other_sep_local = tax_calculator.calculate_local_tax(other_sep_tax)
            other_comp_income = 0

    comp_income = wage_earned_income + biz_income + fin_comprehensive_income + other_comp_income

    if biz_dependents and wage_dependents:
        warn_dependents = "복합소득자: 인적공제는 1회만 적용됩니다. 부양가족은 '근로소득' 입력의 목록을 사용했습니다."
    else:
        warn_dependents = ""

    total_deductions = int(wage_c.get("total_deductions", 0) or 0)
    taxable_base = max(comp_income - total_deductions, 0)

    if fin.get("종합과세여부") is True:
        tax_cmp = tax_calculator.compare_financial_income_tax(
            other_comprehensive_income=wage_earned_income + biz_income + other_comp_income,
            financial_income=int(fin.get("금융소득합계", 0) or 0),
            total_deductions=total_deductions,
        )
        income_tax = int(tax_cmp.get("최종산출세액", 0) or 0)
        fin_tax_note = f"금융소득 종합과세 — {tax_cmp.get('적용방법', '')}"
    else:
        tax = tax_calculator.calculate_tax(taxable_base)
        income_tax = int(tax.get("산출세액", 0) or 0)
        fin_tax_note = fin.get("비고", "")

    earned_credit = tax_calculator.calculate_earned_income_tax_credit(income_tax, wage_gross_salary) if wage_gross_salary > 0 else {"최종공제액": 0, "공제한도": 0}
    earned_credit_final = int(earned_credit.get("최종공제액", 0) or 0)

    deps = (wage.get("dependents") or [])
    medical_raw = int((wage.get("expenses", {}) or {}).get("medical_expense", 0) or 0)
    medical_base = max(medical_raw - int(wage_gross_salary * 0.03), 0) if wage_gross_salary > 0 else 0
    credits = tax_calculator.calculate_tax_credits(
        {
            "gross_salary": wage_gross_salary,
            "children_count": _children_count_from_dependents(deps),
            "medical_expense": medical_base,
            "education_expense": int((wage.get("expenses", {}) or {}).get("education_expense", 0) or 0),
            "monthly_rent": 0,
            "irp_pension": int(wage.get("irp_pension", 0) or 0),
            "total_income": comp_income,
        }
    )
    other_credits_total = int(credits.get("세액공제_합계", 0) or 0)

    dividend_credit = 0
    dividend_credit_note = ""
    if fin.get("종합과세여부") is True:
        div_credit = tax_calculator.calculate_dividend_tax_credit(
            gross_up=int(fin.get("Gross_up금액", 0) or 0),
            dividend_income=int(fin.get("배당소득금액", 0) or 0),
            total_financial_income=int(fin.get("금융소득합계", 0) or 0),
        )
        dividend_credit = int(div_credit.get("배당세액공제액", 0) or 0)
        dividend_credit_note = div_credit.get("근거", "")

    total_credits = earned_credit_final + other_credits_total + dividend_credit

    decision_income_tax = max(income_tax - total_credits, 0)
    local_tax = tax_calculator.calculate_local_tax(decision_income_tax)
    decision_total_comp = decision_income_tax + local_tax

    sep_tax_total = (fin_separate_tax + fin_separate_local) + (other_sep_tax + other_sep_local)
    decision_total_all = decision_total_comp + sep_tax_total

    prepaid_user = int(wage.get("prepaid_tax", 0) or 0) + int(biz_inputs.get("prepaid_tax", 0) or 0)
    prepaid_all = prepaid_user + sep_tax_total
    final_diff = decision_total_all - prepaid_all

    income_rows = []
    income_rows.extend(
        [
            ("근로소득금액", wage_earned_income, ""),
            ("사업소득금액", biz_income, f"업종 {biz.get('업종명', '')} ({biz.get('업종코드', '')})"),
        ]
    )
    if other_items:
        income_rows.append(("기타소득 종합과세편입", other_comp_income, other.get("과세방식", "")))
    income_rows.append(("금융소득 종합과세편입", fin_comprehensive_income, fin_tax_note))
    income_rows.append(("종합과세 소득 합계", comp_income, ""))

    deduction_rows = [
        ("소득공제_합계", total_deductions, ""),
    ]

    credit_rows = []
    if wage_gross_salary > 0:
        credit_rows.append(("근로소득세액공제", earned_credit_final, f"한도 {_fmt(earned_credit.get('공제한도', 0) or 0)}"))
    if dividend_credit:
        credit_rows.append(("배당세액공제", dividend_credit, dividend_credit_note))
    for k, v in credits.items():
        if k == "세액공제_합계":
            continue
        credit_rows.append((k, int(v), ""))
    credit_rows.append(("세액공제_합계", total_credits, ""))

    warnings = []
    warnings.extend(wage_c["personal"].get("warnings", []) or [])
    if warn_dependents:
        warnings.append(warn_dependents)

    return {
        "income_rows": income_rows,
        "deduction_rows": deduction_rows,
        "credit_rows": credit_rows,
        "warnings": warnings,
        "final": {
            "과세표준": taxable_base,
            "산출세액": income_tax,
            "결정소득세": decision_income_tax,
            "지방소득세": local_tax,
            "분리과세(확정) 합계": sep_tax_total,
            "총결정세액": decision_total_all,
            "기납부세액": prepaid_all,
            "차감후": final_diff,
        },
        "meta": {
            "gross_income": comp_income,
            "total_deductions": total_deductions,
            "taxable_income": taxable_base,
        },
    }


def calculate_tax_flow():
    console.print(Panel("소득 유형별 입력값으로 세액을 계산하고, 기납부세액을 차감해 환급/추납을 출력합니다.", title="3. 세액 계산"))

    profile = tax_store.get_user_profile()
    if not profile:
        console.print("[yellow]먼저 '1. 내 정보 입력'을 완료해 주세요.[/yellow]")
        return

    flags = profile.get("flags", {}) or {}
    inputs = (flags.get("inputs") or {})
    income_type = ((profile.get("income_type") or [""])[0]) or ""

    if not inputs:
        console.print("[yellow]저장된 입력값이 없습니다. '1. 내 정보 입력'을 다시 실행해 주세요.[/yellow]")
        return

    if income_type == "근로소득자":
        result = _calculate_wage_pipeline((inputs.get("wage") or {}))
    elif income_type == "사업소득자":
        result = _calculate_business_pipeline((inputs.get("business") or {}))
    else:
        result = _calculate_composite_pipeline((inputs.get("composite") or {}))

    _render_breakdown_tables(result)

    meta = result.get("meta", {}) or {}
    tax_store.save_calculation(
        {
            "user_id": 1,
            "tax_year": profile.get("tax_year", 2024),
            "gross_income": int(meta.get("gross_income", 0) or 0),
            "total_deductions": int(meta.get("total_deductions", 0) or 0),
            "taxable_income": int(meta.get("taxable_income", 0) or 0),
            "result": result,
        }
    )


# ── 메뉴 4: 공제 체크 ────────────────────────────────────────────────────────

def deduction_check_flow():
    console.print(Panel("누락 가능한 공제 항목을 확인합니다.", title="4. 공제 체크"))

    profile = tax_store.get_user_profile()
    if not profile:
        console.print("[yellow]먼저 '1. 내 정보 입력'을 완료해 주세요.[/yellow]")
        return

    user_data = _profile_to_strategy_user_data(profile)
    missing = strategy_engine.check_missing_deductions(user_data)
    if not missing:
        console.print("[green]누락된 공제 항목이 없습니다.[/green]")
        return

    table = Table(title=f"누락 가능 공제 항목 {len(missing)}건")
    table.add_column("항목")
    table.add_column("예상절세액", justify="right")
    table.add_column("조건")
    table.add_column("법령 근거")
    for item in missing:
        table.add_row(
            item["name"],
            _fmt(item["expected_saving"]),
            item["condition"],
            item["legal_ref"],
        )
    console.print(table)


# ── 메뉴 5: 절세 전략 ────────────────────────────────────────────────────────

def strategy_flow():
    console.print(Panel("우선순위별 절세 전략을 제안합니다.", title="5. 절세 전략"))

    profile = tax_store.get_user_profile()
    if not profile:
        console.print("[yellow]먼저 '1. 내 정보 입력'을 완료해 주세요.[/yellow]")
        return

    latest = tax_store.get_latest_calculation()
    tax_result = (latest or {}).get("result", {}) or {}
    user_data = _profile_to_strategy_user_data(profile)
    strategies = strategy_engine.generate_strategy(user_data, tax_result)

    if not strategies:
        console.print("[green]추천할 절세 전략이 없습니다.[/green]")
        return

    table = Table(title="우선순위별 절세 전략")
    table.add_column("#", width=3)
    table.add_column("항목")
    table.add_column("예상절세액", justify="right")
    table.add_column("조건")
    table.add_column("법령 근거")
    for i, s in enumerate(strategies, 1):
        table.add_row(str(i), s["항목"], _fmt(s["예상절세액"]), s["조건"], s["법령조항"])
    console.print(table)

    if latest:
        sims = strategy_engine.simulate_savings(profile, tax_result)
        if sims:
            sim_table = Table(title="[시뮬레이션] 추가 적용 전/후 세액 비교")
            sim_table.add_column("#", width=3)
            sim_table.add_column("항목")
            sim_table.add_column("현재세액", justify="right")
            sim_table.add_column("적용후세액", justify="right")
            sim_table.add_column("절세액", justify="right")
            for i, s in enumerate(sims, 1):
                sim_table.add_row(
                    str(i),
                    s["항목"],
                    _fmt(s["현재세액"]),
                    _fmt(s["적용후세액"]),
                    _fmt(s["절세액"]),
                )
            console.print(sim_table)

    tax_store.save_strategies({"strategies": strategies})


# ── 메뉴 6: 법령 검색 ────────────────────────────────────────────────────────

def law_search_flow():
    console.print(Panel("법제처 Open API로 법령을 검색합니다.", title="6. 법령 검색"))
    query = Prompt.ask("검색어").strip()
    if not query:
        console.print("[red]검색어가 비어 있습니다.[/red]")
        return

    try:
        result = legal_search.search_law(query)
        console.print(Panel(json.dumps(result, ensure_ascii=False, indent=2), title="법령 검색 결과"))
    except legal_search.LegalSearchError as e:
        console.print(f"[red]{e}[/red]")
        return

    if Confirm.ask("국세청 법령해석례도 검색할까요?", default=True):
        try:
            nts = legal_search.search_nts_interpretation(query)
            console.print(Panel(json.dumps(nts, ensure_ascii=False, indent=2), title="국세청 법령해석례"))
        except legal_search.LegalSearchError as e:
            console.print(f"[red]{e}[/red]")

    if Confirm.ask("법령 본문을 조회할까요? (MST 번호 필요)", default=False):
        mst = Prompt.ask("MST 번호").strip()
        if mst:
            try:
                content = legal_search.get_law_content(mst)
                console.print(Panel(json.dumps(content, ensure_ascii=False, indent=2), title="법령 본문"))
            except legal_search.LegalSearchError as e:
                console.print(f"[red]{e}[/red]")


# ── 메인 루프 ────────────────────────────────────────────────────────────────

def main():
    load_dotenv()
    tax_store.init_db()

    console.print(Panel(
        "[bold cyan]Tax Agent Phase 1[/bold cyan]\n"
        "개인소득세 AI 세무 어시스턴트\n"
        "[dim]법제처 API 기반 · 2024년 귀속[/dim]",
        title="Tax Agent"
    ))

    MENU = {
        "1": ("내 정보 입력",   input_user_info),
        "2": ("자료 업로드 (PDF)", upload_document),
        "3": ("세액 계산",     calculate_tax_flow),
        "4": ("공제 체크",     deduction_check_flow),
        "5": ("절세 전략 보기", strategy_flow),
        "6": ("법령 검색",     law_search_flow),
        "7": ("종료",          None),
    }

    while True:
        console.print("\n" + "\n".join(f"  {k}) {v[0]}" for k, v in MENU.items()))
        choice = Prompt.ask("메뉴 선택", choices=list(MENU.keys()), default="7")

        if choice == "7":
            console.print("종료합니다.")
            break

        _, fn = MENU[choice]
        try:
            fn()
        except Exception as e:
            console.print(f"[red]오류: {e}[/red]")


if __name__ == "__main__":
    main()
