# Phase 3 — 상속세·증여세 (Level 4)

> **완료**: 2026-04-13 (Phase 2 Level 4 달성 후 착수)

## 챕터 현황

| 챕터 | 모듈/내용 | 상태 |
|---|---|---|
| Ch01 상속세 | `calculate_inheritance_tax()` — 상속재산, 공제, 세율 | **Level 4** |
| Ch02 증여세 | `calculate_gift_tax()` + 특수증여 3종 | **Level 4** |
| Ch03 재산의 평가 | 부동산(토지/건물/주택/임대) + 유가증권 + 예금 | **Level 4** |
| Ch04 신고/납부 | 연부연납, 물납 안내 | Level 2 |

## 완료 (Level 0 → Level 4, 2026-04-12~13)

**Level 2 (뼈대)**
- [x] 조문 캐시 25개 조문 (법제처 API) → `data/inheritance_gift/statutes_cache.txt`
- [x] `inheritance_gift_calculator.py` Ch01~Ch04 핵심 함수
- [x] eval 20/20 통과

**Level 3 (숫자 검증)**
- [x] 장례비 봉안시설 분리계산 (시행령 §9)
- [x] 감정평가수수료 500만 한도 (시행령 §49의2)
- [x] CPA 기출 3건 정답 일치 (eval 23/23)

**Level 4 (실무 완성)**
- [x] 가업상속공제 (§18의2): 경영기간별 300/400/600억 한도
- [x] 영농상속공제 (§18의3): 30억 한도
- [x] 특수증여 3종: 저가양도(§35), 부동산무상사용(§37), 금전무상대출(§41의4)
- [x] 부동산 보충적 평가: 토지(공시지가×배율), 건물(기준시가), 주택(공시가격), 임대재산
- [x] `inheritance_gift_calc_cli.py` — 12개 서브커맨드
- [x] eval 30/30 전부 통과

## 결과

Phase 3 완료. Phase 4(법인세) 시작 가능.
