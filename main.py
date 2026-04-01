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


def _fmt(n):
    return f"{int(n):,}원"


# ── 메뉴 1: 내 정보 입력 ─────────────────────────────────────────────────────

def input_user_info():
    console.print(Panel("소득 유형과 기본 정보를 입력합니다.", title="1. 내 정보 입력"))

    name = Prompt.ask("이름(또는 별칭)", default="나")
    tax_year = int(Prompt.ask("귀속 연도", default="2024"))

    console.print("\n[bold]소득 유형[/bold] (해당하는 것 모두 입력, 쉼표 구분)")
    console.print("  예: 근로, 사업  /  근로  /  사업, 기타")
    income_types_raw = Prompt.ask("소득 유형", default="근로")
    income_types = [t.strip() for t in income_types_raw.split(",")]

    income = {}
    for itype in income_types:
        amt = Prompt.ask(f"  {itype}소득 금액 (원)", default="0")
        income[f"{itype}소득"] = int(amt.replace(",", ""))

    total_deductions = int(
        Prompt.ask("\n총 소득공제 금액 (연금보험료·인적공제 등 합산, 모르면 0)", default="0").replace(",", "")
    )

    console.print("\n[bold]추가 공제 항목 해당 여부[/bold] (y/n)")
    flags = {
        "월세지출":      Confirm.ask("  월세 지출이 있나요?",          default=False),
        "중소기업취업":  Confirm.ask("  중소기업 취업자 감면 대상인가요?", default=False),
        "부양가족수":    int(Prompt.ask("  부양가족 수 (없으면 0)",      default="0")),
        "교육비지출":    Confirm.ask("  취학 전 아동 교육비가 있나요?",  default=False),
        "의료비지출":    Confirm.ask("  안경/렌즈 구입비가 있나요?",     default=False),
        "중도퇴사":      Confirm.ask("  올해 중도 퇴사한 이력이 있나요?",default=False),
        "혼인":          Confirm.ask("  올해 혼인신고를 했나요?",        default=False),
        "기부금이월":    Confirm.ask("  이월 기부금이 있나요?",          default=False),
        "종교단체기부":  Confirm.ask("  종교단체 기부금이 있나요?",      default=False),
    }

    profile = {
        "name": name,
        "tax_year": tax_year,
        "income_type": income_types,
        "income": income,
        "total_deductions": total_deductions,
        "flags": flags,
    }
    tax_store.save_user_profile(profile)
    console.print(f"\n[green]저장 완료 — {name}님 ({tax_year}년 귀속)[/green]")


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

def calculate_tax_flow():
    console.print(Panel("종합소득세 예상 세액을 계산합니다.", title="3. 세액 계산"))

    profile = tax_store.get_user_profile()
    if profile:
        income = profile.get("flags", {})
        gross = sum(
            v for k, v in (profile.get("income") or {}).items()
            if isinstance(v, (int, float))
        )
        deductions = profile.get("total_deductions", 0)
        console.print(f"저장된 정보 — 총 소득: {_fmt(gross)}, 공제: {_fmt(deductions)}")
        use_saved = Confirm.ask("저장된 정보로 계산할까요?", default=True)
    else:
        use_saved = False

    if not use_saved:
        gross = int(Prompt.ask("총 소득 금액 (원)").replace(",", ""))
        deductions = int(Prompt.ask("총 소득공제 금액 (원)", default="0").replace(",", ""))

    taxable = max(gross - deductions, 0)
    result = tax_calculator.calculate_tax(taxable)
    local = tax_calculator.calculate_local_tax(result["산출세액"])

    table = Table(title="세액 계산 결과")
    table.add_column("항목")
    table.add_column("금액", justify="right")
    table.add_row("총 소득",       _fmt(gross))
    table.add_row("총 소득공제",   _fmt(deductions))
    table.add_row("과세표준",      _fmt(taxable))
    table.add_row("적용 세율",     f"{result['적용세율']*100:.0f}%")
    table.add_row("누진공제액",    _fmt(result["누진공제액"]))
    table.add_row("[bold]산출세액[/bold]",     f"[bold]{_fmt(result['산출세액'])}[/bold]")
    table.add_row("지방소득세 (10%)", _fmt(local))
    table.add_row("[bold red]총 납부 예상액[/bold red]", f"[bold red]{_fmt(result['산출세액'] + local)}[/bold red]")
    console.print(table)

    tax_store.save_calculation({
        "gross_income": gross,
        "total_deductions": deductions,
        "taxable_income": taxable,
        "result": result,
    })


# ── 메뉴 4: 공제 체크 ────────────────────────────────────────────────────────

def deduction_check_flow():
    console.print(Panel("누락 가능한 공제 항목을 확인합니다.", title="4. 공제 체크"))

    profile = tax_store.get_user_profile()
    if not profile:
        console.print("[yellow]먼저 '1. 내 정보 입력'을 완료해 주세요.[/yellow]")
        return

    missing = strategy_engine.check_missing_deductions(profile)
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
    strategies = strategy_engine.generate_strategy(profile, tax_result)

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
