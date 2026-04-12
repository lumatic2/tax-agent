import argparse
import sys

from tax_calculator import (
    calculate_employment_income_deduction,
    calculate_executive_retirement_limit,
    calculate_exit_tax,
    calculate_exit_tax_adjustment,
    calculate_exit_tax_foreign_credit,
    calculate_financial_income,
    calculate_other_income,
    calculate_pension_income,
    calculate_retirement_income_tax,
    calculate_simplified_withholding,
    calculate_stock_transfer_tax,
    calculate_tax,
    calculate_transfer_income_tax,
    calculate_wage_income_tax,
    calculate_withholding_tax,
    get_other_income_expense_ratio,
)


def format_won(amount: int) -> str:
    return f"{int(amount):,}원"


def format_rate(rate: float) -> str:
    return f"{float(rate) * 100:g}%"


def normalize_asset_type(asset_type: str) -> str:
    mapping = {
        "일반": "general",
        "general": "general",
        "1세대1주택": "one_house",
        "one_house": "one_house",
    }
    try:
        return mapping[asset_type]
    except KeyError as exc:
        raise ValueError("asset_type은 일반|1세대1주택|general|one_house 중 하나여야 합니다.") from exc


def normalize_income_type(income_type: str) -> str:
    mapping = {
        "이자": "interest",
        "interest": "interest",
        "배당": "dividend",
        "dividend": "dividend",
        "사업": "business_service",
        "business": "business_service",
        "business_service": "business_service",
        "기타": "other",
        "other": "other",
    }
    try:
        return mapping[income_type]
    except KeyError as exc:
        raise ValueError("income_type은 이자|배당|사업|근로|기타 중 하나여야 합니다.") from exc


def handle_earned_deduction(args: argparse.Namespace) -> None:
    deduction = calculate_employment_income_deduction(args.salary)
    earned_income = int(args.salary) - deduction
    print(f"근로소득공제: {format_won(deduction)} / 근로소득금액: {format_won(earned_income)}")


def handle_income_tax(args: argparse.Namespace) -> None:
    result = calculate_tax(args.taxable)
    print(
        f"산출세액: {format_won(result['산출세액'])} / "
        f"세율구간: {format_rate(result['적용세율'])}"
    )


def handle_wage_tax(args: argparse.Namespace) -> None:
    result = calculate_wage_income_tax(args.salary)
    print(
        f"종합소득과세표준: {format_won(result['과세표준'])} / "
        f"산출세액: {format_won(result['산출세액'])} / "
        f"결정세액: {format_won(result['총납부예상'])}"
    )


def handle_retirement_tax(args: argparse.Namespace) -> None:
    result = calculate_retirement_income_tax(args.pay, args.years)
    print(
        f"근속연수공제: {format_won(result['근속연수공제'])} / "
        f"환산급여: {format_won(result['환산급여'])} / "
        f"환산급여공제: {format_won(result['환산급여공제'])} / "
        f"환산산출세액: {format_won(result['환산산출세액'])} / "
        f"퇴직소득세: {format_won(result['퇴직소득산출세액'])}"
    )


def handle_transfer_tax(args: argparse.Namespace) -> None:
    asset_type = normalize_asset_type(args.asset_type)
    result = calculate_transfer_income_tax(
        transfer_price=args.price,
        acquisition_price=args.acq_price,
        holding_years=args.held_years,
        asset_type=asset_type,
    )
    print(
        f"양도차익: {format_won(result['양도차익'])} / "
        f"장기보유공제: {format_won(result['장기보유특별공제액'])} / "
        f"과세표준: {format_won(result['양도소득과세표준'])} / "
        f"산출세액: {format_won(result['산출세액'])}"
    )


def handle_pension_income(args: argparse.Namespace) -> None:
    result = calculate_pension_income(args.total)
    print(
        f"연금소득공제: {format_won(result['연금소득공제'])} / "
        f"연금소득금액: {format_won(result['연금소득금액'])}"
    )


def handle_financial_income(args: argparse.Namespace) -> None:
    result = calculate_financial_income(
        interest=args.interest,
        dividend=args.dividend,
        gross_up_eligible_dividend=args.grossup_dividend,
        grossup_mode=args.grossup_mode,
    )
    mode = "종합과세" if result["종합과세여부"] else "분리과세"
    print(
        f"이자소득금액: {format_won(result['이자소득금액'])} / "
        f"배당소득금액: {format_won(result['배당소득금액'])} / "
        f"Gross-up: {format_won(result['Gross_up금액'])} / "
        f"합계: {format_won(result['금융소득합계'])} / "
        f"과세방식: {mode}"
    )
    print(f"비고: {result['비고']}")


def handle_other_income(args: argparse.Namespace) -> None:
    type_map = {
        "일반": "general", "general": "general",
        "복권": "lottery", "lottery": "lottery",
        "슬롯머신": "slot_machine", "slot_machine": "slot_machine",
        "연금계좌": "pension_account", "pension_account": "pension_account",
    }
    income_type = type_map.get(args.type, args.type)
    result = calculate_other_income(
        gross_income=args.gross,
        income_type=income_type,
        expense_ratio=args.expense_ratio,
        ticket_cost=args.ticket_cost,
    )
    print(
        f"총수입금액: {format_won(result['총수입금액'])} / "
        f"필요경비: {format_won(result['필요경비'])} / "
        f"기타소득금액: {format_won(result['기타소득금액'])} / "
        f"원천징수세액: {format_won(result['원천징수세액'])}"
    )
    print(f"비고: {result['비고']}")


def handle_stock_transfer_tax(args: argparse.Namespace) -> None:
    result = calculate_stock_transfer_tax(
        transfer_price=args.price, acquisition_price=args.acq_price,
        necessary_expenses=args.expenses, holding_years=args.held_years,
        stock_type=args.stock_type,
    )
    print(
        f"양도차익: {format_won(result['양도차익'])} / "
        f"과세표준: {format_won(result['양도소득과세표준'])} / "
        f"산출세액: {format_won(result['산출세액'])} / "
        f"총납부: {format_won(result['총납부세액'])}"
    )
    print(f"세율: {result['세율_설명']}")


def handle_exit_tax(args: argparse.Namespace) -> None:
    result = calculate_exit_tax(
        market_value_at_exit=args.market_value, acquisition_price=args.acq_price,
        necessary_expenses=args.expenses, stock_type=args.stock_type,
    )
    print(
        f"출국일 시가: {format_won(result['출국일_시가'])} / "
        f"양도소득금액: {format_won(result['양도소득금액'])} / "
        f"과세표준: {format_won(result['양도소득과세표준'])} / "
        f"산출세액: {format_won(result['산출세액'])}"
    )
    print(f"세율: {result['세율_설명']}")


def handle_expense_ratio(args: argparse.Namespace) -> None:
    result = get_other_income_expense_ratio(args.item_type)
    print(f"의제율: {result['의제율']:.0%} / 근거: {result['법령근거']}")


def handle_executive_retirement_limit(args: argparse.Namespace) -> None:
    result = calculate_executive_retirement_limit(
        avg_salary_pre_2020=args.avg_salary_pre_2020,
        avg_salary_pre_retire=args.avg_salary_pre_retire,
        months_b=args.months_b,
        months_c=args.months_c,
        total_retirement_pay=args.total_pay,
        a_amount_rule=args.a_rule,
        total_months=args.total_months,
        pre_2012_months=args.pre_2012_months,
        select_min_earned=(args.select == "auto"),
    )
    print(
        f"B구간 한도: {format_won(result['한도_B구간'])} / "
        f"C구간 한도: {format_won(result['한도_C구간'])} / "
        f"임원한도: {format_won(result['임원한도'])}"
    )
    print(
        f"A금액 비율법: {format_won(result['A금액_비율법'])} / "
        f"A금액 규정법: {format_won(result['A금액_규정법'])} / "
        f"선택: {format_won(result['A금액_선택'])}"
    )
    print(
        f"한도 대상 기본금액: {format_won(result['한도_대상_기본금액'])} / "
        f"근로소득 재분류액: {format_won(result['초과액_근로소득화'])} / "
        f"한도내 퇴직소득: {format_won(result['퇴직소득_산정기준'])}"
    )
    print(f"비고: {result['비고']}")


def handle_withholding(args: argparse.Namespace) -> None:
    if args.type == "근로":
        result = calculate_simplified_withholding(args.amount)
        tax = int(result["원천징수세액"])
        rate = (tax / int(args.amount)) if int(args.amount) else 0.0
    else:
        income_type = normalize_income_type(args.type)
        result = calculate_withholding_tax(args.amount, income_type)
        tax = int(result["원천징수세액"])
        rate = float(result["원천징수세율"])

    print(f"원천징수세액: {format_won(tax)} / 세율: {format_rate(rate)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="세액 계산 CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    earned = subparsers.add_parser("earned-deduction")
    earned.add_argument("--salary", type=int, required=True)
    earned.set_defaults(func=handle_earned_deduction)

    income = subparsers.add_parser("income-tax")
    income.add_argument("--taxable", type=int, required=True)
    income.set_defaults(func=handle_income_tax)

    wage = subparsers.add_parser("wage-tax")
    wage.add_argument("--salary", type=int, required=True)
    wage.set_defaults(func=handle_wage_tax)

    retirement = subparsers.add_parser("retirement-tax")
    retirement.add_argument("--pay", type=int, required=True)
    retirement.add_argument("--years", type=int, required=True)
    retirement.set_defaults(func=handle_retirement_tax)

    transfer = subparsers.add_parser("transfer-tax")
    transfer.add_argument("--price", type=int, required=True)
    transfer.add_argument("--acq-price", type=int, required=True)
    transfer.add_argument("--held-years", type=float, required=True)
    transfer.add_argument("--asset-type", default="일반")
    transfer.set_defaults(func=handle_transfer_tax)

    pension = subparsers.add_parser("pension-income")
    pension.add_argument("--total", type=int, required=True)
    pension.set_defaults(func=handle_pension_income)

    withholding = subparsers.add_parser("withholding")
    withholding.add_argument("--amount", type=int, required=True)
    withholding.add_argument("--type", required=True)
    withholding.set_defaults(func=handle_withholding)

    financial = subparsers.add_parser(
        "financial-income",
        help="금융소득(이자+배당) Gross-up + 2천만 종합과세 판정 (§16·§17·§14③6)",
    )
    financial.add_argument("--interest", type=int, default=0, help="이자소득 총수입금액")
    financial.add_argument("--dividend", type=int, default=0, help="배당소득 총수입금액")
    financial.add_argument(
        "--grossup-dividend", type=int, default=0,
        help="Gross-up 대상 배당금액 (내국법인 일반배당 등, §17③ 본문)",
    )
    financial.add_argument(
        "--grossup-mode", choices=["full", "threshold"], default="full",
        help="Gross-up 계산 방식. full=전액×10% (기본, 법 문언) / threshold=2천만 초과분만 (시험 실무)",
    )
    financial.set_defaults(func=handle_financial_income)

    other = subparsers.add_parser(
        "other-income",
        help="기타소득 단일항목 계산 (§21·영§87 필요경비 의제)",
    )
    other.add_argument("--gross", type=int, required=True, help="총수입금액")
    other.add_argument(
        "--type", default="일반",
        help="일반|복권|슬롯머신|연금계좌 (기본 일반)",
    )
    other.add_argument(
        "--expense-ratio", type=float, default=0.60,
        help="필요경비 의제율 (일반 항목만 적용, 기본 0.60). "
             "§87①1호 가·다: 0.80 / §87①1의2호 §21①7·8의2·9·15·19: 0.60 / 그 외: 0.00",
    )
    other.add_argument("--ticket-cost", type=int, default=0, help="복권 구입비 (lottery 전용)")
    other.set_defaults(func=handle_other_income)

    exec_ret = subparsers.add_parser(
        "executive-retirement-limit",
        help="임원 퇴직급여 한도 (§22③ + 영§42의2⑥)",
    )
    exec_ret.add_argument("--avg-salary-pre-2020", dest="avg_salary_pre_2020", type=int, required=True,
                          help="2019.12.31 이전 3년 연평균 총급여 (B구간용)")
    exec_ret.add_argument("--avg-salary-pre-retire", dest="avg_salary_pre_retire", type=int, required=True,
                          help="퇴직일 이전 3년 연평균 총급여 (C구간용)")
    exec_ret.add_argument("--months-b", dest="months_b", type=int, required=True,
                          help="2012.1.1~2019.12.31 근무월수 (1월 미만 절상 후)")
    exec_ret.add_argument("--months-c", dest="months_c", type=int, required=True,
                          help="2020.1.1~퇴직일 근무월수 (1월 미만 절상 후)")
    exec_ret.add_argument("--total-pay", dest="total_pay", type=int, default=0,
                          help="전체 퇴직급여 (공적연금 제외) — 비율법·한도 기본금액 산정용")
    exec_ret.add_argument("--a-rule", dest="a_rule", type=int, default=0,
                          help="2011.12.31 가정 규정상 퇴직금 (규정법 A금액)")
    exec_ret.add_argument("--total-months", dest="total_months", type=int, default=0,
                          help="전체 근무월수 (비율법용)")
    exec_ret.add_argument("--pre-2012-months", dest="pre_2012_months", type=int, default=0,
                          help="2011.12.31 이전 근무월수 (비율법용)")
    exec_ret.add_argument("--select", choices=["auto", "rule"], default="auto",
                          help="A금액 선택: auto=근로소득 적게(비율법/규정법 중 큰 쪽), rule=규정법 고정")
    exec_ret.set_defaults(func=handle_executive_retirement_limit)

    stock = subparsers.add_parser("stock-transfer-tax", help="주식 양도소득세 (§104)")
    stock.add_argument("--price", type=int, required=True, help="양도가액")
    stock.add_argument("--acq-price", type=int, required=True, help="취득가액")
    stock.add_argument("--expenses", type=int, default=0, help="필요경비")
    stock.add_argument("--held-years", type=float, default=3.0, help="보유기간(년)")
    stock.add_argument("--stock-type", default="listed_major",
                       choices=["listed_major", "listed_minor", "unlisted", "unlisted_sme"],
                       help="주식유형")
    stock.set_defaults(func=handle_stock_transfer_tax)

    exit_tax = subparsers.add_parser("exit-tax", help="국외전출세 (§118의9~10)")
    exit_tax.add_argument("--market-value", type=int, required=True, help="출국일 시가")
    exit_tax.add_argument("--acq-price", type=int, required=True, help="취득가액")
    exit_tax.add_argument("--expenses", type=int, default=0, help="필요경비")
    exit_tax.add_argument("--stock-type", default="listed_major",
                          choices=["listed_major", "listed_minor", "unlisted", "unlisted_sme"])
    exit_tax.set_defaults(func=handle_exit_tax)

    expense_ratio = subparsers.add_parser("expense-ratio", help="기타소득 필요경비 의제율 (영§87)")
    expense_ratio.add_argument("--item-type", required=True,
                               choices=["prize_public", "housing_delay", "patent", "goodwill",
                                        "mining_right", "temp_property", "ai_copyright",
                                        "penalty", "bribe", "invention", "general"],
                               help="§21 항목 유형")
    expense_ratio.set_defaults(func=handle_expense_ratio)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
