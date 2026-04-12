"""상속세/증여세 계산 CLI

Usage:
    python inheritance_gift_calc_cli.py inheritance --estate 2000000000 --debts 200000000
    python inheritance_gift_calc_cli.py gift --value 300000000 --donor 직계존속
    python inheritance_gift_calc_cli.py rate --base 500000000
    python inheritance_gift_calc_cli.py stock --nav 25000 --npv 20000 --shares 20000
    python inheritance_gift_calc_cli.py low-price --market 300000000 --price 130000000
    python inheritance_gift_calc_cli.py free-use --value 2000000000
    python inheritance_gift_calc_cli.py loan --amount 200000000
    python inheritance_gift_calc_cli.py filing --death-date 2026-03-15
    python inheritance_gift_calc_cli.py installment --tax 50000000
"""

import argparse
import sys
from datetime import date

from inheritance_gift_calculator import (
    apply_tax_rate,
    calculate_inheritance_tax,
    calculate_inheritance_tax_base_amount,
    calculate_spouse_deduction,
    calculate_other_personal_deductions,
    calculate_lump_sum_deduction,
    calculate_financial_asset_deduction,
    calculate_family_business_deduction,
    calculate_farming_deduction,
    calculate_gift_tax,
    calculate_gift_deduction,
    calculate_marriage_childbirth_deduction,
    calculate_low_price_transfer_gift,
    calculate_high_price_transfer_gift,
    calculate_free_use_of_real_estate_gift,
    calculate_interest_free_loan_gift,
    evaluate_listed_stock,
    evaluate_unlisted_stock,
    evaluate_max_shareholder_premium,
    evaluate_deposit,
    evaluate_land,
    evaluate_building,
    evaluate_housing,
    evaluate_leased_property,
    get_inheritance_filing_deadline,
    calculate_installment_payment,
    check_payment_in_kind_eligibility,
)


def fmt(amount: int) -> str:
    return f"{int(amount):,}"


def print_dict(d: dict, indent: int = 0):
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            print(f"{prefix}{k}:")
            print_dict(v, indent + 1)
        elif isinstance(v, float):
            print(f"{prefix}{k}: {v * 100:g}%")
        elif isinstance(v, int) and abs(v) >= 1000:
            print(f"{prefix}{k}: {fmt(v)}")
        else:
            print(f"{prefix}{k}: {v}")


# ── handlers ──

def handle_rate(args):
    r = apply_tax_rate(args.base)
    print(f"[세율표] 과세표준: {fmt(args.base)}")
    print(f"  세율: {r['적용세율']*100:g}% / 누진공제: {fmt(r['누진공제'])} / 산출세액: {fmt(r['산출세액'])}")


def handle_inheritance(args):
    r = calculate_inheritance_tax(
        gross_estate=args.estate,
        public_charges=args.public_charges,
        funeral_expenses=args.funeral,
        funeral_enshrined=args.enshrined,
        debts=args.debts,
        pre_gift_to_heirs=args.pre_gift_heirs,
        pre_gift_to_others=args.pre_gift_others,
        has_spouse=args.spouse,
        spouse_actual_inheritance=args.spouse_actual,
        spouse_legal_share_amount=args.spouse_legal,
        children_count=args.children,
        financial_assets=args.financial,
        financial_debts=args.financial_debts,
        pre_gift_tax_paid=args.pre_gift_tax,
        appraisal_fee=args.appraisal,
    )
    print(f"[상속세 계산]")
    print(f"  과세가액:     {fmt(r['과세가액'])}")
    print(f"  공제합계:     {fmt(r['공제합계'])}")
    print(f"  과세표준:     {fmt(r['과세표준'])}")
    print(f"  산출세액:     {fmt(r['산출세액'])}")
    if r['세대생략할증']:
        print(f"  세대생략할증: {fmt(r['세대생략할증'])}")
    if r['증여세액공제']:
        print(f"  증여세액공제: {fmt(r['증여세액공제'])}")
    print(f"  신고세액공제: {fmt(r['신고세액공제'])}")
    print(f"  납부세액:     {fmt(r['납부세액'])}")


def handle_gift(args):
    r = calculate_gift_tax(
        gift_value=args.value,
        assumed_debts=args.debts,
        prior_gifts_10yr=args.prior_gifts,
        donor_relationship=args.donor,
        is_minor=args.minor,
        prior_deductions_used=args.prior_deductions,
        is_marriage_gift=args.marriage,
        is_childbirth_gift=args.childbirth,
        prior_gift_tax_paid=args.prior_tax,
        appraisal_fee=args.appraisal,
    )
    print(f"[증여세 계산]")
    print(f"  과세가액:     {fmt(r['과세가액'])}")
    print(f"  증여재산공제: {fmt(r['증여재산공제'])}")
    if r['혼인출산공제']:
        print(f"  혼인출산공제: {fmt(r['혼인출산공제'])}")
    print(f"  과세표준:     {fmt(r['과세표준'])}")
    print(f"  산출세액:     {fmt(r['산출세액'])}")
    if r['기납부세액공제']:
        print(f"  기납부공제:   {fmt(r['기납부세액공제'])}")
    print(f"  신고세액공제: {fmt(r['신고세액공제'])}")
    print(f"  납부세액:     {fmt(r['납부세액'])}")


def handle_stock(args):
    if args.listed:
        print("[상장주식 평가] (가격 리스트 직접 전달 필요 - CLI에서는 단가 평균만)")
        print(f"  단가: {fmt(args.nav)}")
    else:
        r = evaluate_unlisted_stock(
            net_asset_value_per_share=args.nav,
            net_profit_value_per_share=args.npv,
            is_real_estate_company=args.realestate,
        )
        total = r['평가액'] * args.shares
        print(f"[비상장주식 평가]")
        print(f"  1주 평가액: {fmt(r['평가액'])} ({r['가중치']})")
        print(f"  {args.shares:,}주 총액: {fmt(total)}")
        if args.max_shareholder:
            p = evaluate_max_shareholder_premium(base_value=r['평가액'])
            print(f"  최대주주할증: {fmt(p['평가액'])} (할증 {fmt(p['할증액'])})")
            print(f"  할증 후 총액: {fmt(p['평가액'] * args.shares)}")


def handle_low_price(args):
    r = calculate_low_price_transfer_gift(
        market_value=args.market,
        transfer_price=args.price,
        is_related_party=not args.unrelated,
    )
    print(f"[저가양수 증여] 시가: {fmt(args.market)} / 대가: {fmt(args.price)}")
    print_dict(r, indent=1)


def handle_high_price(args):
    r = calculate_high_price_transfer_gift(
        market_value=args.market,
        transfer_price=args.price,
        is_related_party=not args.unrelated,
    )
    print(f"[고가양도 증여] 시가: {fmt(args.market)} / 대가: {fmt(args.price)}")
    print_dict(r, indent=1)


def handle_free_use(args):
    r = calculate_free_use_of_real_estate_gift(
        property_value=args.value,
        annual_benefit_rate=args.rate,
        annuity_pv_factor=args.pv_factor,
    )
    print(f"[부동산 무상사용 증여] 시가: {fmt(args.value)}")
    print_dict(r, indent=1)


def handle_loan(args):
    r = calculate_interest_free_loan_gift(
        loan_amount=args.amount,
        loan_rate=args.loan_rate,
        appropriate_rate=args.appropriate_rate,
    )
    print(f"[금전 무상대출 증여] 대출금: {fmt(args.amount)}")
    print_dict(r, indent=1)


def handle_filing(args):
    death = date.fromisoformat(args.death_date)
    r = get_inheritance_filing_deadline(
        death_date=death,
        is_foreign_address=args.foreign,
    )
    print(f"[상속세 신고기한]")
    print(f"  상속개시일: {r['상속개시일']} / 신고기한: {r['신고기한']} ({r['기간']})")


def handle_installment(args):
    r = calculate_installment_payment(
        tax_payable=args.tax,
        is_inheritance=not args.gift,
        is_family_business=args.family_biz,
    )
    print(f"[연부연납]")
    print_dict(r, indent=1)


def handle_land(args):
    r = evaluate_land(
        officially_assessed_price=args.price,
        multiplier=args.multiplier,
    )
    total = r['평가액'] * args.area if args.area else r['평가액']
    print(f"[토지 보충적 평가] 공시지가: {fmt(args.price)}/m2 x 배율 {args.multiplier}")
    print(f"  m2당 평가액: {fmt(r['평가액'])}")
    if args.area:
        print(f"  총 평가액 ({args.area}m2): {fmt(total)}")


def handle_family_biz(args):
    r = calculate_family_business_deduction(
        business_asset_value=args.value,
        years_managed=args.years,
        is_sme=not args.mid_sized,
        is_mid_sized=args.mid_sized,
    )
    print(f"[가업상속공제]")
    print_dict(r, indent=1)


# ── parser ──

def main():
    parser = argparse.ArgumentParser(
        description="상속세/증여세 계산 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="서브커맨드")

    # rate
    p = sub.add_parser("rate", help="세율표 적용")
    p.add_argument("--base", type=int, required=True, help="과세표준")

    # inheritance
    p = sub.add_parser("inheritance", help="상속세 종합 계산")
    p.add_argument("--estate", type=int, required=True, help="총상속재산")
    p.add_argument("--public-charges", type=int, default=0, help="공과금")
    p.add_argument("--funeral", type=int, default=0, help="장례비(봉안 제외)")
    p.add_argument("--enshrined", type=int, default=0, help="봉안시설 비용")
    p.add_argument("--debts", type=int, default=0, help="채무")
    p.add_argument("--pre-gift-heirs", type=int, default=0, help="상속인 사전증여(10년)")
    p.add_argument("--pre-gift-others", type=int, default=0, help="비상속인 사전증여(5년)")
    p.add_argument("--spouse", action="store_true", default=True, help="배우자 있음")
    p.add_argument("--no-spouse", dest="spouse", action="store_false")
    p.add_argument("--spouse-actual", type=int, default=0, help="배우자 실제상속액")
    p.add_argument("--spouse-legal", type=int, default=0, help="배우자 법정상속지분")
    p.add_argument("--children", type=int, default=0, help="자녀 수")
    p.add_argument("--financial", type=int, default=0, help="금융재산")
    p.add_argument("--financial-debts", type=int, default=0, help="금융채무")
    p.add_argument("--pre-gift-tax", type=int, default=0, help="기납부 증여세")
    p.add_argument("--appraisal", type=int, default=0, help="감정평가수수료")

    # gift
    p = sub.add_parser("gift", help="증여세 종합 계산")
    p.add_argument("--value", type=int, required=True, help="증여재산가액")
    p.add_argument("--debts", type=int, default=0, help="인수채무")
    p.add_argument("--prior-gifts", type=int, default=0, help="10년 합산 기증여")
    p.add_argument("--donor", default="직계존속", help="증여자 관계")
    p.add_argument("--minor", action="store_true", help="미성년 수증자")
    p.add_argument("--prior-deductions", type=int, default=0, help="기사용 공제액")
    p.add_argument("--marriage", action="store_true", help="혼인증여")
    p.add_argument("--childbirth", action="store_true", help="출산증여")
    p.add_argument("--prior-tax", type=int, default=0, help="기납부 증여세")
    p.add_argument("--appraisal", type=int, default=0, help="감정평가수수료")

    # stock
    p = sub.add_parser("stock", help="비상장주식 평가")
    p.add_argument("--nav", type=int, required=True, help="순자산가치/주")
    p.add_argument("--npv", type=int, default=0, help="순손익가치/주")
    p.add_argument("--shares", type=int, default=1, help="주식 수")
    p.add_argument("--realestate", action="store_true", help="부동산과다법인")
    p.add_argument("--max-shareholder", action="store_true", help="최대주주 할증")
    p.add_argument("--listed", action="store_true", help="상장주식 모드")

    # low-price
    p = sub.add_parser("low-price", help="저가양수 증여 (§35)")
    p.add_argument("--market", type=int, required=True, help="시가")
    p.add_argument("--price", type=int, required=True, help="양수가액")
    p.add_argument("--unrelated", action="store_true", help="비특수관계인")

    # high-price
    p = sub.add_parser("high-price", help="고가양도 증여 (§35)")
    p.add_argument("--market", type=int, required=True, help="시가")
    p.add_argument("--price", type=int, required=True, help="양도가액")
    p.add_argument("--unrelated", action="store_true", help="비특수관계인")

    # free-use
    p = sub.add_parser("free-use", help="부동산 무상사용 증여 (§37)")
    p.add_argument("--value", type=int, required=True, help="부동산 시가")
    p.add_argument("--rate", type=float, default=0.02, help="연간이익률")
    p.add_argument("--pv-factor", type=float, default=3.7907, help="연금현가계수")

    # loan
    p = sub.add_parser("loan", help="금전 무상대출 증여 (§41의4)")
    p.add_argument("--amount", type=int, required=True, help="대출금액")
    p.add_argument("--loan-rate", type=float, default=0.0, help="실제 이자율")
    p.add_argument("--appropriate-rate", type=float, default=0.045, help="적정이자율")

    # filing
    p = sub.add_parser("filing", help="상속세 신고기한")
    p.add_argument("--death-date", required=True, help="사망일 (YYYY-MM-DD)")
    p.add_argument("--foreign", action="store_true", help="외국주소")

    # installment
    p = sub.add_parser("installment", help="연부연납 안내")
    p.add_argument("--tax", type=int, required=True, help="납부세액")
    p.add_argument("--gift", action="store_true", help="증여세 (기본: 상속세)")
    p.add_argument("--family-biz", action="store_true", help="가업상속")

    # land
    p = sub.add_parser("land", help="토지 보충적 평가")
    p.add_argument("--price", type=int, required=True, help="공시지가 (원/m2)")
    p.add_argument("--multiplier", type=float, default=1.0, help="배율")
    p.add_argument("--area", type=float, default=0, help="면적 (m2)")

    # family-biz
    p = sub.add_parser("family-biz", help="가업상속공제")
    p.add_argument("--value", type=int, required=True, help="가업재산가액")
    p.add_argument("--years", type=int, required=True, help="경영연수")
    p.add_argument("--mid-sized", action="store_true", help="중견기업")

    args = parser.parse_args()

    handlers = {
        "rate": handle_rate,
        "inheritance": handle_inheritance,
        "gift": handle_gift,
        "stock": handle_stock,
        "low-price": handle_low_price,
        "high-price": handle_high_price,
        "free-use": handle_free_use,
        "loan": handle_loan,
        "filing": handle_filing,
        "installment": handle_installment,
        "land": handle_land,
        "family-biz": handle_family_biz,
    }

    if args.command in handlers:
        handlers[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
