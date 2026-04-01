# Tax Agent

> 대한민국 세법 기반 개인소득세 전문 AI 세무 에이전트 — 세무사 실무를 대체하는 개인 맞춤 자동화 시스템

## 기술 스택

| 영역 | 기술 |
|---|---|
| AI 코어 (Phase 1) | Claude Code (claude CLI) |
| AI 코어 (Phase 2) | Claude API (claude-sonnet-4-6) |
| 백엔드 | Python 3.12 + FastAPI |
| DB (Phase 1) | SQLite + SQLCipher |
| DB (Phase 2) | PostgreSQL |
| 문서 파싱 | pdfplumber + pytesseract + Pillow |
| 법령 조회 | 법제처 Open API |
| 웹 UI (Phase 2) | Next.js 15 + Tailwind CSS |
| 패키지 관리 | uv |

## 목표 / 완성 기준

- 세무 자료 제출 → 전략 제안까지 10분 이내
- 제안된 절세 항목이 실제 세무사 검토 결과와 80% 이상 일치
- 법령 인용 오류 0건 (법제처 API 직접 조회 기준)
- 사용자가 에이전트 제안만으로 종합소득세 신고서 독립 완성 가능

## PRD / TRD

- vault: `30-projects/tax-agent/PRD.md`
- vault: `30-projects/tax-agent/TRD.md`

## 프로젝트 구조

(초기 단계 — 개발 진행 시 업데이트)

## 개발 명령어

```bash
# 설치
uv sync

# 실행
python main.py

# 테스트
uv run pytest
```

## 작업 방식

- 새 기능 → 항상 계획 먼저, 구현 나중
- 50줄+ 코드 작성 → Codex 위임
- 복잡 리서치 → Gemini 위임
- Phase 1은 Claude Code 환경 전용, Phase 2에서 Claude API로 전환

## 핵심 모듈

- `document_parser.py` — PDF/이미지 세무자료 파싱
- `legal_search.py` — 법제처 Open API 연동
- `tax_calculator.py` — 소득세 세액 계산 엔진
- `strategy_engine.py` — 절세 전략 수립 (Claude 추론)
- `execution_planner.py` — 전략 실행 지원 (신고서 초안)
- `tax_store.py` — SQLite 데이터 영속성

## 환경 변수 (.env)

```
MOLEG_API_KEY=       # 법제처 Open API 인증키
DB_ENCRYPTION_KEY=   # SQLite 암호화 키 (64자 hex)
ANTHROPIC_API_KEY=   # Phase 2용
```
