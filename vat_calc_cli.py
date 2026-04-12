import argparse
import sys

from vat_calculator import (
    # Ch05
    extract_supply_value,
    calculate_vat_tax_base,
    calculate_vat_output_tax,
    calculate_bad_debt_tax_credit,
    allocate_land_building_supply,
    # Ch06
    calculate_vat_input_tax,
    calculate_vat_non_deductible,
    calculate_deemed_input_tax,
    calculate_credit_card_issue_credit,
    calculate_vat_payable,
    # Ch07
    calculate_common_input_tax_allocation,
    settle_common_input_tax,
    # Ch08
    calculate_invoice_penalty,
    calculate_preliminary_notice,
    calculate_vat_penalties,
    # Ch09
    calculate_simplified_vat,
    calculate_simplified_to_general_inventory_credit,
    # Gap 보강
    recalculate_mixed_use_asset_tax,
    calculate_proxy_payment_tax,
    calculate_deemed_input_tax_with_limit,
    calculate_local_consumption_tax,
)


def format_won(amount: int) -> str:
    return f"{int(amount):,}원"


def format_rate(rate: float) -> str:
    return f"{float(rate) * 100:g}%"


# ── handlers ──

def handle_supply_value(args):
    r = extract_supply_value(args.total, vat_inclusive=not args.no_vat)
    print(f"공급가액: {format_won(r['공급가액'])} / 부가세: {format_won(r['부가세액'])} / 공급대가: {format_won(r['공급대가'])}")


def handle_output_tax(args):
    r = calculate_vat_output_tax(args.tax_base)
    print(f"과세표준: {format_won(r['과세표준'])} / 매출세액: {format_won(r['매출세액'])}")


def handle_bad_debt(args):
    r = calculate_bad_debt_tax_credit(args.amount, vat_inclusive=not args.no_vat)
    print(f"대손금액: {format_won(r['대손금액'])} / 대손세액공제: {format_won(r['대손세액공제액'])}")


def handle_land_building(args):
    r = allocate_land_building_supply(
        total_price=args.total,
        land_base_price=args.land_base,
        building_base_price=args.building_base,
    )
    print(
        f"토지: {format_won(r['토지공급가액'])} / "
        f"건물: {format_won(r['건물공급가액'])} / "
        f"건물세액: {format_won(r['건물매출세액'])}"
    )


def handle_deemed_input(args):
    r = calculate_deemed_input_tax(
        purchase_amount=args.amount,
        business_type=args.biz_type,
        vat_inclusive=args.vat_inclusive if hasattr(args, 'vat_inclusive') else False,
    )
    print(f"매입가액: {format_won(r['매입가액'])} / 공제율: {r['공제율']} / 의제매입세액: {format_won(r['의제매입세액'])}")


def handle_card_credit(args):
    r = calculate_credit_card_issue_credit(
        credit_card_sales=args.sales,
        business_type=args.biz_type,
    )
    print(
        f"발행금액: {format_won(r['발행금액'])} / "
        f"공제율: {format_rate(r['공제율'])} / "
        f"공제액: {format_won(r['최종공제액'])} (한도 {format_won(r['한도'])})"
    )


def handle_payable(args):
    r = calculate_vat_payable(
        output_tax=args.output,
        deductible_input_tax=args.input,
        deemed_input_credit=args.deemed or 0,
        bad_debt_credit=args.bad_debt or 0,
        card_issue_credit=args.card_credit or 0,
        electronic_filing_credit=10_000 if args.e_filing else 0,
    )
    label = "환급세액" if r['환급여부'] else "납부세액"
    print(
        f"매출세액: {format_won(r['매출세액'])} / "
        f"매입세액: {format_won(r['공제매입세액'])} / "
        f"세액공제: {format_won(r['세액공제합계'])} / "
        f"{label}: {format_won(abs(r['납부할세액']))}"
    )


def handle_common_alloc(args):
    r = calculate_common_input_tax_allocation(
        common_input_tax=args.common,
        taxable_supply_value=args.taxable,
        exempt_supply_value=args.exempt,
    )
    print(
        f"공통매입세액: {format_won(r['공통매입세액'])} / "
        f"면세비율: {format_rate(r['면세비율'])} / "
        f"불공제: {format_won(r['면세귀속분_불공제'])} / "
        f"공제: {format_won(r['과세귀속분_공제'])}"
    )


def handle_settle(args):
    r = settle_common_input_tax(
        preliminary_exempt_portion=args.prelim,
        annual_taxable_supply=args.taxable,
        annual_exempt_supply=args.exempt,
        common_input_tax=args.common,
    )
    adj = r['추가불공제_또는_환급']
    label = "추가불공제" if adj > 0 else "추가환급"
    print(
        f"예정면세귀속: {format_won(r['예정신고_면세귀속분'])} / "
        f"정산면세귀속: {format_won(r['정산_면세귀속분'])} / "
        f"{label}: {format_won(abs(adj))}"
    )


def handle_invoice_penalty(args):
    r = calculate_invoice_penalty(supply_value=args.supply, violation_type=args.type)
    print(f"공급가액: {format_won(r['공급가액'])} / 위반: {r['위반유형']} / 가산세: {format_won(r['가산세액'])}")


def handle_prelim_notice(args):
    r = calculate_preliminary_notice(prior_period_tax=args.prior)
    print(f"직전기: {format_won(r['직전기납부세액'])} / 예정고지: {format_won(r['예정고지세액'])}")


def handle_penalty(args):
    r = calculate_vat_penalties(
        penalty_type=args.type,
        tax_base_or_tax=args.amount,
        days_late=args.days or 0,
    )
    print(f"유형: {r['유형']} / 기준: {format_won(r['기준금액'])} / 가산세: {format_won(r['가산세액'])} / 산식: {r['산식']}")


def handle_simplified(args):
    r = calculate_simplified_vat(
        gross_receipts=args.receipts,
        business_type=args.biz_type,
        invoice_purchase=args.invoice_purchase or 0,
        card_sales=args.card_sales or 0,
        prepaid_tax=args.prepaid or 0,
        year=args.year,
    )
    if r['납부면제여부']:
        print(f"공급대가: {format_won(r['공급대가'])} / 납부면제")
    else:
        print(
            f"공급대가: {format_won(r['공급대가'])} / "
            f"부가가치율: {format_rate(r['부가가치율'])} / "
            f"산출세액: {format_won(r['산출세액'])}"
        )
        print(
            f"매입공제(§63③): {format_won(r['매입공제_§63③'])} / "
            f"카드공제(§46): {format_won(r['카드공제_§46'])} / "
            f"공제합계: {format_won(r['공제합계'])}"
        )
        print(
            f"납부세액: {format_won(r['납부세액'])} / "
            f"예정부과: {format_won(r['예정부과세액'])} / "
            f"차가감: {format_won(r['차가감납부세액'])}"
        )


# ── Gap 보강 handlers ──

def handle_recalc(args):
    ratios = [float(x) / 100 for x in args.ratios.split(',')]
    r = recalculate_mixed_use_asset_tax(
        input_tax=args.input_tax,
        original_exempt_ratio=args.original / 100,
        period_exempt_ratios=ratios,
        asset_type=args.asset_type,
    )
    print(f"매입세액: {format_won(r['매입세액'])} / 최초면세: {format_rate(r['최초면세비율'])} / {r['자산유형']}({r['총과세기간수']}기)")
    for d in r['기간별상세']:
        sign = "가산" if d['가감세액'] >= 0 else "차감"
        print(f"  {d['과세기간순서']}기: 면세 {format_rate(d['면세비율'])} / 변동 {d['비율변동']:+.2%} / 잔존 {format_rate(d['잔존비율'])} / {sign} {format_won(abs(d['가감세액']))}")
    print(f"누적가산: {format_won(r['누적가산세액'])} / 누적차감: {format_won(abs(r['누적차감세액']))} / 순: {format_won(r['순가감세액'])}")


def handle_proxy(args):
    methods = None
    if args.methods:
        methods = []
        for item in args.methods.split(';'):
            parts = item.split(',')
            methods.append({'방식': parts[0], '금액': float(parts[1]), '환율': float(parts[2])})
    r = calculate_proxy_payment_tax(
        foreign_amount=args.amount,
        exchange_rates={'기준환율': args.rate},
        payment_methods=methods,
        exempt_ratio=args.exempt_ratio / 100,
    )
    print(
        f"과세표준: {format_won(r['과세표준'])} / "
        f"대리납부: {format_won(r['대리납부세액'])} / "
        f"공제: {format_won(r['공제가능매입세액'])} / "
        f"불공제(면세): {format_won(r['불공제매입세액_면세귀속'])}"
    )


def handle_deemed_limit(args):
    r = calculate_deemed_input_tax_with_limit(
        purchase_amount=args.amount,
        business_type=args.biz_type,
        vat_inclusive=args.vat_inclusive if hasattr(args, 'vat_inclusive') and args.vat_inclusive else False,
        taxable_supply_value=args.taxable or 0,
    )
    print(
        f"의제매입세액: {format_won(r['의제매입세액'])} / "
        f"한도: {format_won(r['한도'])} ({format_rate(r['한도율'])}) / "
        f"최종공제: {format_won(r['최종공제액'])} / "
        f"한도초과: {r['한도초과여부']}"
    )


def handle_local_tax(args):
    r = calculate_local_consumption_tax(vat_payable=args.vat, year=args.year)
    print(
        f"부가세: {format_won(r['부가세납부세액'])} / "
        f"지방소비세({format_rate(r['지방소비세율'])}): {format_won(r['지방소비세'])} / "
        f"총납부: {format_won(r['총납부세액'])}"
    )


# ── parser ──

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="부가가치세 계산 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # Ch05
    p = sub.add_parser("supply-value", help="공급대가 → 공급가액/부가세 분리 (§29)")
    p.add_argument("--total", type=int, required=True, help="금액")
    p.add_argument("--no-vat", action="store_true", help="금액이 VAT 미포함인 경우")
    p.set_defaults(func=handle_supply_value)

    p = sub.add_parser("output-tax", help="매출세액 = 과세표준 × 10% (§30)")
    p.add_argument("--tax-base", type=int, required=True, help="과세표준")
    p.set_defaults(func=handle_output_tax)

    p = sub.add_parser("bad-debt", help="대손세액공제 (§45)")
    p.add_argument("--amount", type=int, required=True, help="대손금액")
    p.add_argument("--no-vat", action="store_true", help="금액이 VAT 미포함인 경우")
    p.set_defaults(func=handle_bad_debt)

    p = sub.add_parser("land-building", help="토지·건물 일괄공급 안분 (§29④)")
    p.add_argument("--total", type=int, required=True, help="총 공급가액")
    p.add_argument("--land-base", type=int, required=True, help="토지 기준시가")
    p.add_argument("--building-base", type=int, required=True, help="건물 기준시가")
    p.set_defaults(func=handle_land_building)

    # Ch06
    p = sub.add_parser("deemed-input", help="의제매입세액공제 (§42, 조특법 §108)")
    p.add_argument("--amount", type=int, required=True, help="면세농산물 매입가액")
    p.add_argument("--biz-type", required=True,
                   choices=["음식점업_개인", "음식점업_법인", "제조업", "제조업_2억이하", "기타"])
    p.add_argument("--vat-inclusive", action="store_true", help="매입가액이 VAT 포함인 경우")
    p.set_defaults(func=handle_deemed_input)

    p = sub.add_parser("card-credit", help="신용카드발행 세액공제 (§46, 조특법 §126의2)")
    p.add_argument("--sales", type=int, required=True, help="신용카드 발행 공급대가")
    p.add_argument("--biz-type", default="일반", choices=["일반", "음식숙박업"])
    p.set_defaults(func=handle_card_credit)

    p = sub.add_parser("payable", help="납부세액 종합계산 (§37)")
    p.add_argument("--output", type=int, required=True, help="매출세액")
    p.add_argument("--input", type=int, required=True, help="공제매입세액")
    p.add_argument("--deemed", type=int, default=0, help="의제매입세액공제")
    p.add_argument("--bad-debt", type=int, default=0, help="대손세액공제")
    p.add_argument("--card-credit", type=int, default=0, help="카드발행세액공제")
    p.add_argument("--e-filing", action="store_true", help="전자신고 세액공제 적용")
    p.set_defaults(func=handle_payable)

    # Ch07
    p = sub.add_parser("common-alloc", help="공통매입세액 안분 (§40)")
    p.add_argument("--common", type=int, required=True, help="공통매입세액")
    p.add_argument("--taxable", type=int, required=True, help="과세공급가액")
    p.add_argument("--exempt", type=int, required=True, help="면세공급가액")
    p.set_defaults(func=handle_common_alloc)

    p = sub.add_parser("settle", help="공통매입세액 정산 (영§61②)")
    p.add_argument("--prelim", type=int, required=True, help="예정신고 면세귀속분")
    p.add_argument("--common", type=int, required=True, help="과세기간 공통매입세액")
    p.add_argument("--taxable", type=int, required=True, help="연간 과세공급가액")
    p.add_argument("--exempt", type=int, required=True, help="연간 면세공급가액")
    p.set_defaults(func=handle_settle)

    # Ch04/Ch08
    p = sub.add_parser("invoice-penalty", help="세금계산서 가산세 (§60)")
    p.add_argument("--supply", type=int, required=True, help="공급가액")
    p.add_argument("--type", required=True,
                   choices=["미발급", "지연발급", "허위기재", "전자미발급", "미수취", "지연수취", "허위수취"])
    p.set_defaults(func=handle_invoice_penalty)

    p = sub.add_parser("prelim-notice", help="예정고지세액 (§48③)")
    p.add_argument("--prior", type=int, required=True, help="직전 과세기간 납부세액")
    p.set_defaults(func=handle_prelim_notice)

    p = sub.add_parser("penalty", help="가산세 계산 (§60)")
    p.add_argument("--type", required=True,
                   choices=["무신고_일반", "무신고_부정", "과소신고_일반", "과소신고_부정",
                            "납부지연", "영세율과표신고불성실"])
    p.add_argument("--amount", type=int, required=True, help="기준금액(세액 또는 과세표준)")
    p.add_argument("--days", type=int, default=0, help="납부지연 경과일수")
    p.set_defaults(func=handle_penalty)

    # Ch09
    p = sub.add_parser("simplified", help="간이과세 납부세액 (§63)")
    p.add_argument("--receipts", type=int, required=True, help="공급대가")
    p.add_argument("--biz-type", required=True,
                   choices=list(__import__('vat_calculator').SIMPLIFIED_VALUE_ADDED_RATES.keys()))
    p.add_argument("--invoice-purchase", type=int, default=0, help="세금계산서 수취 매입 공급대가(VAT포함)")
    p.add_argument("--card-sales", type=int, default=0, help="신용카드+현금영수증 매출액")
    p.add_argument("--prepaid", type=int, default=0, help="예정부과기간 고지세액")
    p.add_argument("--year", type=int, default=2025, help="과세연도")
    p.set_defaults(func=handle_simplified)

    # Gap 보강
    p = sub.add_parser("recalc", help="겸영 감가상각자산 재계산 (§43, 영§63)")
    p.add_argument("--input-tax", type=int, required=True, help="취득 시 공통매입세액")
    p.add_argument("--original", type=float, required=True, help="최초기 면세비율 (%)")
    p.add_argument("--ratios", required=True,
                   help="2기~N기 면세비율(%) 쉼표구분. 예: 46,55,51,56,49")
    p.add_argument("--asset-type", default="부동산", choices=["부동산", "기타"])
    p.set_defaults(func=handle_recalc)

    p = sub.add_parser("proxy", help="대리납부세액 (§52)")
    p.add_argument("--amount", type=float, required=True, help="외화 대가 총액")
    p.add_argument("--rate", type=float, required=True, help="기준환율")
    p.add_argument("--methods", default=None,
                   help="지급방식별 내역. 세미콜론 구분. 예: 보유외화,10000,1420;원화매입,10000,1430")
    p.add_argument("--exempt-ratio", type=float, default=0, help="면세비율 (%)")
    p.set_defaults(func=handle_proxy)

    p = sub.add_parser("deemed-limit", help="의제매입세액 한도 포함 (§42, 조특법 §108)")
    p.add_argument("--amount", type=int, required=True, help="면세농산물 매입가액")
    p.add_argument("--biz-type", required=True,
                   choices=["음식점업_개인", "음식점업_법인", "제조업", "제조업_2억이하", "기타"])
    p.add_argument("--vat-inclusive", action="store_true")
    p.add_argument("--taxable", type=int, default=0, help="과세 공급가액 (한도 산정용)")
    p.set_defaults(func=handle_deemed_limit)

    p = sub.add_parser("local-tax", help="지방소비세 (지방세법 §69)")
    p.add_argument("--vat", type=int, required=True, help="부가세 납부세액")
    p.add_argument("--year", type=int, default=2025, help="귀속연도")
    p.set_defaults(func=handle_local_tax)

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
