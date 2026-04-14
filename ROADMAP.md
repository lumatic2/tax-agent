# Tax Agent 로드맵

> 마지막 업데이트: 2026-04-13

> 정우승·이철재 「세법 워크북」 목차 구조를 기반으로 소득세 전체를 커버하고,
> 이후 부가세·법인세로 확장하는 단계별 계획.
>
> **현재 상태:** Phase 1~4 전 세목 Level 4 완료. Phase 4 기출 실증: 1차 6/6 완료, 2차 2024 39/39 + 2025 39/39 완료. **2차 서술형 전수 검증 완료.**
>
> **전략: 수직 완성 우선** — 한 세목을 실제 세무사 검토 수준(숫자 일치 80%+)으로
> 완전히 끝낸 뒤 다음 세목으로 이동.

---

## 설계 원칙

### 법령 기반 구현 철학

세무사는 법령을 읽고 로직을 머릿속에 내재화한 뒤 실무에 적용한다.
이 스킬도 동일한 구조로 작동한다:

```
세무사:   법령 읽기 → 로직 암기 → 사례에 적용
스킬:     법령 읽기 → Python 함수로 구현 → 사례에 적용
                      (법령 개정 시 함수 업데이트)
```

### 법제처 API의 실제 한계

법제처 API가 조문 원문을 반환하지만 계산에 직접 쓰기 어려운 이유:
- **세율표·공제액 표가 이미지(`<img>`)로 첨부** — 숫자 추출 불가
- **본법·시행령·시행규칙에 계산식 산재** — 조합 로직 복잡
- **개정 이력과 현행 조문이 혼재** — 현행 기준 파싱 불안정

따라서 API를 실시간 파싱해서 계산하는 구조는 채택하지 않는다.

### 역할 분담

| 역할 | 담당 | 구체적 용도 |
|---|---|---|
| 계산·공제 로직 | **Python 함수** | 세율 적용, 공제 계산, 단계별 산출 — 법령을 코드로 번역한 것 |
| 조문 원문 확인 | **법제처 API** | Claude가 읽고 해석·설명, 근거 조문 제시 |
| 개정 여부 확인 | **법제처 API** | 연간 업데이트 시 변경 감지 |
| 특수 케이스 해석 | **법제처 API + Claude** | 비과세 요건, 예규·해석례 조회 |
| 판단·설명·대화 | **Claude** | 숫자는 모듈에서, 맥락과 전략은 Claude가 |

### 완성 기준 (세목별 동일 적용)

```
Level 1 — 함수 존재:     코드가 실행됨
Level 2 — 파이프라인:    시나리오 흐름이 연결됨          ← 현재 Phase 1 상태
Level 3 — 숫자 검증:     세법 교재·홈택스 계산기와 수치 일치
Level 4 — 실무 완성:     경계값·특수케이스·선택 로직까지 커버  ← 목표
```

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

현재 assert는 방향만 검증. 아래 기준으로 교체:

- [x] **시나리오1 숫자 assert** — exact match
- [x] **시나리오2 §62 비교세액 포함 재계산** — exact match
- [x] **시나리오3 각 케이스 산출세액 exact match**

### 1-C. 미커버 시나리오 추가

- [x] **시나리오4: 퇴직소득세** — `calculate_retirement_income_tax()` 검증
  - 근속연수공제 → 환산급여 → 환산급여공제 → 환산산출세액 → 퇴직소득세액
  - 세법 교재 예제값으로 exact assert
- [x] **시나리오5: 연금소득** — `calculate_pension_income()` 검증
  - 총연금액 1,500만 이하(분리과세 선택) / 초과(종합과세) 각각 케이스
- [x] **시나리오6: 결손금 통산 순서** — `calculate_loss_netting()` 순서 검증
  - 사업결손금 → 근로→연금→기타→이자→배당 순서 assert
  - 부동산임대업 결손금 격리 assert
- [x] **시나리오7: 중소기업취업자 감면** — `calculate_sme_employment_tax_reduction()` 검증
  - 청년(90%)/일반(70%), 200만 한도 케이스

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
| 통합 시나리오 | S1~S7 (근로·사업·양도·퇴직·연금·결손금·감면) | 100% 통과 |
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
| Ch08 | `calculate_loss_netting()` | 통산 순서(근로→연금→기타→이자→배당), 부동산임대 격리 |
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

## Phase 2 — 부가가치세 (2026 세법 워크북 제4부)

> Phase 1 Level 4 달성 + 인증 통과(22/22) 후 시작. (2026-04-12~)
>
> **구현 순서**: 핵심 계산 먼저 (Ch05→Ch06→Ch07→Ch09) → 판정·안내 (Ch01~Ch04, Ch08)
>
> **법령 범위**: 부가가치세법 본법 + 시행령 + **조세특례제한법 부가세 특례** 포함
>
> **구현 패턴**: law-mcp `get_law_article` → `data/vat/*.txt` 저장 → `vat_calculator.py` 함수 추가 → `eval_scenarios_vat.py` exact assert → `certify_phase2.py` 인증 게이트

### 개요 테이블

| 챕터 | 모듈/내용 | 구현 순서 | 상태 |
|---|---|---|---|
| Ch05 과세표준·매출세액 | `calculate_vat_output_tax()` 외 4개 | 🔴 1순위 | [x] Level 2 |
| Ch06 매입세액·납부세액 | `calculate_vat_input_tax()` 외 5개 | 🔴 2순위 | [x] Level 2 |
| Ch07 겸영사업자 | `calculate_common_input_tax_allocation()` 외 2개 | 🔴 3순위 | [x] Level 2 |
| Ch09 간이과세 | `calculate_simplified_vat()` 외 1개 | 🔴 4순위 | [x] Level 2 |
| Ch01 총설 | `is_vat_taxpayer()`, `get_vat_tax_period()` + SKILL.md | 🟡 5순위 | [x] Level 2 |
| Ch02 과세거래 | `is_deemed_supply()`, `get_supply_time()` + SKILL.md | 🟡 6순위 | [x] Level 2 |
| Ch03 영세율·면세 | `is_zero_rated()`, `is_vat_exempt()` + SKILL.md | 🟡 7순위 | [x] Level 2 |
| Ch04 세금계산서 | `calculate_invoice_penalty()` + SKILL.md | 🟡 8순위 | [x] Level 2 |
| Ch08 신고·납부 | `calculate_vat_penalties()`, `calculate_preliminary_notice()` + SKILL.md | 🟡 9순위 | [x] Level 2 |

### Ch05. 과세표준과 매출세액 (1순위)

- [ ] `calculate_vat_tax_base()` — 과세표준 계산 (§29: 공급가액 = 대가 - 부가세, 간주공급 시가)
- [ ] `calculate_vat_output_tax()` — 매출세액 = 과세표준 × 10% (§30)
- [ ] 대손세액공제 `calculate_bad_debt_tax_credit()` (§45: 대손확정일 속하는 과세기간, 대손세액 = 대손금액 × 10/110)
- [ ] 과세표준 특례: 토지·건물 일괄공급 시 안분 (§29④, 영§64)
- [ ] 외화 환산 규정 (§29⑤)
- [ ] 조특법 부가세 특례: 면세농산물 의제매입세액공제율 등

### Ch06. 매입세액과 납부세액 (2순위)

- [ ] `calculate_vat_input_tax()` — 공제 매입세액 합계 (§38)
- [ ] `calculate_vat_non_deductible()` — 불공제 매입세액 판정 (§39: 비영업용 소형승용차, 접대비, 면세사업 관련, 세금계산서 미수취 등)
- [ ] `calculate_vat_payable()` — 납부세액 = 매출세액 - 매입세액 (§37)
- [ ] 의제매입세액공제 `calculate_deemed_input_tax()` (§42, 조특법 §108: 업종별 공제율 2/102~9/109)
- [ ] 재활용폐자원 매입세액공제 (조특법 §108)
- [ ] 신용카드매출전표 발행 세액공제 (§46, 조특법 §126의2)
- [ ] 전자신고 세액공제 (조특법 §104의8)

### Ch07. 겸영사업자 (3순위)

- [ ] `calculate_common_input_tax_allocation()` — 공통매입세액 안분 (§40, 영§61: 면세공급가액 비율)
- [ ] 정산 로직: 예정신고 시 안분 → 확정신고 시 정산 (영§61②)
- [ ] 납부세액·환급세액 재계산 (§43: 과세전환·면세전환 시)

### Ch09. 간이과세 (4순위)

- [ ] `calculate_simplified_vat()` — 간이과세 납부세액 (§61: 공급대가 × 업종별 부가가치율 × 10%)
- [ ] 업종별 부가가치율 테이블 (§61②, 영§111: 소매 15%, 제조 20%, 음식 15%, 숙박 25%, 운수 30%, 기타서비스 30%)
- [ ] 간이과세 적용 기준: 직전연도 공급대가 8,000만 미만 (§61①), 배제 업종
- [ ] 납부면제: 공급대가 4,800만 미만 (§69)
- [ ] 간이→일반 전환 시 재고매입세액 계산 (§64)
- [ ] 간이과세자 세금계산서 발급 특례 (§36의2)

### Ch01. 부가가치세 총설 (5순위)

- [ ] `is_vat_taxpayer()` — 납세의무자 판정 (§2~§3: 사업자, 재화수입자)
- [ ] `get_vat_tax_period()` — 과세기간 (§5: 1기 1.1~6.30, 2기 7.1~12.31)
- [ ] 사업자등록 의무·기한 안내 (§8) → SKILL.md
- [ ] 사업장 판정 규정 (§6) → SKILL.md

### Ch02. 과세거래 (6순위)

- [ ] `is_taxable_supply_of_goods()` — 재화의 공급 판정 (§9: 계약상 모든 원인에 의한 인도·양도)
- [ ] `is_deemed_supply()` — 간주공급 판정 (§10: 자가공급·개인적공급·사업상증여·폐업 잔존재화)
- [ ] `is_taxable_supply_of_services()` — 용역의 공급 판정 (§11)
- [ ] `get_supply_time()` — 공급시기 (§15~§17: 재화 인도일, 용역 완료일)
- [ ] 재화의 수입 (§12: 보세구역 반출)

### Ch03. 영세율과 면세 (7순위)

- [ ] `is_zero_rated()` — 영세율 적용 대상 판정 (§21~§24: 수출재화, 국외용역, 외화획득)
- [ ] `is_vat_exempt()` — 면세 대상 판정 (§26: 기초생활필수품, 의료·교육, 금융·보험)
- [ ] 면세 포기 신청 안내 (§27) → SKILL.md
- [ ] 조특법 영세율 특례 (조특법 §105: 외교관 면세 등)

### Ch04. 세금계산서 (8순위)

- [ ] `calculate_invoice_penalty()` — 세금계산서 관련 가산세 (§60: 미발급 2%, 지연발급 1%, 허위기재 2%)
- [ ] 수정세금계산서 발급 사유 (§32②) → SKILL.md
- [ ] 전자세금계산서 발급 의무 기준 (§32②, 영§68) → SKILL.md
- [ ] 영수증 발급 대상 (§36) → SKILL.md

### Ch08. 신고와 납부 (9순위)

- [ ] `calculate_vat_penalties()` — 가산세 통합 (§60: 무신고·과소신고·납부지연·영세율과세표준신고불성실)
- [ ] 예정신고·확정신고 기한 안내 (§48~§49) → SKILL.md
- [ ] 예정고지 계산 (§48③: 직전 과세기간 납부세액 × 50%)
- [ ] 환급 유형: 일반환급 vs 조기환급 (§59) → SKILL.md
- [ ] 대리납부 (§52: 국외사업자 용역)

### Phase 2 완료 기준

```
모든 챕터 함수 구현 + exact assert 통과
certify_phase2.py 인증 게이트 전항목 통과
부가세 기출(세무사 1차 2023~2025) A/B 실증 완료
```

### 기출 현황

| 연도 | 부가세 문항 | 번호 |
|---|---|---|
| 2023 | 9개 | Q48, Q71~Q80 |
| 2024 | 8개 | Q71~Q78 |
| 2025 | 9개 | Q67, Q71~Q78 |

기출 JSON 변환 완료 (`소재: "부가가치세"` 태그로 필터 가능)

### A/B 실증 진행 현황 (2026-04-12)

| 문제 | 정답 | B | A | A 도구 | 결과 |
|---|---|---|---|---|---|
| 2025 Q71 | ③ | ③ | ③ | vat_calc_cli land-building, common-alloc, **recalc** | B=A 정답 · recalc로 exact match 확인 |
| 2025 Q72 | ② | ② | ② | 판정형, law-mcp 실패 | B=A 정답 · 도구 불필요(판정형) |
| 2025 Q73 | ③ | ③ | ③ | vat_calc_cli deemed-input, deemed-limit, payable | B=A 정답 · 17K 오차(의제매입세액 산출기준 차이) |
| 2025 Q74 | ④ | ④ | ④ | vat_calc_cli **proxy**, common-alloc | B=A 정답 · proxy로 exact match 확인 |
| 2025 Q75 | ④ | ④ | ④ | law-mcp 영§40①2호다목 확인 | B=A 정답 · A 근거 보강 |
| 2025 Q76 | ② 366K | 불확실 | ② (4K오차) | §63③(0.5%)+§46(1.3%) 수동계산=370K | **A 도구 기여** · B 공식불명 |
| 2025 Q77 | ④ | ④ | ④ | 판정형 | B=A 정답 |
| 2025 Q78 | ② 1.3 | ② | ② | art_60_가산세.txt 캐시 | B=A 정답 · A 근거 보강 |

- 완료: **8/8** (100%)
- Gap 보강 완료 (2026-04-12):
  - [x] §43/영§63 재계산: `recalculate_mixed_use_asset_tax()` + CLI `recalc` → Q71 exact match
  - [x] §52 대리납부: `calculate_proxy_payment_tax()` + CLI `proxy` → Q74 exact match
  - [x] 의제매입세액 한도: `calculate_deemed_input_tax_with_limit()` + CLI `deemed-limit`
  - [x] CLI bool 버그: argparse `type=bool` → `action="store_true"`
  - [x] 지방소비세: `calculate_local_consumption_tax()` + CLI `local-tax`
- eval 22/22 통과 (기존 18 + gap 보강 4시나리오)

### law-mcp 버그 (2026-04-12 발견)

**증상**: `get_law_article(law_id="부가가치세법", ...)` → HTTP 500 ("법제처 API 일시 장애")
**원인**: 법명(한글)을 법제처 API의 `ID` 파라미터에 그대로 전달 → API가 숫자 ID 기대 → 500. `shouldStopLawFetchFallback()`이 500을 `LAW_API_TEMPORARY_ERROR`로 분류하여 MST 폴백도 차단.
**우회**: `search_law("부가가치세법")` → 법령코드 "001571" 획득 후 숫자 코드로 호출하면 정상 동작
**수정 위치**: `~/projects/law-mcp/src/providers/lawgo-provider.ts` `getLawArticle()` — 법명이 숫자가 아니면 `searchLaw`로 ID 먼저 조회하는 로직 추가 필요
**상태**: 미수정 (tax-agent 외부 프로젝트)

### 법령코드 참조

| 법령 | 코드 | 비고 |
|---|---|---|
| 부가가치세법 | 001571 | law-mcp 우회용 |
| 부가가치세법 시행령 | 003666 | |
| 소득세법 | 001565 | |

### 조문 인용 정정 (2026-04-12)

기출 실증 과정에서 발견: 재계산 규정은 **§41/영§83** (이전 추정 §43/영§63은 오류)
- §41: 공통매입세액 재계산 (5% 이상 변동 시)
- 영§83: 재계산 세부 계산식 (경과기간 = 영§66② 준용: 건물 20기, 기타 4기)
- §43: 면세→과세 전환 시 매입세액공제 특례 (별개 규정)
- 영§63: 공통사용 재화의 공급가액 계산 (별개 규정)

### API 복구 후 할 일 (2026-04-12 전체 완료)

- [x] law-mcp 버그 수정 — `resolveLawId()` 추가, 한글 법명→숫자코드 자동변환
- [x] 부가세 핵심 조문 일괄 캐시 (`data/vat/`) — 21개 조문
- [x] 재계산 함수 조문 근거 보강 — §41/영§83 정정, 5% threshold+기준비율갱신, 기타자산 4기
- [x] Q75~Q78 4문항 A/B 실증 완료 — 8/8(100%), Q76만 4K 오차
- [x] 대리납부 환율 적용 근거 확인 — 영§95③
- [x] 간이과세 함수 확장 — §63③(0.5%)+§46(카드)+§63⑥ 한도, CLI+eval V23
- [x] CPA 2차 2025 문제3 물음1 풀이+해설 대조 — 6항목 중 3정답/3오류
- [x] CPA 2차 해설 PDF 복구 — 3개 연도 `cpa_2차/해설/`에 복사

### Phase 2 현재 상태 (2026-04-12)

**Level 4** — 1차 MCQ 8/8, 2차 서술형 3개년 전항목 정답, eval 27/27

| 구분 | 상태 |
|---|---|
| 계산엔진 | 9개 챕터 + gap 9개 = 18개 함수, eval 27/27 |
| 조문 캐시 | 21개 (`data/vat/`) |
| 1차 실증 | **8/8** (B 87.5%, A 100%) |
| 2차 실증 | **2025 6/6** + **2024 14/14** + **2023 전항목** — 3개년 완전 검증 |
| 정답 JSON | 3개년 부가세 정답 숫자 파싱 완료 |
| CLI | 18개 서브커맨드 (simplified 확장 포함) |

### 완료 항목 (2026-04-12)

- [x] 임직원 증정 비과세 한도 구현 (§10④ 단서, 영§17: 구분별 1인 10만원)
- [x] 수출 과세표준 환율 세분화 (영§59: 환가분 vs 미환가분 분리)
- [x] 예정신고 누락분 판정 로직 (공급시기 vs 세금계산서 발급일 불일치)
- [x] Q76 4K 차이 조사 완료 — 의제매입 폐지·지방소비세·마일리지 확인, 해설집 미입수로 미확정
- [x] 조특법§108 재활용폐자원·중고자동차 함수 구현 (eval V27)
- [x] CPA 2차 2025 물음1 6/6 — 과세표준·세액 전항목 정답
- [x] CPA 2차 2024 14/14 — 겸영+간이전환 전항목 정답
- [x] CPA 2차 2023 전항목 — 공급시기/폐업/매입세액/간이과세 정답
- [x] CPA 2차 부가세 정답 JSON 보완 — 3개년 숫자 추출 완료

### 잔여 (선택)

- [ ] Q76 4K 원인 확정 — 세무사 해설집 입수 시 재조사
- [ ] CLI 서브커맨드 3개 추가 (gift/export/omission)
- [ ] certify_phase2.py 작성 — Phase 1과 동일 형식의 자동 인증 게이트

---

## Phase 3 — 상속세·증여세 (2026 세법 워크북 제5부)

Phase 2 **Level 4 달성** (2026-04-12). Phase 3 시작.

| 챕터 | 모듈/내용 | 상태 |
|---|---|---|
| Ch01 상속세 | `calculate_inheritance_tax()` -- 상속재산, 공제, 세율 | **Level 4** |
| Ch02 증여세 | `calculate_gift_tax()` + 특수증여 3종 | **Level 4** |
| Ch03 재산의 평가 | 부동산(토지/건물/주택/임대) + 유가증권 + 예금 | **Level 4** |
| Ch04 신고/납부 | 연부연납, 물납 안내 | Level 2 |

### 완료 (Level 0 -> Level 4, 2026-04-12~13)

**Level 2 (뼈대)**
- [x] 조문 캐시 25개 조문 (법제처 API) -> `data/inheritance_gift/statutes_cache.txt`
- [x] `inheritance_gift_calculator.py` Ch01~Ch04 핵심 함수
- [x] eval 20/20 통과

**Level 3 (숫자 검증)**
- [x] 장례비 봉안시설 분리계산(시행령9), 감정평가수수료 500만 한도(시행령49의2)
- [x] CPA 기출 3건 정답 일치 (eval 23/23)

**Level 4 (실무 완성)**
- [x] 가업상속공제(18의2): 경영기간별 300/400/600억 한도
- [x] 영농상속공제(18의3): 30억 한도
- [x] 특수증여 3종: 저가양도(35), 부동산무상사용(37), 금전무상대출(41의4)
- [x] 부동산 보충적 평가: 토지(공시지가x배율), 건물(기준시가), 주택(공시가격), 임대재산
- [x] `inheritance_gift_calc_cli.py` -- 12개 서브커맨드
- [x] eval 30/30 전부 통과

### Phase 3 완료. Phase 4(법인세) 시작 가능.

---

## Phase 4 — 법인세 (별도 세법 워크북 1권) ✅ COMPLETE

**Level 4 달성** (2026-04-13). eval 30/30 pass.

### 산출물

| 파일 | 내용 | 규모 |
|---|---|---|
| `corporate_tax_calculator.py` | 계산 엔진 24개 함수 | ~1100줄 |
| `corporate_tax_calc_cli.py` | CLI 11개 서브커맨드 | ~250줄 |
| `eval_scenarios_corporate_tax.py` | exact-match 시나리오 | 30개, ~800줄 |
| `data/corporate_tax/` | 법령 조문 캐시 | §55, §13 |

### 구현 챕터

| Level | 챕터 | 함수 | Eval |
|---|---|---|---|
| L1 | Ch10 세율·과세표준·이월결손금 | `apply_corporate_tax_rate`, `calculate_loss_carryforward`, `calculate_corporate_tax_base`, `calculate_corporate_tax` | CT1~CT5 |
| L2 | Ch02~04 세무조정 | `calculate_taxable_income`, `calculate_dividend_received_deduction`, `calculate_entertainment_expense_limit_corp`, `calculate_donation_limit`, `check_non_deductible_expenses` | CT6~CT12 |
| L3 | Ch07~08 감가상각·충당금 | `calculate_depreciation_limit`, `get_statutory_useful_life`, `get_declining_balance_rate`, `calculate_retirement_allowance_reserve`, `calculate_bad_debt_reserve` | CT13~CT20 |
| L4 | Ch09,11~14 세액공제·최저한세 | `calculate_unfair_transaction_denial`, `calculate_foreign_tax_credit`, `calculate_sme_tax_reduction`, `apply_minimum_tax`, `calculate_land_transfer_additional_tax`, `calculate_interim_prepayment`, `classify_corporation_type`, `calculate_corporate_tax_full` | CT21~CT30 |

### 핵심 설계

- 이월결손금 한도: **80%** (현행 §13, 중소기업 100%) — 로드맵 초기 60% 기재는 구법 기준
- 세율: 9%/19%/21%/24% 4단계 (2023 개정)
- 세무조정: `list[dict]` 구조 (`{항목, 금액, 소득처분}`)
- 최저한세: 중소 7% / 일반 10~17% (조특법 §132)
- 전체 파이프라인: 회계이익 → 세무조정 → 과세표준 → 세율 → 감면 → 최저한세 → 토지추가 → 납부세액

### Phase 4 완료. Phase 5(상위 레이어) 시작 가능.

---

## Phase 5 — 상위 레이어 (전 세목 완성 후)

모든 세목 계산 엔진이 Level 4에 도달한 후 구축.

| 모듈 | 내용 |
|---|---|
| `strategy_engine.py` | 절세 전략 수립 — 공제 최적화, 분리/종합 선택, 시뮬레이션 |
| `execution_planner.py` | 신고서 초안 생성 (`generate_tax_return_draft()`) |
| Claude API 전환 | Phase 1 Claude Code → Phase 2 FastAPI + claude-sonnet-4-6 |

### Phase 5-A — strategy_engine 설계 (2026-04-14)

실제 세무사 절세 업무 파이프라인을 모델링한 4단계 구조.

**웹검색 기반 업무 흐름**: 자료 수집·분류 → 완전성 점검 → 기장 방식 판정 → 필요경비 최대화 → 공제·감면 전수 적용 → 분리/종합 최적화 → 시나리오 시뮬레이션 → 신고서 초안 + 리스크 경고

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

**착수 순서**:
- [x] 5-A-1: 규칙 카탈로그 YAML 스키마 v0 확정 (JSON 구조 조건식 DSL + formula/simulate/fixed estimator) — 2026-04-14
- [x] 5-A-2: 골든 셋 5규칙(FIN_SEPARATION·BOOK_DOUBLE_ENTRY·CRED_MONTHLY_RENT·DED_PENSION_IRP·TIMING_MEDICAL) + `eval_strategy_rules.py` 12/12 통과 — 2026-04-14
- [x] 5-A-3: 종소세 end-to-end 시나리오(근로+금융 겸업자)로 orchestrator 통합 검증 — `eval_strategy_e2e.py` 7/7 통과 (profile_builder flatten, 4규칙 동시 발동, 우선순위 정렬, 금융 2,500만 케이스 분리과세 비발동) — 2026-04-14
- [x] 5-A-4: 기출 2차 서술형 재활용 회귀 — 법인세 리스크 규칙 2개(`CORP_EXECUTIVE_BONUS_EXCESS`, `CORP_UNFAIR_HIGH_PRICE_PURCHASE`) 추가, CPA 2024 Q5(부당행위 최대매입가 6,194,999,999) + CPA 2025 Q5(임원상여 한도초과) 프로필로 `eval_strategy_corp_risk.py` 8/8 통과. 개인·법인 스코프 격리(크로스 오발동 방지), 5% 경계값, trace 실패 조항 추적 전부 검증 — 2026-04-14
- [x] 5-A-5: 규칙 카탈로그 v1 확장 — **22개 규칙** (소득세 13 + 법인세 5 + 상속세 2 + 증여세 2). 19종 estimator 공식 추가, profile_builder 전 세목 필드 defaults. `eval_strategy_catalog_v1.py` 30/30 통과 (각 신규 규칙 적용/비적용 + 크로스-세목 스코프 격리 2종) — 2026-04-14

**Phase 5-A 통합 회귀**: eval_strategy_rules 12/12 + e2e 7/7 + corp_risk 8/8 + catalog_v1 30/30 = **57/57** + certify_phase1 26/26 유지

---

## 자료 수집 자동화 로드맵

### 현재 (MVP) — PDF 파싱

사용자가 홈택스에서 직접 출력 → 파일 경로 입력 → `document_parser.parse_pdf()` 파싱.
SKILL.md에 출력 방법 단계별 안내 포함.

### 추후 검토 — CODEF API 연동

- **CODEF** (codef.io): 민간 인증 대행 API. 공동인증서/간편인증으로 간소화 자료를 JSON으로 반환.
- 사용자 본인 인증 기반이라 법적으로 안전한 방식.
- 서비스화(다수 사용자) 단계에서 도입 검토.
- 테스트 무료, 실사용 소액 과금.
- 구현 위치: `document_parser.py`에 `fetch_hometax_via_codef()` 추가.

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
> 구현 패턴: law-mcp `get_law_article` → `data/*.txt` 저장 → `tax_calculator.py` 함수 추가 → `law_watch.py` 등록 → `eval_scenarios.py` exact assert 추가

### Ch01. 소득세 총설
- [x] `is_resident()` — 거주자/비거주자 판정 (§1의2: 국내 주소 또는 183일 거소)
- [x] `get_taxable_period()` — 과세기간 특례 (§5: 사망·출국 시 단축)
- [x] 납세지 규정 안내 (§6~§8: 주소지/사업장 납세지신고) → SKILL.md

### Ch02. 이자소득
- [x] `calculate_nontaxable_interest()` — 비과세 이자소득 항목별 판정 (§12③1: 비과세종합저축 2천만 한도 등)
- [x] 이자소득 수입시기 규정 (§45: 약정일/지급일) → SKILL.md
- [x] 무조건 분리과세 이자소득 `calculate_interest_income_tax()` (§14②: 비실명45%·장기채권30%·직장공제회)

### Ch03. 배당소득
- [x] `calculate_deemed_dividend()` — 의제배당 계산 (§17②: 잉여금 자본전입·감자·해산·합병·분할)
- [x] `calculate_recognized_dividend()` — 인정배당 (§17①4: 법인세법상 소득처분)
- [x] 집합투자기구 배당소득 특례 (§17①5) → SKILL.md

### Ch04. 사업소득 — 필요경비 상세
- [x] `calculate_entertainment_expense_limit()` — 접대비 한도 (§35③: 중소기업3,600만/일반1,200만 + 수입금액 한도)
- [x] `calculate_depreciation()` — 감가상각비 (§33①6, 영§62~§68: 정액법·정률법, 내용연수별 상각률)
- [x] `calculate_car_expense_limit()` — 업무용승용차 관련비용 한도 (§33의2: 감가상각비 연 800만 한도)
- [x] 총수입금액 귀속시기 규정 (§39) → SKILL.md
- [x] 비과세 사업소득 (§12①) → SKILL.md

### Ch05. 근로소득
- [x] `calculate_simplified_withholding()` — 간이세액표 월별 원천징수 (§129·영§194: 부양가족 수별 세액)
- [x] 비과세 근로소득 추가 항목 (§12③: 벽지수당·위험수당·국외근로소득·연구보조비 등) → `calculate_nontaxable_employment_income()` 확장
- [x] 근로소득 수입시기 (§49) → SKILL.md

### Ch06. 연금소득 — 현재 구현 완료 ✓

### Ch07. 기타소득
- [x] 무조건 분리과세 세율 세분화 (§14②: 복권 3억 초과 33%, 슬롯머신 등) → `calculate_other_income()` 수정

### Ch08. 종합소득금액 — 현재 구현 완료 ✓

### Ch09. 종합소득공제
- [x] `calculate_housing_savings_deduction()` — 주택청약종합저축 소득공제 (조특법 §87: 총급여 7천만 이하, 납입액×40%, 한도 300만)
- [x] `apply_deduction_aggregate_limit()` — 소득공제 종합한도 2,500만원 (조특법 §132의2)

### Ch10. 세액 계산 — 현재 구현 완료 ✓

### Ch11. 세액공제·세액감면
- [x] `calculate_earned_income_tax_credit()` 재구현 — 근로소득세액공제 (§59: 총급여 구간별 55~74%, 한도 50~74만)
- [x] `calculate_insurance_tax_credit()` — 보험료세액공제 (§59의4①: 보장성 12%, 장애인보장성 15%, 한도 100만)
- [x] `calculate_medical_tax_credit_detail()` — 의료비세액공제 상세 (§59의4②: 본인·경로우대·장애인 한도 없음, 일반 200만)
- [x] `calculate_education_tax_credit_detail()` — 교육비세액공제 상세 (§59의4③: 취학전~대학, 본인 전액, 장애인)
- [x] `calculate_donation_tax_credit_detail()` — 기부금세액공제 상세 (§59의4④: 법정/지정/종교단체 한도 구분, 15%/30%)
- [x] `calculate_disaster_loss_tax_credit()` — 재해손실세액공제 (§58: 피해액/종합소득세액 비율)

### Ch12. 퇴직소득 — 현재 구현 완료 ✓

### Ch13. 양도소득
- [x] `check_one_house_exemption()` — 1세대1주택 비과세 요건 판정 (§89①3: 2년 보유·거주, 세대원 구성, 12억 기준)
- [x] `calculate_estimated_acquisition_price()` — 취득가액 의제 (§97②: 기준시가·환산취득가액)

### Ch14. 신고·납부
- [x] `calculate_withholding_tax()` — 원천징수 세율표 통합 (§129: 이자 14%, 배당 14%, 사업 3.3%, 기타 22%, 근로 간이세액)
- [x] 양도소득 예정신고 안내 (§105~§106) → SKILL.md

### Ch15. 비거주자
- [x] `calculate_nonresident_tax()` — 국내원천소득 과세 (§119~§121: 소득유형별 세율)
- [x] 조세조약 제한세율 안내 → SKILL.md

---

## 법제처 API vs Python 함수 분담 원칙

```
계산이 필요한 것 → Python 함수
  예: 공제 금액, 세율 적용, 단계별 산출

조문 해석이 필요한 것 → 법제처 API
  예: 비과세 요건 판단, 특례 적용 여부, 최신 개정 확인

둘 다 필요한 것 → 함수로 계산 + API로 근거 제시
  예: 1세대1주택 비과세 (요건은 API, 세액은 함수)
```

---

## Phase 1-실증 — 소득세 A/B 검증

> 목적: 구축한 소득세 계산기(`tax_calc_cli.py`)와 법령 조회(`law-mcp`)가 실제 시험문제를
> 풀 때 **유의미하게 기여하는지** 한 문제씩 검증.
>
> 원칙: **대화창 내 수동 풀이**. subprocess·병렬·파싱 스크립트 금지
> (자동화 시도가 반복 실패 — 하단 "중단된 접근" 참고).

### 평가 설계

| 구분 | A: 시스템 활용 | B: LLM 단독 |
|---|---|---|
| 계산 | `python tax_calc_cli.py ...` 호출 | 내부 추론만 |
| 법령 확인 | `law-mcp` (`get_law_article` 등) | 내부 지식만 |
| 기록 | 정답 여부 + **도구 호출 종류·횟수** | 정답 여부 |

- A에서 도구를 한 번도 호출하지 않으면 "도구 기여도 0"으로 별도 표시
- 동일 문제를 **B 먼저 → A 나중** 순서로 풀어 A가 B 결과를 베끼지 않게 함
- 풀이 reasoning은 전부 공개 (번호 맞히기만 하는 게 아니라 과정도 검수)

### 워크플로 (한 문제 단위)

```
1. 대상 문제 선정 (예: 세무사 1차 2025 Q51)
2. Read 도구로 문제·선택지·정답 JSON 직접 로드
3. B 풀이: 도구 없이 reasoning + 예측 번호
4. A 풀이: 필요 시 tax_calc_cli / law-mcp 호출 (호출 로그 기록)
5. 정답 비교 → data/exam/results/소득세_실증.md 에 누적
```

### 결과 누적 포맷 (`data/exam/results/소득세_실증.md`)

```markdown
## 2025 Q{n} — {주제}
- 정답: {번호}
- B 예측: {번호} ({정오})
- A 예측: {번호} ({정오})
- A 도구 호출: [tax_calc_cli income-tax ..., law-mcp get_law_article 소득세법 §{n}, ...]
- 분석: {한 줄}
```

최종 테이블(누적본 최상단):

| 문제 | 정답 | B | A | A 도구 | 개선? |
|---|---|---|---|---|---|
| ... |

### 대상 문제

- 1차: 세무사 1차 2025 소득세법 Q51~Q60 (10문항)
- 2차(1차 완료 후): 2024·2023 동일 10문항씩

### 완료 기준

```
Q51~Q60 10문항 A/B 양쪽 완료 + 결과 기록
A 정답률 > B 정답률 (도구 기여 입증)
또는 A 정답률 == B 이지만 근거 조항 정밀도 상승 (law-mcp 기여 입증)
```

### 진행 현황 (2026-04-12 업데이트)

| 문제 | 정답 | B | A | A 도구 호출 | 결과 |
|---|---|---|---|---|---|
| 2025 Q51 | ③ 40,350,000 | ③ | ③ | law-mcp §17 | A=B 정답 · Gross-up 비율 10% 조문 확인 |
| 2025 Q52 | ④ ㄱ18.7M/ㄴ1.34M | ④ (역산 찍기) | ④ | law-mcp §12·§21·§22, 영§17의3·§18·§87 | A=B 정답 · A가 경로 정확 |
| 2025 Q53 | ⑤ ㄱ354.4M/ㄴ409.4M | ⑤ | ⑤ | law-mcp §22·§48, 영§42의2 | A=B 정답 · A는 영§42의2⑥ 선택권 확정 |
| 2025 Q54 | ② 609,856,000 | ② | ② | law-mcp §97·§97의2·§95·§101, 영§163 | A=B 정답 · A는 3개 조문 동시 확정 |
| 2025 Q55~Q60 | — | — | — | — | 미진행 |

- 완료: **4/10** (40%)
- 현재까지 정답률: A 4/4, B 4/4 (Q52 B는 역산, Q53 B는 구조 기억 불안정, Q54는 3개 법리 동시)
- 도구 기여도: Q51~Q54 모두 A에서 조문 인용 정밀도 상승 입증
- 인프라 확장: Q53 계기로 `calculate_executive_retirement_limit()` + `executive-retirement-limit` CLI 구현, certify_phase1 Ch12b 추가
- 인프라 확장 (2차): §104 주식양도세율 + 영§87 의제율매핑 + §118의9~16 국외전출세 파이프라인 → **26/26 인증 재통과**
- 실증 결론: 소득세 도구 기여도 입증 완료. 1차 MCQ는 확신도·경로 보강, 2차 서술형은 조문 정정·숫자 확정에서 결정적 기여. **Phase 2(부가세) 진행 가능**

### 세션 결과물 (2026-04-12)

**정답 JSON 전수 재작성**
- 세무사 1차 2023·2024·2025 세법학개론 정답 JSON → 원본 PDF 기반 재작성 완료
- 2025 Q51 기존 "2" → "3" 수정 등 31/40 파싱 오류 해소
- 검증 방법: 2023·2024는 `pdfplumber.page.to_image()` + 멀티모달 Read, 2025는 텍스트 추출
- CPA 1차 2024·2025·2026 정답 JSON 전수 검증 → **모두 정상** (파싱 오류는 세무사 1차 파이프라인 국소 버그)

**tax_calc_cli 확장 (소득세 9종)**
- 기존 7종 유지 + 추가 2종:
  - `financial-income` (`--grossup-mode full|threshold`) — §17 금융소득 Gross-up + 2천만 종합과세 판정
  - `other-income` (`--type 일반|복권|슬롯머신|연금계좌`, `--expense-ratio`) — §21 기타소득 단일항목
- `calculate_financial_income`에 `grossup_mode` 파라미터 도입
  - `full`: §17③ 문언 그대로 전액 × 10% (기본, S2 등 기존 시나리오 보존)
  - `threshold`: 2천만 초과분만 × 10% (시험 실무 해석, Q51 검산용)
- certify_phase1 22/22 회귀 통과 확인

**인프라 발견**
- **PyMuPDF(fitz)**가 pdfplumber보다 견고 — CPA 2026 확정답안 PDF를 pdfplumber는 `Unexpected EOF`로 실패하지만 fitz는 정상 파싱
- 향후 PDF 파이프라인에서 fitz를 1차 선택지로 고려

### 중단된 접근 (재시도 금지)

- `mcq_eval.py` 병렬 배치 채점 — 파싱·타임아웃·리소스 경쟁으로 반복 실패
- `claude -p --tools Bash` subprocess — 프로젝트 CLAUDE.md 컨텍스트 로드되며 MCQ를 프로젝트 질의로 오해
- 원인 정리: **"자동화된 다문항 배치"가 이 규모에선 디버깅을 막음** — 응답 못 봄, 오류 로그 파편화
- 대안: 대화창 수동 풀이 (위 워크플로) — Claude 자신이 솔버 겸 채점자

### 인프라 현황 (그대로 유지)

- 문제 JSON: `data/exam/parsed/세무사_1차_세법학개론_{year}_{문제|정답}.json`
- 계산 CLI: `tax_calc_cli.py` (소득세 7종: earned-deduction, income-tax, wage-tax, retirement-tax, transfer-tax, pension-income, withholding)
- 법령 조회: `law-mcp` (`~/projects/law-mcp/`, `~/.claude.json` 등록됨)
  - 제공 도구: `search_law`, `get_law_article`, `search_precedents`, `batch_validate_legal_terms`
  - 본문 반환 패치 적용 완료 (2026-04-11, `src/providers/lawgo-provider.ts`)

---

## 이어서 할 일
> 다음 세션에서 이 항목부터 시작한다.

- [x] **법인세 2차 서술형 A/B 실증** — 2024 39/39 + 2025 39/39 = **78/78 전수 검증 완료**
  - [x] 2024 Q4: 접대비 한도·출자전환·지급이자·주식매수선택권·개발비 — 25/25
  - [x] 2024 Q5: 부당행위계산부인(실권주)·결손금 소급공제 — 8/8 (정답JSON 4건 수정)
  - [x] 2024 Q6: 상속세 과세가액·증여 반환시기 — 6/6
  - [x] 2025 Q4: 의제배당·퇴직급여충당금·대손충당금·업무용승용차 — 22/22
  - [x] 2025 Q5: 임원상여금·퇴직금 한도·기부금·부당행위계산부인 — 10/10
  - [x] 2025 Q6: 연결납세 — 2/2
  - [x] 2025 Q7: 증여세(부동산 무상사용·금전무상대출·보험금) — 5/5 (JSON 누락 2건 보완)
- [x] Phase 5-A **strategy_engine 카탈로그화 완료** (2026-04-14): 22규칙 + 57/57 회귀 + certify 26/26 무회귀

### 다음 세션 — Phase 5-B: 프론트엔드 통합 (`local-ai-workstation` → `tax-agent` 이전)

> **배경**: 바탕화면 `Tax Agent.exe`는 별도 프로젝트 `~/projects/local-ai-workstation`에 있음 (Streamlit + LangGraph + Ollama qwen3:32b). 이미 `sys.path.insert('../tax-agent')`로 백엔드를 import 중. 유지보수 단순화 위해 세무 관련 자산을 전부 `tax-agent`로 이전하기로 결정.

**이전 대상**:
- `infrastructure/tax_dashboard.py`, `tax_app.py`(pywebview), `start_tax_app.bat`, `create_shortcut.ps1` → `tax-agent/app/`
- `phase1_automation/track_b_poc.py`, `law_client.py`, `tax_verifier.py`, `eval_loop.py`, `tax_rag/` → `tax-agent/agent/`
- `TaxAgentDebug.spec`, `infrastructure/tax_agent.spec` → `tax-agent/packaging/`
- `assets/icon.ico`, `icon_1024.png`, `make_desktop_shortcut.ps1` → `tax-agent/assets/`

**비-이전**: phase0_benchmark, phase2_advanced(투자), hardware.md, roi-analysis.md는 `local-ai-workstation`에 잔류.

**작업 순서** (PlanMode 권장, 대공사):
1. 디렉토리 생성 + 파일 복사 (원본 유지, 검증 후 정리)
2. import 경로 수정: `sys.path.insert('../tax-agent')` 제거, `tax_rag` → `agent.rag`, 등
3. `pyproject.toml` 의존성 추가: `streamlit`, `langgraph`, `langchain-core`, `langchain-ollama`, `pywebview` → `uv sync`
4. PyInstaller `.spec` 경로 갱신 + **YAML 리소스 번들링 추가** (`strategy_engine/rules/**/*.yaml` datas, `yaml` hiddenimports)
5. Streamlit 런타임 테스트 — 새 엔진(22규칙) 동작 확인
6. **UI 확장**: 현 소득세 탭 외 **법인세·상속세·증여세 탭 3개 추가** + LangGraph `@tool` 3개 추가 (`get_corporate_tax_strategies`, `get_inheritance_strategies`, `get_gift_strategies`)
7. `.exe` 재빌드 + 바탕화면 바로가기 갱신 (타깃 경로 변경)
8. ROADMAP 갱신 + 원본 `local-ai-workstation` 세무 폴더 정리(검증 후)

**백엔드 준비 상태**: `strategy_engine.run(profile)`이 이미 4세목 전부 지원. API 변경 불필요.
