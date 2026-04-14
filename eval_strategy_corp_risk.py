"""CPA 2차 기출 Q5 (법인세) → strategy_engine 리스크 규칙 회귀.

ROADMAP 5-A-4: 기출 서술형 사례를 입력 프로필로 재활용하여
임원상여금 한도초과·부당행위계산부인 리스크 규칙이 정확히 발동하는지 검증.

대상 사례:
- CPA 2025 Q5: 임원상여금 한도초과(상여 지급기준 결의액 초과)
- CPA 2024 Q5: 특수관계자 고가매입(실권주 재배정 맥락, 최대매입가 6,194,999,999)
- 정상 케이스: 시가 범위 내 매입·결의 한도 내 상여 → 비발동
"""

from __future__ import annotations

from strategy_engine import run
from strategy_engine.catalog import load_all
from strategy_engine.simulator import corp_rate_exposure


# --- profile fixtures ------------------------------------------------------

def profile_cpa2025_q5_bonus_excess():
    """임원상여 지급기준 결의 3억, 실지급 4억 → 1억 초과분."""
    return {
        "is_corporation": True,
        "corp_tax_rate": 0.19,
        "executive_bonus_paid": 400_000_000,
        "executive_bonus_resolution_amount": 300_000_000,
        # 부당행위 요소는 없음
        "related_party_purchase_price": 0,
        "related_party_market_price": 0,
    }


def profile_cpa2024_q5_unfair_high_price():
    """CPA 2024 Q5 정답의 "최대매입가 6,194,999,999"는 시가 5,900M × 1.05 - 1원 =
    부당행위 미해당 상한선. 상한을 초과해 매입한 경우를 시나리오화한다.
    6,500M 매입가 → 시가 대비 10.2% 초과로 명백한 부당행위.
    """
    return {
        "is_corporation": True,
        "corp_tax_rate": 0.19,
        "related_party_purchase_price": 6_500_000_000,
        "related_party_market_price": 5_900_000_000,
        "executive_bonus_paid": 0,
        "executive_bonus_resolution_amount": 0,
    }


def profile_clean_corporation():
    """정상 법인: 결의 한도 준수·시가 매입."""
    return {
        "is_corporation": True,
        "corp_tax_rate": 0.19,
        "executive_bonus_paid": 250_000_000,
        "executive_bonus_resolution_amount": 300_000_000,
        "related_party_purchase_price": 1_000_000_000,
        "related_party_market_price": 1_000_000_000,
    }


def profile_individual_taxpayer():
    """개인 소득세 프로필 — 법인세 리스크 규칙 절대 발동 금지."""
    return {
        "has_earned_income": True,
        "gross_salary": 50_000_000,
        "interest_income": 0,
        "dividend_income": 0,
        "financial_income_total": 0,
    }


# --- tests -----------------------------------------------------------------

def test_corporate_rules_loaded():
    ids = {r.id for r in load_all()}
    assert "CORP_EXECUTIVE_BONUS_EXCESS" in ids
    assert "CORP_UNFAIR_HIGH_PRICE_PURCHASE" in ids


def test_bonus_excess_triggers_on_cpa2025_q5():
    result = run(profile_cpa2025_q5_bonus_excess())
    ids = {c["rule"].id for c in result["candidates"]}
    assert "CORP_EXECUTIVE_BONUS_EXCESS" in ids
    assert "CORP_UNFAIR_HIGH_PRICE_PURCHASE" not in ids

    c = next(x for x in result["candidates"] if x["rule"].id == "CORP_EXECUTIVE_BONUS_EXCESS")
    expected = corp_rate_exposure(100_000_000, 0.19)
    assert expected == 19_000_000, f"공식 검증: {expected}"
    assert c["saving"] == expected
    assert c["risk"]["level"] == "high"
    assert "세무조사_트리거" in c["risk"]["flags"]


def test_unfair_purchase_triggers_on_cpa2024_q5():
    result = run(profile_cpa2024_q5_unfair_high_price())
    ids = {c["rule"].id for c in result["candidates"]}
    assert "CORP_UNFAIR_HIGH_PRICE_PURCHASE" in ids
    assert "CORP_EXECUTIVE_BONUS_EXCESS" not in ids

    c = next(x for x in result["candidates"] if x["rule"].id == "CORP_UNFAIR_HIGH_PRICE_PURCHASE")
    excess = 6_500_000_000 - 5_900_000_000  # 600,000,000
    expected = corp_rate_exposure(excess, 0.19)
    assert expected == 114_000_000, f"공식 검증: {expected}"
    assert c["saving"] == expected
    assert c["risk"]["level"] == "high"
    assert "소득처분_배당" in c["risk"]["flags"]


def test_clean_corporation_no_risk_fires():
    result = run(profile_clean_corporation())
    ids = {c["rule"].id for c in result["candidates"]}
    assert "CORP_EXECUTIVE_BONUS_EXCESS" not in ids
    assert "CORP_UNFAIR_HIGH_PRICE_PURCHASE" not in ids


def test_individual_profile_does_not_trigger_corporate_rules():
    """개인 프로필에 법인세 규칙 오발동 방지 (스코프 격리)."""
    result = run(profile_individual_taxpayer())
    ids = {c["rule"].id for c in result["candidates"]}
    assert "CORP_EXECUTIVE_BONUS_EXCESS" not in ids
    assert "CORP_UNFAIR_HIGH_PRICE_PURCHASE" not in ids


def test_corporate_profile_does_not_trigger_income_tax_rules():
    """법인 프로필에 소득세 규칙 오발동 방지."""
    result = run(profile_cpa2025_q5_bonus_excess())
    ids = {c["rule"].id for c in result["candidates"]}
    for rid in ("FIN_SEPARATION_2000", "CRED_MONTHLY_RENT", "DED_PENSION_IRP_700",
                "TIMING_MEDICAL_EXPENSE", "BOOK_DOUBLE_ENTRY_4800"):
        assert rid not in ids, f"{rid} 가 법인 프로필에서 잘못 발동"


def test_high_price_threshold_5pct_boundary():
    """시가 대비 4.99% 초과는 비발동, 5% 이상은 발동."""
    below = {
        "is_corporation": True,
        "corp_tax_rate": 0.19,
        "related_party_purchase_price": 1_049_000_000,  # 4.9% 초과
        "related_party_market_price": 1_000_000_000,
    }
    above = {
        "is_corporation": True,
        "corp_tax_rate": 0.19,
        "related_party_purchase_price": 1_050_000_000,  # 정확히 5.0%
        "related_party_market_price": 1_000_000_000,
    }
    r1 = run(below)
    r2 = run(above)
    assert "CORP_UNFAIR_HIGH_PRICE_PURCHASE" not in {c["rule"].id for c in r1["candidates"]}
    assert "CORP_UNFAIR_HIGH_PRICE_PURCHASE" in {c["rule"].id for c in r2["candidates"]}


def test_trace_dump_identifies_failing_clause():
    """정상 법인에서 어느 조항이 False 였는지 trace 로 설명 가능."""
    from strategy_engine.catalog import load_all
    from strategy_engine.dsl import evaluate
    from strategy_engine.profile_builder import build_profile

    rule = next(r for r in load_all() if r.id == "CORP_EXECUTIVE_BONUS_EXCESS")
    profile = build_profile(profile_clean_corporation())
    _, trace = evaluate(rule.applies_when, profile)
    assert trace["result"] is False
    # 결의 한도(3억) >= 지급액(2.5억) → paid > resolution 조건 false
    last_clause = trace["of"][-1]
    assert last_clause["op"] == ">"
    assert last_clause["left_value"] == 250_000_000
    assert last_clause["right_value"] == 300_000_000
    assert last_clause["result"] is False


if __name__ == "__main__":
    tests = [
        ("corporate rules loaded", test_corporate_rules_loaded),
        ("bonus excess CPA2025 Q5", test_bonus_excess_triggers_on_cpa2025_q5),
        ("unfair purchase CPA2024 Q5", test_unfair_purchase_triggers_on_cpa2024_q5),
        ("clean corp no risk", test_clean_corporation_no_risk_fires),
        ("individual scope isolation", test_individual_profile_does_not_trigger_corporate_rules),
        ("corporate scope isolation", test_corporate_profile_does_not_trigger_income_tax_rules),
        ("5pct boundary", test_high_price_threshold_5pct_boundary),
        ("trace dump", test_trace_dump_identifies_failing_clause),
    ]
    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"[PASS] {name}")
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {name}: {e}")
        except Exception as e:
            import traceback
            print(f"[ERR ] {name}: {e!r}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} passed")
    if passed != len(tests):
        raise SystemExit(1)
