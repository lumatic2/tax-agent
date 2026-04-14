"""비상장주식 평가 — 상증법 제63조 보충적 평가방법.

증여·상속·부당행위계산부인 등 시가 미확인 케이스에서
순손익가치와 순자산가치를 가중평균하여 1주당 가액을 산출한다.

참조:
- 상증법 §60 (평가의 원칙)
- 상증법 §63 ①1나 (비상장주식)
- 상증법시행령 §54 (순손익가치·순자산가치의 가중평균)
- 상증법시행령 §55 (순자산가치의 계산)
- 상증법시행령 §56 (순손익가치의 계산)
"""

from __future__ import annotations

from dataclasses import dataclass


# 순손익 환원율 (상증법시행령 §54①: 기획재정부장관 고시 — 현행 10%)
CAPITALIZATION_RATE = 0.10


@dataclass(frozen=True)
class ValuationInput:
    """평가 입력값."""

    shares_outstanding: int                # 발행주식수
    net_profit_y1: int                     # 직전 1년 순손익 (가중치 3)
    net_profit_y2: int                     # 직전 2년 순손익 (가중치 2)
    net_profit_y3: int                     # 직전 3년 순손익 (가중치 1)
    total_assets: int                      # 자산총액 (평가기준일)
    total_liabilities: int                 # 부채총액
    real_estate_ratio: float = 0.0         # 부동산 비중 (자산대비)


@dataclass(frozen=True)
class ValuationResult:
    per_share_value: int                   # 1주당 평가액 (원)
    net_profit_value: int                  # 1주당 순손익가치
    net_asset_value: int                   # 1주당 순자산가치
    weight_profit: int                     # 가중치(순손익)
    weight_asset: int                      # 가중치(순자산)
    method: str                            # "일반" | "부동산과다_50_80" | "부동산과다_80이상"
    lower_bound_applied: bool              # 80% 하한 적용 여부


def _per_share_net_profit_float(
    net_profit_y1: int,
    net_profit_y2: int,
    net_profit_y3: int,
    shares_outstanding: int,
    capitalization_rate: float = CAPITALIZATION_RATE,
) -> float:
    if shares_outstanding <= 0:
        return 0.0
    weighted = (
        int(net_profit_y1) * 3
        + int(net_profit_y2) * 2
        + int(net_profit_y3) * 1
    ) / 6.0
    return (weighted / shares_outstanding) / float(capitalization_rate)


def _per_share_net_asset_float(
    total_assets: int,
    total_liabilities: int,
    shares_outstanding: int,
) -> float:
    if shares_outstanding <= 0:
        return 0.0
    net_asset = max(int(total_assets) - int(total_liabilities), 0)
    return net_asset / shares_outstanding


def per_share_net_profit_value(
    net_profit_y1: int,
    net_profit_y2: int,
    net_profit_y3: int,
    shares_outstanding: int,
    capitalization_rate: float = CAPITALIZATION_RATE,
) -> int:
    """1주당 순손익가치 (직전3년 가중평균 순이익을 10% 환원)."""
    return int(_per_share_net_profit_float(
        net_profit_y1, net_profit_y2, net_profit_y3,
        shares_outstanding, capitalization_rate,
    ))


def per_share_net_asset_value(
    total_assets: int,
    total_liabilities: int,
    shares_outstanding: int,
) -> int:
    """1주당 순자산가치 = (자산 − 부채) / 발행주식수."""
    return int(_per_share_net_asset_float(total_assets, total_liabilities, shares_outstanding))


def _weights(real_estate_ratio: float) -> tuple[int, int, str]:
    """부동산 비중별 (w_profit, w_asset, method_label) 반환."""
    r = float(real_estate_ratio or 0.0)
    if r >= 0.80:
        return 0, 1, "부동산과다_80이상"     # 순자산가치만 사용
    if r >= 0.50:
        return 2, 3, "부동산과다_50_80"       # 2:3 가중
    return 3, 2, "일반"                        # 3:2 가중


def evaluate_unlisted_stock(inp: ValuationInput) -> ValuationResult:
    """비상장주식 1주당 평가액 산출.

    원칙: (순손익가치 × w1 + 순자산가치 × w2) / (w1 + w2)
    하한: 순자산가치 × 80%
    부동산과다(80%↑)는 순자산가치만 인정.
    """
    profit_f = _per_share_net_profit_float(
        inp.net_profit_y1, inp.net_profit_y2, inp.net_profit_y3,
        inp.shares_outstanding,
    )
    asset_f = _per_share_net_asset_float(
        inp.total_assets, inp.total_liabilities, inp.shares_outstanding,
    )

    w_profit, w_asset, method = _weights(inp.real_estate_ratio)
    denom = w_profit + w_asset
    weighted_avg_f = (profit_f * w_profit + asset_f * w_asset) / max(denom, 1)

    lower_bound_f = asset_f * 0.80
    applied_lower = weighted_avg_f < lower_bound_f
    per_share = int(max(weighted_avg_f, lower_bound_f))

    return ValuationResult(
        per_share_value=per_share,
        net_profit_value=int(profit_f),
        net_asset_value=int(asset_f),
        weight_profit=w_profit,
        weight_asset=w_asset,
        method=method,
        lower_bound_applied=applied_lower,
    )


# --- 간이 회귀 테스트 ------------------------------------------------------

def _test_general_weighting():
    """일반법인: 순손익 3:2 가중."""
    r = evaluate_unlisted_stock(ValuationInput(
        shares_outstanding=100_000,
        net_profit_y1=3_000_000_000,
        net_profit_y2=2_000_000_000,
        net_profit_y3=1_000_000_000,
        total_assets=20_000_000_000,
        total_liabilities=5_000_000_000,
        real_estate_ratio=0.30,
    ))
    # 가중평균 순이익 = (3*3 + 2*2 + 1*1)*1e9 / 6 = 14e9/6 ≈ 2.333e9
    # 1주당 순이익 = 2.333e9 / 100,000 = 23,333 → /0.10 = 233,333
    # 순자산 = 15e9 / 100,000 = 150,000
    # 가중평균 = (233,333×3 + 150,000×2)/5 = (700k + 300k)/5 = 200,000
    assert r.method == "일반"
    assert r.net_profit_value == 233_333
    assert r.net_asset_value == 150_000
    assert r.per_share_value == 200_000
    assert not r.lower_bound_applied


def _test_real_estate_50_80_reverse_weight():
    """부동산 50~80%: 가중치 순손익 2, 순자산 3."""
    r = evaluate_unlisted_stock(ValuationInput(
        shares_outstanding=100_000,
        net_profit_y1=1_000_000_000,
        net_profit_y2=1_000_000_000,
        net_profit_y3=1_000_000_000,
        total_assets=20_000_000_000,
        total_liabilities=0,
        real_estate_ratio=0.60,
    ))
    # 순손익가치 = 1e9/100k / 0.1 = 100,000
    # 순자산가치 = 20e9/100k = 200,000
    # 가중 = (100k×2 + 200k×3)/5 = (200k+600k)/5 = 160,000
    assert r.method == "부동산과다_50_80"
    assert r.per_share_value == 160_000


def _test_real_estate_over_80_asset_only():
    """부동산 80%↑: 순자산가치 단독."""
    r = evaluate_unlisted_stock(ValuationInput(
        shares_outstanding=100_000,
        net_profit_y1=5_000_000_000,
        net_profit_y2=5_000_000_000,
        net_profit_y3=5_000_000_000,
        total_assets=20_000_000_000,
        total_liabilities=0,
        real_estate_ratio=0.85,
    ))
    # 순자산가치 = 200,000 단독 (순손익가치 무시)
    assert r.method == "부동산과다_80이상"
    assert r.per_share_value == 200_000


def _test_lower_bound_80pct_of_asset():
    """순이익 미미·순자산 큰 경우 — 순자산가치 80% 하한 적용."""
    r = evaluate_unlisted_stock(ValuationInput(
        shares_outstanding=100_000,
        net_profit_y1=0,
        net_profit_y2=0,
        net_profit_y3=0,
        total_assets=10_000_000_000,
        total_liabilities=0,
        real_estate_ratio=0.30,
    ))
    # 순손익가치 0, 순자산가치 100,000
    # 가중평균 = (0×3 + 100k×2)/5 = 40,000
    # 하한 = 100k × 0.80 = 80,000 → 적용
    assert r.per_share_value == 80_000
    assert r.lower_bound_applied


def _test_zero_shares_guard():
    r = evaluate_unlisted_stock(ValuationInput(
        shares_outstanding=0,
        net_profit_y1=100, net_profit_y2=100, net_profit_y3=100,
        total_assets=1_000_000, total_liabilities=0,
        real_estate_ratio=0.0,
    ))
    assert r.per_share_value == 0
    assert r.net_profit_value == 0
    assert r.net_asset_value == 0


if __name__ == "__main__":
    tests = [
        ("general 3:2", _test_general_weighting),
        ("real estate 50~80 → 2:3", _test_real_estate_50_80_reverse_weight),
        ("real estate 80↑ asset only", _test_real_estate_over_80_asset_only),
        ("80% lower bound", _test_lower_bound_80pct_of_asset),
        ("zero shares guard", _test_zero_shares_guard),
    ]
    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"[PASS] {name}")
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {name}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    if passed != len(tests):
        raise SystemExit(1)
