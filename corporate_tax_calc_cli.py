"""법인세 계산 CLI

Usage:
    python corporate_tax_calc_cli.py rate --base 2000000000
    python corporate_tax_calc_cli.py loss-carryforward --income 1000000000 --losses 500000000:6,400000000:5
    python corporate_tax_calc_cli.py tax-base --income 3000000000 --losses 1000000000:5
    python corporate_tax_calc_cli.py tax --income 3000000000 --losses 1000000000:5 --credits 50000000
"""

import argparse
import sys

from corporate_tax_calculator import (
    apply_corporate_tax_rate,
    calculate_loss_carryforward,
    calculate_corporate_tax_base,
    calculate_corporate_tax,
    calculate_entertainment_expense_limit_corp,
    calculate_donation_limit,
    calculate_depreciation_limit,
    calculate_retirement_allowance_reserve,
    calculate_bad_debt_reserve,
    calculate_unfair_transaction_denial,
    calculate_foreign_tax_credit,
    apply_minimum_tax,
    calculate_land_transfer_additional_tax,
    calculate_interim_prepayment,
    calculate_corporate_tax_full,
)


def fmt(amount: int) -> str:
    return f"{int(amount):,}"


def print_dict(d: dict, indent: int = 0):
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            print(f"{prefix}{k}:")
            print_dict(v, indent + 1)
        elif isinstance(v, list):
            if not v:
                print(f"{prefix}{k}: (없음)")
            else:
                print(f"{prefix}{k}:")
                for item in v:
                    if isinstance(item, dict):
                        print_dict(item, indent + 1)
                        if indent < 2:
                            print(f"{prefix}  ---")
                    else:
                        print(f"{prefix}  {item}")
        elif isinstance(v, float):
            print(f"{prefix}{k}: {v * 100:g}%")
        elif isinstance(v, int) and abs(v) >= 1000:
            print(f"{prefix}{k}: {fmt(v)}")
        elif v is None:
            print(f"{prefix}{k}: -")
        else:
            print(f"{prefix}{k}: {v}")


def parse_losses(losses_str: str) -> list[dict]:
    """Parse loss string format: '금액:경과연수,금액:경과연수,...'"""
    if not losses_str:
        return []
    result = []
    for i, item in enumerate(losses_str.split(',')):
        parts = item.strip().split(':')
        amount = int(parts[0])
        years = int(parts[1]) if len(parts) > 1 else 1
        result.append({
            '사업연도': f'Y-{years}',
            '결손금': amount,
            '경과연수': years,
        })
    return result


# ── handlers ──

def handle_rate(args):
    r = apply_corporate_tax_rate(taxable_base=args.base)
    print(f"[법인세 세율] 과세표준: {fmt(args.base)}")
    print(f"  세율: {r['적용세율']*100:g}% / 누진공제: {fmt(r['누진공제'])} / 산출세액: {fmt(r['산출세액'])}")


def handle_loss_carryforward(args):
    losses = parse_losses(args.losses)
    r = calculate_loss_carryforward(
        income_before_loss=args.income,
        carried_losses=losses,
        is_sme=args.sme,
    )
    print(f"[이월결손금 공제] {'중소기업' if args.sme else '일반법인'}")
    print_dict(r, indent=1)


def handle_tax_base(args):
    losses = parse_losses(args.losses) if args.losses else None
    r = calculate_corporate_tax_base(
        income_per_year=args.income,
        carried_losses=losses,
        is_sme=args.sme,
        nontaxable_income=args.nontaxable,
        income_deductions=args.deductions,
    )
    print(f"[과세표준 계산] {'중소기업' if args.sme else '일반법인'}")
    print_dict(r, indent=1)


def handle_tax(args):
    losses = parse_losses(args.losses) if args.losses else None
    r = calculate_corporate_tax(
        income_per_year=args.income,
        carried_losses=losses,
        is_sme=args.sme,
        nontaxable_income=args.nontaxable,
        income_deductions=args.deductions,
        tax_credits=args.credits,
        prepaid_tax=args.prepaid,
    )
    print(f"[법인세 계산] {'중소기업' if args.sme else '일반법인'}")
    print_dict({
        '각사업연도소득': r['각사업연도소득'],
        '과세표준': r['과세표준'],
        '산출세액': r['산출세액'],
        '세액공제감면': r['세액공제감면'],
        '결정세액': r['결정세액'],
        '기납부세액': r['기납부세액'],
        '납부할세액': r['납부할세액'],
    }, indent=1)


def handle_entertainment(args):
    r = calculate_entertainment_expense_limit_corp(
        revenue=args.revenue, actual_entertainment=args.actual, is_sme=args.sme)
    print(f"[접대비 한도] {'중소기업' if args.sme else '일반법인'}")
    print_dict(r, indent=1)


def handle_donation(args):
    r = calculate_donation_limit(
        income_before_donation=args.income,
        statutory_donations=args.statutory,
        designated_donations=args.designated)
    print("[기부금 한도]")
    print_dict(r, indent=1)


def handle_depreciation(args):
    r = calculate_depreciation_limit(
        acquisition_cost=args.cost, useful_life=args.life,
        method=args.method, company_recorded=args.recorded,
        prior_accumulated=args.prior)
    print(f"[감가상각 시부인] {args.method}")
    print_dict(r, indent=1)


def handle_minimum_tax(args):
    r = apply_minimum_tax(
        computed_tax=args.computed, total_reductions=args.reductions,
        taxable_base=args.base, is_sme=args.sme)
    print("[최저한세]")
    print_dict(r, indent=1)


def handle_land(args):
    r = calculate_land_transfer_additional_tax(
        transfer_gain=args.gain, asset_type=args.asset_type,
        is_unregistered=args.unregistered)
    print("[토지 추가과세]")
    print_dict(r, indent=1)


def handle_interim(args):
    r = calculate_interim_prepayment(
        prior_year_computed_tax=args.prior_tax,
        prior_year_credits=args.prior_credits)
    print("[중간예납]")
    print_dict(r, indent=1)


def handle_full(args):
    losses = parse_losses(args.losses) if args.losses else None
    r = calculate_corporate_tax_full(
        accounting_profit=args.profit,
        carried_losses=losses,
        is_sme=args.sme,
        sme_reduction_rate=args.reduction_rate,
        prepaid_tax=args.prepaid)
    print(f"[법인세 전체] {'중소기업' if args.sme else '일반법인'}")
    print_dict({
        '당기순이익': r['당기순이익'],
        '각사업연도소득': r['각사업연도소득'],
        '과세표준': r['과세표준'],
        '산출세액': r['산출세액'],
        '감면합계': r['감면합계'],
        '최저한세적용': r['최저한세적용'],
        '결정세액': r['결정세액'],
        '기납부세액': r['기납부세액'],
        '납부할세액': r['납부할세액'],
    }, indent=1)


def main():
    parser = argparse.ArgumentParser(
        description="법인세 계산 CLI (Phase 4)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="서브커맨드")

    # rate
    p = sub.add_parser("rate", help="세율표 적용 (§55)")
    p.add_argument("--base", type=int, required=True, help="과세표준")

    # loss-carryforward
    p = sub.add_parser("loss-carryforward", help="이월결손금 공제 (§13)")
    p.add_argument("--income", type=int, required=True, help="각사업연도소득")
    p.add_argument("--losses", type=str, required=True, help="이월결손금 (금액:경과연수,...)")
    p.add_argument("--sme", action="store_true", help="중소기업 여부")

    # tax-base
    p = sub.add_parser("tax-base", help="과세표준 계산 (§13)")
    p.add_argument("--income", type=int, required=True, help="각사업연도소득")
    p.add_argument("--losses", type=str, default=None, help="이월결손금 (금액:경과연수,...)")
    p.add_argument("--sme", action="store_true", help="중소기업 여부")
    p.add_argument("--nontaxable", type=int, default=0, help="비과세소득")
    p.add_argument("--deductions", type=int, default=0, help="소득공제액")

    # tax
    p = sub.add_parser("tax", help="법인세 종합계산 (§55, §13)")
    p.add_argument("--income", type=int, required=True, help="각사업연도소득")
    p.add_argument("--losses", type=str, default=None, help="이월결손금 (금액:경과연수,...)")
    p.add_argument("--sme", action="store_true", help="중소기업 여부")
    p.add_argument("--nontaxable", type=int, default=0, help="비과세소득")
    p.add_argument("--deductions", type=int, default=0, help="소득공제액")
    p.add_argument("--credits", type=int, default=0, help="세액공제·감면 합계")
    p.add_argument("--prepaid", type=int, default=0, help="기납부세액")

    # entertainment-limit
    p = sub.add_parser("entertainment-limit", help="접대비 한도 (§25)")
    p.add_argument("--revenue", type=int, required=True, help="수입금액")
    p.add_argument("--actual", type=int, default=0, help="실지출액")
    p.add_argument("--sme", action="store_true", help="중소기업 여부")

    # donation-limit
    p = sub.add_parser("donation-limit", help="기부금 한도 (§24)")
    p.add_argument("--income", type=int, required=True, help="기준소득")
    p.add_argument("--statutory", type=int, default=0, help="특례기부금")
    p.add_argument("--designated", type=int, default=0, help="일반기부금")

    # depreciation
    p = sub.add_parser("depreciation", help="감가상각 시부인 (§23)")
    p.add_argument("--cost", type=int, required=True, help="취득가액")
    p.add_argument("--life", type=int, required=True, help="내용연수")
    p.add_argument("--method", choices=['정액법', '정률법'], default='정액법', help="상각방법")
    p.add_argument("--recorded", type=int, default=0, help="회사계상액")
    p.add_argument("--prior", type=int, default=0, help="전기누적상각액")

    # minimum-tax
    p = sub.add_parser("minimum-tax", help="최저한세 (조특법 §132)")
    p.add_argument("--computed", type=int, required=True, help="산출세액")
    p.add_argument("--reductions", type=int, required=True, help="감면합계")
    p.add_argument("--base", type=int, required=True, help="과세표준")
    p.add_argument("--sme", action="store_true", help="중소기업 여부")

    # land-surcharge
    p = sub.add_parser("land-surcharge", help="토지 추가과세 (§55의2)")
    p.add_argument("--gain", type=int, required=True, help="양도소득")
    p.add_argument("--type", dest="asset_type", default='비사업용토지', help="자산유형")
    p.add_argument("--unregistered", action="store_true", help="미등기 여부")

    # interim-prepay
    p = sub.add_parser("interim-prepay", help="중간예납 (§63)")
    p.add_argument("--prior-tax", type=int, required=True, help="직전 산출세액")
    p.add_argument("--prior-credits", type=int, default=0, help="직전 공제감면")

    # full
    p = sub.add_parser("full", help="전체 파이프라인")
    p.add_argument("--profit", type=int, required=True, help="당기순이익")
    p.add_argument("--losses", type=str, default=None, help="이월결손금")
    p.add_argument("--sme", action="store_true", help="중소기업 여부")
    p.add_argument("--reduction-rate", type=float, default=0.0, help="감면율")
    p.add_argument("--prepaid", type=int, default=0, help="기납부세액")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    handlers = {
        "rate": handle_rate,
        "loss-carryforward": handle_loss_carryforward,
        "tax-base": handle_tax_base,
        "tax": handle_tax,
        "entertainment-limit": handle_entertainment,
        "donation-limit": handle_donation,
        "depreciation": handle_depreciation,
        "minimum-tax": handle_minimum_tax,
        "land-surcharge": handle_land,
        "interim-prepay": handle_interim,
        "full": handle_full,
    }

    handlers[args.command](args)


if __name__ == "__main__":
    main()
