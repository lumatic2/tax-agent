"""Phase 5-B — 신고서 초안 생성기 스키마 검증.

네 세목 모두 기본 필드와 라인 아이템이 올바로 채워지는지 확인.
strategy·judgment 주입 시 섹션이 추가되는 것까지 검증.
"""
from __future__ import annotations

from execution_planner import generate_tax_return_draft


def _assert_common(draft: dict, scope: str) -> None:
    assert draft["scope"] == scope, draft["scope"]
    for key in ("신고서제목", "과세기간", "행항목", "적용전략", "판단이슈", "체크리스트", "주의사항"):
        assert key in draft, f"missing {key}"
    assert isinstance(draft["행항목"], list) and draft["행항목"], "행항목 empty"
    for row in draft["행항목"]:
        for k in ("번호", "항목", "금액", "법령"):
            assert k in row, f"row missing {k}: {row}"


def test_income_tax_basic() -> None:
    tax = {
        "종합소득금액": 80_000_000,
        "소득공제합계": 15_000_000,
        "과세표준": 65_000_000,
        "적용세율": "24%",
        "산출세액": 10_470_000,
        "세액공제감면합계": 1_200_000,
        "결정세액": 9_270_000,
        "기납부세액": 5_000_000,
        "납부할세액": 4_270_000,
    }
    draft = generate_tax_return_draft("income_tax", tax, year=2025)
    _assert_common(draft, "income_tax")
    amounts = {r["항목"]: r["금액"] for r in draft["행항목"]}
    assert amounts["과세표준"] == 65_000_000
    assert amounts["납부할세액"] == 4_270_000
    assert "2025" in draft["과세기간"]
    print("[PASS] income_tax basic")


def test_corporate_tax_basic() -> None:
    tax = {
        "당기순이익": 500_000_000,
        "익금산입": 30_000_000,
        "손금산입": 10_000_000,
        "각사업연도소득금액": 520_000_000,
        "이월결손금공제": 0,
        "과세표준": 520_000_000,
        "적용세율": "19%",
        "산출세액": 78_800_000,
        "공제감면세액": 5_000_000,
        "총부담세액": 73_800_000,
    }
    draft = generate_tax_return_draft("corporate_tax", tax)
    _assert_common(draft, "corporate_tax")
    assert any(r["항목"] == "총부담세액" and r["금액"] == 73_800_000 for r in draft["행항목"])
    print("[PASS] corporate_tax basic")


def test_vat_basic() -> None:
    tax = {
        "과세표준_과세": 200_000_000,
        "과세표준_영세": 50_000_000,
        "매출세액": 20_000_000,
        "매입세액": 12_000_000,
        "매입세액_불공제": 500_000,
        "납부세액": 8_000_000,
        "가산세합계": 0,
        "차가감납부세액": 8_000_000,
    }
    draft = generate_tax_return_draft("vat", tax)
    _assert_common(draft, "vat")
    assert any(r["항목"] == "차가감납부세액" and r["금액"] == 8_000_000 for r in draft["행항목"])
    print("[PASS] vat basic")


def test_inheritance_gift_basic() -> None:
    tax = {
        "구분": "상속",
        "재산가액": 2_000_000_000,
        "비과세": 100_000_000,
        "사전증여합산": 300_000_000,
        "공과금채무": 200_000_000,
        "과세가액": 2_000_000_000,
        "공제합계": 500_000_000,
        "과세표준": 1_500_000_000,
        "적용세율": "40%",
        "산출세액": 440_000_000,
        "납부세액": 440_000_000,
    }
    draft = generate_tax_return_draft("inheritance_gift", tax)
    _assert_common(draft, "inheritance_gift")
    assert any("상속재산가액" == r["항목"] for r in draft["행항목"])
    print("[PASS] inheritance_gift basic")


def test_with_strategies_and_judgments() -> None:
    class MockRule:
        id = "DED_PENSION_IRP"
        name = "연금계좌세액공제 최대활용"
        legal_basis = [{"law": "소득세법", "article": "제59조의3"}]

    tax = {"종합소득금액": 80_000_000, "결정세액": 9_270_000}
    strat = {
        "profile": {},
        "candidates": [
            {"rule": MockRule(), "saving": 1_200_000,
             "risk": {"level": "medium", "note": "IRP 해지 시 세액 추징"}},
        ],
    }
    judgments = [
        {
            "issue_id": "GRAY_CAR_BUSINESS_RATIO",
            "judgment": {
                "ruling": "한도내인정",
                "confidence": 0.5,
                "cited_sources": [
                    {"type": "statute", "law": "소득세법", "article": "제33조의2"},
                ],
                "caveats": ["운행기록부 증빙 보강 필요"],
            },
            "adversary": {"required_evidence": ["운행기록부 km·목적지 상세화"]},
        }
    ]
    draft = generate_tax_return_draft("income_tax", tax, strat, judgments)
    _assert_common(draft, "income_tax")
    assert len(draft["적용전략"]) == 1
    assert draft["적용전략"][0]["절세액"] == 1_200_000
    assert len(draft["판단이슈"]) == 1
    assert draft["판단이슈"][0]["판단"] == "한도내인정"
    assert any("MEDIUM" in w for w in draft["주의사항"]), draft["주의사항"]
    assert any("LOW_CONF" in w for w in draft["주의사항"]), draft["주의사항"]
    assert any("전략 적용" in c for c in draft["체크리스트"])
    print("[PASS] strategy + judgment integration")


def test_unsupported_scope() -> None:
    try:
        generate_tax_return_draft("unknown", {})
    except ValueError:
        print("[PASS] unsupported scope raises")
        return
    raise AssertionError("expected ValueError")


def main() -> None:
    tests = [
        test_income_tax_basic,
        test_corporate_tax_basic,
        test_vat_basic,
        test_inheritance_gift_basic,
        test_with_strategies_and_judgments,
        test_unsupported_scope,
    ]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    import sys
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
