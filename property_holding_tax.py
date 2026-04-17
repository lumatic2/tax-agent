"""종합부동산세(보유세) 계산 엔진.

종부세법 §8~§9의2, 2026년 개정 기준.

과세표준 = (공시가 합계 - 공제금액) × 공정시장가액비율(60%)
공제금액:
  - 1세대 1주택: 12억
  - 일반(단독): 9억
  - 부부 공동명의(1주택 특례 미선택): 각 9억 = 18억
세율: 일반(2주택 이하) / 중과(3주택 이상) 누진.
1세대 1주택 세액공제: 고령(60/65/70 → 20/30/40%) + 장기보유(5/10/15 → 20/40/50%), 합산 한도 80%.
"""

from __future__ import annotations

PROPERTY_FAIR_RATIO = 0.60

# (upper, rate, progressive_deduction)
_GENERAL_BRACKETS = [
    (300_000_000, 0.005, 0),
    (600_000_000, 0.007, 600_000),
    (1_200_000_000, 0.010, 1_500_000),
    (2_500_000_000, 0.013, 3_300_000),
    (5_000_000_000, 0.015, 5_900_000),
    (9_400_000_000, 0.020, 18_400_000),
    (None, 0.027, 49_200_000),
]

_HEAVY_BRACKETS = [
    (300_000_000, 0.005, 0),
    (600_000_000, 0.007, 600_000),
    (1_200_000_000, 0.010, 1_500_000),
    (2_500_000_000, 0.020, 7_500_000),
    (5_000_000_000, 0.030, 20_500_000),
    (9_400_000_000, 0.040, 45_500_000),
    (None, 0.050, 89_500_000),
]


def _progressive(base: int, brackets) -> int:
    for upper, rate, deduction in brackets:
        if upper is None or base <= upper:
            return int(max(base * rate - deduction, 0))
    return 0


def calculate_housing_cht(
    total_published_price: int,
    house_count: int = 1,
    is_one_house_household: bool = False,
    is_spouse_joint: bool = False,
) -> dict:
    """주택분 종부세 산출세액 계산.

    Args:
        total_published_price: 공시가 합계(원)
        house_count: 소유 주택 수 (3 이상 시 중과세율)
        is_one_house_household: 1세대 1주택 특례 여부(공제 12억)
        is_spouse_joint: 부부 공동명의(각 9억 공제 = 18억). 1주택 특례와 배타.
    """
    total = int(total_published_price or 0)
    if is_spouse_joint:
        deduction_total = 1_800_000_000
    elif is_one_house_household:
        deduction_total = 1_200_000_000
    else:
        deduction_total = 900_000_000

    taxable_base = int(max(total - deduction_total, 0) * PROPERTY_FAIR_RATIO)
    brackets = _HEAVY_BRACKETS if int(house_count or 0) >= 3 else _GENERAL_BRACKETS
    tax = _progressive(taxable_base, brackets)

    return {
        "공시가합계": total,
        "공제금액": deduction_total,
        "과세표준": taxable_base,
        "적용세율표": "중과" if int(house_count or 0) >= 3 else "일반",
        "산출세액": tax,
        "농특세": int(tax * 0.20),
    }


def _age_credit_rate(age: int) -> float:
    a = int(age or 0)
    if a >= 70:
        return 0.40
    if a >= 65:
        return 0.30
    if a >= 60:
        return 0.20
    return 0.0


def _holding_credit_rate(years: int) -> float:
    y = int(years or 0)
    if y >= 15:
        return 0.50
    if y >= 10:
        return 0.40
    if y >= 5:
        return 0.20
    return 0.0


def calculate_one_house_credit(tax: int, owner_age: int = 0, holding_years: int = 0) -> int:
    """1세대 1주택 고령·장기보유 세액공제액 (한도 80%)."""
    t = int(max(int(tax or 0), 0))
    if t <= 0:
        return 0
    rate = min(_age_credit_rate(owner_age) + _holding_credit_rate(holding_years), 0.80)
    return int(t * rate)
