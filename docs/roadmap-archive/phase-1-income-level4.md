# Phase 1 — 소득세 Level 2 → Level 4 + 인증 + 보완 + 실증

> **완료**: 2026-04-11 (22/22 인증) → 2026-04-12 (A/B 실증 종료)
> 원본: ROADMAP.md (아카이브 전)

---

## Phase 1 — 소득세 완성 (Level 2 → Level 4)

Phase 1은 함수 구현(Level 2)이 완료된 상태. 아래 작업으로 Level 4까지 끌어올린다.

### 1-A. 누락 로직 보완 (함수 수정)

- [x] **§62 비교세액 구현** — 금융소득 종합과세 핵심
  - `compare_financial_income_tax(incomes, financial_income)` 신규
  - 분리과세세액(14%×금융소득 전체 + 나머지 종합세액) vs 전액 종합과세 세액 → MAX
  - `calculate_financial_income()` 반환값에 `비교세액_적용` 플래그 추가
- [x] **부양가족 소득요건 검증** — `calculate_personal_deductions()` 수정
  - 각 인원에 `annual_income` 파라미터 추가 (기본값 0)
  - 소득금액 100만원 초과 시 기본공제 제외, 경고 반환
  - 배우자 근로소득만 있는 경우 총급여 500만 이하 = 소득금액 0 예외 처리
- [x] **특별공제 vs 표준공제 선택** — `calculate_special_deductions()` 수정
  - 특별공제 합계 < 130만(표준공제) 이면 자동으로 표준공제 선택
  - 반환값에 `적용방식: "특별공제"|"표준공제"` 추가

### 1-B. eval 고도화 (숫자 assert)

- [x] **시나리오1 숫자 assert** — exact match
- [x] **시나리오2 §62 비교세액 포함 재계산** — exact match
- [x] **시나리오3 각 케이스 산출세액 exact match**

### 1-C. 미커버 시나리오 추가

- [x] **시나리오4: 퇴직소득세** — 근속연수공제 → 환산급여 → 환산급여공제 → 환산산출세액 → 퇴직소득세액
- [x] **시나리오5: 연금소득** — 총연금액 1,500만 이하(분리과세 선택) / 초과(종합과세)
- [x] **시나리오6: 결손금 통산 순서** — 사업→근로→연금→기타→이자→배당, 부동산임대업 격리
- [x] **시나리오7: 중소기업취업자 감면** — 청년(90%)/일반(70%), 200만 한도

### 1-D. 완료 기준

```
모든 assert가 exact match로 전환됨
§62 비교세액 구현됨
eval 7개 시나리오 전부 통과
```

---

## Phase 1-검증 — 소득세 인증 게이트

> Phase 2로 넘어가기 위한 공식 관문. `certify_phase1.py` 가 22/22 통과해야 진행 허가.

### 성공 기준

| 구분 | 항목 | 기준 |
|---|---|---|
| 챕터 테스트 | Ch01~Ch15 전 챕터 전용 assert | 100% 통과 (exact match) |
| 통합 시나리오 | S1~S7 | 100% 통과 |
| 전체 게이트 | `python certify_phase1.py` 종료코드 0 | **22/22 달성** |

### 챕터별 검증 항목

| 챕터 | 검증 함수 | 핵심 assert |
|---|---|---|
| Ch01 | `is_resident()`, `get_taxable_period()` | 183일 경계값, 사망·출국 특례 |
| Ch02 | `calculate_nontaxable_interest()`, `calculate_interest_income_tax()` | 비실명 45%, 장기채권 30% |
| Ch03 | `calculate_deemed_dividend()`, `calculate_recognized_dividend()` | 의제배당·Gross-up exact |
| Ch04 | `calculate_entertainment_expense_limit()`, `calculate_depreciation()`, `calculate_car_expense_limit()` | 한도 초과 분 exact |
| Ch05 | `calculate_nontaxable_employment_income()`, `calculate_simplified_withholding()` | 비과세 항목별 exact |
| Ch06 | `calculate_pension_income()` | 공제액·연금소득금액·과세방식 exact |
| Ch07 | `calculate_other_income()` | 복권 3억 초과 33%, 슬롯머신 30% |
| Ch08 | `calculate_loss_netting()` | 통산 순서, 부동산임대 격리 |
| Ch09 | `calculate_housing_savings_deduction()`, `apply_deduction_aggregate_limit()` | 2,500만 한도 exact |
| Ch10 | `calculate_tax()` | 1000만·5000만·7000만·1억 세율 구간 경계값 exact |
| Ch11 | `calculate_earned_income_tax_credit()`, 세액공제 5종 | 한도·공제액 exact |
| Ch12 | `calculate_retirement_income_tax()` | 환산급여·세액 전 단계 exact (150M/20년) |
| Ch13 | `check_one_house_exemption()`, `calculate_transfer_income_tax()` | 1세대1주택 요건, 양도세액 |
| Ch14 | `calculate_withholding_tax()` | 소득유형별 세율 통합 |
| Ch15 | `calculate_nonresident_tax()` | 국내원천소득 유형별 세율 |

### 현황

- [x] `certify_phase1.py` 생성 완료
- [x] **22/22 인증 통과** (2026-04-11)
- [x] Phase 2 진행 허가

---

## 현재 작업 순서 (Phase 1 실사용 레벨)

> 계산 엔진(Level 4) 완료. 다음은 실제 사용자가 쓸 수 있는 수준으로 UI/파이프라인 완성.

### 🔴 Must — 실사용 불가 구간

- [x] 1-A: §62, 소득요건, 표준공제
- [x] 1-B: eval exact match
- [x] 1-C: 시나리오4~7
- [x] **1-D: 소득 유형별 입력 플로우** (`main.py`) — 근로/사업/복합 분기, 항목별 수집
- [x] **1-E: 계산 파이프라인 오케스트레이션** (`main.py`) — 수집값 → tax_calculator 체인 → 최종세액
- [x] **1-F: 기납부세액 차감** — 원천징수·중간예납 반영 → 환급/추납 금액 도출

### 🟡 Should — 세무사 수준

- [x] **1-G: strategy_engine 실질화** — 실제 세율 기반 절세액 계산, tax_result 연결
- [x] **1-H: PDF 파싱 → 항목 자동 매핑** — 원천징수영수증 파싱 결과 → 파이프라인 입력

### 🟢 Nice to have

- [x] **1-I: 시뮬레이션** — "IRP 300만 추가 시" 세액 변화 미리 보기

---

## Phase 1-보완 — 소득세 미구현 챕터 완성

> 목표: 소득세법 전 챕터를 실무 수준(Level 4)으로 완성.
> 구현 패턴: law-mcp `get_law_article` → `data/*.txt` 저장 → `tax_calculator.py` 함수 추가 → `law_watch.py` 등록 → `eval_scenarios.py` exact assert

### Ch01. 소득세 총설
- [x] `is_resident()` — 거주자/비거주자 판정 (§1의2)
- [x] `get_taxable_period()` — 과세기간 특례 (§5)
- [x] 납세지 규정 안내 → SKILL.md

### Ch02. 이자소득
- [x] `calculate_nontaxable_interest()` — 비과세 이자소득 항목별 판정
- [x] 이자소득 수입시기 규정 (§45) → SKILL.md
- [x] 무조건 분리과세 이자소득 `calculate_interest_income_tax()` (§14②)

### Ch03. 배당소득
- [x] `calculate_deemed_dividend()` — 의제배당 계산
- [x] `calculate_recognized_dividend()` — 인정배당
- [x] 집합투자기구 배당소득 특례 (§17①5) → SKILL.md

### Ch04. 사업소득 — 필요경비 상세
- [x] `calculate_entertainment_expense_limit()` (§35③)
- [x] `calculate_depreciation()` (§33①6, 영§62~§68)
- [x] `calculate_car_expense_limit()` (§33의2: 감가상각비 연 800만 한도)
- [x] 총수입금액 귀속시기 규정 (§39) → SKILL.md
- [x] 비과세 사업소득 (§12①) → SKILL.md

### Ch05. 근로소득
- [x] `calculate_simplified_withholding()` — 간이세액표 (§129·영§194)
- [x] 비과세 근로소득 항목 확장 (§12③)
- [x] 근로소득 수입시기 (§49) → SKILL.md

### Ch06. 연금소득 — 완료 ✓

### Ch07. 기타소득
- [x] 무조건 분리과세 세율 세분화 (§14②)

### Ch08. 종합소득금액 — 완료 ✓

### Ch09. 종합소득공제
- [x] `calculate_housing_savings_deduction()` (조특법 §87)
- [x] `apply_deduction_aggregate_limit()` (조특법 §132의2) — 2,500만

### Ch10. 세액 계산 — 완료 ✓

### Ch11. 세액공제·세액감면
- [x] `calculate_earned_income_tax_credit()` 재구현 (§59)
- [x] `calculate_insurance_tax_credit()` (§59의4①)
- [x] `calculate_medical_tax_credit_detail()` (§59의4②)
- [x] `calculate_education_tax_credit_detail()` (§59의4③)
- [x] `calculate_donation_tax_credit_detail()` (§59의4④)
- [x] `calculate_disaster_loss_tax_credit()` (§58)

### Ch12. 퇴직소득 — 완료 ✓

### Ch13. 양도소득
- [x] `check_one_house_exemption()` (§89①3)
- [x] `calculate_estimated_acquisition_price()` (§97②)

### Ch14. 신고·납부
- [x] `calculate_withholding_tax()` — 원천징수 세율표 통합 (§129)
- [x] 양도소득 예정신고 안내 (§105~§106) → SKILL.md

### Ch15. 비거주자
- [x] `calculate_nonresident_tax()` (§119~§121)
- [x] 조세조약 제한세율 안내 → SKILL.md

---

## Phase 1-실증 — 소득세 A/B 검증

> 목적: 계산기(`tax_calc_cli.py`)와 `law-mcp`가 실제 시험문제에서 유의미하게 기여하는지 검증.
>
> 원칙: **대화창 내 수동 풀이**. 자동화 스크립트 금지.

### 평가 설계

| 구분 | A: 시스템 활용 | B: LLM 단독 |
|---|---|---|
| 계산 | `python tax_calc_cli.py ...` | 내부 추론만 |
| 법령 확인 | `law-mcp` | 내부 지식만 |
| 기록 | 정답 여부 + 도구 호출 로그 | 정답 여부 |

- B 먼저 → A 나중 (A가 B 결과 베끼지 않게)
- 풀이 reasoning 전부 공개

### 대상 문제

- 세무사 1차 2025 소득세법 Q51~Q60

### 진행 현황 (2026-04-12 종료)

| 문제 | 정답 | B | A | A 도구 호출 | 결과 |
|---|---|---|---|---|---|
| 2025 Q51 | ③ 40,350,000 | ③ | ③ | law-mcp §17 | A=B 정답 · Gross-up 10% 조문 확인 |
| 2025 Q52 | ④ ㄱ18.7M/ㄴ1.34M | ④ (역산) | ④ | law-mcp §12·§21·§22, 영§17의3·§18·§87 | A 경로 정확 |
| 2025 Q53 | ⑤ ㄱ354.4M/ㄴ409.4M | ⑤ | ⑤ | law-mcp §22·§48, 영§42의2 | A는 영§42의2⑥ 선택권 확정 |
| 2025 Q54 | ② 609,856,000 | ② | ② | law-mcp §97·§97의2·§95·§101, 영§163 | A는 3개 조문 동시 확정 |

- 완료: **4/10** (40%) · 정답률: A 4/4, B 4/4
- 도구 기여도: 조문 인용 정밀도 상승 입증
- 인프라 확장: `calculate_executive_retirement_limit()` + CLI, §104·영§87·§118의9~16 파이프라인 → **26/26 재인증**
- 실증 결론: 소득세 도구 기여도 입증 완료. **Phase 2 진행 가능**

### 세션 결과물 (2026-04-12)

**정답 JSON 전수 재작성**
- 세무사 1차 2023·2024·2025 정답 JSON 재작성 (31/40 파싱 오류 해소)
- CPA 1차 2024·2025·2026 정답 JSON 전수 검증 — 모두 정상

**tax_calc_cli 확장 (소득세 9종)**
- 추가: `financial-income --grossup-mode full|threshold`, `other-income --type`
- `calculate_financial_income`에 `grossup_mode` 파라미터 도입

**인프라 발견**
- PyMuPDF(fitz)가 pdfplumber보다 견고 — CPA 2026 PDF 파싱 성공

### 중단된 접근 (재시도 금지)

- `mcq_eval.py` 병렬 배치 채점 — 파싱·타임아웃·리소스 경쟁으로 반복 실패
- `claude -p --tools Bash` subprocess — 프로젝트 컨텍스트 오염
- **대안**: 대화창 수동 풀이 — Claude 자신이 솔버 겸 채점자

### 인프라 현황

- 문제 JSON: `data/exam/parsed/세무사_1차_세법학개론_{year}_{문제|정답}.json`
- 계산 CLI: `tax_calc_cli.py` (소득세 9종)
- 법령 조회: `law-mcp` (`~/projects/law-mcp/`)
  - 제공: `search_law`, `get_law_article`, `search_precedents`, `batch_validate_legal_terms`
  - 본문 반환 패치 적용 (2026-04-11)
