"""절세 전략 엔진

공제 체크리스트 12개 항목 기반으로 누락 공제 발굴 및 우선순위별 전략 제안.
"""

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


def _is_applicable(item, user_data):
    """user_data 기반으로 해당 공제 항목 적용 여부 판단."""
    income = user_data.get("income", {}) if isinstance(user_data, dict) else {}
    flags = user_data.get("flags", {}) if isinstance(user_data, dict) else {}
    name = item["name"]

    if name == "노란우산공제":
        return int(income.get("사업소득", 0) or 0) > 0
    if name == "월세세액공제":
        return bool(flags.get("월세지출", False))
    if name == "중소기업취업자감면":
        return bool(flags.get("중소기업취업", False))
    if name == "부양가족인적공제":
        return int(flags.get("부양가족수", 0) or 0) > 0
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


def check_missing_deductions(user_data):
    """누락 가능 공제 항목 목록 반환."""
    deductions = user_data.get("deductions", {}) if isinstance(user_data, dict) else {}
    missing = []
    for item in CHECKLIST:
        if not _is_applicable(item, user_data):
            continue
        if deductions.get(item["name"]) is True:
            continue
        missing.append(item)
    return missing


def generate_strategy(user_data, tax_result):
    """우선순위별 절세 전략 목록 반환 (예상절세액 내림차순)."""
    missing = check_missing_deductions(user_data)
    strategies = [
        {
            "항목": item["name"],
            "예상절세액": item["expected_saving"],
            "조건": item["condition"],
            "법령조항": item["legal_ref"],
        }
        for item in missing
    ]
    strategies.sort(key=lambda x: x["예상절세액"], reverse=True)
    return strategies
