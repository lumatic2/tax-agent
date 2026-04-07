# 다음 세션에서 할 일

_최종 업데이트: 2026-04-07_

## 1. 비과세 함수 파이프라인 연결 (Codex 위임)

`calculate_nontaxable_employment_income()`이 tax_calculator.py에 구현됐지만 main.py 파이프라인에 연결 안 됨.

**작업 내용:**
- `main.py`의 `_input_wage_inputs()`에 `pay_items` 옵션 추가
  - 사용자가 급여 항목별(기본급, 식대, 교통보조금 등)로 입력 가능하도록
- `_calculate_wage_pipeline()` 초반에 pay_items가 있으면 `calculate_nontaxable_employment_income()` 호출 → gross_salary 자동 산출
- pay_items 없으면 기존처럼 gross_salary 직접 입력

**Codex 플래그:** `--background --write "main.py _input_wage_inputs와 _calculate_wage_pipeline에 calculate_nontaxable_employment_income 연결..."`

---

## 2. 미구현 항목 (우선순위 순)

### 2-1. 이연퇴직소득세 (DC형) — 높음
- CPA 60회 2025 해설에서 직접 출제됨
- `calculate_retirement_income_tax()`에 `deferred_amount` 파라미터 추가
- 산출세액 × (DC계좌 이전액 / 총퇴직급여) = 이연세액
- 원천징수세액 = 산출세액 - 이연세액

### 2-2. 퇴직소득 한도 계산 — 높음
- CPA 60회 2025 해설 요구사항3에 출제됨
- 2019년 이전 구간: 연평균총급여 × 1/10 × 근무월수(해당기간) × 3배
- 2020년 이후 구간: 연평균총급여 × 1/10 × 근무월수(해당기간) × 2배
- 별도 함수 `calculate_retirement_income_limit()` 신설

### 2-3. 추계신고 (기준경비율/단순경비율) — 높음
- 자영업자 세무신고 핵심
- 국세청 고시 경비율 테이블 필요
- `calculate_business_income_estimated()` 신설

### 2-4. 주택임차차입금 원리금 상환액 공제 — 중간
- 연말정산 빈출 항목
- `calculate_special_deductions()`에 `housing_loan_repayment` 파라미터 추가
- 한도: 연 400만원 (2023년 이후 300만→400만 개정)

### 2-5. 장기주택저당차입금 이자상환액 공제 — 중간
- 한도: 600만~2,000만원 (상환방식·고정금리 여부에 따라)
- `calculate_special_deductions()`에 추가

### 2-6. 일용근로소득 — 낮음
- 일 150,000원 비과세, 초과분 6% 분리과세
- `calculate_daily_wage_tax()` 신설

---

## 3. 검증 현황

| 항목 | 검증 결과 |
|---|---|
| 근로소득공제 | ✅ CPA 60회 일치 |
| 퇴직소득 산출세액 | ✅ CPA 60회 일치 (근속연수공제 2024년 개정 반영) |
| 양도소득 (일반/이월과세) | ✅ CPA 60회 일치 |
| 금융소득 비교과세 산출세액 | ✅ CPA 60회 일치 |
| 비과세 근로소득 판단 | ✅ 함수 구현 (파이프라인 미연결) |
| 이연퇴직소득세 | ❌ 미구현 |
| 퇴직소득 한도 | ❌ 미구현 |
| 추계신고 | ❌ 미구현 |

---

## 4. 참고 파일

- 해설 PDF: `C:/Users/1/Downloads/2025년 2차 회계사 기출_해설.pdf` (양소영, 19p)
- 기출 문제: `~/Desktop/cpa_tax_2024.pdf`, `~/Desktop/cpa_tax_2025.pdf`
