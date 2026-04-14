"""절세 전략 엔진

공제 체크리스트 기반으로 누락/추가 공제 가능성을 점검하고,
tax_result(세액 계산 결과)의 한계세율(적용세율)을 반영해 절세액을 산출한다.
"""

from tax_calculator import calculate_tax, calculate_sme_employment_tax_reduction

CHECKLIST = [
    {
        "name": "노란우산공제",
        "condition": "개인사업자/소기업·소상공인이고 노란우산에 가입 가능",
        "expected_saving": 500_000,
        "legal_ref": "조세특례제한법(소기업·소상공인 공제부금)",
    },
    {
        "name": "IRP추가납입",
        "condition": "IRP/연금저축 추가 납입 여력이 있음 (연 900만원 한도, 세액공제 13.2~16.5%)",
        "expected_saving": 400_000,
        "legal_ref": "소득세법/조세특례제한법(연금계좌 세액공제)",
    },
    {
        "name": "중소기업취업자감면",
        "condition": "중소기업 취업자 감면 요건 해당 (5년간 최대 90% 감면)",
        "expected_saving": 500_000,
        "legal_ref": "조세특례제한법 제30조(중소기업 취업자 소득세 감면)",
    },
    {
        "name": "월세세액공제",
        "condition": "무주택 세대주(또는 세대원)로 월세 지출이 있음",
        "expected_saving": 300_000,
        "legal_ref": "조세특례제한법 제95조의2(월세액 세액공제)",
    },
    {
        "name": "부양가족인적공제",
        "condition": "부양가족 소득요건(연 100만원 이하) 충족 가족이 있음",
        "expected_saving": 300_000,
        "legal_ref": "소득세법 제50조(인적공제)",
    },
    {
        "name": "연금저축",
        "condition": "연금저축 납입액이 있거나 추가 납입 가능",
        "expected_saving": 250_000,
        "legal_ref": "소득세법(연금계좌 세액공제)",
    },
    {
        "name": "기부금이월공제",
        "condition": "기부금 한도 초과분이 있고 이월공제를 미활용",
        "expected_saving": 150_000,
        "legal_ref": "소득세법(기부금 세액공제 및 이월)",
    },
    {
        "name": "중도퇴사자특별공제",
        "condition": "연중 중도퇴사로 특별공제(의료비·교육비 등) 누락 가능성",
        "expected_saving": 150_000,
        "legal_ref": "소득세법(근로소득 관련 공제 정산)",
    },
    {
        "name": "결혼세액공제",
        "condition": "해당 연도(2024~2026) 혼인신고 시 1인당 50만원 세액공제",
        "expected_saving": 500_000,
        "legal_ref": "소득세법(혼인 세액공제, 2024 신설)",
    },
    {
        "name": "취학전아동학원비",
        "condition": "취학 전 아동의 학원/어린이집 비용이 있음 (간소화 서비스 미자동조회)",
        "expected_saving": 100_000,
        "legal_ref": "소득세법(교육비 세액공제)",
    },
    {
        "name": "안경구입비",
        "condition": "본인/부양가족 안경·콘택트렌즈 구입비가 있음 (간소화 서비스 미자동조회)",
        "expected_saving": 50_000,
        "legal_ref": "소득세법(의료비 세액공제)",
    },
    {
        "name": "종교단체기부금",
        "condition": "종교단체 기부금 지출이 있음 (직접 영수증 수집 필요)",
        "expected_saving": 80_000,
        "legal_ref": "소득세법(기부금 세액공제)",
    },
]


def _to_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return int(default)


def _to_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)


def _get_income_dict(user_data):
    if not isinstance(user_data, dict):
        return {}
    income = user_data.get("income", {})
    return income if isinstance(income, dict) else {}


def _get_total_income(user_data):
    income = _get_income_dict(user_data)
    if income:
        return sum(_to_int(v, 0) for v in income.values())
    return _to_int((user_data or {}).get("gross_income", 0), 0)


def _get_gross_salary(user_data):
    income = _get_income_dict(user_data)
    if "근로소득" in income:
        return _to_int(income.get("근로소득", 0), 0)
    if "총급여" in (user_data or {}):
        return _to_int((user_data or {}).get("총급여", 0), 0)
    return _get_total_income(user_data)


def _get_total_deductions(user_data):
    if not isinstance(user_data, dict):
        return 0
    return _to_int(user_data.get("total_deductions", 0), 0)


def _get_marginal_rate(user_data, tax_result):
    if isinstance(tax_result, dict) and "적용세율" in tax_result:
        return _to_float(tax_result.get("적용세율", 0.15), 0.15)

    total_income = _get_total_income(user_data)
    total_deductions = _get_total_deductions(user_data)
    taxable_income = max(int(total_income - total_deductions), 0)
    try:
        return _to_float(calculate_tax(taxable_income).get("적용세율", 0.15), 0.15)
    except Exception:
        return 0.15


def _is_applicable(item, user_data):
    """user_data 기반으로 해당 공제 항목 적용 여부 판단."""
    income = user_data.get("income", {}) if isinstance(user_data, dict) else {}
    flags = user_data.get("flags", {}) if isinstance(user_data, dict) else {}
    name = item["name"]

    if name == "노란우산공제":
        return int(income.get("사업소득", 0) or 0) > 0
    if name == "월세세액공제":
        monthly_rent = _to_int((user_data or {}).get("monthly_rent", 0), 0)
        return bool(flags.get("월세지출", False)) or monthly_rent > 0
    if name == "중소기업취업자감면":
        return bool(flags.get("중소기업취업", False))
    if name == "부양가족인적공제":
        dependents_total = _to_int((user_data or {}).get("dependents_total", flags.get("부양가족수", 0)), 0)
        return dependents_total > 0
    if name == "취학전아동학원비":
        return bool(flags.get("교육비지출", False))
    if name == "중도퇴사자특별공제":
        return bool(flags.get("중도퇴사", False))
    if name == "결혼세액공제":
        return bool(flags.get("혼인", False))
    if name == "안경구입비":
        return bool(flags.get("의료비지출", False))
    if name == "기부금이월공제":
        return bool(flags.get("기부금이월", False))
    if name == "종교단체기부금":
        return bool(flags.get("종교단체기부", False))
    # IRP, 연금저축은 누구에게나 해당
    return True


def _calc_irp_saving(user_data):
    gross_salary = _get_gross_salary(user_data)
    credit_rate = 0.165 if gross_salary <= 55_000_000 else 0.132

    irp_now = _to_int((user_data or {}).get("irp_pension", 0), 0)
    pension_now = _to_int((user_data or {}).get("pension_savings", 0), 0)
    limit = 9_000_000
    remaining = max(limit - (irp_now + pension_now), 0)

    saving = int(remaining * credit_rate)
    return {
        "예상절세액": int(saving),
        "현재적용액": int(irp_now),
        "추가가능액": int(remaining),
        "세액공제율": float(credit_rate),
    }


def _calc_pension_saving(user_data):
    gross_salary = _get_gross_salary(user_data)
    credit_rate = 0.165 if gross_salary <= 55_000_000 else 0.132

    irp_now = _to_int((user_data or {}).get("irp_pension", 0), 0)
    pension_now = _to_int((user_data or {}).get("pension_savings", 0), 0)
    limit = 9_000_000
    remaining = max(limit - (irp_now + pension_now), 0)

    saving = int(remaining * credit_rate)
    return {
        "예상절세액": int(saving),
        "현재적용액": int(pension_now),
        "추가가능액": int(remaining),
        "세액공제율": float(credit_rate),
    }


def _calc_monthly_rent_saving(user_data):
    gross_salary = _get_gross_salary(user_data)
    credit_rate = 0.17 if gross_salary <= 55_000_000 else 0.15

    annual_rent = _to_int((user_data or {}).get("monthly_rent", 0), 0) * 12
    cap = 10_000_000
    claimable = min(int(annual_rent), int(cap))
    saving = int(claimable * credit_rate)

    claimed = _to_int((user_data or {}).get("monthly_rent_claimed", 0), 0)
    additional_saving = max(int(saving - claimed), 0)
    return {
        "예상절세액": int(additional_saving),
        "현재적용액": int(claimed),
        "추가가능액": int(claimable),
        "세액공제율": float(credit_rate),
    }


def _calc_sme_employment_reduction(user_data, tax_result):
    income_tax = _to_int((tax_result or {}).get("산출세액", 0), 0)

    worker_type = (user_data or {}).get("sme_worker_type")
    if worker_type not in ("youth", "general"):
        worker_type = "general"

    years_employed = _to_float((user_data or {}).get("sme_years_employed", 0.0), 0.0)

    reduction = calculate_sme_employment_tax_reduction(income_tax, worker_type, years_employed)
    possible = _to_int(reduction.get("감면세액", 0), 0)
    claimed = _to_int((user_data or {}).get("sme_reduction_claimed", 0), 0)
    saving = max(int(possible - claimed), 0)

    return {
        "예상절세액": int(saving),
        "현재적용액": int(claimed),
        "추가가능액": int(possible),
        "감면율": float(reduction.get("감면율", 0.0)),
    }


def _calc_yellow_umbrella_saving(user_data, marginal_rate):
    paid = _to_int((user_data or {}).get("yellow_umbrella", 0), 0)
    limit = 5_000_000
    remaining = max(int(limit - paid), 0)
    saving = int(remaining * float(marginal_rate))
    return {
        "예상절세액": int(saving),
        "현재적용액": int(paid),
        "추가가능액": int(remaining),
    }


def _calc_dependents_saving(user_data, marginal_rate):
    flags = (user_data or {}).get("flags", {}) if isinstance(user_data, dict) else {}
    total = _to_int((user_data or {}).get("dependents_total", flags.get("부양가족수", 0)), 0)
    claimed = _to_int((user_data or {}).get("dependents_claimed", 0), 0)
    additional_count = max(int(total - claimed), 0)

    per_person = 1_500_000
    additional_amount = additional_count * per_person
    saving = int(additional_amount * float(marginal_rate))
    return {
        "예상절세액": int(saving),
        "현재적용액": int(claimed * per_person),
        "추가가능액": int(additional_amount),
        "추가가능인원": int(additional_count),
    }


def _calc_item_saving(name, user_data, tax_result, marginal_rate):
    if name == "IRP추가납입":
        d = _calc_irp_saving(user_data)
        d["한계세율"] = float(marginal_rate)
        return d
    if name == "연금저축":
        d = _calc_pension_saving(user_data)
        d["한계세율"] = float(marginal_rate)
        return d
    if name == "월세세액공제":
        d = _calc_monthly_rent_saving(user_data)
        d["한계세율"] = float(marginal_rate)
        return d
    if name == "중소기업취업자감면":
        d = _calc_sme_employment_reduction(user_data, tax_result or {})
        d["한계세율"] = float(marginal_rate)
        return d
    if name == "노란우산공제":
        d = _calc_yellow_umbrella_saving(user_data, marginal_rate)
        d["한계세율"] = float(marginal_rate)
        return d
    if name == "부양가족인적공제":
        d = _calc_dependents_saving(user_data, marginal_rate)
        d["한계세율"] = float(marginal_rate)
        return d

    return {
        "예상절세액": int(0),
        "현재적용액": int(0),
        "추가가능액": int(0),
        "한계세율": float(marginal_rate),
    }


def _has_confirmed_deduction(deductions, name):
    if not isinstance(deductions, dict):
        return False
    v = deductions.get(name)
    if v is True:
        return True
    try:
        return float(v) > 0
    except Exception:
        return False


def check_missing_deductions(user_data):
    """누락 가능 공제 항목 목록 반환."""
    deductions = user_data.get("deductions") if isinstance(user_data, dict) else None
    total_income = _get_total_income(user_data)
    total_deductions = _get_total_deductions(user_data)
    taxable_income = max(int(total_income - total_deductions), 0)
    try:
        est_tax = calculate_tax(taxable_income)
    except Exception:
        est_tax = {"산출세액": 0, "적용세율": 0.15}

    marginal_rate = _to_float(est_tax.get("적용세율", 0.15), 0.15)
    missing = []
    for item in CHECKLIST:
        if not _is_applicable(item, user_data):
            continue

        name = item["name"]
        calc = _calc_item_saving(name, user_data, {"산출세액": est_tax.get("산출세액", 0)}, marginal_rate)

        if _has_confirmed_deduction(deductions, name) and calc.get("추가가능액", 0) <= 0:
            continue
        if int(calc.get("예상절세액", 0)) <= 0:
            continue

        enriched = dict(item)
        enriched["expected_saving"] = int(calc.get("예상절세액", 0))
        missing.append(enriched)
    return missing


def generate_strategy(user_data, tax_result):
    """우선순위별 절세 전략 목록 반환 (예상절세액 내림차순)."""
    marginal_rate = _get_marginal_rate(user_data, tax_result or {})

    strategies = []
    for item in CHECKLIST:
        if not _is_applicable(item, user_data):
            continue

        name = item["name"]
        calc = _calc_item_saving(name, user_data, tax_result or {}, marginal_rate)
        saving = int(calc.get("예상절세액", 0))
        if saving <= 0:
            continue

        strategies.append(
            {
                "항목": name,
                "예상절세액": saving,
                "조건": item["condition"],
                "법령조항": item["legal_ref"],
                "현재적용액": int(calc.get("현재적용액", 0)),
                "추가가능액": int(calc.get("추가가능액", 0)),
                "한계세율": float(calc.get("한계세율", marginal_rate)),
            }
        )

    strategies.sort(key=lambda x: x["예상절세액"], reverse=True)
    return strategies


def simulate_savings(user_data, tax_result):
    """각 절세 전략 항목에 대해 추가 적용 전/후 세액 비교."""
    if isinstance(user_data, dict) and "income" not in user_data and "income_type" in user_data:
        profile = user_data
        flags = profile.get("flags", {}) or {}
        inputs = flags.get("inputs") or {}
        income_type = ((profile.get("income_type") or [""])[0]) or ""
        income = {}
        try:
            if income_type == "근로소득자":
                wage = inputs.get("wage") or {}
                income["근로소득"] = int(wage.get("gross_salary", 0) or 0)
            elif income_type == "사업소득자":
                biz_inputs = inputs.get("business") or {}
                import tax_calculator as _tax_calculator

                biz = _tax_calculator.calculate_business_income(
                    revenue=int(biz_inputs.get("revenue", 0) or 0),
                    industry_code=str(biz_inputs.get("industry_code", "") or ""),
                    method=str(biz_inputs.get("method", "간편") or "간편"),
                    prev_year_revenue=int(biz_inputs.get("prev_year_revenue", 0) or 0),
                    major_expenses=biz_inputs.get("major_expenses", {}) or {},
                    actual_expenses=int(biz_inputs.get("actual_expenses", 0) or 0),
                )
                income["사업소득"] = int(biz.get("사업소득금액", 0) or 0)
            else:
                comp = inputs.get("composite") or {}
                wage = comp.get("wage") or {}
                biz_inputs = comp.get("business") or {}
                if wage:
                    income["근로소득"] = int(wage.get("gross_salary", 0) or 0)

                import tax_calculator as _tax_calculator

                biz = _tax_calculator.calculate_business_income(
                    revenue=int(biz_inputs.get("revenue", 0) or 0),
                    industry_code=str(biz_inputs.get("industry_code", "") or ""),
                    method=str(biz_inputs.get("method", "간편") or "간편"),
                    prev_year_revenue=int(biz_inputs.get("prev_year_revenue", 0) or 0),
                    major_expenses=biz_inputs.get("major_expenses", {}) or {},
                    actual_expenses=int(biz_inputs.get("actual_expenses", 0) or 0),
                )
                income["사업소득"] = int(biz.get("사업소득금액", 0) or 0)
        except Exception:
            pass

        user_data = {"income": income, "flags": flags}

    current_tax = 0
    if isinstance(tax_result, dict):
        current_tax = _to_int(tax_result.get("총결정세액", tax_result.get("산출세액", 0)), 0)

    strategies = generate_strategy(user_data, tax_result)
    result = []
    for s in strategies:
        saving = int(s.get("예상절세액", 0))
        if saving <= 0:
            continue
        result.append(
            {
                "항목": s["항목"],
                "현재세액": current_tax,
                "적용후세액": current_tax - saving,
                "절세액": saving,
            }
        )
    return result
