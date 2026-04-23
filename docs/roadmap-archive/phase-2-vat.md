# Phase 2 — 부가가치세 (Level 4)

> **완료**: 2026-04-12 (eval 27/27 · 1차 8/8 · 2차 3개년 전항목)

## 개요

- 시작: Phase 1 Level 4 + 22/22 인증 후 (2026-04-12~)
- 법령 범위: 부가가치세법 본법 + 시행령 + 조세특례제한법 부가세 특례
- 구현 패턴: law-mcp → `data/vat/*.txt` → `vat_calculator.py` → `eval_scenarios_vat.py` → `certify_phase2.py`

## 챕터별 구현 순서

| 챕터 | 모듈/내용 | 순위 | 상태 |
|---|---|---|---|
| Ch05 과세표준·매출세액 | `calculate_vat_output_tax()` 외 4개 | 1 | [x] Level 2 |
| Ch06 매입세액·납부세액 | `calculate_vat_input_tax()` 외 5개 | 2 | [x] Level 2 |
| Ch07 겸영사업자 | `calculate_common_input_tax_allocation()` 외 2개 | 3 | [x] Level 2 |
| Ch09 간이과세 | `calculate_simplified_vat()` 외 1개 | 4 | [x] Level 2 |
| Ch01 총설 | `is_vat_taxpayer()`, `get_vat_tax_period()` | 5 | [x] Level 2 |
| Ch02 과세거래 | `is_deemed_supply()`, `get_supply_time()` | 6 | [x] Level 2 |
| Ch03 영세율·면세 | `is_zero_rated()`, `is_vat_exempt()` | 7 | [x] Level 2 |
| Ch04 세금계산서 | `calculate_invoice_penalty()` | 8 | [x] Level 2 |
| Ch08 신고·납부 | `calculate_vat_penalties()`, `calculate_preliminary_notice()` | 9 | [x] Level 2 |

## 기출 현황

| 연도 | 부가세 문항 | 번호 |
|---|---|---|
| 2023 | 9개 | Q48, Q71~Q80 |
| 2024 | 8개 | Q71~Q78 |
| 2025 | 9개 | Q67, Q71~Q78 |

## A/B 실증 진행 (2026-04-12)

| 문제 | 정답 | B | A | A 도구 | 결과 |
|---|---|---|---|---|---|
| 2025 Q71 | ③ | ③ | ③ | vat_calc_cli land-building, common-alloc, **recalc** | B=A 정답 · recalc로 exact match |
| 2025 Q72 | ② | ② | ② | 판정형 | B=A 정답 |
| 2025 Q73 | ③ | ③ | ③ | deemed-input, deemed-limit, payable | B=A 정답 · 17K 오차 |
| 2025 Q74 | ④ | ④ | ④ | **proxy**, common-alloc | B=A 정답 · proxy로 exact match |
| 2025 Q75 | ④ | ④ | ④ | law-mcp 영§40①2호다목 | B=A 정답 · A 근거 보강 |
| 2025 Q76 | ② 366K | 불확실 | ② (4K오차) | §63③·§46 수동계산=370K | **A 도구 기여** |
| 2025 Q77 | ④ | ④ | ④ | 판정형 | B=A 정답 |
| 2025 Q78 | ② 1.3 | ② | ② | art_60_가산세.txt | B=A 정답 |

- 완료: **8/8** (100%)

## Gap 보강 (2026-04-12)

- [x] §43/영§63 재계산: `recalculate_mixed_use_asset_tax()` + CLI `recalc`
- [x] §52 대리납부: `calculate_proxy_payment_tax()` + CLI `proxy`
- [x] 의제매입세액 한도: `calculate_deemed_input_tax_with_limit()` + CLI `deemed-limit`
- [x] 지방소비세: `calculate_local_consumption_tax()` + CLI `local-tax`

## law-mcp 버그 (2026-04-12 발견, 수정)

**증상**: `get_law_article(law_id="부가가치세법", ...)` → HTTP 500
**원인**: 법명(한글)을 API의 `ID`에 그대로 전달 → 숫자 ID 기대 → 500
**수정**: `getLawArticle()`에 `resolveLawId()` 추가, 한글 법명→숫자코드 자동변환

## 법령코드 참조

| 법령 | 코드 |
|---|---|
| 부가가치세법 | 001571 |
| 부가가치세법 시행령 | 003666 |
| 소득세법 | 001565 |

## 조문 인용 정정 (2026-04-12)

- §41: 공통매입세액 재계산 (5% 이상 변동)
- 영§83: 재계산 세부 (건물 20기, 기타 4기)
- §43: 면세→과세 전환 시 매입세액공제 특례
- 영§63: 공통사용 재화의 공급가액 계산

## API 복구 후 완료 (2026-04-12)

- [x] law-mcp `resolveLawId()` 추가
- [x] 부가세 핵심 조문 21개 일괄 캐시 (`data/vat/`)
- [x] 재계산 함수 조문 정정 (§41/영§83)
- [x] Q75~Q78 A/B 실증 — 8/8 (Q76만 4K 오차)
- [x] 대리납부 환율 근거 확인 (영§95③)
- [x] 간이과세 함수 확장 — §63③(0.5%)+§46(카드)+§63⑥, CLI+eval V23
- [x] CPA 2차 2025 문제3 물음1 — 6항목 중 3정답/3오류
- [x] CPA 2차 해설 PDF 복구

## Phase 2 현재 상태 (2026-04-12)

**Level 4** — 1차 MCQ 8/8, 2차 서술형 3개년 전항목 정답, eval 27/27

| 구분 | 상태 |
|---|---|
| 계산엔진 | 9개 챕터 + gap 9개 = 18개 함수, eval 27/27 |
| 조문 캐시 | 21개 (`data/vat/`) |
| 1차 실증 | **8/8** (B 87.5%, A 100%) |
| 2차 실증 | **2025 6/6** + **2024 14/14** + **2023 전항목** |
| 정답 JSON | 3개년 부가세 정답 숫자 파싱 완료 |
| CLI | 18개 서브커맨드 |

## 완료 항목 (2026-04-12)

- [x] 임직원 증정 비과세 한도 (§10④ 단서)
- [x] 수출 과세표준 환율 세분화 (영§59)
- [x] 예정신고 누락분 판정 로직
- [x] Q76 4K 조사 (미확정, 해설집 미입수)
- [x] 조특법§108 재활용폐자원·중고자동차 함수
- [x] CPA 2차 2025 물음1 6/6
- [x] CPA 2차 2024 14/14
- [x] CPA 2차 2023 전항목
- [x] CPA 2차 부가세 정답 JSON 3개년 완료

## 잔여 (선택)

- [ ] Q76 4K 원인 확정 — 세무사 해설집 입수 시 재조사
- [ ] CLI 서브커맨드 3개 추가 (gift/export/omission)
- [ ] certify_phase2.py 작성

## Phase 2 완료 기준

```
모든 챕터 함수 구현 + exact assert 통과
certify_phase2.py 인증 게이트 전항목 통과  (← 미작성)
부가세 기출(세무사 1차 2023~2025) A/B 실증 완료 ✅
```
