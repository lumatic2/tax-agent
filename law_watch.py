"""핵심 조문 개정 감지 루틴.

사용 예:
  1) 기준 스냅샷 갱신
     uv run python law_watch.py --refresh
  2) 변경 감지 점검(기본)
     uv run python law_watch.py

종료 코드:
  0: 변경 없음(또는 refresh 성공)
  1: 기준 대비 변경 감지됨
  2: 기준 스냅샷 파일이 없음
  3: 조회 실패 또는 필수 조문 누락
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import legal_search


@dataclass(frozen=True)
class WatchTarget:
    law_name: str
    article_no: str
    title_keyword: str
    reason: str

    @property
    def target_id(self) -> str:
        return f"{self.law_name}|{self.article_no}|{self.title_keyword}"


# 변경 이유:
# - 소득세법 v1에서 실제 계산/납부 안내 품질에 직접 영향을 주는 조문만 우선 감시한다.
# - 조문번호만으로는 절/관(전문)과 충돌할 수 있어 title_keyword를 함께 키로 사용한다.
WATCH_TARGETS: list[WatchTarget] = [
    WatchTarget("소득세법", "50", "기본공제", "인적공제 기준"),
    WatchTarget("소득세법", "52", "특별소득공제", "특별공제/표준공제 분기"),
    WatchTarget("소득세법", "55", "세율", "누진세율 계산"),
    WatchTarget("소득세법", "59", "근로소득세액공제", "근로소득세액공제 계산"),
    WatchTarget("소득세법", "59", "특별세액공제", "의료비/교육비 등 세액공제"),
    WatchTarget("소득세법", "59", "연금계좌세액공제", "IRP·연금저축 공제"),
    WatchTarget("소득세법", "62", "이자소득 등에 대한 종합과세 시 세액 계산의 특례", "금융소득 §62 비교세액"),
    WatchTarget("소득세법", "65", "중간예납", "중간예납 안내"),
    WatchTarget("소득세법", "70", "종합소득과세표준", "종합소득세 신고기한"),
    WatchTarget("소득세법", "110", "양도소득과세표준", "양도소득세 신고기한"),
    WatchTarget("조세특례제한법", "126", "신용카드 등 사용금액에 대한 소득공제", "신용카드 소득공제"),
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_laws(search_payload: dict[str, Any]) -> list[dict[str, Any]]:
    laws = search_payload.get("laws")
    if isinstance(laws, list):
        return laws
    raw = ((search_payload.get("LawSearch") or {}).get("law")) or []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return [raw]
    return []


def _extract_articles(content_payload: dict[str, Any]) -> list[dict[str, Any]]:
    articles = (((content_payload.get("법령") or {}).get("조문") or {}).get("조문단위")) or []
    if isinstance(articles, dict):
        return [articles]
    if isinstance(articles, list):
        return articles
    return []


def _normalize_text(value: Any) -> str:
    # 변경 이유:
    # - 법제처 본문은 개행/공백 변동이 잦아서, 의미 없는 공백 차이는 감지 대상에서 제외한다.
    text = str(value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _iter_targets() -> Iterable[WatchTarget]:
    return WATCH_TARGETS


def _find_law_meta(law_name: str) -> dict[str, Any]:
    payload = legal_search.search_law(law_name)
    laws = _extract_laws(payload)
    if not laws:
        raise RuntimeError(f"법령 검색 결과가 없습니다: {law_name}")

    exact = next((x for x in laws if x.get("법령명한글") == law_name), None)
    return exact or laws[0]


def _find_article(articles: list[dict[str, Any]], target: WatchTarget) -> dict[str, Any]:
    # 변경 이유:
    # - '전문(절/관)'도 같은 조문번호를 가지는 경우가 있어 조문여부=조문만 대상으로 제한한다.
    candidates = [
        a
        for a in articles
        if str(a.get("조문번호") or "") == target.article_no and str(a.get("조문여부") or "") == "조문"
    ]
    for article in candidates:
        title = _normalize_text(article.get("조문제목"))
        body = _normalize_text(article.get("조문내용"))
        if target.title_keyword in title or target.title_keyword in body:
            return article

    if candidates:
        return candidates[0]
    raise RuntimeError(
        f"핵심 조문을 찾지 못했습니다: {target.law_name} 제{target.article_no}조 ({target.title_keyword})"
    )


def build_snapshot(targets: Iterable[WatchTarget]) -> dict[str, Any]:
    grouped: dict[str, list[WatchTarget]] = {}
    for t in targets:
        grouped.setdefault(t.law_name, []).append(t)

    entries: list[dict[str, Any]] = []
    for law_name, law_targets in grouped.items():
        law_meta = _find_law_meta(law_name)
        mst = str(law_meta.get("법령일련번호") or "").strip()
        if not mst:
            raise RuntimeError(f"MST(법령일련번호) 누락: {law_name}")

        content = legal_search.get_law_content(mst)
        articles = _extract_articles(content)

        for target in law_targets:
            article = _find_article(articles, target)
            title = _normalize_text(article.get("조문제목"))
            body = _normalize_text(article.get("조문내용"))
            text_for_hash = f"{title}\n{body}"

            entries.append(
                {
                    "target_id": target.target_id,
                    "law_name": target.law_name,
                    "law_mst": mst,
                    "law_effective_date": law_meta.get("시행일자"),
                    "law_promulgation_date": law_meta.get("공포일자"),
                    "article_no": str(article.get("조문번호") or target.article_no),
                    "article_title": title,
                    "title_keyword": target.title_keyword,
                    "reason": target.reason,
                    "article_text_hash": _sha256(text_for_hash),
                    "article_title_hash": _sha256(title),
                    "article_excerpt": body[:220],
                    "fetched_at_utc": _utc_now_iso(),
                }
            )

    entries.sort(key=lambda x: x["target_id"])
    return {
        "generated_at_utc": _utc_now_iso(),
        "watch_target_count": len(entries),
        "entries": entries,
    }


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _entry_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = snapshot.get("entries") or []
    return {str(x.get("target_id")): x for x in entries if isinstance(x, dict)}


def compare_snapshots(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    before = _entry_map(baseline)
    after = _entry_map(current)

    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed: list[dict[str, Any]] = []

    for key in sorted(set(before) & set(after)):
        a = before[key]
        b = after[key]
        diffs: dict[str, dict[str, Any]] = {}

        for field in ["law_mst", "law_effective_date", "law_promulgation_date", "article_title", "article_text_hash"]:
            if a.get(field) != b.get(field):
                diffs[field] = {"before": a.get(field), "after": b.get(field)}

        if diffs:
            changed.append(
                {
                    "target_id": key,
                    "law_name": b.get("law_name"),
                    "article_no": b.get("article_no"),
                    "title_keyword": b.get("title_keyword"),
                    "reason": b.get("reason"),
                    "diffs": diffs,
                }
            )

    return {
        "checked_at_utc": _utc_now_iso(),
        "summary": {
            "total_targets": len(after),
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "has_changes": bool(added or removed or changed),
        },
        "added": [after[x] for x in added],
        "removed": [before[x] for x in removed],
        "changed": changed,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="핵심 조문 개정 감지")
    parser.add_argument(
        "--snapshot",
        default="data/legal_watch_snapshot.json",
        help="기준 스냅샷 파일 경로",
    )
    parser.add_argument(
        "--report",
        default="data/legal_watch_report_latest.json",
        help="비교 리포트 파일 경로",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="현재 조문으로 기준 스냅샷 갱신",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    snapshot_path = Path(args.snapshot)
    report_path = Path(args.report)

    try:
        current = build_snapshot(_iter_targets())
    except Exception as e:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(e),
                    "hint": "LAW_API_OC/.env 설정과 법제처 API 응답 상태를 확인하세요.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 3

    if args.refresh:
        _write_json(snapshot_path, current)
        print(
            json.dumps(
                {
                    "ok": True,
                    "mode": "refresh",
                    "snapshot_path": str(snapshot_path),
                    "watch_target_count": current.get("watch_target_count"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not snapshot_path.exists():
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "기준 스냅샷이 없습니다.",
                    "next": f"uv run python law_watch.py --refresh --snapshot {snapshot_path}",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    baseline = _load_json(snapshot_path)
    report = compare_snapshots(baseline, current)
    _write_json(report_path, report)

    output = {
        "ok": not report["summary"]["has_changes"],
        "snapshot_path": str(snapshot_path),
        "report_path": str(report_path),
        "summary": report["summary"],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 1 if report["summary"]["has_changes"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

