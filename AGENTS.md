# AGENTS.md

이 저장소에서 작업하는 Codex는 먼저 `./CLAUDE.md`를 읽고 프로젝트 목적, 구조, 작업 방식을 따른다.

## 이 저장소의 성격

- 대한민국 개인소득세 중심 AI 세무 에이전트 프로젝트
- 현재 단계는 Python CLI 프로토타입
- 핵심 흐름은 문서 파싱 → 소득/공제 계산 → 절세 전략 제안

## Codex 작업 규칙

- 구현 전에 관련 파일을 먼저 읽고 현재 구조를 확인한다.
- 작은 수정은 직접 수행하고, 큰 변경은 영향 범위를 먼저 정리한 뒤 진행한다.
- 기존 사용자의 변경사항은 되돌리지 않는다.
- 숫자 계산 로직 변경 시 가능한 범위에서 시나리오나 테스트로 검증한다.
- 법령 해석이 필요한 부분은 계산 코드와 설명 로직을 혼동하지 않는다.

## 우선 참고 파일

- `CLAUDE.md`
- `ROADMAP.md`
- `main.py`
- `tax_calculator.py`
- `document_parser.py`
- `strategy_engine.py`
- `legal_search.py`
- `tax_store.py`

## 메모

- `CLAUDE.md`는 프로젝트 설명과 작업 원칙의 기준 문서다.
- `AGENTS.md`는 Codex가 이 저장소에서 따를 최소 실행 규칙만 담는다.
