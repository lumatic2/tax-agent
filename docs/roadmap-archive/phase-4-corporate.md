# Phase 4 — 법인세 (Level 4)

> **완료**: 2026-04-13 · eval 30/30 pass

## 산출물

| 파일 | 내용 | 규모 |
|---|---|---|
| `corporate_tax_calculator.py` | 계산 엔진 24개 함수 | ~1100줄 |
| `corporate_tax_calc_cli.py` | CLI 11개 서브커맨드 | ~250줄 |
| `eval_scenarios_corporate_tax.py` | exact-match 시나리오 | 30개, ~800줄 |
| `data/corporate_tax/` | 법령 조문 캐시 | §55, §13 |

## 구현 챕터

| Level | 챕터 | 함수 | Eval |
|---|---|---|---|
| L1 | Ch10 세율·과세표준·이월결손금 | `apply_corporate_tax_rate`, `calculate_loss_carryforward`, `calculate_corporate_tax_base`, `calculate_corporate_tax` | CT1~CT5 |
| L2 | Ch02~04 세무조정 | `calculate_taxable_income`, `calculate_dividend_received_deduction`, `calculate_entertainment_expense_limit_corp`, `calculate_donation_limit`, `check_non_deductible_expenses` | CT6~CT12 |
| L3 | Ch07~08 감가상각·충당금 | `calculate_depreciation_limit`, `get_statutory_useful_life`, `get_declining_balance_rate`, `calculate_retirement_allowance_reserve`, `calculate_bad_debt_reserve` | CT13~CT20 |
| L4 | Ch09,11~14 세액공제·최저한세 | `calculate_unfair_transaction_denial`, `calculate_foreign_tax_credit`, `calculate_sme_tax_reduction`, `apply_minimum_tax`, `calculate_land_transfer_additional_tax`, `calculate_interim_prepayment`, `classify_corporation_type`, `calculate_corporate_tax_full` | CT21~CT30 |

## 핵심 설계

- **이월결손금 한도 80%** (현행 §13, 중소기업 100%) — 초기 60% 기재는 구법 기준 오류
- **세율**: 9%/19%/21%/24% 4단계 (2023 개정)
- **세무조정**: `list[dict]` 구조 (`{항목, 금액, 소득처분}`)
- **최저한세**: 중소 7% / 일반 10~17% (조특법 §132)
- **전체 파이프라인**: 회계이익 → 세무조정 → 과세표준 → 세율 → 감면 → 최저한세 → 토지추가 → 납부세액

## 법인세 2차 서술형 A/B 실증 — 78/78 전수 검증

- [x] 2024 Q4: 접대비 한도·출자전환·지급이자·주식매수선택권·개발비 — 25/25
- [x] 2024 Q5: 부당행위계산부인(실권주)·결손금 소급공제 — 8/8 (정답JSON 4건 수정)
- [x] 2024 Q6: 상속세 과세가액·증여 반환시기 — 6/6
- [x] 2025 Q4: 의제배당·퇴직급여충당금·대손충당금·업무용승용차 — 22/22
- [x] 2025 Q5: 임원상여금·퇴직금 한도·기부금·부당행위계산부인 — 10/10
- [x] 2025 Q6: 연결납세 — 2/2
- [x] 2025 Q7: 증여세(부동산 무상사용·금전무상대출·보험금) — 5/5 (JSON 누락 2건 보완)

**합계**: 2024 39/39 + 2025 39/39 = **78/78 전수 검증 완료**
