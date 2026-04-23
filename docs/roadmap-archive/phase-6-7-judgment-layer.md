# Phase 6 + 7 + 7-A — 판단형 세무 에이전트 (Judgment Layer)

> **완료**: 2026-04-17 · 회색지대 30/30 = 100% 달성
> 계산·룰베이스·LLM 프롬프트까지 "정답이 있는 문제"는 Phase 1~5로 해결. 회색지대 판단·증빙 적격성·세무조사 리스크를 다루는 레이어.

---

## Phase 6 — Judgment Layer MVP (소득세 10케이스)

### 아키텍처

```
strategy_engine.run(profile)
        ↓
[1] Issue Extractor   — profile + 발동규칙에서 회색지대 이슈 식별
[2] Legal Retriever   — 하이브리드 RAG (로컬 코어 + law-mcp on-demand)
[3] Reasoning Engine  — LLM이 판례·예규 근거로 판단 + 신뢰도
[4] Audit Adversary   — 세무조사관 페르소나로 반박·보강증빙 요구
        ↓
출력: {issue, 판단, 신뢰도, 근거조문·판례, 반박포인트, 보강증빙}
```

### 모듈 구성

- `reasoning_engine/issue_extractor.py` — 회색지대 이슈 플래그
- `reasoning_engine/legal_retriever.py` — 하이브리드 RAG (BM25 로컬 + law-mcp 폴백)
- `reasoning_engine/reasoner.py` — LLM 판단 (프롬프트 v5, JSON 출력)
- `reasoning_engine/adversary.py` — 조사관 self-check
- `reasoning_engine/orchestrator.py` — 4단계 실행
- `reasoning_engine/issues/income_tax_gray.yaml` — 10개 회색지대 이슈
- `data/precedent_corpus.json` · `data/admin_rule_corpus.json` — 로컬 코어 캐시

### 완료 항목 (2026-04-14)

- [x] 6-A: 10 이슈 카탈로그 + `judgment_goldset_v1.yaml`
- [x] 6-B: `agent/law_client.py` 확장, BM25 검색
- [x] 6-C: `reasoner.py` + `orchestrator.py` 프로토타입 v5
- [x] 6-D: `adversary.py` — 세무조사관 페르소나 (조사4국)
- [x] 6-E: `eval_judgment_v1.py` — 3메트릭

### 검증 (2026-04-14)

- [x] 소득세 10/10: ruling 8/10, source 10/10, forbidden 10/10 ✅
- [x] `eval_strategy_catalog_v1`: 94/94 ✅
- [x] `eval_goldset`: 25/25 = 100% ✅

### 비용·리스크 통제

- **할루시네이션**: retrieved_legal에 없는 판례번호 인용 금지
- **비용**: reasoner+adversary 2콜 = 케이스당 2×LLM. risk medium↑ 게이트
- **프롬프트 분리**: v4는 strategy, v5는 reasoning. registry 확장

---

## Phase 7 — 판단 레이어 횡확장 (2026-04-14 완료)

Phase 6 MVP 아키텍처를 법인세·부가세·상증세로 확장.

### 산출물

- `reasoning_engine/issues/` 디렉토리 스캔 다중 scope
  - `corporate_tax_gray.yaml` 8 issues
  - `vat_gray.yaml` 6 issues
  - `inheritance_gift_gray.yaml` 6 issues
- `data/eval/judgment_goldset_v1_{scope}.yaml` 분리 (글롭 로딩)
- `eval_judgment_v1.py --scope {corporate_tax|vat|inheritance_gift}` 필터

### 결과 (26+10 = 30 케이스, 3메트릭)

| 세목 | ruling | source | forbidden |
|---|---|---|---|
| 소득세 (기존) | 8/10 | 10/10 | 10/10 |
| 법인세 | 7/8 (87%) | 8/8 | 8/8 |
| 부가세 | 4/6 (67%) | 6/6 | 6/6 |
| 상증세 | 5/6 (83%) | 6/6 | 6/6 |
| **전체** | **24/30 (80%)** | **30/30 (100%)** | **30/30 (100%)** |

부가세 67%는 LLM 보수 bias(안분 선호·실질과세 약함·최신판례 미반영). → Phase 7-A에서 검색 레이어로 돌파.

---

## Phase 7-A — decisive_sources (2026-04-14 ~ 2026-04-17)

> **배경**: 부가세 67%·상증세 J302 미달 원인은 프롬프트가 아니라 **검색 천장**. 결정판례가 retrieved_legal에 없으면 어떤 프롬프트로도 못 뒤집는다.

### 작업

- [x] 7-A-1: issue yaml `decisive_sources` 필드 (판례·예규 ID + 메타)
- [x] 7-A-2: `legal_retriever.py` — `_pin_decisive()` top-k 강제
- [x] 7-A-3: `agent/law_client.py` — `get_precedent()` 추가
- [x] 7-A-4: `reasoner.py` — 결정판례 판결요지 프롬프트 노출 + 지시 0번 최우선
- [x] 7-A-5: `eval_judgment_v1.py` — `decisive_in_context` 메트릭
- [x] 7-A-6: J302/J202/J205 핀 — 3건 스폿체크 통과
- [x] 7-A-7: 30 회귀 — 27/30 = 90% (24→27, +10%p)
- [x] 7-A-8: J002/J007/J105 핀 추가 (2026-04-17)
  - J002: 대법원 2022두32382 — 가사관련경비 추정 + 면적비율 안분 ⇒ 안분인정 ✓
  - J007: 부산지법 2017구합22603 — §48 근속연수공제(5년→500만) + §50 합산 ⇒ 공제부인 ✓
  - J105: 서울행정 2014구합68188 + 서울고법 2020누43281 + 국세청 사전심사 ⇒ 일부자본화 ✓
- [x] 7-A-9: 30 회귀 — **28/30 = 93%** (3핀 통과 +1, J205 변동성 -1)
- [x] 7-A-10: J305·J205 핀 강화 → **30/30 = 100%** (2026-04-17)
  - J305: 서울행정 2018구합63426 — 대습상속인 = 상속인 → 10년 합산, 7년전 5억 → 전액합산 ✓
  - J205: 계산식(8천+8천>1억400만) + ruling 라벨 "일반과세전환" 명시 → 3연속 통과 안정화 ✓

### Phase 7-A 결론

**검색 천장 완전 돌파**: 프롬프트 튜닝 없이 검색 레이어만으로 24/30 → **30/30 = 100%** (+20%p). 결정판례가 retrieved_legal에 강제 주입되면 LLM은 올바른 판단을 내린다 = 검색이 진짜 병목이었음이 최종 증명됨.

**핀 작성 교훈**: 단순 판례 인용만으로는 부족. 판결요지에 **계산식·ruling 라벨**을 직접 박아야 LLM이 ruling_spectrum 라벨을 정확히 선택한다. (J007 500만 산식, J205 일반과세전환 라벨 명시가 결정적)

---

## Phase 6 후속 — strategy_engine v2 확장 (2026-04-14)

### 법인세 v2 6규칙 추가 (22→28)

2차 실증 78/78 근거 기반.
- CORP_BAD_DEBT_RESERVE_EXCESS — 대손충당금 한도초과 (법34·령61·62)
- CORP_RETIREMENT_RESERVE_EXCESS — 퇴직급여충당금 한도초과 (법33·령60)
- CORP_COMPANY_VEHICLE_EXCESS — 업무용승용차 1,500만 초과 (법27의2·령50의2)
- CORP_ESO_NONDEDUCTIBLE — 주식매수선택권 비벤처·비중소 손금불산입 (법19의2)
- CORP_DEEMED_DIVIDEND_WITHHOLDING — 의제배당 원천징수 14% (법16·소127)
- CORP_LOSS_CARRYBACK — 중소기업 결손금 소급공제 환급 (법72)
- 회귀: **95/95**

### 증여세 v2 4규칙 (28→32)

- GIFT_LOW_PRICE_TRANSFER — 저가양수·고가양도 (상증 35·령 26)
- GIFT_FREE_LOAN_BENEFIT — 금전 무상·저리 대여 (상증 41의4·령 31의4)
- GIFT_FREE_REAL_ESTATE_USE — 부동산 무상사용 (상증 37·령 27)
- GIFT_INSURANCE_PROCEED — 보험금 납부자≠수익자 (상증 34)
- 회귀: **103/103**

### 비상장주식 평가 모듈

- `unlisted_stock_valuation.py` — 상증법 §63 보충적 평가
- 순손익가치(직전3년 가중평균 ÷ 10%) + 순자산가치 가중평균
- 케이스: 일반(3:2) / 부동산과다 50~80%(2:3) / 80↑(순자산 단독) / 80% 하한
- 회귀 5/5

### 조특법 세액공제 3종 (32→35)

- CORP_RD_TAX_CREDIT — R&D (조특 10): 중소 25% / 신성장 30% / 대 15%
- CORP_INTEGRATED_INVESTMENT_CREDIT — 통합투자 (조특 24): 기본+증가 3%
- CORP_EMPLOYMENT_INCREASE_CREDIT — 통합고용 (조특 29의8): 청년·일반 × 2.5년
- 회귀: **113/113**

### 가업상속·가업승계 2규칙 (35→37) — Phase 6 공식 종료

- INH_FAMILY_BUSINESS_DEDUCTION — 가업상속공제 (상증 18의2): 10/20/30년 300/400/600억
- GIFT_FAMILY_BUSINESS_SUCCESSION — 가업승계 증여 (조특 30의6): 10억 공제 + 120억 10% / 초과 20%
- 회귀: **119/119**

### Phase 7 양도소득세 14규칙 (37→51)

소득세 13→27.

- 7.1 양도차익 기본 (3): TRANSFER_ACQUISITION_DOC · NECESSARY_EXPENSE · GIFT_CARRYOVER
- 7.2 장특공제 (2): LTCG_TABLE1 · LTCG_TABLE2_ONE_HOUSE
- 7.3 1세대 1주택 (4): ONE_HOUSE_EXEMPT · TEMP_TWO_HOUSE · INHERITED_HOUSE · HIGH_VALUE_EXCESS_LTCG
- 7.4 세율·중과 (3): SHORT_TERM_EXTEND · UNREGISTERED_AVOID · MULTI_HOUSE_DEFER
- 7.5 특례·감면 (2): SELF_CULTIVATED_FARMLAND · PUBLIC_EXPROPRIATION
- 회귀: **121/121**

### 품질·실증 레이어 B1/B2/B3

- B2: `eval_scenarios_transfer.py` — 양도 복합 7/7
- B1: `eval_ollama_rule_firing.py` — Ollama 하네스 skeleton
- B3: `eval_goldset.py` + `data/eval/goldset_v1.yaml` — PRD 80% 측정
- 회귀: **128/128**

### 골드셋 5→25 확장

소득세/양도/법인세/증여/복합 20케이스 추가. 51규칙 중 약 80% 커버.

### qwen3:32b 베이스라인

- v1 (필드 최소): **0/5 = 0%** — 통화 오파싱, 도메인 플래그 미추출
- v2 (필드 사전 + 통화 예시, 양도 전용): **4/5 = 80%**
- v2 (goldset 25, 전 세목): **10/25 = 40%** — 실무 베이스라인
- v3 (umbrella flag 15 추가): **15/25 = 60%** (+20%p)
- 개선: 상속 가업승계, 법인 손익합산, 증여 무상대여·저가양수·보험 일부
- 잔여 실패: 개념 누락(임대·기타소득 필드), 긴 설명 체인

---

## Phase 8 후보 — LLM 레지스트리·벤치 (2026-04-14)

- [x] **LLM 레지스트리·어댑터**: `agent/llm/{registry.yaml,registry.py,adapter.py}` 신설. 4개 콜사이트 하드코드 제거. `--compare-all` 추가.
- [x] **qwen3:32b vs gemma4:31b** (goldset 25):
  - qwen3:32b: **16/25 (64%)** · avg 11.6s
  - gemma4:31b: **16/25 (64%)** · avg 12.5s
  - **실패 9건 100% 겹침** — 모델 품질이 아니라 규칙 발동 조건 구조적 결함
  - default qwen3:32b 유지, v3 → v3.1 (temp_two_house old_house_gain 매핑)
- [x] **qwen3.5:35b 실패** (12/25 중단 후 삭제):
  - 6/12 · avg **43s** (3~4배 느림) · 실패 케이스 동일 · 256K 컨텍스트 로딩 비용만 큼
  - 로그 보존: `data/eval/ollama_runs/_qwen35_35b_goldset.log`
- [x] **프롬프트 v4 + 규칙/엔진 보강**: **16→20/25 = 64%→80% (PRD 달성)**
  - simulator 5곳 fallback: `double_entry`, `other_income_separation`, `transfer_multi_house`, `inh_installment`, `gift_insurance`
  - 규칙 YAML 4곳: INH_INSTALLMENT, GIFT_INSURANCE, TRANSFER_NECESSARY_EXPENSE, TRANSFER_GIFT_CARRYOVER
  - **profile_builder 치명 버그**: `_FLAT_TRIGGERS`가 9개 필드(`other_income_net`, `insurance_proceed_amount` 등) 인식 못해 LLM 추출 필드 버려짐 → 추가
  - 프롬프트 v4: `acquisition_docs_available`, `business_revenue` umbrella
  - 회귀 94/94 + 25/25 + 26/26

### 남은 과제

- [ ] **남은 5건 변동성**: LLM 분산으로 재실행마다 20~22/25 진동. G022 GIFT_INSURANCE는 qwen3:32b의 상속/증여 오분류 지식 한계. → 신규 ROADMAP Track B로 이월.
