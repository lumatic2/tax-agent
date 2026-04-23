# Phase 9 — 개인 세무 에이전트 UI (2026-04-18 중단)

> **중단 결정 (2026-04-18)**: 대화형 "나만의 세무사" 기능은 **Claude Code 터미널 + `/tax` 스킬 + Claude 채널(텔레그램)** 조합으로 이미 모두 커버됨. 별도 웹 UI 실익 없음. 9-4부터 중단.
>
> **보존 결정**: 9-1~9-3 코드(`agent/sdk/{smoke,smoke_full,server,tools}.py`)와 의존성(`claude-agent-sdk`, `fastapi`, `sse-starlette`)은 exploration 흔적으로 남김. Agent SDK 쓸 일 생기면 레퍼런스.

---

## 원래 아키텍처 (참고)

```
[PC/휴대폰 브라우저] → Next.js 채팅 UI (:3000)
                    ↓ SSE
                FastAPI (:8000)
                    ↓
            Claude Agent SDK (Python)
                    ↓ spawns
            `claude` CLI subprocess  ← Claude Code 구독, 비용 0, Opus 4.7
                    │
    ┌──────────────┼──────────────┐
    ↓              ↓              ↓
tax_calculator  strategy_engine  RAG(decisive_sources)
 (기존 엔진)    (37규칙)         법령·판례
```

## 진행한 단계 (9-1 ~ 9-3)

- [x] **9-1. Agent SDK 스모크** (2026-04-18): `claude-agent-sdk==0.1.63` 설치, `claude` CLI 2.1.114. `agent/sdk/smoke.py` — tax_calculator 1개 tool 붙여 왕복 성공 (16.2s, Opus 4.7)
- [x] **9-2. Tool 전체 포팅** (2026-04-18): `agent/sdk/tools.py` — 7개 tool (`calculate_income_tax` / `get_income_tax_strategies` / `search_tax_law` / `get_corporate_tax_strategies` / `get_inheritance_strategies` / `get_gift_strategies` / `retrieve_legal_sources`) Agent SDK `@tool` 재등록. `smoke_full.py`로 2-tool 체이닝 + 법령 인용 답변 검증
- [x] **9-3. FastAPI + SSE** (2026-04-18): `agent/sdk/server.py`. `/chat` SSE (system/assistant/tool_use/tool_result/result/done), `/sessions` 목록, `/sessions/{id}` 메시지/DELETE. `resume` 세션 이어가기 확인(2회차 3.2s). 포트 8321
  - 남은 이슈: `list_sessions()`가 Claude CLI 전체 세션 반환 → 9-4에서 SQLite 필터 테이블 예정이었으나 중단

## 중단

- [~] **9-4 ~ 9-9 중단 (2026-04-18)** — Claude Code 터미널 + `/tax` 스킬이 같은 목적을 더 싸게 달성

---

## 결정 사항 (2026-04-18)

- **모델**: Opus 4.7 (claude CLI 기본값 그대로)
- **비용**: 0 — Claude Code 구독으로 CLI 사용
- **보안**: 로컬·개인용, 인증 없음. LAN 밖 접속 막기
- **DB**: SQLite 유지 (PostgreSQL 불필요)
