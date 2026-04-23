# Tax Agent 로드맵

> 마지막 업데이트: 2026-04-24
>
> **현재 상태**: Phase 1~8-A 완료 + Phase 10 `/tax` 스킬 재정비. 계산·룰·판단·UI 4레이어 모두 실용 가능 수준. Phase 9 웹 UI는 중단(Claude Code 터미널로 대체).
>
> **다음 방향**: Track B(판단 깊이) + Track C(사용자 경험). 홈택스 전자신고(Track A)는 실무 필요 생길 때까지 후순위.

---

## 현재 시스템 스냅샷

| 레이어 | 산출물 | 지표 |
|---|---|---|
| 계산 엔진 | 소득·부가·상증·법인·종부 Level 4 + 양도 14규칙 + 비상장주식 평가 | certify_phase1 26/26, Phase 2~4 eval 전부 pass |
| strategy_engine | 40+ 규칙 (소득·법인·상증·증여·양도·종부) | catalog_v1 105/105, goldset 20~22/25 = 80% (PRD 달성) |
| reasoning_engine | 30 이슈 (4세목) + decisive_sources 핀 8건 | 회색지대 **30/30 = 100% ruling** |
| 프론트엔드 | `TaxAgent.exe` Streamlit + LangGraph 6 tool | 5탭(소득·법인·상속·증여·법령검색) 데스크톱 |
| Skill 진입점 | `/tax` SKILL.md (891줄) | Phase 1~8-A 전체 기능 호출 가이드 |
| 시험 파이프라인 | CPA 1차·2차, 세무사 1차·2차 기출 2023~2026 파싱 | `parse_exam_papers` + `mcq_eval` + `exam_eval` |

---

## PRD 완성 기준 대비 달성도

| # | 기준 | 상태 |
|---|---|---|
| 1 | 자료 제출 → 전략 제안 10분 이내 | ✅ 달성 |
| 2 | 절세 제안이 세무사 검토와 80% 일치 | ✅ 회색지대 100% + 골드셋 80% |
| 3 | 법령 인용 오류 0건 | ✅ decisive_sources + law-mcp |
| 4 | 에이전트 제안만으로 신고서 독립 완성 | ⏸ Track A (실무 필요 생길 때) |

---

## Track B — 판단 깊이 확장

**목표**: PRD 2번을 80% → 95%로. 회색지대·기출 커버리지 확대.

### B-1. 변동성 대응 (2026-04-24 완료 · 결론: 로컬 모델 제거)

qwen3:32b 20~22/25 → **Opus 4.7 로 25/25 = 100%**. 변동성은 로컬 모델 품질 한계였음.

- [x] 2026-04-24: `data/eval/claude_runs/opus_goldset_v1.yaml` — description 만 보고 Claude 가 profile 추출 → `eval_goldset.py` 채점 **25/25 = 100%** 통과
- [x] 결론: 변동성 원인 = LLM 추출 품질(a). Opus 4.7 경로로 전환하면 해소
- 보고: `data/eval/claude_runs/b1_result.md`

### B-2. 규칙·이슈 확장 (1~2주)

**정량 규칙 누락분 보강 (반나절씩)**
- [ ] `DED_HOUSING_SAVINGS_CHEONGYAK` 신설 — 주택청약종합저축 소득공제 (조특 §87, 납입액×40%, 한도 300만). C-1 S1 실증에서 누락 확인
- [ ] 월세 세액공제 조건 확장 — `CRED_MONTHLY_RENT` 현행 대비 요건(총급여 7천→8천만 상향 등) 재검증
- [ ] 근로자 중소기업 취업 감면(조특 §30) 규칙 존재 여부 확인 → 없으면 추가
- [ ] `GRAY_CORP_GAJIGEUPGEUM_INTEREST` decisive_sources 핀 추가 — C-1 S3 실증에서 핀 없음 확인. 관련 대법원 판례·국세청 예규 pinning

**회색지대 이슈 30 → 50**
현재 법인 8·소득 10·상증 6·부가 6. 확장 후보:
- [ ] 양도세 심화 10건 (1세대1주택 + 일시적 2주택 + 분양권 + 부수토지 + 주거전용 판정)
- [ ] 국제조세 4건 (거주자 판정·이중거주 타이브레이커·국외전출세·이전가격)
- [ ] 부가세 보강 4건 (간주공급·폐업시 잔존재화·세금계산서 수정 사유)
- [ ] decisive_sources 핀을 각 이슈마다 최소 1건 (핀 8 → 30건 목표)

### B-3. 골드셋 25 → 50 (1주)
- [ ] 추가 25케이스 — 복합 시나리오 우선 (소득+양도, 법인+증여, 가업승계+연부연납)
- [ ] 각 케이스에 expected 규칙 발동 목록 + confidence threshold
- [ ] `eval_goldset` 50/50 = 100% 달성 기준

### B-4. 2026년 세법 개정 반영 (1주, 연 1회)
- [ ] `law_watch.py` 실행 → 2025년 대비 변경 조문 diff
- [ ] 세율·한도 변경 식별 → 계산 엔진 업데이트
- [ ] 회귀 무회귀 확인
- [ ] CHANGELOG.md에 "2026 반영 완료" 기록

### B-5. 세무사 2차 서술형 자동 채점 확장 (선택, 1~2주)
현재 수동 풀이. 자동화 위험성은 과거 `mcq_eval.py` 병렬 배치 실패로 확인됨 → 배치 금지, 1문제 단위로.
- [ ] `cpa_eval.py` → `cta2_eval.py` 확장 (세무사 2차)
- [ ] 채점 기준 — 정답 JSON 숫자 exact + 서술형은 핵심 키워드 포함
- [ ] 2023~2025 3개년 × 4문제 = 12문제 돌려보기

---

## Track C — 사용자 경험 강화

**목표**: `/tax` 스킬과 `TaxAgent.exe`가 실제 "누구나 쓸 수 있는" 수준으로.

### C-1. `/tax` 스킬 실사용 테스트

- [x] **엔진 단위 테스트 3/3 (2026-04-24)** — `scripts/c1_engine_unit_tests.py` + Claude 직접 분석
  - S1 소득세 strategy_engine: 3/3 발동 (CRED_CHILDREN · DED_PENSION_IRP_700 · TIMING_MEDICAL_EXPENSE)
  - S2 법인세 strategy_engine: 2/2 발동 (CORP_INTEGRATED_INVESTMENT_CREDIT · CORP_RD_TAX_CREDIT)
  - S3 회색지대 가지급금: Claude + law-mcp 경로로 ruling "당좌대출이자율적용" 도출
  - 보고: `data/eval/tax_skill_runs/c1_scenarios.md`
- [ ] **실제 /tax 호출 시나리오 10건** — Claude Code 터미널에서 질의 → 경로 선택 검증 (C-1 확장)
  - 근로·사업·양도·증여·법인·부가·종부·회색지대 각 1~2건
  - 실패 케이스 → SKILL.md 분기 규칙·예시 보강

### C-2. Phase 8-B orchestrator Top-3 추천 (2~3일)
현재 40+규칙 전체 나열 → 실행 가능한 3~5개 우선순위로 변환.
- [ ] **다중 기준 스코어링** — 절세액 × 확실성 × 실행 난이도 가중합. registry에 weight 노출
- [ ] **리스크 필터** — 세무조사 트리거 높은 전략(부당행위·실질과세·조세회피)에 경고 배지 + confidence cap
- [ ] **상호작용 처리** — 상충 규칙(분리 vs 합산, 이연 vs 즉시) 감지 → 시뮬레이터로 세액 비교 → 1개 top 추천
- [ ] **사용자 프로필 적응** — `risk_tolerance: conservative|balanced|aggressive`로 필터링
- [ ] UI 탭에 "추천 전략 Top 3" 섹션 표시

### C-3. TaxAgent.exe UI 개선 (1주)
- [ ] 종부세 탭 추가 (현재 5탭 → 6탭)
- [ ] 양도세 탭 추가 (현재 소득세와 합쳐져 있음)
- [ ] 입력 폼 UX 개선 — PDF 드래그앤드롭 → 자동 파싱 → 필드 채움
- [ ] orchestrator Top-3 결과를 "추천 전략" 카드 형태로

### C-4. 다중 세션 영속성 (선택, 2~3일)
- [ ] `tax_store.py` SQLCipher 활용 — 납세자 프로필·과거 계산 이력 저장
- [ ] UI에서 "지난 계산 불러오기" — 기간 조정 후 재계산
- [ ] 연도별 세액 추이 그래프 (2025 vs 2026)

---

## Track A — 홈택스 전자신고 (후순위)

실무 신고 필요 생기면 착수. 현재는 보류.

- [ ] 홈택스 개발자 가이드 XML 포맷 분석 (종소세·법인세·부가세·상증세)
- [ ] `execution_planner_hometax.py` — dict → XML 변환기
- [ ] 파일 유효성 검증 (실제 제출 금지, 포맷 valid만)
- [ ] 세무사 검증 1회
- [ ] 제약: 자동 제출 안 함. 공인인증서 로그인·제출은 사용자 직접. ANTHROPIC_API_KEY 금지 유지

---

## 이어서 할 일

> 다음 세션에서 여기부터 시작.

### 2026-04-24 세션 산출물

- ROADMAP 1055→182줄, 아카이브 9개 파일 분리
- B-1 완료 (Opus 25/25), C-1 엔진 단위 3/3 통과
- 발견: 주택청약 규칙 누락, 가지급금 이슈 핀 없음, reasoning_engine 내부 LLM 로컬 의존

### 다음 우선순위

1. **C-1 확장 — 실제 `/tax` 호출 시나리오 3~5건** — Claude Code 터미널에서 실제 사용자처럼 질의 → 경로 선택 로그 + SKILL.md 분기 규칙 검증
2. **B-2 정량 규칙 2종 신설** — 주택청약(조특 §87) + 가지급금 핀 추가 (반나절씩)
3. **아키텍처 결정** — `agent/llm/registry.yaml`에 Claude adapter 추가 여부. reasoning_engine 내부 LLM을 Claude 로 돌릴 수 있게 → B-1 결론의 연장선

---

## 설계 원칙 (변경 없음)

### 법령 기반 구현

세무사는 법령을 읽고 로직을 머릿속에 내재화한 뒤 실무에 적용한다. 이 시스템도 동일:

```
세무사:   법령 읽기 → 로직 암기 → 사례에 적용
스킬:     법령 읽기 → Python 함수로 구현 → 사례에 적용
                      (법령 개정 시 함수 업데이트)
```

### 법제처 API vs Python 함수 분담

```
계산이 필요한 것 → Python 함수
  예: 공제 금액, 세율 적용, 단계별 산출

조문 해석이 필요한 것 → 법제처 API
  예: 비과세 요건 판단, 특례 적용 여부, 최신 개정 확인

둘 다 필요한 것 → 함수로 계산 + API로 근거 제시
  예: 1세대1주택 비과세 (요건은 API, 세액은 함수)
```

### 완성 기준 (세목별 동일 적용)

```
Level 1 — 함수 존재:     코드가 실행됨
Level 2 — 파이프라인:    시나리오 흐름이 연결됨
Level 3 — 숫자 검증:     세법 교재·홈택스 계산기와 수치 일치
Level 4 — 실무 완성:     경계값·특수케이스·선택 로직까지 커버
```

---

## 자료 수집 자동화 (참고)

### 현재 (MVP) — PDF 파싱
사용자가 홈택스에서 직접 출력 → 파일 경로 입력 → `document_parser.parse_pdf()` 파싱. SKILL.md에 출력 방법 안내.

### 추후 — CODEF API 연동 (서비스화 단계)
- CODEF (codef.io): 민간 인증 대행 API. 공동인증서/간편인증으로 간소화 자료를 JSON 반환.
- 사용자 본인 인증 기반, 법적 안전.
- 다수 사용자 서비스 단계에서 도입 검토.

---

## 완료 이력 (아카이브)

- Phase 1 — 소득세 Level 4 + 인증 + 보완 + A/B 실증 · [archive](docs/roadmap-archive/phase-1-income-level4.md)
- Phase 2 — 부가세 Level 4 (1차 8/8, 2차 3개년) · [archive](docs/roadmap-archive/phase-2-vat.md)
- Phase 3 — 상속세·증여세 Level 4 · [archive](docs/roadmap-archive/phase-3-inheritance-gift.md)
- Phase 4 — 법인세 Level 4 + 2차 서술형 78/78 · [archive](docs/roadmap-archive/phase-4-corporate.md)
- Phase 5 — strategy_engine + execution_planner + PDF 렌더러 + 프론트엔드 · [archive](docs/roadmap-archive/phase-5-strategy-planner.md)
- Phase 6/7/7-A — 판단 레이어 30/30 = 100% · [archive](docs/roadmap-archive/phase-6-7-judgment-layer.md)
- Phase 8-A — 규칙 3종 (조특§7·종부세·지방소득세) · [archive](docs/roadmap-archive/phase-8-a-rules-3.md)
- Phase 9 — 웹 UI 중단 (`/tax` + Claude 채널로 대체) · [archive](docs/roadmap-archive/phase-9-web-ui-canceled.md)
- Phase 10 — /tax 스킬 전면 보강 · [archive](docs/roadmap-archive/phase-10-tax-skill.md)
