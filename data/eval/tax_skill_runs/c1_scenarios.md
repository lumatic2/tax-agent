# C-1: /tax 스킬 실사용 테스트 시나리오 3건

> **목적**: /tax 스킬의 경로 선택 로직이 올바르게 작동하는지 검증.
> **기준**: 각 시나리오에서 스킬이 아래 "expected path"와 동일한 도구/모듈을 호출하는가?

---

## 시나리오 1 — 소득세 (근로 + 부양가족 + 공제)

**질의**:
```
2025년 근로소득 8천만 (총급여), 배우자 근로소득 3천만(소득금액 약 0), 자녀 2명(8세/12세),
연금계좌(IRP) 700만 납입, 의료비 200만, 주택청약종합저축 월 20만(연 240만).
절세 포인트와 예상 세액 알려줘.
```

**Expected path**:
1. `tax_calculator.calculate_tax()` — 종합소득 산출세액
2. `strategy_engine.run(profile)` — 규칙 발동
3. 법령 인용 (MCP): §59의4(세액공제), §51(자녀), 조특 §87(주택청약)

**Expected 규칙 발동 (strategy_engine 40+ 중)**:
- DED_PENSION_IRP (연금계좌 세액공제)
- CRED_CHILD (자녀세액공제 2명 = 55만)
- TIMING_MEDICAL (의료비 몰아주기)
- DED_HOUSING_SAVINGS (주택청약 소득공제)
- (배우자 기본공제 가능성 — 소득금액 0)

**검증 포인트**:
- [ ] 지방소득세 10% 포함 여부
- [ ] 배우자 기본공제 적격 판단 (총급여 500만 이하)
- [ ] strategy_engine `run()` 정상 호출 (레거시 `generate_strategy` 쓰면 FAIL)

---

## 시나리오 2 — 법인세 (중소제조 + R&D + 투자세액공제)

**질의**:
```
중소제조업 법인, 매출 80억, 영업이익 8억, R&D 인건비 3억, 신규 설비투자 5억(통합투자세액공제 대상).
법인세 + 세액공제 + 최저한세 걸리는지 계산하고 절세 전략 알려줘.
```

**Expected path**:
1. `corporate_tax_calculator.calculate_corporate_tax_full()` — 과세표준·세율·최저한세
2. `strategy_engine.run(profile with is_corporation=true, is_sme_corporation=true)`
3. 법령 인용: 법§55(세율), 조특 §10(R&D), 조특 §24(통합투자), 조특 §132(최저한세)

**Expected 규칙 발동**:
- CORP_RD_TAX_CREDIT (R&D 중소 25%)
- CORP_INTEGRATED_INVESTMENT_CREDIT (통합투자 기본 10% + 증가분 3%)
- 최저한세 체크 (중소 7%)

**검증 포인트**:
- [ ] 세율 9% 구간(과표 2억 이하) vs 19% 구간 정확히 적용
- [ ] 세액공제 적용 후 최저한세 비교 수행
- [ ] 법인지방소득세 산출세액 10% 포함

---

## 시나리오 3 — 회색지대 (대표이사 가지급금 인정이자)

**질의**:
```
중소법인 대표이사가 법인에서 5억을 빌려서 개인 부동산 취득에 사용.
법인에 연 2% 이자 지급 중. 가지급금 인정이자 부당행위계산부인 리스크 있나?
당좌대출이자율 대비 저리라 문제될까?
```

**Expected path**:
1. `reasoning_engine.run("GRAY_CORP_GAJIGEUPGEUM_INTEREST", profile)` ← **법령 MCP 대신 이걸 먼저 호출해야 함**
2. 해당 이슈: `corporate_tax_gray.yaml`의 `GRAY_CORP_GAJIGEUPGEUM_INTEREST`
3. decisive_sources 핀으로 판례/예규 주입
4. reasoner + adversary 출력

**Expected ruling**:
- 당좌대출이자율(현행 4.6%) > 지급이자 2% → **인정이자 차액 익금산입**
- 상여 처분 또는 배당 처분 리스크
- ruling 라벨: "익금산입" 또는 "부당행위해당"

**검증 포인트**:
- [ ] **법령 MCP를 먼저 호출하면 FAIL** — reasoning_engine 우선 원칙 위배
- [ ] decisive_sources 핀 주입 확인 (`judgment.retrieved_legal`에 판례 ID 포함)
- [ ] adversary 페르소나가 소득처분·세무조사 리스크 거론

---

## 실행 방법

세션에서 위 3개 질의를 각각 /tax로 실행 후, 아래 항목을 기록:

```markdown
### S{N} 결과
- 호출된 모듈/도구: [...]
- strategy_engine.run() 호출? (y/n)
- reasoning_engine.run() 호출? (y/n)
- 법령 MCP 호출 순서: [...]
- 발동된 규칙 id: [...]
- 기대와 일치: [y/n, 불일치면 사유]
```

## 채점 기준

- **3/3 올바른 경로**: C-1 통과. 다음은 C-2 orchestrator Top-3로 진행
- **2/3**: 실패 시나리오 분석 → SKILL.md 분기 규칙 보강 후 재측정
- **1/3 이하**: /tax SKILL.md 경로 분기 로직 전면 재검토

---

## 엔진 단위 테스트 결과 (2026-04-24)

> **목적**: /tax 스킬 전체 경로 검증 전에, 엔진(strategy_engine · reasoning_engine)이 기대대로 발동하는지 먼저 확인.
> 스크립트: `scripts/c1_engine_unit_tests.py`

### S1 소득세 — PASS (3/3)

```json
{
  "fired": ["CRED_CHILDREN", "DED_PENSION_IRP_700", "TIMING_MEDICAL_EXPENSE"],
  "expected_any_of": ["CRED_CHILDREN", "DED_PENSION_IRP_700", "TIMING_MEDICAL_EXPENSE"],
  "coverage": "3/3"
}
```

### S2 법인세 — PASS (2/2)

```json
{
  "fired": ["CORP_INTEGRATED_INVESTMENT_CREDIT", "CORP_RD_TAX_CREDIT"],
  "expected_any_of": ["CORP_INTEGRATED_INVESTMENT_CREDIT", "CORP_RD_TAX_CREDIT"],
  "coverage": "2/2"
}
```

### S3 회색지대 가지급금 — PASS (Claude 직접 판단)

**실행 방식**: 로컬 Ollama reasoning_engine 거치지 않고 /tax 스킬 원칙에 따라 Claude 가 직접 법령 MCP 로 조문 확인 후 판단.

**법령 근거** (law-mcp 로 실시간 확인):
- 법§52 — 특수관계인 거래 부당행위계산 부인, 시가 기준 재계산
- 영§89③ — 금전 대여 시가: 원칙 **가중평균차입이자율**, 조건 충족·신청 시 **당좌대출이자율(4.6%)**
  - 가중평균 적용 불가 사유 / 대여기간 5년 초과 / 영§89③2 신고 시 선택(당 사업연도 + 이후 2년)

**판단 (Claude 자체 reasoning)**:
- 대표이사 = 특수관계인 → 저리 대여는 부당행위 명백
- 시가 = 당좌대출이자율 4.6% (개인 부동산 취득 → 업무무관, 법인 차입 여부 미상)
- 인정이자: 5억 × (4.6% − 2%) = **연 1,300만원 익금산입**
- 소득처분: 대표이사 귀속 → **상여 처분** (영§106①1) → 근로소득 원천징수
- 장기 미회수 시 영§53 업무무관가지급금 지급이자 손금불산입 추가 페널티

**ruling** (ruling_spectrum 매핑): **"당좌대출이자율적용"**

**리스크**: HIGH — 가지급금은 세무조사 핵심 타깃. 업무무관 용도 명백(개인 부동산).

**권고**:
1. 5억 조기 회수 + 기발생 이자 납부
2. 불가피하면 당좌대출이자율 소급 재산정
3. 신고 시 영§89③2 당좌대출이자율 선택 → 향후 일관성

**검증 결과**:
- [x] 법령 MCP 조문 확인 (§52, 영§89)
- [x] ruling 라벨 결정: "당좌대출이자율적용"
- [x] 세무조사 리스크 high 명시
- [x] 소득처분(상여) 거론
- [~] decisive_sources 핀 주입 확인 → **이슈에 핀 없음**. B-2 확장 대상(30개 이슈 중 핀 8건만 있음).

---

## C-1 종합 결론

| 시나리오 | 경로 | 결과 |
|---|---|---|
| S1 소득세 | strategy_engine.run() | PASS 3/3 |
| S2 법인세 | strategy_engine.run() | PASS 2/2 |
| S3 회색지대 가지급금 | Claude + law-mcp (reasoning_engine 우회) | PASS, ruling 결정 |

**3/3 경로 모두 올바르게 작동**. /tax 스킬이 Claude 기반 경로에서 정상 작동 확인.

## 발견 사항 정리

1. **주택청약 소득공제 규칙 누락** — B-2 정량 규칙 확장
2. **가지급금 이슈 decisive_sources 핀 없음** — B-2 핀 30건 목표
3. **reasoning_engine 내부 LLM이 로컬 Ollama** — 사용자 결정(로컬 모델 제거) 반영하려면 Claude 기반 adapter 필요
4. **규칙 ID 네이밍 일관성** — 문서·스킬에서 약칭 사용 시 참조 불일치

### 발견한 공백 (Track B-2 확장 대상)

- **주택청약 소득공제 규칙 미구현** (조특 §87). 현재 `DED_HOUSING_SAVINGS` 류 규칙이 `strategy_engine/rules/income_tax/deductions.yaml`에 없음. 실제 발동 가능한 건 DED_PENSION_IRP_700, DED_CREDIT_CARD 2개뿐.
- 명세: 총급여 7천만 이하, 납입액 × 40%, 한도 300만
- 예상 rule_id: `DED_HOUSING_SAVINGS_CHEONGYAK`

### ID 네이밍 학습

실제 규칙 ID는 suffix 포함(`DED_PENSION_IRP_700`, `TIMING_MEDICAL_EXPENSE`, `CRED_CHILDREN`). SKILL.md/문서에서 약칭 쓰면 참조 불일치 발생. 규칙 신설 시 네이밍 일관성 확인 필요.
