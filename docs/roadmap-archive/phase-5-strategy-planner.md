# Phase 5 — 상위 레이어 (strategy_engine · execution_planner · 프론트엔드)

> **상태**: 5-A/5-B/5-C-1 완료 · 5-C-2(홈택스 XML)는 신규 ROADMAP에 이월 (실무 필요 없어 후순위)

## 개요

모든 세목 계산 엔진이 Level 4에 도달한 후 구축.

| 모듈 | 내용 |
|---|---|
| `strategy_engine.py` | 절세 전략 — 공제 최적화, 분리/종합 선택, 시뮬레이션 |
| `execution_planner.py` | 신고서 초안 생성 |
| Claude API 전환 | Phase 1 Claude Code → Phase 2 FastAPI + claude-sonnet-4-6 (Phase 9 중단으로 보류) |

## Phase 5-A — strategy_engine 설계 (2026-04-14)

실제 세무사 절세 업무 파이프라인을 모델링한 4단계.

**4단계 아키텍처**:

```
입력: tax_result (Phase 4 계산 결과) + 원시자료 + 납세자 프로필
 ↓
[1] 완전성 진단 (Gap Detector) — 누락 경비·공제 탐지
 ↓
[2] 전략 후보 생성 (Strategy Generator) — 규칙 카탈로그 기반
    · 분리/종합 선택 (금융 2천만·주택임대 2천만·기타 300만 경계)
    · 기장 방식 전환 (매출 4,800만·7,500만 임계치)
    · 공제·감면 전수 체크 (중기특별감면·자녀·월세·연금계좌)
    · 시점 전략 (의료비 몰아주기·기부금 이월)
 ↓
[3] 시뮬레이터 (What-if Engine) — tax_calc_cli 재호출로 세액 비교
 ↓
[4] 리스크 플래그 (Risk Gate) — law-mcp 조문 검증 + 세무조사 트리거
 ↓
출력: 우선순위화된 전략 리스트 + 절세액 + 근거조문 + 리스크
```

**모듈 구성**:
- `strategy_engine/gap_detector.py` — 체크리스트 기반 누락 탐지
- `strategy_engine/strategy_rules.py` — 규칙 카탈로그 (YAML/JSON 드리븐)
- `strategy_engine/simulator.py` — tax_calc_cli 호출 래퍼
- `strategy_engine/risk_flags.py` — 리스크 룰
- `strategy_engine/orchestrator.py` — 4단계 실행 + 결과 종합

### 완료

- [x] 5-A-1: 규칙 카탈로그 YAML 스키마 v0 (2026-04-14)
- [x] 5-A-2: 골든 셋 5규칙 + `eval_strategy_rules.py` 12/12 통과
- [x] 5-A-3: 종소세 e2e — `eval_strategy_e2e.py` 7/7 통과
- [x] 5-A-4: 기출 2차 서술형 재활용 회귀 — 법인세 리스크 규칙 2개 추가, CPA 2024 Q5 + CPA 2025 Q5 프로필 `eval_strategy_corp_risk.py` 8/8 통과
- [x] 5-A-5: 규칙 카탈로그 v1 — **22규칙** (소득 13 + 법인 5 + 상속 2 + 증여 2). 19종 estimator, profile_builder defaults. `eval_strategy_catalog_v1.py` 30/30

**Phase 5-A 통합 회귀**: rules 12/12 + e2e 7/7 + corp_risk 8/8 + catalog_v1 30/30 = **57/57** + certify_phase1 26/26

## Phase 5-B — execution_planner (2026-04-14)

- [x] `execution_planner.py` — 4세목 신고서 초안 MVP. tax_result + strategy + judgment 통합
- [x] 출력 스키마: 신고서제목·과세기간·행항목·적용전략·판단이슈·체크리스트·주의사항
- [x] `eval_execution_planner.py` 6/6 통과
- [ ] 세목별 신고서 서식(pdf) 출력은 5-C-1로 이관

## Phase 5-B 프론트엔드 통합 (2026-04-14)

`local-ai-workstation` → `tax-agent` 이전 + UI + LangGraph + `TaxAgent.exe` 재빌드

- [x] 1-2. 13개 파일 복사 + import 경로 재편 (`sys.path` 제거, `tax_rag` → `agent.rag`)
- [x] 3. pyproject 의존성 5종 (`streamlit`, `langgraph`, `langchain-core`, `langchain-ollama`, `pywebview`)
- [x] 4. PyInstaller spec 재작성 (패키지형 `strategy_engine` + YAML rules 번들)
- [x] 5. Streamlit 부팅 테스트 (HTTP 200)
- [x] 6. UI 5탭(소득·법인·상속·증여·법령검색) + LangGraph `@tool` 6개
- [x] 7. `TaxAgent.exe` 재빌드 96MB + 바로가기 갱신
- [x] 7-A. Ollama 자동 기동 (`tax_app.py`의 `ensure_ollama`)
- [x] 7-B. 140GB 모델 C:→D: 이동 (`OLLAMA_MODELS=D:\ollama\models`)
- [x] 7-C. 소득세 탭 결정론적 엔진 직접 호출 (qwen3:32b 툴 우회 보정)
- [x] 7-D. 사용자 GUI 실증 (절세 전략 섹션 채워짐 확인)
- [x] 8. `local-ai-workstation/*` 13개 파일 `git rm` (commit ec5c830)

## Phase 5-C-1 — PDF 렌더러 (완료)

- [x] `execution_planner_pdf.py` — dict → PDF (reportlab + NanumGothic)
- [x] 4세목 템플릿 (소득·법인·부가·상증)
- [x] 행항목 표 + 적용전략 박스 + 판단이슈 박스 + 체크리스트·주의사항
- [x] `eval_execution_planner_pdf.py` — 파일 크기·페이지 수 assert

## Phase 5-C-2 — 홈택스 전자신고 (이월)

신규 ROADMAP 하단 "Track A (후순위)" 참조. 실무 신고 필요 생길 때 착수.
