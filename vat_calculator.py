"""부가가치세 계산 엔진 — 부가가치세법 기준

Phase 2: Ch05→Ch06→Ch07→Ch09 (핵심 계산) → Ch01~Ch04, Ch08 (판정·안내)
"""

from datetime import date
from typing import Optional


# ──────────────────────────────────────────────
# Ch01. 부가가치세 총설
# ──────────────────────────────────────────────

def is_vat_taxpayer(
    *,
    is_business_operator: bool,
    is_goods_importer: bool = False,
    is_individual: bool = True,
) -> dict:
    """납세의무자 판정 (§2~§3).

    부가가치세 납세의무자:
    1. 사업자: 영리 목적 유무 불문, 사업상 독립적으로 재화·용역 공급하는 자
    2. 재화를 수입하는 자 (사업자 여부 불문)

    Args:
        is_business_operator: 사업상 독립적으로 재화·용역을 공급하는지
        is_goods_importer: 재화를 수입하는지
        is_individual: 개인(True) / 법인(False)

    Returns:
        dict: {납세의무자여부, 사유, 사업자유형}
    """
    reasons = []
    if is_business_operator:
        reasons.append('§3: 사업상 독립적으로 재화·용역을 공급하는 자')
    if is_goods_importer:
        reasons.append('§2②: 재화를 수입하는 자')

    is_taxpayer = len(reasons) > 0
    biz_type = '개인사업자' if is_individual else '법인사업자'

    return {
        '납세의무자여부': is_taxpayer,
        '사유': reasons if reasons else ['납세의무 없음'],
        '사업자유형': biz_type if is_business_operator else '비사업자(수입자)',
    }


def get_vat_tax_period(
    *,
    period_number: int,
    year: int = 2025,
) -> dict:
    """과세기간 (§5).

    1기: 1.1~6.30 (예정 1.1~3.31, 확정 4.1~6.30)
    2기: 7.1~12.31 (예정 7.1~9.30, 확정 10.1~12.31)

    신규사업자: 사업개시일~해당 과세기간 종료일
    폐업자: 폐업일이 속하는 과세기간 개시일~폐업일

    Args:
        period_number: 1 또는 2
        year: 귀속연도

    Returns:
        dict: {과세기간, 예정신고기간, 확정신고기간, 예정신고기한, 확정신고기한}
    """
    if period_number == 1:
        return {
            '과세기간': f'{year}.01.01~{year}.06.30',
            '예정신고기간': f'{year}.01.01~{year}.03.31',
            '확정신고기간': f'{year}.04.01~{year}.06.30',
            '예정신고기한': f'{year}.04.25',
            '확정신고기한': f'{year}.07.25',
        }
    else:
        return {
            '과세기간': f'{year}.07.01~{year}.12.31',
            '예정신고기간': f'{year}.07.01~{year}.09.30',
            '확정신고기간': f'{year}.10.01~{year}.12.31',
            '예정신고기한': f'{year}.10.25',
            '확정신고기한': f'{year+1}.01.25',
        }


# ──────────────────────────────────────────────
# Ch02. 과세거래
# ──────────────────────────────────────────────

DEEMED_SUPPLY_TYPES = {
    '자가공급': '§10①1: 사업자가 자기 사업과 관련하여 생산·취득한 재화를 자기 사업을 위하여 직접 사용·소비',
    '개인적공급': '§10①2: 사업자가 자기 사업과 관련하여 생산·취득한 재화를 사업과 직접 관계없이 자기 개인 또는 그 사용인의 개인적 목적이나 그 밖의 목적을 위하여 사용·소비',
    '사업상증여': '§10①3: 사업자가 자기 사업과 관련하여 생산·취득한 재화를 타인에게 무상으로 공급',
    '폐업잔존재화': '§10②: 폐업 시 잔존하는 재화',
}


def is_deemed_supply(
    *,
    supply_type: str,
    is_for_own_business: bool = False,
) -> dict:
    """간주공급 판정 (§10).

    실제 대가 없이도 공급으로 보는 경우.
    단, 자가공급 중 사업 목적 사용은 과세 제외 (면세전용·비영업용 소형승용차만 해당).

    Args:
        supply_type: DEEMED_SUPPLY_TYPES 키
        is_for_own_business: 자기 과세사업에 직접 사용 여부

    Returns:
        dict: {간주공급여부, 유형, 근거}
    """
    if supply_type == '자가공급' and is_for_own_business:
        return {
            '간주공급여부': False,
            '유형': supply_type,
            '근거': '자기 과세사업 직접 사용은 간주공급 해당 안 됨',
        }

    desc = DEEMED_SUPPLY_TYPES.get(supply_type)
    return {
        '간주공급여부': desc is not None,
        '유형': supply_type,
        '근거': desc or '해당 유형 없음',
    }


# 임직원 증정 비과세 한도 (§10④ 단서, 영§17)
EMPLOYEE_GIFT_CATEGORIES = {
    '경조사': 100_000,   # 1인당 연 10만원
    '명절': 100_000,
    '기념일': 100_000,
    '생일': 100_000,
    '기타': 100_000,
}


def calculate_employee_gift_deemed_supply(
    *,
    gifts: list[dict],
) -> dict:
    """임직원 증정 비과세 한도 판정 (§10④ 단서, 영§17).

    사업상증여(§10①3) 중 임직원에 대한 증정은
    구분별 1인당 연간 10만원 이하인 경우 간주공급 제외.
    초과분만 간주공급 과세.

    Args:
        gifts: 증정 내역 리스트
            각 항목: {
                '수령인': str,
                '구분': '경조사'|'명절'|'기념일'|'생일'|'기타',
                '금액': int,  # 시가 기준
            }

    Returns:
        dict: {
            총증정액, 비과세액, 과세대상액,
            수령인별상세: [{수령인, 구분, 금액, 한도, 비과세, 과세}]
        }
    """
    details = []
    total_gift = 0
    total_exempt = 0
    total_taxable = 0

    # 수령인+구분별 집계
    aggregated: dict[tuple[str, str], int] = {}
    gift_items: dict[tuple[str, str], list[dict]] = {}
    for g in gifts:
        key = (g['수령인'], g['구분'])
        aggregated[key] = aggregated.get(key, 0) + g['금액']
        gift_items.setdefault(key, []).append(g)

    for (recipient, category), amount in aggregated.items():
        limit = EMPLOYEE_GIFT_CATEGORIES.get(category, 100_000)
        exempt = min(amount, limit)
        taxable = max(0, amount - limit)

        details.append({
            '수령인': recipient,
            '구분': category,
            '금액': amount,
            '한도': limit,
            '비과세': exempt,
            '과세': taxable,
        })
        total_gift += amount
        total_exempt += exempt
        total_taxable += taxable

    return {
        '총증정액': total_gift,
        '비과세액': total_exempt,
        '과세대상액': total_taxable,
        '간주공급세액': int(total_taxable * 0.10),
        '수령인별상세': details,
    }


def get_supply_time(
    *,
    transaction_type: str,
) -> dict:
    """공급시기 판정 (§15~§17).

    재화·용역의 공급시기 = 세금계산서 발급 기준일 = 매출세액 귀속시기.

    Args:
        transaction_type: '재화_이동필요' | '재화_이동불필요' | '용역_일반' |
                          '용역_완성도기준' | '중간지급조건' | '장기할부'

    Returns:
        dict: {거래유형, 공급시기, 근거}
    """
    supply_time_map = {
        '재화_이동필요': ('재화가 인도되는 때', '§15①'),
        '재화_이동불필요': ('재화가 이용가능하게 되는 때', '§15②'),
        '용역_일반': ('역무가 제공되는 때 또는 재화·시설물·권리가 사용되는 때', '§16'),
        '용역_완성도기준': ('대가의 각 부분을 받기로 한 때', '§16 단서'),
        '중간지급조건': ('대가의 각 부분을 받기로 한 때', '§17①'),
        '장기할부': ('대가의 각 부분을 받기로 한 때', '§17②'),
    }

    time_desc, article = supply_time_map.get(
        transaction_type,
        ('판정 불가 — 거래유형 확인 필요', ''),
    )

    return {
        '거래유형': transaction_type,
        '공급시기': time_desc,
        '근거': article,
    }


# ──────────────────────────────────────────────
# Ch03. 영세율과 면세
# ──────────────────────────────────────────────

ZERO_RATED_CATEGORIES = {
    '수출재화': '§21①1: 직접 수출, 중계무역 수출, 위탁판매 수출, 외국인도 수출, 위탁가공무역 수출',
    '국외용역': '§22: 국외에서 공급하는 용역',
    '외화획득재화용역': '§23: 외국항행 용역, 외교관 면세물품, 조건부면세 반입물품 등',
    '방위산업물자': '§24: 방위산업에 관한 특별조치법에 의한 물자',
}

VAT_EXEMPT_CATEGORIES = {
    '기초생활필수품': '§26①1: 미가공식료품, 수돗물, 연탄·무연탄',
    '국민후생용역': '§26①2: 의료·교육·여객운송(시내버스 등)',
    '문화관련': '§26①3: 도서·신문·잡지, 예술행사',
    '부동산임대': '§26①4: 주택과 부수토지 임대',
    '금융보험': '§26①5: 금융·보험 용역',
    '인적용역': '§26①6: 저술·강연·전문직·우편',
    '토지': '§26①7: 토지 공급',
    '국가등공급': '§26①8: 국가·지자체 공급',
    '국민주택및부수토지': '§26①9: 국민주택(85㎡ 이하) 및 부수토지',
    '기타_법령지정': '§26①10~: 종교·자선·학술 단체, 묘지관련 등',
}


def is_zero_rated(
    *,
    category: str,
    has_export_evidence: bool = True,
) -> dict:
    """영세율 적용 대상 판정 (§21~§24).

    영세율 = 세율 0% 적용 → 매출세액 0 + 매입세액 전액 환급.
    (면세와 다름: 면세는 매입세액 공제 불가)

    Args:
        category: ZERO_RATED_CATEGORIES 키
        has_export_evidence: 수출 증빙 구비 여부

    Returns:
        dict: {영세율적용, 근거, 매출세액}
    """
    desc = ZERO_RATED_CATEGORIES.get(category)
    if desc is None:
        return {'영세율적용': False, '근거': '해당 카테고리 없음', '매출세액': None}

    if category == '수출재화' and not has_export_evidence:
        return {
            '영세율적용': False,
            '근거': '수출 증빙 미구비 — 일반 과세',
            '매출세액': None,
        }

    return {
        '영세율적용': True,
        '근거': desc,
        '매출세액': 0,
    }


def is_vat_exempt(
    *,
    category: str,
    waiver_filed: bool = False,
) -> dict:
    """면세 대상 판정 (§26~§27).

    면세 = 부가세 면제 → 매출세액 없음 + 매입세액 공제 불가.
    면세사업자는 면세 포기(§27) 신고로 과세사업자 전환 가능.

    Args:
        category: VAT_EXEMPT_CATEGORIES 키
        waiver_filed: 면세 포기 신고 여부

    Returns:
        dict: {면세대상, 근거, 면세포기여부, 최종과세방식}
    """
    desc = VAT_EXEMPT_CATEGORIES.get(category)
    if desc is None:
        return {
            '면세대상': False,
            '근거': '면세 대상 아님 — 일반 과세',
            '면세포기여부': False,
            '최종과세방식': '과세',
        }

    if waiver_filed:
        return {
            '면세대상': True,
            '근거': desc,
            '면세포기여부': True,
            '최종과세방식': '과세 (면세 포기 §27)',
        }

    return {
        '면세대상': True,
        '근거': desc,
        '면세포기여부': False,
        '최종과세방식': '면세',
    }


# ──────────────────────────────────────────────
# Ch04. 세금계산서
# ──────────────────────────────────────────────

INVOICE_PENALTY_RATES = {
    '미발급': 0.02,
    '지연발급': 0.01,
    '허위기재': 0.02,
    '전자미발급': 0.005,
    '미수취': 0.005,
    '지연수취': 0.005,
    '허위수취': 0.02,
}


def calculate_invoice_penalty(
    *,
    supply_value: int,
    violation_type: str,
) -> dict:
    """세금계산서 관련 가산세 계산 (§60②~③).

    Args:
        supply_value: 해당 세금계산서 공급가액
        violation_type: INVOICE_PENALTY_RATES 키

    Returns:
        dict: {공급가액, 위반유형, 가산세율, 가산세액}
    """
    rate = INVOICE_PENALTY_RATES.get(violation_type, 0)
    penalty = int(supply_value * rate)

    return {
        '공급가액': supply_value,
        '위반유형': violation_type,
        '가산세율': rate,
        '가산세액': penalty,
    }


# ──────────────────────────────────────────────
# Ch08. 신고와 납부
# ──────────────────────────────────────────────

def calculate_preliminary_notice(
    *,
    prior_period_tax: int,
) -> dict:
    """예정고지세액 (§48③).

    직전 과세기간 납부세액의 50%를 예정고지.
    개인사업자 중 일정 요건 충족 시 예정고지로 갈음 (예정신고 불요).

    Args:
        prior_period_tax: 직전 과세기간 납부세액

    Returns:
        dict: {직전기납부세액, 예정고지세액}
    """
    notice_amount = int(prior_period_tax * 0.5)
    return {
        '직전기납부세액': prior_period_tax,
        '예정고지세액': notice_amount,
    }


# 예정/확정 신고기간 경계일 (월-일)
_PERIOD_BOUNDARIES = [
    # (시작, 끝, 기간명)
    ((1, 1), (3, 31), '1기예정'),
    ((4, 1), (6, 30), '1기확정'),
    ((7, 1), (9, 30), '2기예정'),
    ((10, 1), (12, 31), '2기확정'),
]


def _get_vat_period(d: date) -> str:
    """날짜가 속하는 부가세 신고기간 반환."""
    for (sm, sd), (em, ed), name in _PERIOD_BOUNDARIES:
        start = date(d.year, sm, sd)
        end = date(d.year, em, ed)
        if start <= d <= end:
            return f"{d.year}-{name}"
    return f"{d.year}-불명"


def classify_preliminary_omission(
    *,
    transactions: list[dict],
) -> dict:
    """예정신고 누락분 판정 (§15~§17, §48).

    공급시기와 세금계산서 발급일이 다른 신고기간에 속하면
    공급시기 기준 귀속기간으로 신고해야 함.
    세금계산서 발급일 기준으로만 신고 시 → 공급시기 귀속기간에서 누락.

    Args:
        transactions: 거래 목록
            각 항목: {
                '거래명': str,
                '공급시기': date,  # 실제 재화/용역 공급일
                '세금계산서발급일': date,
                '공급가액': int,
            }

    Returns:
        dict: {
            총건수, 정상건수, 불일치건수,
            누락위험거래: [{거래명, 공급시기, 발급일, 귀속기간, 발급기간, 공급가액}]
        }
    """
    normal = []
    mismatched = []

    for tx in transactions:
        supply_date = tx['공급시기']
        invoice_date = tx['세금계산서발급일']
        supply_period = _get_vat_period(supply_date)
        invoice_period = _get_vat_period(invoice_date)

        entry = {
            '거래명': tx['거래명'],
            '공급시기': str(supply_date),
            '세금계산서발급일': str(invoice_date),
            '귀속기간': supply_period,
            '발급기간': invoice_period,
            '공급가액': tx['공급가액'],
        }

        if supply_period == invoice_period:
            normal.append(entry)
        else:
            entry['판정'] = f"공급시기({supply_period}) ≠ 발급일({invoice_period}) → {supply_period} 귀속, {invoice_period} 신고 시 누락"
            mismatched.append(entry)

    return {
        '총건수': len(transactions),
        '정상건수': len(normal),
        '불일치건수': len(mismatched),
        '누락위험거래': mismatched,
    }


def calculate_vat_penalties(
    *,
    penalty_type: str,
    tax_base_or_tax: int,
    days_late: int = 0,
) -> dict:
    """부가세 가산세 계산 (§60).

    Args:
        penalty_type: '무신고_일반' | '무신고_부정' | '과소신고_일반' | '과소신고_부정' |
                      '납부지연' | '영세율과표신고불성실'
        tax_base_or_tax: 무/과소신고 시 해당 세액, 납부지연 시 미납세액, 영세율 시 과세표준
        days_late: 납부지연 시 경과일수

    Returns:
        dict: {유형, 기준금액, 가산세액, 산식}
    """
    if penalty_type == '무신고_일반':
        penalty = int(tax_base_or_tax * 0.20)
        formula = '무신고납부세액 × 20%'
    elif penalty_type == '무신고_부정':
        penalty = int(tax_base_or_tax * 0.40)
        formula = '무신고납부세액 × 40%'
    elif penalty_type == '과소신고_일반':
        penalty = int(tax_base_or_tax * 0.10)
        formula = '과소신고납부세액 × 10%'
    elif penalty_type == '과소신고_부정':
        penalty = int(tax_base_or_tax * 0.40)
        formula = '과소신고납부세액 × 40%'
    elif penalty_type == '납부지연':
        daily_rate = 0.00022  # 1일 0.022%
        penalty = int(tax_base_or_tax * daily_rate * days_late)
        formula = f'미납세액 × 0.022% × {days_late}일'
    elif penalty_type == '영세율과표신고불성실':
        penalty = int(tax_base_or_tax * 0.005)
        formula = '영세율과세표준 × 0.5%'
    else:
        penalty = 0
        formula = '해당 없음'

    return {
        '유형': penalty_type,
        '기준금액': tax_base_or_tax,
        '가산세액': penalty,
        '산식': formula,
    }


# ──────────────────────────────────────────────
# Ch05. 과세표준과 매출세액
# ──────────────────────────────────────────────

VAT_RATE = 0.10  # §30: 부가가치세율 10%


def extract_supply_value(total_price: int, *, vat_inclusive: bool = True) -> dict:
    """공급대가에서 공급가액과 부가세를 분리한다.

    §29①: 과세표준 = 공급가액 (부가세 제외)
    공급대가(VAT 포함) = 공급가액 × 110/100
    공급가액 = 공급대가 × 100/110

    Args:
        total_price: 금액 (원)
        vat_inclusive: True면 부가세 포함 금액, False면 공급가액 그 자체

    Returns:
        dict: {공급가액, 부가세액, 공급대가}
    """
    if vat_inclusive:
        supply_value = int(total_price * 100 / 110)
        vat_amount = total_price - supply_value
    else:
        supply_value = int(total_price)
        vat_amount = int(supply_value * VAT_RATE)

    return {
        '공급가액': supply_value,
        '부가세액': vat_amount,
        '공급대가': supply_value + vat_amount,
    }


def calculate_vat_tax_base(
    *,
    supply_values: list[int] | None = None,
    deemed_supply_values: list[int] | None = None,
) -> dict:
    """과세표준 계산 (§29).

    과세표준 = 일반 공급가액 합계 + 간주공급 시가 합계

    Args:
        supply_values: 각 거래별 공급가액(VAT 제외) 리스트
        deemed_supply_values: 간주공급(자가공급·개인적공급 등) 시가 리스트

    Returns:
        dict: {일반공급가액, 간주공급가액, 과세표준}
    """
    normal = sum(supply_values or [])
    deemed = sum(deemed_supply_values or [])
    tax_base = normal + deemed

    return {
        '일반공급가액': normal,
        '간주공급가액': deemed,
        '과세표준': tax_base,
    }


def calculate_vat_output_tax(tax_base: int) -> dict:
    """매출세액 계산 (§30).

    매출세액 = 과세표준 × 10%

    Args:
        tax_base: 과세표준 (원)

    Returns:
        dict: {과세표준, 세율, 매출세액}
    """
    output_tax = int(tax_base * VAT_RATE)
    return {
        '과세표준': tax_base,
        '세율': VAT_RATE,
        '매출세액': output_tax,
    }


def calculate_bad_debt_tax_credit(bad_debt_amount: int, *, vat_inclusive: bool = True) -> dict:
    """대손세액공제 (§45).

    공급일로부터 5년 이내에 대손이 확정된 경우,
    대손세액 = 대손금액(VAT 포함) × 10/110

    Args:
        bad_debt_amount: 대손 확정 금액 (원)
        vat_inclusive: True면 부가세 포함 금액

    Returns:
        dict: {대손금액, 대손세액공제액}
    """
    if vat_inclusive:
        credit = int(bad_debt_amount * 10 / 110)
    else:
        credit = int(bad_debt_amount * VAT_RATE)

    return {
        '대손금액': bad_debt_amount,
        'VAT포함여부': vat_inclusive,
        '대손세액공제액': credit,
    }


def allocate_land_building_supply(
    *,
    total_price: int,
    land_base_price: int,
    building_base_price: int,
) -> dict:
    """토지·건물 일괄공급 시 안분 (§29④, 영§64).

    실지거래가액 중 토지·건물 가액이 불분명한 경우
    기준시가 비율로 안분하여 건물분만 과세표준으로 한다.

    건물 공급가액 = 총 공급가액 × (건물 기준시가 / (토지+건물 기준시가))

    Args:
        total_price: 일괄 공급가액(VAT 제외)
        land_base_price: 토지 기준시가
        building_base_price: 건물 기준시가

    Returns:
        dict: {토지공급가액, 건물공급가액(과세표준), 건물매출세액}
    """
    total_base = land_base_price + building_base_price
    if total_base == 0:
        return {
            '토지공급가액': 0,
            '건물공급가액': 0,
            '건물매출세액': 0,
        }

    building_ratio = building_base_price / total_base
    building_value = int(total_price * building_ratio)
    land_value = total_price - building_value

    return {
        '토지공급가액': land_value,
        '건물공급가액': building_value,
        '건물매출세액': int(building_value * VAT_RATE),
    }


def calculate_foreign_currency_supply(
    *,
    foreign_amount: float,
    exchange_rate_supply_date: float,
    exchange_rate_invoice_date: float | None = None,
) -> dict:
    """외화 공급가액 환산 (§29⑤, 영§62).

    공급시기의 외국환거래법에 의한 기준환율 또는 재정환율 적용.
    세금계산서 발급일의 환율과 공급시기 환율이 다르면 공급시기 환율 적용.

    Args:
        foreign_amount: 외화 금액
        exchange_rate_supply_date: 공급시기 기준환율 (원/외화)
        exchange_rate_invoice_date: 세금계산서 발급일 환율 (참고용)

    Returns:
        dict: {외화금액, 적용환율, 원화공급가액}
    """
    supply_value_krw = int(foreign_amount * exchange_rate_supply_date)
    result = {
        '외화금액': foreign_amount,
        '적용환율': exchange_rate_supply_date,
        '원화공급가액': supply_value_krw,
    }
    if exchange_rate_invoice_date is not None:
        result['세금계산서발급일환율'] = exchange_rate_invoice_date
        result['환율차이'] = exchange_rate_supply_date - exchange_rate_invoice_date
    return result


def calculate_export_supply_value(
    *,
    remitted: list[dict] | None = None,
    unremitted_amount: float = 0,
    base_rate_supply_date: float = 0,
) -> dict:
    """수출 과세표준 환율 세분화 (영§59).

    영§59에 따라 수출재화의 원화환산은 환가 여부에 따라 구분:
      - 환가분(환전완료): 실제 환가한 날의 외국환거래법 기준환율/재정환율
      - 미환가분(미환전): 공급시기의 기준환율/재정환율

    Args:
        remitted: 환가분 목록 [{금액: float, 환율: float, 환가일: str(optional)}]
        unremitted_amount: 미환가 외화 금액
        base_rate_supply_date: 공급시기 기준환율 (미환가분 적용)

    Returns:
        dict: {환가분합계, 미환가분합계, 총원화공급가액, 환가상세}
    """
    remitted = remitted or []

    remitted_details = []
    remitted_total = 0
    for item in remitted:
        krw = int(item['금액'] * item['환율'])
        remitted_details.append({
            '외화금액': item['금액'],
            '환율': item['환율'],
            '원화금액': krw,
            '환가일': item.get('환가일', ''),
        })
        remitted_total += krw

    unremitted_krw = int(unremitted_amount * base_rate_supply_date)

    total = remitted_total + unremitted_krw

    return {
        '환가분합계': remitted_total,
        '환가상세': remitted_details,
        '미환가외화금액': unremitted_amount,
        '미환가적용환율': base_rate_supply_date,
        '미환가분합계': unremitted_krw,
        '총원화공급가액': total,
    }


# ──────────────────────────────────────────────
# Ch06. 매입세액과 납부세액
# ──────────────────────────────────────────────

NON_DEDUCTIBLE_REASONS = {
    '비영업용소형승용차': '§39①2: 비영업용 소형승용차 구입·유지 관련 매입세액',
    '접대비': '§39①3: 접대비 및 이와 유사한 비용 관련 매입세액',
    '면세사업관련': '§39①4: 면세사업과 관련된 매입세액',
    '토지관련': '§39①5: 토지의 자본적 지출 관련 매입세액',
    '사업과무관': '§39①6: 사업과 직접 관련 없는 지출의 매입세액',
    '세금계산서미수취': '§39①1: 세금계산서를 발급받지 아니한 매입세액',
    '사업자등록전': '§39①7: 사업자등록 전 매입세액 (등록 전 20일 이내 제외)',
}


def calculate_vat_input_tax(
    *,
    invoice_input_taxes: list[int] | None = None,
    credit_card_input_taxes: list[int] | None = None,
) -> dict:
    """공제 매입세액 합계 (§38).

    세금계산서상 매입세액 + 신용카드매출전표 등 매입세액

    Args:
        invoice_input_taxes: 세금계산서별 매입세액 리스트
        credit_card_input_taxes: 신용카드매출전표 등 매입세액 리스트

    Returns:
        dict: {세금계산서매입세액, 신용카드등매입세액, 공제매입세액합계}
    """
    invoice_total = sum(invoice_input_taxes or [])
    card_total = sum(credit_card_input_taxes or [])

    return {
        '세금계산서매입세액': invoice_total,
        '신용카드등매입세액': card_total,
        '공제매입세액합계': invoice_total + card_total,
    }


def calculate_vat_non_deductible(
    *,
    items: list[dict],
) -> dict:
    """불공제 매입세액 판정 (§39).

    Args:
        items: [{'사유': str, '매입세액': int}, ...]
            사유: NON_DEDUCTIBLE_REASONS 키 중 하나

    Returns:
        dict: {불공제항목: [...], 불공제매입세액합계}
    """
    details = []
    total = 0
    for item in items:
        reason_key = item['사유']
        amount = item['매입세액']
        details.append({
            '사유': reason_key,
            '근거': NON_DEDUCTIBLE_REASONS.get(reason_key, '미분류'),
            '매입세액': amount,
        })
        total += amount

    return {
        '불공제항목': details,
        '불공제매입세액합계': total,
    }


def calculate_deemed_input_tax(
    *,
    purchase_amount: int,
    business_type: str,
    vat_inclusive: bool = True,
) -> dict:
    """의제매입세액공제 (§42, 조특법 §108).

    면세 농·축·수·임산물을 과세사업에 사용하는 경우 공제.

    업종별 공제율:
        음식점업 (개인): 8/108 (조특법 §108①1)
        음식점업 (법인): 6/106
        제조업: 4/104 (조특법 §108①2, 과세표준 2억 이하: 6/106)
        기타: 2/102

    Args:
        purchase_amount: 면세농산물 등 매입가액 (원)
        business_type: '음식점업_개인' | '음식점업_법인' | '제조업' | '제조업_2억이하' | '기타'
        vat_inclusive: True면 매입가액이 부가세 포함

    Returns:
        dict: {매입가액, 업종, 공제율, 의제매입세액}
    """
    rate_map = {
        '음식점업_개인': (8, 108),
        '음식점업_법인': (6, 106),
        '제조업': (4, 104),
        '제조업_2억이하': (6, 106),
        '기타': (2, 102),
    }
    numerator, denominator = rate_map.get(business_type, (2, 102))

    if vat_inclusive:
        base = int(purchase_amount * 100 / 110)
    else:
        base = purchase_amount

    credit = int(base * numerator / denominator)

    return {
        '매입가액': purchase_amount,
        '업종': business_type,
        '공제율': f'{numerator}/{denominator}',
        '의제매입세액': credit,
    }


def calculate_credit_card_issue_credit(
    *,
    credit_card_sales: int,
    business_type: str = '일반',
) -> dict:
    """신용카드매출전표 발행 세액공제 (§46, 조특법 §126의2).

    일반과세자가 신용카드매출전표를 발행한 경우.
    공제율: 1.3% (음식·숙박업 2.6%)
    한도: 연 1,000만원 (2025 기준)

    Args:
        credit_card_sales: 신용카드 등 발행 공급대가 (VAT 포함)
        business_type: '일반' | '음식숙박업'

    Returns:
        dict: {발행금액, 공제율, 공제액, 한도, 최종공제액}
    """
    if business_type == '음식숙박업':
        rate = 0.026
    else:
        rate = 0.013

    annual_limit = 10_000_000

    raw_credit = int(credit_card_sales * rate)
    final_credit = min(raw_credit, annual_limit)

    return {
        '발행금액': credit_card_sales,
        '공제율': rate,
        '공제액': raw_credit,
        '한도': annual_limit,
        '최종공제액': final_credit,
    }


def calculate_electronic_filing_credit() -> dict:
    """전자신고 세액공제 (조특법 §104의8).

    전자신고 시 1만원 세액공제.

    Returns:
        dict: {공제액}
    """
    return {'공제액': 10_000}


def calculate_vat_payable(
    *,
    output_tax: int,
    deductible_input_tax: int,
    non_deductible_input_tax: int = 0,
    deemed_input_credit: int = 0,
    bad_debt_credit: int = 0,
    card_issue_credit: int = 0,
    electronic_filing_credit: int = 0,
    other_credits: int = 0,
) -> dict:
    """납부세액(환급세액) 계산 (§37).

    납부세액 = 매출세액 - 매입세액(공제분) + 가감조정
    실제 납부세액 = 납부세액 - 각종 세액공제

    Args:
        output_tax: 매출세액
        deductible_input_tax: 공제 매입세액 (불공제 제외한 순액)
        non_deductible_input_tax: 불공제 매입세액 (참고 표시용)
        deemed_input_credit: 의제매입세액공제
        bad_debt_credit: 대손세액공제
        card_issue_credit: 신용카드발행 세액공제
        electronic_filing_credit: 전자신고 세액공제
        other_credits: 기타 세액공제

    Returns:
        dict: 납부세액 상세
    """
    net_vat = output_tax - deductible_input_tax

    total_credits = (
        deemed_input_credit
        + bad_debt_credit
        + card_issue_credit
        + electronic_filing_credit
        + other_credits
    )

    final_payable = net_vat - total_credits

    return {
        '매출세액': output_tax,
        '공제매입세액': deductible_input_tax,
        '불공제매입세액_참고': non_deductible_input_tax,
        '차감납부세액': net_vat,
        '의제매입세액공제': deemed_input_credit,
        '대손세액공제': bad_debt_credit,
        '신용카드발행세액공제': card_issue_credit,
        '전자신고세액공제': electronic_filing_credit,
        '기타세액공제': other_credits,
        '세액공제합계': total_credits,
        '납부할세액': final_payable,
        '환급여부': final_payable < 0,
    }


# ──────────────────────────────────────────────
# Ch07. 겸영사업자
# ──────────────────────────────────────────────

def calculate_common_input_tax_allocation(
    *,
    common_input_tax: int,
    taxable_supply_value: int,
    exempt_supply_value: int,
) -> dict:
    """공통매입세액 안분 (§40, 영§61).

    과세·면세 겸영사업자의 공통매입세액 중 면세사업 귀속분은 불공제.

    면세귀속분 = 공통매입세액 × (면세공급가액 / 총공급가액)
    과세귀속분(공제) = 공통매입세액 - 면세귀속분

    Args:
        common_input_tax: 과세·면세 공통으로 사용된 매입세액
        taxable_supply_value: 과세공급가액 (영세율 포함)
        exempt_supply_value: 면세공급가액

    Returns:
        dict: {공통매입세액, 면세비율, 면세귀속분(불공제), 과세귀속분(공제)}
    """
    total_supply = taxable_supply_value + exempt_supply_value
    if total_supply == 0:
        return {
            '공통매입세액': common_input_tax,
            '면세비율': 0,
            '면세귀속분_불공제': 0,
            '과세귀속분_공제': common_input_tax,
        }

    exempt_ratio = exempt_supply_value / total_supply
    exempt_portion = int(common_input_tax * exempt_ratio)
    taxable_portion = common_input_tax - exempt_portion

    return {
        '공통매입세액': common_input_tax,
        '총공급가액': total_supply,
        '과세공급가액': taxable_supply_value,
        '면세공급가액': exempt_supply_value,
        '면세비율': round(exempt_ratio, 4),
        '면세귀속분_불공제': exempt_portion,
        '과세귀속분_공제': taxable_portion,
    }


def settle_common_input_tax(
    *,
    preliminary_exempt_portion: int,
    annual_taxable_supply: int,
    annual_exempt_supply: int,
    common_input_tax: int,
) -> dict:
    """공통매입세액 정산 — 확정신고 시 (영§61②).

    예정신고 시 안분한 면세귀속분을 확정신고 시 연간 비율로 정산.

    정산 면세귀속분 = 공통매입세액 × (연간 면세공급가액 / 연간 총공급가액)
    추가 불공제(또는 환급) = 정산 면세귀속분 - 예정신고 시 면세귀속분

    Args:
        preliminary_exempt_portion: 예정신고 시 안분한 면세귀속분
        annual_taxable_supply: 연간(확정) 과세공급가액
        annual_exempt_supply: 연간(확정) 면세공급가액
        common_input_tax: 해당 과세기간 공통매입세액 합계

    Returns:
        dict: 정산 결과
    """
    total = annual_taxable_supply + annual_exempt_supply
    if total == 0:
        settled_exempt = 0
    else:
        settled_exempt = int(common_input_tax * annual_exempt_supply / total)

    adjustment = settled_exempt - preliminary_exempt_portion

    return {
        '예정신고_면세귀속분': preliminary_exempt_portion,
        '연간_면세비율': round(annual_exempt_supply / total, 4) if total else 0,
        '정산_면세귀속분': settled_exempt,
        '추가불공제_또는_환급': adjustment,
        '추가불공제여부': adjustment > 0,
    }


def recalculate_vat_on_use_change(
    *,
    original_input_tax: int,
    direction: str,
    elapsed_years: int,
) -> dict:
    """납부세액·환급세액 재계산 — 과세전환·면세전환 (§43, 영§62).

    과세사업에 사용하던 자산을 면세사업으로 전환(또는 반대)할 때
    매입세액의 일부를 가감한다.

    과세→면세 전환: 납부 = 매입세액 × (1 - 경과연수×5%) × (잔존가치율)
                    5년(부동산 10년) 초과 시 재계산 불필요
    면세→과세 전환: 공제 = 동일 산식으로 환급

    Args:
        original_input_tax: 취득 시 매입세액
        direction: '과세→면세' | '면세→과세'
        elapsed_years: 전환 시점까지 경과 연수

    Returns:
        dict: 재계산 결과
    """
    depreciation_rate_per_year = 0.05
    max_years = 5  # 부동산은 10년이지만 기본은 5년
    remaining_ratio = max(0, 1 - elapsed_years * depreciation_rate_per_year)

    recalc_amount = int(original_input_tax * remaining_ratio)

    if direction == '과세→면세':
        label = '추가납부세액'
    else:
        label = '추가환급세액'

    return {
        '원매입세액': original_input_tax,
        '방향': direction,
        '경과연수': elapsed_years,
        '잔존비율': remaining_ratio,
        label: recalc_amount,
    }


# ──────────────────────────────────────────────
# Ch09. 간이과세
# ──────────────────────────────────────────────

SIMPLIFIED_VALUE_ADDED_RATES = {
    '소매업': 0.15,
    '재생용재료수집및판매업': 0.15,
    '음식점업': 0.15,
    '제조업': 0.20,
    '농업_임업_어업': 0.20,
    '숙박업': 0.25,
    '건설업': 0.30,
    '운수및창고업': 0.30,
    '정보통신업': 0.30,
    '금융및보험관련서비스업': 0.30,
    '전문과학및기술서비스업': 0.30,
    '사업시설관리_사업지원및임대서비스업': 0.30,
    '부동산관련서비스업': 0.30,
    '부동산임대업': 0.40,
    '기타서비스업': 0.30,
}


def calculate_simplified_vat(
    *,
    gross_receipts: int,
    business_type: str,
    invoice_purchase: int = 0,
    card_sales: int = 0,
    prepaid_tax: int = 0,
    year: int = 2025,
) -> dict:
    """간이과세자 납부세액 전체 계산 (§63).

    §63②: 산출세액 = 공급대가 × 업종별 부가가치율 × 10%
    §63③: 매입세금계산서 공제 = 세금계산서등 수취 공급대가 × 0.5%
    §46①: 신용카드매출전표 발급 세액공제
    §63⑥: 공제합계 > 산출세액 → 초과분 없음

    납부면제: 해당 과세기간 공급대가 4,800만원 미만 (§69)

    Args:
        gross_receipts: 공급대가 합계 (VAT 포함, 원)
        business_type: SIMPLIFIED_VALUE_ADDED_RATES 키
        invoice_purchase: 세금계산서등 수취분 매입 공급대가 (VAT포함, 원)
        card_sales: 신용카드+현금영수증 매출 발급금액 (원)
        prepaid_tax: 예정부과기간 고지세액 (원)
        year: 과세연도

    Returns:
        dict: {공급대가, 산출세액, 매입공제, 카드공제, 납부세액, ...}
    """
    va_rate = SIMPLIFIED_VALUE_ADDED_RATES.get(business_type, 0.30)
    gross_tax = int(gross_receipts * va_rate * VAT_RATE)
    exempt_from_payment = gross_receipts < 48_000_000

    # §63③: 매입세금계산서등 공제 = 공급대가 × 0.5%
    invoice_credit = int(invoice_purchase * 0.005)

    # §46①: 신용카드매출전표 발급 세액공제
    card_rate = 0.013 if year <= 2026 else 0.01
    card_limit = 10_000_000 if year <= 2026 else 5_000_000
    card_credit_raw = int(card_sales * card_rate)
    card_credit = min(card_credit_raw, card_limit)

    # §63⑥: 공제합계 한도 = 산출세액
    total_credits = invoice_credit + card_credit
    if total_credits > gross_tax:
        # 비례 배분하지 않고 순서대로 적용 후 cap
        total_credits = gross_tax
        card_credit = min(card_credit, gross_tax - invoice_credit)
        if card_credit < 0:
            card_credit = 0
            invoice_credit = gross_tax

    payable = gross_tax - total_credits if not exempt_from_payment else 0

    # 차가감
    final = max(0, payable - prepaid_tax)

    return {
        '공급대가': gross_receipts,
        '업종': business_type,
        '부가가치율': va_rate,
        '산출세액': gross_tax,
        '매입공제_§63③': invoice_credit,
        '카드공제_§46': card_credit,
        '공제합계': invoice_credit + card_credit,
        '납부세액': payable,
        '예정부과세액': prepaid_tax,
        '차가감납부세액': final,
        '납부면제여부': exempt_from_payment,
    }


def calculate_simplified_to_general_inventory_credit(
    *,
    inventory_values: list[dict],
) -> dict:
    """간이→일반 전환 시 재고매입세액 (§64).

    전환 시 보유 재고에 대해 매입세액을 공제받을 수 있다.
    재고매입세액 = 재고품 취득가액(VAT 포함) × 업종별 부가가치율 × 10/110
    (부동산 임대업은 적용 불가)

    Args:
        inventory_values: [{'취득가액': int, '업종': str}, ...]

    Returns:
        dict: {재고항목: [...], 재고매입세액합계}
    """
    details = []
    total = 0
    for item in inventory_values:
        cost = item['취득가액']
        btype = item['업종']
        va_rate = SIMPLIFIED_VALUE_ADDED_RATES.get(btype, 0.30)
        credit = int(cost * va_rate * 10 / 110)
        details.append({
            '취득가액': cost,
            '업종': btype,
            '부가가치율': va_rate,
            '재고매입세액': credit,
        })
        total += credit

    return {
        '재고항목': details,
        '재고매입세액합계': total,
    }


# ──────────────────────────────────────────────
# Gap 보강 — 기출 실증에서 발견된 누락 함수
# ──────────────────────────────────────────────

# Gap 1: §43/영§63 — 겸영 감가상각자산 납부세액 재계산

def recalculate_mixed_use_asset_tax(
    *,
    input_tax: int,
    original_exempt_ratio: float,
    period_exempt_ratios: list[float],
    asset_type: str = '부동산',
) -> dict:
    """겸영사업자 공통사용 감가상각자산 납부세액 재계산 (§41, 영§83).

    과세·면세 겸영사업자가 공통사용 감가상각자산을 취득한 후,
    매 과세기간별 면세비율 변동에 따라 매입세액을 재계산.

    영§83②: 재계산 산식 (영§66② 준용)
      가감세액 = 매입세액 × (해당기 면세비율 - 기준 면세비율)
                 × (잔존 과세기간수 / 총 과세기간수)

      면세비율 증가 → 가산(납부세액 증가)
      면세비율 감소 → 차감(납부세액 감소)

    영§83①: 기준비율 대비 5% 이상 차이 시에만 재계산 적용
    영§66② 준용: 경과 과세기간수 한도
      건물·구축물: 20기 (10년 × 2)
      기타 감가상각자산: 4기 (2년 × 2)

    Args:
        input_tax: 취득 시 공통매입세액 (건물 등)
        original_exempt_ratio: 최초 과세기간 면세비율 (0~1)
        period_exempt_ratios: 2번째 과세기간부터 각 기의 면세비율 리스트
            (최초기 제외, 재계산 대상 기간만)
        asset_type: '부동산' (20기) | '기타' (4기)

    Returns:
        dict: {기간별상세: [...], 누적가산세액, 누적차감세액, 순가감세액}
    """
    total_periods = 20 if asset_type == '부동산' else 4

    details = []
    cumulative_add = 0
    cumulative_sub = 0
    basis_ratio = original_exempt_ratio  # 영§83①: 재계산 시 기준비율 갱신

    for i, exempt_ratio in enumerate(period_exempt_ratios):
        period_no = i + 2  # 2번째 과세기간부터
        remaining = total_periods - (period_no - 1)
        if remaining <= 0:
            break

        remaining_ratio = remaining / total_periods
        diff = exempt_ratio - basis_ratio

        # 영§83①: 5% 이상 차이 시에만 재계산 적용
        if abs(diff) < 0.05:
            entry = {
                '과세기간순서': period_no,
                '면세비율': round(exempt_ratio, 4),
                '기준비율': round(basis_ratio, 4),
                '비율변동': round(diff, 4),
                '잔존비율': round(remaining_ratio, 4),
                '가감세액': 0,
                '비고': '5%미만_미적용',
            }
            details.append(entry)
            continue

        adjustment = int(input_tax * diff * remaining_ratio)

        entry = {
            '과세기간순서': period_no,
            '면세비율': round(exempt_ratio, 4),
            '기준비율': round(basis_ratio, 4),
            '비율변동': round(diff, 4),
            '잔존비율': round(remaining_ratio, 4),
            '가감세액': adjustment,
        }
        details.append(entry)

        if adjustment > 0:
            cumulative_add += adjustment
        else:
            cumulative_sub += adjustment

        # 영§83①: 재계산한 기간의 비율이 다음 기준비율이 됨
        basis_ratio = exempt_ratio

    net = cumulative_add + cumulative_sub

    return {
        '매입세액': input_tax,
        '최초면세비율': original_exempt_ratio,
        '자산유형': asset_type,
        '총과세기간수': total_periods,
        '기간별상세': details,
        '누적가산세액': cumulative_add,
        '누적차감세액': cumulative_sub,
        '순가감세액': net,
    }


# Gap 2: §52 — 대리납부

def calculate_proxy_payment_tax(
    *,
    foreign_amount: float,
    exchange_rates: dict,
    payment_methods: list[dict] | None = None,
    exempt_ratio: float = 0.0,
) -> dict:
    """국외사업자 용역 대리납부세액 (§52).

    국내사업장 없는 국외사업자로부터 용역 공급받을 때,
    공급받는 자가 부가세를 대리납부.

    과세표준 = 대가 × 기준환율 (영§87의2)
    대리납부세액 = 과세표준 × 10%

    겸영사업자의 경우 공통사용 시 면세귀속분은 매입세액 공제 불가.

    Args:
        foreign_amount: 외화 대가 총액
        exchange_rates: {
            '기준환율': float,         # 대가 지급일 기준
            '대고객매도율': float,      # optional
            '대고객매입율': float,      # optional
        }
        payment_methods: 지급 방식별 내역 (없으면 전액 기준환율)
            [{'방식': '보유외화'|'원화매입', '금액': float, '환율': float}, ...]
        exempt_ratio: 면세비율 (겸영 공통사용 시, 0~1)

    Returns:
        dict: {과세표준, 대리납부세액, 공제가능매입세액, 불공제매입세액(면세귀속)}
    """
    if payment_methods:
        tax_base = 0
        for pm in payment_methods:
            tax_base += int(pm['금액'] * pm['환율'])
    else:
        base_rate = exchange_rates.get('기준환율', 0)
        tax_base = int(foreign_amount * base_rate)

    proxy_tax = int(tax_base * VAT_RATE)
    non_deductible = int(proxy_tax * exempt_ratio)
    deductible = proxy_tax - non_deductible

    return {
        '외화대가': foreign_amount,
        '과세표준': tax_base,
        '대리납부세액': proxy_tax,
        '면세비율': exempt_ratio,
        '공제가능매입세액': deductible,
        '불공제매입세액_면세귀속': non_deductible,
    }


# Gap 3: 의제매입세액 한도 (조특법 §108②)

def calculate_deemed_input_tax_with_limit(
    *,
    purchase_amount: int,
    business_type: str,
    vat_inclusive: bool = False,
    taxable_supply_value: int = 0,
    prior_year_deemed_credit: int = 0,
) -> dict:
    """의제매입세액공제 — 한도 포함 (§42, 조특법 §108).

    한도 = 과세표준(매출세액 기초) × 업종별 한도율

    업종별 한도율:
        음식점업(개인, 과세표준 2억 이하): 75%
        음식점업(개인, 과세표준 2억 초과): 65%
        음식점업(법인): 45%
        제조업(과세표준 2억 이하): 65%
        제조업(과세표준 2억 초과): 55%
        기타: 40% → 2024 이후 면세농산물 직접 수출 포함

    ※ 한도율은 매출세액 × 한도율, 즉 (과세표준 × 10%) × 한도율

    Args:
        purchase_amount: 면세농산물 등 매입가액
        business_type: '음식점업_개인' | '음식점업_법인' | '제조업' | '제조업_2억이하' | '기타'
        vat_inclusive: 매입가액 VAT 포함 여부
        taxable_supply_value: 해당 과세기간 과세 공급가액 (한도 산정용)
        prior_year_deemed_credit: 직전연도 의제매입세액 (이월 한도용, 미사용)

    Returns:
        dict: {의제매입세액, 한도, 최종공제액, 한도초과여부}
    """
    # 기본 의제매입세액 계산
    rate_map = {
        '음식점업_개인': (8, 108),
        '음식점업_법인': (6, 106),
        '제조업': (4, 104),
        '제조업_2억이하': (6, 106),
        '기타': (2, 102),
    }
    numerator, denominator = rate_map.get(business_type, (2, 102))

    if vat_inclusive:
        base = int(purchase_amount * 100 / 110)
    else:
        base = purchase_amount

    raw_credit = int(base * numerator / denominator)

    # 한도 계산
    limit_rate_map = {
        '음식점업_개인': 0.75 if taxable_supply_value <= 200_000_000 else 0.65,
        '음식점업_법인': 0.45,
        '제조업': 0.55,
        '제조업_2억이하': 0.65,
        '기타': 0.40,
    }
    limit_rate = limit_rate_map.get(business_type, 0.40)
    output_tax = int(taxable_supply_value * VAT_RATE)
    limit = int(output_tax * limit_rate)

    final_credit = min(raw_credit, limit) if taxable_supply_value > 0 else raw_credit

    return {
        '매입가액': purchase_amount,
        '업종': business_type,
        '공제율': f'{numerator}/{denominator}',
        '의제매입세액': raw_credit,
        '과세공급가액': taxable_supply_value,
        '매출세액': output_tax,
        '한도율': limit_rate,
        '한도': limit,
        '최종공제액': final_credit,
        '한도초과여부': raw_credit > limit if taxable_supply_value > 0 else False,
    }


# Gap 5: 지방소비세

def calculate_local_consumption_tax(
    *,
    vat_payable: int,
    year: int = 2025,
) -> dict:
    """지방소비세 (지방세법 §69).

    부가가치세 납부세액에 대해 지방소비세를 추가 납부.

    세율 변천:
        2014~2018: 부가세의 11%
        2019: 15%
        2020~2023: 21%
        2024~: 25.3% (지방세법 §69①, 2024.1.1 시행)

    ※ 시험 문제에서는 "지방소비세 포함" 시 해당 연도 세율 적용

    Args:
        vat_payable: 부가가치세 납부세액 (음수면 환급)
        year: 귀속연도

    Returns:
        dict: {부가세납부세액, 지방소비세율, 지방소비세, 총납부세액}
    """
    if year >= 2024:
        rate = 0.253
    elif year >= 2020:
        rate = 0.21
    elif year == 2019:
        rate = 0.15
    else:
        rate = 0.11

    local_tax = int(vat_payable * rate)
    total = vat_payable + local_tax

    return {
        '부가세납부세액': vat_payable,
        '지방소비세율': rate,
        '지방소비세': local_tax,
        '총납부세액': total,
    }
