# Phase 8-A — 규칙 추가 3종 (2026-04-17 완료)

> `strategy_engine` 37규칙 → 40. 커버리지 부채를 값싸게 상환.
> 실행 순서: 2 → 1 → 3 (2026-04-17 확정)

---

## [x] 🥇 조특법 §7 중소기업 특별세액감면 (2026-04-17)

- `sme_special_reduction_savings` estimator + `RED_SME_SPECIAL_SECTION7` YAML
- **16셀 감면율 테이블**: 업종(제조/도소매·의료/지식기반/기타) × 규모(소/중) × 소재지(수도권/비수도권)
- 연 1억 한도
- eval_strategy_catalog 94→97 (+3 tests), 51→52 규칙

## [x] 🥈 종합부동산세 규칙 신설 (2026-04-17)

- `property_holding_tax.py` 신설 — 일반/중과 누진 브래킷 + 1세대1주택 세액공제
- `rules/property_holding/holding.yaml` 3규칙:
  - `CHT_SPOUSE_JOINT` — 부부 공동명의 공제 12→18억
  - `CHT_RENTAL_EXCLUSION` — 임대주택 합산배제
  - `CHT_ONE_HOUSE_CREDIT` — 고령·장기보유 80%
- `tax_type="종합부동산세"` 신설
- eval 97→105 (+8 tests), 52→55 규칙

## [x] 🥉 개인지방소득세 (지방세법 §103의52) (2026-04-17)

- `tax_calculator.calculate_tax()` 반환 dict에 `지방소득세` 필드 추가 (산출세액 × 10%)
- `calculate_local_tax` 헬퍼 기존 유지

---

## 결과

- 총 55규칙 (소득세·법인세·상증세·증여세·양도·부동산보유 통합)
- 기존 회귀 무회귀 유지
