"""Phase 5-B — 신고서 초안 생성기.

tax_calculator 결과 + strategy_engine 전략 + reasoning_engine 판단을
통합하여 신고 실무에 바로 투입 가능한 구조화된 초안을 만든다.

출력 스키마:
  {
    "scope": "income_tax|corporate_tax|vat|inheritance_gift",
    "신고서제목": str,
    "과세기간": str,
    "행항목": [  # 신고서 라인 아이템
      {"번호": "01", "항목": "총수입금액", "금액": int, "법령": str},
      ...
    ],
    "적용전략": [  # strategy_engine에서 발동된 규칙
      {"rule_id": str, "항목": str, "절세액": int, "법령": str, "리스크": {...}},
      ...
    ],
    "판단이슈": [  # reasoning_engine 회색지대 판단
      {"issue_id": str, "판단": str, "신뢰도": float, "근거": [...], "보강증빙": [...]},
      ...
    ],
    "체크리스트": [str, ...],  # 신고 전 확인사항
    "주의사항": [str, ...],  # 리스크 high/medium 항목 요약
  }

CLI:
  python execution_planner.py --scope income_tax --tax-result-json '{...}' [--strategy-json '{...}']
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from typing import Any

SCOPE_TITLES = {
    "income_tax": "종합소득세 과세표준확정신고 및 납부계산서",
    "corporate_tax": "법인세 과세표준 및 세액신고서",
    "vat": "부가가치세 신고서",
    "inheritance_gift": "상속세(증여세) 과세표준신고 및 자진납부계산서",
}


def _period_for(scope: str, year: int | None = None) -> str:
    y = year or date.today().year - 1
    if scope == "income_tax":
        return f"{y}.01.01 ~ {y}.12.31 (종합소득)"
    if scope == "corporate_tax":
        return f"{y}.01.01 ~ {y}.12.31 (사업연도)"
    if scope == "vat":
        return f"{y} 제2기 확정 (7.1 ~ 12.31)"
    if scope == "inheritance_gift":
        return f"{y} 과세사건"
    return str(y)


def _income_tax_lines(tax: dict) -> list[dict]:
    rows = []
    def add(n, item, amt, law=""):
        val = amt if isinstance(amt, str) else int(amt or 0)
        rows.append({"번호": n, "항목": item, "금액": val, "법령": law})
    add("11", "종합소득금액", tax.get("종합소득금액", 0), "소득세법 §14")
    add("21", "종합소득공제", tax.get("소득공제합계", 0), "소득세법 §50~§54")
    add("22", "과세표준", tax.get("과세표준", 0), "소득세법 §14")
    add("23", "세율", tax.get("적용세율", ""), "소득세법 §55")
    add("24", "산출세액", tax.get("산출세액", 0), "소득세법 §55")
    add("25", "세액공제·감면", tax.get("세액공제감면합계", 0), "소득세법 §56~§59의4")
    add("26", "결정세액", tax.get("결정세액", 0), "소득세법 §15")
    add("27", "기납부세액", tax.get("기납부세액", 0), "소득세법 §76")
    add("28", "납부할세액", tax.get("납부할세액", 0), "소득세법 §76")
    return rows


def _corporate_tax_lines(tax: dict) -> list[dict]:
    rows = []
    def add(n, item, amt, law=""):
        val = amt if isinstance(amt, str) else int(amt or 0)
        rows.append({"번호": n, "항목": item, "금액": val, "법령": law})
    add("11", "결산서상 당기순이익", tax.get("당기순이익", 0), "법인세법 §14")
    add("12", "익금산입·손금불산입", tax.get("익금산입", 0), "법인세법 §15·§19")
    add("13", "손금산입·익금불산입", tax.get("손금산입", 0), "법인세법 §19")
    add("14", "각사업연도소득금액", tax.get("각사업연도소득금액", 0), "법인세법 §14")
    add("15", "이월결손금", tax.get("이월결손금공제", 0), "법인세법 §13")
    add("16", "과세표준", tax.get("과세표준", 0), "법인세법 §13")
    add("17", "세율", tax.get("적용세율", ""), "법인세법 §55")
    add("18", "산출세액", tax.get("산출세액", 0), "법인세법 §55")
    add("19", "공제감면세액", tax.get("공제감면세액", 0), "조세특례제한법")
    add("20", "총부담세액", tax.get("총부담세액", 0), "법인세법 §57")
    return rows


def _vat_lines(tax: dict) -> list[dict]:
    rows = []
    def add(n, item, amt, law=""):
        val = amt if isinstance(amt, str) else int(amt or 0)
        rows.append({"번호": n, "항목": item, "금액": val, "법령": law})
    add("01", "과세표준(과세)", tax.get("과세표준_과세", 0), "부가가치세법 §29")
    add("02", "과세표준(영세)", tax.get("과세표준_영세", 0), "부가가치세법 §21~§24")
    add("03", "매출세액", tax.get("매출세액", 0), "부가가치세법 §29")
    add("04", "매입세액", tax.get("매입세액", 0), "부가가치세법 §37")
    add("05", "공제불가 매입세액", tax.get("매입세액_불공제", 0), "부가가치세법 §39")
    add("06", "납부세액", tax.get("납부세액", 0), "부가가치세법 §37")
    add("07", "가산세", tax.get("가산세합계", 0), "부가가치세법 §60")
    add("08", "차가감납부세액", tax.get("차가감납부세액", 0), "부가가치세법 §48")
    return rows


def _inheritance_gift_lines(tax: dict) -> list[dict]:
    rows = []
    def add(n, item, amt, law=""):
        val = amt if isinstance(amt, str) else int(amt or 0)
        rows.append({"번호": n, "항목": item, "금액": val, "법령": law})
    kind = tax.get("구분", "상속")
    add("11", f"{kind}재산가액", tax.get("재산가액", 0), "상증법 §7·§31")
    add("12", "비과세·과세가액불산입", tax.get("비과세", 0), "상증법 §12·§46")
    add("13", "사전증여합산", tax.get("사전증여합산", 0), "상증법 §13")
    add("14", "공과금·채무·장례비", tax.get("공과금채무", 0), "상증법 §14")
    add("15", "과세가액", tax.get("과세가액", 0), "상증법 §13")
    add("16", "상속공제·증여공제", tax.get("공제합계", 0), "상증법 §18~§24·§53")
    add("17", "과세표준", tax.get("과세표준", 0), "상증법 §25·§55")
    add("18", "세율", tax.get("적용세율", ""), "상증법 §26·§56")
    add("19", "산출세액", tax.get("산출세액", 0), "상증법 §26·§56")
    add("20", "납부세액", tax.get("납부세액", 0), "상증법 §27·§58")
    return rows


LINE_BUILDERS = {
    "income_tax": _income_tax_lines,
    "corporate_tax": _corporate_tax_lines,
    "vat": _vat_lines,
    "inheritance_gift": _inheritance_gift_lines,
}


def _format_strategies(strategy_result: dict | None) -> list[dict]:
    if not strategy_result:
        return []
    out = []
    for c in strategy_result.get("candidates", []) or []:
        rule = c.get("rule")
        legal = ""
        name = ""
        rule_id = ""
        if rule is not None:
            legal = " / ".join(
                f"{lb.get('law','')} {lb.get('article','')}".strip()
                for lb in (getattr(rule, 'legal_basis', None) or [])
            )
            name = getattr(rule, 'name', '')
            rule_id = getattr(rule, 'id', '')
        out.append({
            "rule_id": rule_id,
            "항목": name,
            "절세액": int(c.get("saving", 0) or 0),
            "법령": legal,
            "리스크": c.get("risk", {}),
        })
    return out


def _format_judgments(judgments: list[dict] | None) -> list[dict]:
    if not judgments:
        return []
    out = []
    for run in judgments:
        j = run.get("judgment", {}) if isinstance(run, dict) else {}
        adv = run.get("adversary", {}) if isinstance(run, dict) else {}
        cited = [
            {
                "type": c.get("type"),
                "법령": c.get("law") or c.get("사건명") or c.get("행정규칙명"),
                "조항": c.get("article") or c.get("사건번호") or c.get("rule_id"),
            }
            for c in (j.get("cited_sources") or [])
        ]
        out.append({
            "issue_id": run.get("issue_id", ""),
            "판단": j.get("ruling", ""),
            "신뢰도": j.get("confidence", 0.0),
            "근거": cited,
            "보강증빙": adv.get("required_evidence", []) or [],
            "주의": j.get("caveats", []) or [],
        })
    return out


def _checklist(scope: str, tax: dict, strategies: list[dict], judgments: list[dict]) -> list[str]:
    items: list[str] = []
    if scope == "income_tax":
        items.append("신고·납부 기한: 다음해 5.31 (성실신고확인대상 6.30)")
        if tax.get("기납부세액", 0) > tax.get("결정세액", 0):
            items.append("기납부세액 > 결정세액 → 환급 신청")
    elif scope == "corporate_tax":
        items.append("신고·납부 기한: 사업연도 종료일부터 3개월 이내")
        items.append("지방소득세(법인분) 동시 신고")
    elif scope == "vat":
        items.append("신고·납부 기한: 제1기(7.25)·제2기(1.25) 확정")
        items.append("세금계산서 합계표·매입처별세금계산서 합계표 첨부")
    elif scope == "inheritance_gift":
        items.append("신고 기한: 상속개시일 속한 달 말일부터 6개월 / 증여 3개월")

    for s in strategies:
        if s["절세액"] > 0:
            items.append(f"전략 적용: {s['항목']} (예상 절세 {s['절세액']:,}원)")
    for j in judgments:
        if j["판단"]:
            items.append(f"판단사항: {j['issue_id']} → {j['판단']} (신뢰도 {j['신뢰도']})")
    return items


def _warnings(strategies: list[dict], judgments: list[dict]) -> list[str]:
    warns: list[str] = []
    for s in strategies:
        risk = (s.get("리스크") or {}).get("level", "")
        if risk in ("high", "medium"):
            warns.append(f"[{risk.upper()}] {s['항목']}: {(s.get('리스크') or {}).get('note','')}")
    for j in judgments:
        if (j.get("신뢰도") or 0) < 0.6:
            warns.append(
                f"[LOW_CONF] {j['issue_id']}: 보강증빙 필요 — {', '.join(j.get('보강증빙') or [])[:80]}"
            )
    return warns


def generate_tax_return_draft(
    scope: str,
    tax_result: dict,
    strategy_result: dict | None = None,
    judgment_results: list[dict] | None = None,
    *,
    year: int | None = None,
) -> dict[str, Any]:
    """신고서 초안 생성.

    Args:
      scope: income_tax / corporate_tax / vat / inheritance_gift
      tax_result: tax_calculator 출력 dict (세목별 키 상이)
      strategy_result: strategy_engine.orchestrator.run() 출력
      judgment_results: reasoning_engine.orchestrator.run() 출력의 리스트
    """
    if scope not in LINE_BUILDERS:
        raise ValueError(f"unsupported scope: {scope}")

    lines = LINE_BUILDERS[scope](tax_result or {})
    strategies = _format_strategies(strategy_result)
    judgments = _format_judgments(judgment_results)
    return {
        "scope": scope,
        "신고서제목": SCOPE_TITLES[scope],
        "과세기간": _period_for(scope, year),
        "행항목": lines,
        "적용전략": strategies,
        "판단이슈": judgments,
        "체크리스트": _checklist(scope, tax_result or {}, strategies, judgments),
        "주의사항": _warnings(strategies, judgments),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", required=True, choices=list(SCOPE_TITLES.keys()))
    ap.add_argument("--tax-result-json", required=True)
    ap.add_argument("--strategy-json", default=None)
    ap.add_argument("--judgment-json", default=None, help="list of reasoning_engine runs")
    ap.add_argument("--year", type=int, default=None)
    args = ap.parse_args()

    tax = json.loads(args.tax_result_json)
    strat = json.loads(args.strategy_json) if args.strategy_json else None
    judg = json.loads(args.judgment_json) if args.judgment_json else None
    draft = generate_tax_return_draft(args.scope, tax, strat, judg, year=args.year)
    print(json.dumps(draft, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import sys
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
