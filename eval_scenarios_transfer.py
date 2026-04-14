"""양도소득세 복합 시나리오 회귀 (Phase 7 규칙 조합 검증).

단일 규칙 A/B 페어는 eval_strategy_catalog_v1.py 에서 커버. 여기서는
실제 사용자 프로파일을 모사한 복합 케이스에서 Phase 7 14규칙이
의도대로 조합·발동되는지 검증한다.

각 시나리오:
- profile: 실제 사용자 질문 모사
- expected_fire: 반드시 발동해야 할 규칙 id
- expected_skip: 반드시 비발동해야 할 규칙 id
- min_total_saving: 합산 절세액 하한
"""

from __future__ import annotations

from strategy_engine import run


def _ids(cands):
    return {c["rule"].id for c in cands}


def _total_saving(cands, prefix: str = "TRANSFER_"):
    return sum(c["saving"] for c in cands if c["rule"].id.startswith(prefix))


# --- 시나리오 1: 일시적 2주택 + 종전주택 양도 (비과세 + 장특공제) ---------

def test_scenario_temp_two_house_with_ltcg():
    """5년 거주 서울 아파트 + 신축 이사 → 1년 지나 종전주택 양도."""
    profile = {
        "has_transfer_income": True,
        "is_one_house": False,
        "has_temp_two_house": True,
        "months_since_new_house": 12,
        "old_house_gain": 400_000_000,
        "transfer_gain": 400_000_000,
        "transfer_price": 1_000_000_000,
        "holding_years": 5,
        "residence_years": 5,
        "holding_months": 60,
    }
    r = run(profile)
    ids = _ids(r["candidates"])
    assert "TRANSFER_TEMP_TWO_HOUSE" in ids
    assert "TRANSFER_LTCG_TABLE1" in ids  # 일반 표1 (is_one_house=False)
    assert "TRANSFER_ONE_HOUSE_EXEMPT" not in ids  # is_one_house=False
    assert _total_saving(r["candidates"]) >= 80_000_000


# --- 시나리오 2: 12억 초과 1세대 1주택 + 거주요건 미흡 ----------------------

def test_scenario_high_value_one_house():
    """강남 20억 아파트, 1세대 1주택, 보유 7년 거주 3년."""
    profile = {
        "is_one_house": True,
        "has_transfer_income": True,
        "transfer_price": 2_000_000_000,
        "transfer_gain": 1_000_000_000,
        "holding_years": 7,
        "residence_years": 3,
        "holding_months": 84,
    }
    r = run(profile)
    ids = _ids(r["candidates"])
    assert "TRANSFER_HIGH_VALUE_EXCESS_LTCG" in ids
    assert "TRANSFER_LTCG_TABLE2_ONE_HOUSE" in ids
    assert "TRANSFER_ONE_HOUSE_EXEMPT" not in ids  # 12억 초과
    assert "TRANSFER_SHORT_TERM_EXTEND" not in ids  # 84개월


# --- 시나리오 3: 다주택 중과 유예 + 단기양도 회피 ---------------------------

def test_scenario_multi_house_short_term():
    """다주택 2년 미만 보유 — 중과 유예 + 2년 만기 대기."""
    profile = {
        "has_transfer_income": True,
        "is_multi_house_heavy_zone": True,
        "multi_house_defer_active": True,
        "multi_house_surcharge_rate": 0.20,
        "transfer_gain": 300_000_000,
        "holding_years": 1,
        "holding_months": 18,
    }
    r = run(profile)
    ids = _ids(r["candidates"])
    assert "TRANSFER_MULTI_HOUSE_DEFER" in ids
    assert "TRANSFER_SHORT_TERM_EXTEND" in ids
    # 두 전략 합산 = 단기 40%p × 3억 + 중과 20%p × 3억 = 1.2억 + 6천만 = 1.8억
    assert _total_saving(r["candidates"]) >= 150_000_000


# --- 시나리오 4: 미등기 양도 (고위험) ---------------------------------------

def test_scenario_unregistered_high_risk():
    """미등기 자산 양도 — 기본세율 20% 대비 70% 세율 회피."""
    profile = {
        "has_transfer_income": True,
        "is_unregistered_transfer": True,
        "transfer_gain": 200_000_000,
        "holding_years": 4,
        "holding_months": 48,
    }
    r = run(profile)
    ids = _ids(r["candidates"])
    assert "TRANSFER_UNREGISTERED_AVOID" in ids
    # 등기 완료 시 장특공제도 복원됨
    assert "TRANSFER_LTCG_TABLE1" in ids
    # 200M × 50%p = 100M
    savings = {c["rule"].id: c["saving"] for c in r["candidates"]}
    assert savings.get("TRANSFER_UNREGISTERED_AVOID") == 100_000_000


# --- 시나리오 5: 자경농지 8년 감면 + 증여 후 양도 대기 ---------------------

def test_scenario_farmland_with_gift_wait():
    """부친에게 증여받은 농지 8년 자경 + 10년 대기 후 양도."""
    profile = {
        "has_transfer_income": True,
        "is_self_cultivated_farmland": True,
        "self_cultivation_years": 10,
        "is_post_gift_transfer": True,
        "years_since_gift": 8,  # 10년 미만 → 이월과세 경고
        "gift_carryover_gain": 100_000_000,
        "transfer_gain": 300_000_000,
        "holding_years": 10,
        "holding_months": 120,
    }
    r = run(profile)
    ids = _ids(r["candidates"])
    assert "TRANSFER_SELF_CULTIVATED_FARMLAND" in ids
    assert "TRANSFER_GIFT_CARRYOVER" in ids  # 10년 미경과 경고
    # 자경농지 감면 1억 한도
    savings = {c["rule"].id: c["saving"] for c in r["candidates"]}
    assert savings.get("TRANSFER_SELF_CULTIVATED_FARMLAND") == 60_000_000


# --- 시나리오 6: 공익수용 + 필요경비 누락 --------------------------------

def test_scenario_expropriation_with_docs():
    """도시계획 수용 + 취득 당시 중개수수료·법무사비 누락 발견."""
    profile = {
        "has_transfer_income": True,
        "is_public_expropriation": True,
        "expropriation_compensation_type": "bond_5y",
        "transfer_gain": 600_000_000,
        "unreported_necessary_expense": 30_000_000,
        "acquisition_docs_available": False,
        "acquisition_value_gap": 50_000_000,
        "holding_years": 10,
        "holding_months": 120,
    }
    r = run(profile)
    ids = _ids(r["candidates"])
    assert "TRANSFER_PUBLIC_EXPROPRIATION" in ids
    assert "TRANSFER_NECESSARY_EXPENSE" in ids
    assert "TRANSFER_ACQUISITION_DOC" in ids
    # 수용 감면 + 경비 가산 합산
    assert _total_saving(r["candidates"]) >= 50_000_000


# --- 시나리오 7: 양도소득 프로파일 → 타 세목 규칙 비발동 (scope) ------------

def test_scenario_transfer_only_scope_isolation():
    profile = {
        "has_transfer_income": True,
        "transfer_gain": 200_000_000,
        "holding_years": 5,
    }
    r = run(profile)
    ids = _ids(r["candidates"])
    # 법인세·상속세·증여세 규칙 비발동
    for rid in (
        "CORP_LOSS_CARRYFORWARD", "CORP_RD_TAX_CREDIT",
        "INH_SPOUSE_DEDUCTION", "GIFT_SPLIT_10YEAR",
    ):
        assert rid not in ids, rid
    # 소득세 일반 전략(연금·신용카드 등)도 비발동 (has_earned_income=False)
    assert "DED_PENSION_IRP_700" not in ids
    assert "DED_CREDIT_CARD" not in ids


if __name__ == "__main__":
    tests = [
        ("temp two house + ltcg", test_scenario_temp_two_house_with_ltcg),
        ("high value one house", test_scenario_high_value_one_house),
        ("multi house short term", test_scenario_multi_house_short_term),
        ("unregistered high risk", test_scenario_unregistered_high_risk),
        ("farmland + gift wait", test_scenario_farmland_with_gift_wait),
        ("expropriation + docs", test_scenario_expropriation_with_docs),
        ("transfer-only scope", test_scenario_transfer_only_scope_isolation),
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
