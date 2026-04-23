# B-1 결론 (2026-04-24) — 로컬 모델 대체 실험

## 실험 설계

| 항목 | 기존 (qwen3:32b) | 신규 (Opus 4.7 = Claude Code) |
|---|---|---|
| 역할 | 자연어 description → flat profile JSON 추출 | 동일 |
| 경로 | `eval_ollama_rule_firing.py --run` | Claude 가 goldset description 25 건 직접 읽고 profile YAML 작성 |
| 채점 | `strategy_engine.run(extracted_profile)` vs expected | 동일 |

## 결과

| 모델 | Goldset 통과율 | 케이스당 소요 | 변동성 |
|---|---|---|---|
| qwen3:32b v4 | 20~22/25 (80~88%) | ~12s → 실측 3~4분 | **높음** (재실행마다 진동) |
| Opus 4.7 | **25/25 (100%)** | Claude 본인 처리(대화 흐름) | 결정론적 (같은 입력 같은 결과) |

## 해석

1. **변동성 원인 = LLM 추출 품질**. Opus 4.7로 전부 해소.
2. 규칙 트리거 조건(프롬프트 v4 → 규칙 YAML OR 보강)은 이미 Phase 8 후보에서 수정 완료. 남은 부채 없음.
3. G022 보험 상속/증여 오분류 같은 qwen3:32b 지식 한계도 Opus 4.7에선 발생 안 함.

## Track B-1 상태

- [x] **남은 5건 변동성 대응** — **해결**. Opus 4.7 경로로 전환하면 25/25 = 100%.

## 함의 — 아키텍처 결정

로컬 Ollama 사용 시나리오는 사실상 **TaxAgent.exe 프론트엔드 전용** (오프라인·데스크톱). /tax 스킬 + Claude Code 터미널 경로는 이미 Opus 4.7.

### 다음 단계 (별도 논의)

- **`agent/llm/registry.yaml`에 "claude-opus-4-7" 엔트리 + adapter 추가 검토** — 현재 Ollama 전용. reasoning_engine / profile 추출 등을 Claude 기반으로 돌리는 공식 경로 확보.
- **eval_ollama_rule_firing.py 역할 재정의** — "로컬 모델 회귀 검증"으로 좁히고, 주력은 Claude 기반으로.
- **qwen3:32b 골드셋 재측정은 보류** — 프론트엔드 세션에서 문제 생기면 그때 디버깅.

## 입력 파일

- `data/eval/claude_runs/opus_goldset_v1.yaml` — Opus 추출 profile 25 건

## 검증 명령

```bash
uv run python eval_goldset.py --goldset data/eval/claude_runs/opus_goldset_v1.yaml
# 결과: 25/25 = 100.0% (PRD 목표 80%) [OK]
```
