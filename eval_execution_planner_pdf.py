"""Phase 5-C-1 — PDF 렌더러 검증.

네 세목 샘플 draft를 PDF로 렌더하고 파일이 정상 생성·최소 크기 이상임을 확인.
한글 폰트 등록 실패 시 Helvetica 폴백이 동작하는지만 체크(파일 생성 성공).
"""
from __future__ import annotations

from pathlib import Path

from execution_planner import generate_tax_return_draft
from execution_planner_pdf import render_draft_pdf

OUT_DIR = Path(__file__).parent / "data" / "pdf_samples"


def _scenario_income() -> tuple[dict, dict, list[dict]]:
    tax = {
        "종합소득금액": 80_000_000, "소득공제합계": 15_000_000,
        "과세표준": 65_000_000, "적용세율": "24%",
        "산출세액": 10_470_000, "세액공제감면합계": 1_200_000,
        "결정세액": 9_270_000, "기납부세액": 5_000_000,
        "납부할세액": 4_270_000,
    }

    class R:
        id = "DED_PENSION_IRP"
        name = "연금계좌 세액공제 최대활용"
        legal_basis = [{"law": "소득세법", "article": "제59조의3"}]
    strat = {"profile": {}, "candidates": [{
        "rule": R(), "saving": 1_200_000,
        "risk": {"level": "medium", "note": "IRP 중도해지 시 추징"},
    }]}
    judg = [{
        "issue_id": "GRAY_CAR_BUSINESS_RATIO",
        "judgment": {"ruling": "한도내인정", "confidence": 0.6,
                     "cited_sources": [{"type": "statute", "law": "소득세법", "article": "제33조의2"}],
                     "caveats": ["운행기록부 보강"]},
        "adversary": {"required_evidence": ["운행기록부 km 상세화"]},
    }]
    return tax, strat, judg


def test_render_all_scopes() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = {
        "income_tax": _scenario_income(),
        "corporate_tax": ({"당기순이익": 500_000_000, "과세표준": 520_000_000,
                           "적용세율": "19%", "산출세액": 78_800_000,
                           "총부담세액": 73_800_000}, None, None),
        "vat": ({"과세표준_과세": 200_000_000, "매출세액": 20_000_000,
                 "매입세액": 12_000_000, "납부세액": 8_000_000,
                 "차가감납부세액": 8_000_000}, None, None),
        "inheritance_gift": ({"구분": "상속", "재산가액": 2_000_000_000,
                              "과세가액": 2_000_000_000, "공제합계": 500_000_000,
                              "과세표준": 1_500_000_000, "적용세율": "40%",
                              "산출세액": 440_000_000, "납부세액": 440_000_000}, None, None),
    }
    for scope, (tax, strat, judg) in scenarios.items():
        draft = generate_tax_return_draft(scope, tax, strat, judg, year=2025)
        out = OUT_DIR / f"{scope}_draft.pdf"
        path = render_draft_pdf(draft, out)
        assert Path(path).exists(), f"{scope}: file not created"
        size = Path(path).stat().st_size
        assert size > 2000, f"{scope}: file too small ({size} bytes)"
        print(f"[PASS] {scope} — {size:,} bytes → {out}")


def main() -> None:
    test_render_all_scopes()
    print("\n4/4 PDF rendered")


if __name__ == "__main__":
    import sys
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
