"""Phase 5-C-1 — 신고서 초안 PDF 렌더러.

execution_planner.generate_tax_return_draft()의 dict 출력을 국세청 신고서
근접 표 레이아웃 PDF로 변환. 한글 폰트(맑은고딕) 등록.

CLI:
  python execution_planner_pdf.py --scope income_tax --tax-result-json '{...}' \
      --out draft.pdf
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from execution_planner import generate_tax_return_draft

FONT_CANDIDATES = [
    ("KoreanFont", "C:/Windows/Fonts/malgun.ttf"),
    ("KoreanFontBold", "C:/Windows/Fonts/malgunbd.ttf"),
]


def _register_fonts() -> tuple[str, str]:
    """맑은고딕 등록. 실패 시 Helvetica 폴백."""
    regular = "Helvetica"
    bold = "Helvetica-Bold"
    for name, path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                if "Bold" in name:
                    bold = name
                else:
                    regular = name
            except Exception:
                pass
    return regular, bold


def _styles(regular: str, bold: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontName=bold, fontSize=16,
            spaceAfter=8, alignment=1,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName=bold, fontSize=12,
            spaceBefore=10, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName=regular, fontSize=10,
            leading=14,
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"], fontName=regular, fontSize=9,
            leading=12, textColor=colors.grey,
        ),
    }


def _fmt_money(v: Any) -> str:
    if isinstance(v, (int, float)):
        return f"{int(v):,}"
    return str(v or "")


def _lines_table(rows: list[dict], styles: dict) -> Table:
    data = [["번호", "항목", "금액", "법령"]]
    for r in rows:
        data.append([
            r.get("번호", ""),
            Paragraph(r.get("항목", ""), styles["body"]),
            _fmt_money(r.get("금액", "")),
            Paragraph(r.get("법령", ""), styles["small"]),
        ])
    t = Table(data, colWidths=[36, 170, 120, 160], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF7")),
        ("FONTNAME", (0, 0), (-1, 0), styles["h2"].fontName),
        ("FONTNAME", (0, 1), (-1, -1), styles["body"].fontName),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (2, 1), (2, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#AAAAAA")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F8FA")]),
    ]))
    return t


def _strategy_table(strategies: list[dict], styles: dict) -> Table | None:
    if not strategies:
        return None
    data = [["항목", "예상절세액", "법령", "리스크"]]
    for s in strategies:
        risk = s.get("리스크") or {}
        risk_txt = f"{risk.get('level','')}/{risk.get('note','')[:40]}"
        data.append([
            Paragraph(s.get("항목", ""), styles["body"]),
            _fmt_money(s.get("절세액", 0)),
            Paragraph(s.get("법령", ""), styles["small"]),
            Paragraph(risk_txt, styles["small"]),
        ])
    t = Table(data, colWidths=[150, 90, 140, 106], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E7F3E8")),
        ("FONTNAME", (0, 0), (-1, 0), styles["h2"].fontName),
        ("FONTNAME", (0, 1), (-1, -1), styles["body"].fontName),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#AAAAAA")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _judgment_table(judgments: list[dict], styles: dict) -> Table | None:
    if not judgments:
        return None
    data = [["이슈", "판단", "신뢰도", "보강증빙"]]
    for j in judgments:
        data.append([
            Paragraph(j.get("issue_id", ""), styles["small"]),
            Paragraph(j.get("판단", ""), styles["body"]),
            f"{j.get('신뢰도', 0):.2f}",
            Paragraph(", ".join(j.get("보강증빙") or [])[:120], styles["small"]),
        ])
    t = Table(data, colWidths=[140, 120, 60, 166], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FDF4E3")),
        ("FONTNAME", (0, 0), (-1, 0), styles["h2"].fontName),
        ("FONTNAME", (0, 1), (-1, -1), styles["body"].fontName),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#AAAAAA")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def render_draft_pdf(draft: dict, out_path: str | Path) -> str:
    """draft dict → PDF 파일 생성. 반환값: 저장 경로."""
    regular, bold = _register_fonts()
    styles = _styles(regular, bold)
    out_path = str(out_path)

    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=36, rightMargin=36, topMargin=40, bottomMargin=36,
    )
    story: list = []

    story.append(Paragraph(draft.get("신고서제목", "(제목 없음)"), styles["title"]))
    story.append(Paragraph(f"과세기간: {draft.get('과세기간', '')}", styles["body"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("■ 신고서 행항목", styles["h2"]))
    story.append(_lines_table(draft.get("행항목") or [], styles))
    story.append(Spacer(1, 10))

    strat_t = _strategy_table(draft.get("적용전략") or [], styles)
    if strat_t is not None:
        story.append(Paragraph("■ 적용 절세전략", styles["h2"]))
        story.append(strat_t)
        story.append(Spacer(1, 10))

    judg_t = _judgment_table(draft.get("판단이슈") or [], styles)
    if judg_t is not None:
        story.append(Paragraph("■ 회색지대 판단", styles["h2"]))
        story.append(judg_t)
        story.append(Spacer(1, 10))

    checklist = draft.get("체크리스트") or []
    if checklist:
        story.append(Paragraph("■ 신고 전 체크리스트", styles["h2"]))
        for c in checklist:
            story.append(Paragraph(f"• {c}", styles["body"]))
        story.append(Spacer(1, 8))

    warns = draft.get("주의사항") or []
    if warns:
        story.append(Paragraph("■ 주의사항", styles["h2"]))
        for w in warns:
            story.append(Paragraph(
                f"<font color='#B22222'>! {w}</font>", styles["body"]
            ))

    doc.build(story)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", required=True)
    ap.add_argument("--tax-result-json", required=True)
    ap.add_argument("--strategy-json", default=None)
    ap.add_argument("--judgment-json", default=None)
    ap.add_argument("--year", type=int, default=None)
    ap.add_argument("--out", default="tax_return_draft.pdf")
    args = ap.parse_args()

    tax = json.loads(args.tax_result_json)
    strat = json.loads(args.strategy_json) if args.strategy_json else None
    judg = json.loads(args.judgment_json) if args.judgment_json else None
    draft = generate_tax_return_draft(args.scope, tax, strat, judg, year=args.year)
    path = render_draft_pdf(draft, args.out)
    print(f"[saved] {path}")


if __name__ == "__main__":
    import sys
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
