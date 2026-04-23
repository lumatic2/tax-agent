# Phase 10 — /tax 스킬 전면 보강 (2026-04-18 완료)

> **결정**: Phase 9 웹앱 대신 `/tax` 스킬을 Phase 1~8-A 전체 기능을 직접 호출하도록 확장. 진입점은 Claude Code 터미널 + `/tax` + Claude 채널(모바일).

`custom-skills/tax/SKILL.md` 4 커밋 (+491/-23줄):

---

## [x] 10-1. strategy_engine catalog 업그레이드 (`dc0e757`)

legacy `generate_strategy` → `run()` catalog 37규칙. 세목별 profile 필드 매핑표 + 호출 예시 5종.

## [x] 10-2. 세목 확장 (`70db866`)

- description 확장 — 6개 세목 + 세무사 시험문제
- 새 섹션 1-B: corporate_tax·inheritance_gift·vat·property_holding·unlisted_stock 호출 가이드
- 응답 흐름 7종(법인·상속·증여·부가·종부·양도·시험문제)
- 한계 명시에서 법인세·부가세 제거

## [x] 10-3. 회색지대 reasoning_engine (`146c606`)

- 새 섹션 6 + 30 이슈 카탈로그 (법인 8·소득 10·상증 6·부가 6, decisive_sources 핀 7건)
- 회색지대 질문은 법령 MCP 대신 `reasoning_engine.run(issue_id, profile)` 우선
- 기본 원칙 업데이트

## [x] 10-4+5. 시험 파이프라인 + 8-A 템플릿 (`84a2d83`)

- 새 섹션 7: `parse_exam_papers`·`mcq_eval`·`exam_eval` 문서화
- 조특§7 중소기업 특별세액감면 16셀 감면율표
- 개인지방소득세(§103의52) 10% 표기 규칙

---

## Phase 10 다음 (신규 ROADMAP으로 이월)

- 실사용 테스트 — /tax 스킬이 새 경로를 올바르게 선택하는지 확인 → **Track C-1**
- Phase 5-C-2 홈택스 전자신고 XML → **Track A (후순위)**
- Phase 8-B orchestrator 튜닝 Top-3 추천 → **Track C-2**
