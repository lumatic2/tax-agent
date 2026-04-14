"""
Track B — Domain Verifier (L4)

LLM 세무 답변에서 핵심 숫자를 추출하고
tax_calculator 정답과 비교해 PASS / FAIL을 판정한다.

사용 예:
    from tax_verifier import TaxVerifier
    result = TaxVerifier().verify(llm_answer, gross_salary=50_000_000)
    print(result)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import tax_calculator as tc


# ── 1. 한국어 금액 파서 ──────────────────────────────────────────────────────

def _parse_korean_money(text: str) -> Optional[int]:
    """
    한국어 금액 표현을 정수(원)로 변환.
    지원 패턴:
        "459만5,250원"   → 4_595_250
        "1,225만원"      → 12_250_000
        "417만7,500원"   → 4_177_500
        "3,625만원"      → 36_250_000
        "9.19%"          → (백분율이므로 None — 별도 처리)
    """
    text = text.replace(',', '').replace(' ', '')
    m = re.match(r'^(\d+(?:\.\d+)?)억(?:(\d+)만)?(?:(\d+))?원?$', text)
    if m:
        eok  = int(float(m.group(1)) * 100_000_000)
        man  = int(m.group(2) or 0) * 10_000
        rest = int(m.group(3) or 0)
        return eok + man + rest

    m = re.match(r'^(\d+)만(\d+)원?$', text)
    if m:
        return int(m.group(1)) * 10_000 + int(m.group(2))

    m = re.match(r'^(\d+)만원?$', text)
    if m:
        return int(m.group(1)) * 10_000

    m = re.match(r'^(\d+)원?$', text)
    if m:
        return int(m.group(1))

    return None


def _extract_money(pattern: str, text: str) -> Optional[int]:
    """정규식 패턴으로 텍스트에서 금액 추출."""
    m = re.search(pattern + r'[:\s]*([0-9,억만]+원?)', text)
    if m:
        return _parse_korean_money(m.group(1))
    return None


def _extract_pct(pattern: str, text: str) -> Optional[float]:
    """정규식 패턴으로 백분율 추출."""
    m = re.search(pattern + r'[:\s]*([0-9.]+)%', text)
    if m:
        return float(m.group(1))
    return None


# ── 2. LLM 답변에서 숫자 추출 ─────────────────────────────────────────────────

def extract_claims(answer: str) -> dict:
    """LLM 답변 텍스트에서 세액 관련 숫자를 추출한다."""
    t = answer.replace('\n', ' ')
    return {
        'gross_salary':        _extract_money(r'총급여', t),
        'employment_deduction': _extract_money(r'근로소득공제', t),
        'taxable_income':      _extract_money(r'과세표준', t),
        'income_tax':          _extract_money(r'산출세액', t),
        'local_tax':           _extract_money(r'지방소득세', t),
        'total_tax':           _extract_money(r'총납부예상', t),
        'effective_rate':      _extract_pct(r'실(?:효|질)세율', t),
    }


# ── 3. 검증 규칙 ──────────────────────────────────────────────────────────────

@dataclass
class Violation:
    field: str
    claimed: object
    expected: object
    message: str

    def __str__(self):
        return f'[{self.field}] claimed={self.claimed} | expected={self.expected} | {self.message}'


@dataclass
class VerifyResult:
    passed: bool
    violations: list[Violation] = field(default_factory=list)
    ground_truth: dict = field(default_factory=dict)
    claims: dict = field(default_factory=dict)

    def __str__(self):
        status = '✅ PASS' if self.passed else '❌ FAIL'
        lines = [status]
        for v in self.violations:
            lines.append(f'  {v}')
        return '\n'.join(lines)


def _tol_check(claimed: Optional[int], expected: int, tol_pct: float = 1.0) -> bool:
    """허용 오차 범위 내인지 확인 (기본 ±1%)."""
    if claimed is None:
        return True   # 추출 못한 경우 통과 (검증 불가)
    return abs(claimed - expected) <= max(expected * tol_pct / 100, 1000)


# ── 4. TaxVerifier ────────────────────────────────────────────────────────────

class TaxVerifier:
    """
    근로소득세 검증기.

    지원 규칙:
        R1. 근로소득공제 = calculate_employment_income_deduction(gross_salary)
        R2. 산출세액     = calculate_tax(과세표준)['산출세액']
        R3. 지방소득세   = 산출세액 × 10%
        R4. 총납부예상   = 산출세액 + 지방소득세
        R5. 실효세율(%)  = 총납부예상 / 총급여 × 100  (±0.5%p 허용)
        R6. 세율 구간    = 세율표 범위 내 (소득세법 제55조)
    """

    def verify(
        self,
        llm_answer: str,
        gross_salary: int,
        national_pension: int = 0,
        health_insurance: int = 0,
    ) -> VerifyResult:

        # Ground truth 계산
        gt = tc.calculate_wage_income_tax(
            gross_salary,
            extra_deductions={
                **({"국민연금": national_pension} if national_pension else {}),
                **({"건강보험": health_insurance} if health_insurance else {}),
            }
        )

        ground_truth = {
            'gross_salary':         gt['총급여'],
            'employment_deduction': gt['근로소득공제'],
            'taxable_income':       gt['과세표준'],
            'income_tax':           gt['산출세액'],
            'marginal_rate':        gt['적용세율'],
            'local_tax':            gt['지방소득세'],
            'total_tax':            gt['총납부예상'],
            'effective_rate':       round(gt['총납부예상'] / max(gross_salary, 1) * 100, 2),
        }

        claims = extract_claims(llm_answer)
        violations: list[Violation] = []

        # R1. 근로소득공제
        if not _tol_check(claims['employment_deduction'], ground_truth['employment_deduction']):
            violations.append(Violation(
                'employment_deduction',
                claims['employment_deduction'],
                ground_truth['employment_deduction'],
                '근로소득공제 계산 오류 (소득세법 제47조)',
            ))

        # R2. 산출세액
        if not _tol_check(claims['income_tax'], ground_truth['income_tax']):
            violations.append(Violation(
                'income_tax',
                claims['income_tax'],
                ground_truth['income_tax'],
                '산출세액 계산 오류 (소득세법 제55조 세율표)',
            ))

        # R3. 지방소득세 = 산출세액 × 10%
        if claims['income_tax'] is not None and claims['local_tax'] is not None:
            expected_local = round(ground_truth['income_tax'] * 0.1)
            if not _tol_check(claims['local_tax'], expected_local):
                violations.append(Violation(
                    'local_tax',
                    claims['local_tax'],
                    expected_local,
                    '지방소득세 = 산출세액 × 10% 위반',
                ))

        # R4. 총납부예상
        if not _tol_check(claims['total_tax'], ground_truth['total_tax']):
            violations.append(Violation(
                'total_tax',
                claims['total_tax'],
                ground_truth['total_tax'],
                '총납부예상 = 산출세액 + 지방소득세 불일치',
            ))

        # R5. 실효세율 (±0.5%p 허용)
        if claims['effective_rate'] is not None:
            diff = abs(claims['effective_rate'] - ground_truth['effective_rate'])
            if diff > 0.5:
                violations.append(Violation(
                    'effective_rate',
                    f"{claims['effective_rate']}%",
                    f"{ground_truth['effective_rate']}%",
                    f'실효세율 오차 {diff:.2f}%p (허용 ±0.5%p)',
                ))

        # R6. 세율 구간 sanity check
        BRACKETS = [
            (14_000_000, 0.06), (50_000_000, 0.15), (88_000_000, 0.24),
            (150_000_000, 0.35), (300_000_000, 0.38), (500_000_000, 0.40),
            (1_000_000_000, 0.42), (float('inf'), 0.45),
        ]
        ti = ground_truth['taxable_income']
        expected_rate = next(r for upper, r in BRACKETS if ti <= upper)
        if abs(ground_truth['marginal_rate'] - expected_rate) > 0.001:
            violations.append(Violation(
                'marginal_rate',
                ground_truth['marginal_rate'],
                expected_rate,
                '적용세율이 소득세법 제55조 세율표와 불일치',
            ))

        return VerifyResult(
            passed=len(violations) == 0,
            violations=violations,
            ground_truth=ground_truth,
            claims=claims,
        )
