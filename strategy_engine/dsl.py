"""조건식 DSL 평가기.

규칙 YAML의 `applies_when` 섹션을 JSON 구조 트리로 받아
(결과, 트레이스) 를 반환한다. 트레이스는 노드별 평가값을 보존하여
"왜 이 규칙이 적용/비적용 되었는가"를 설명할 수 있게 한다.

지원 연산자:
- 논리: and / or / not  (children: `of: [...]`)
- 비교: ==, !=, <, <=, >, >=
- 포함: in  (right: list)
- 존재: exists  (left: 경로)
"""

from __future__ import annotations

from typing import Any


class DSLError(Exception):
    pass


def _resolve(path: Any, profile: dict) -> Any:
    """문자열 경로(`profile.a.b`) 또는 리터럴을 해석."""
    if not isinstance(path, str):
        return path
    if not path.startswith("profile."):
        return path
    parts = path.split(".")[1:]
    cur: Any = profile
    for key in parts:
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
    return cur


def _exists(path: Any, profile: dict) -> bool:
    if not isinstance(path, str) or not path.startswith("profile."):
        return False
    parts = path.split(".")[1:]
    cur: Any = profile
    for key in parts:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return False
    return True


_CMP = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a is not None and a < b,
    "<=": lambda a, b: a is not None and a <= b,
    ">": lambda a, b: a is not None and a > b,
    ">=": lambda a, b: a is not None and a >= b,
}


def evaluate(node: dict | None, profile: dict) -> tuple[bool, dict]:
    """조건식 트리를 평가하여 (결과, 트레이스) 반환."""
    if node is None:
        return True, {"op": "true", "result": True}

    if not isinstance(node, dict) or "op" not in node:
        raise DSLError(f"invalid node: {node!r}")

    op = node["op"]

    if op in ("and", "or"):
        children = node.get("of") or []
        traces = []
        values = []
        for child in children:
            r, t = evaluate(child, profile)
            traces.append(t)
            values.append(r)
        result = all(values) if op == "and" else any(values)
        return result, {"op": op, "of": traces, "result": result}

    if op == "not":
        child = node.get("of")
        if isinstance(child, list):
            child = child[0] if child else None
        r, t = evaluate(child, profile)
        return (not r), {"op": "not", "of": [t], "result": not r}

    if op == "exists":
        left = node.get("left")
        r = _exists(left, profile)
        return r, {"op": "exists", "left": left, "result": r}

    if op == "in":
        left = node.get("left")
        right = node.get("right")
        lv = _resolve(left, profile)
        r = lv in right if isinstance(right, (list, tuple)) else False
        return r, {"op": "in", "left": left, "left_value": lv, "right": right, "result": r}

    if op in _CMP:
        left = node.get("left")
        right = node.get("right")
        lv = _resolve(left, profile)
        rv = _resolve(right, profile) if isinstance(right, str) and right.startswith("profile.") else right
        try:
            r = _CMP[op](lv, rv)
        except TypeError:
            r = False
        return r, {
            "op": op,
            "left": left,
            "left_value": lv,
            "right": right,
            "right_value": rv,
            "result": r,
        }

    raise DSLError(f"unknown op: {op!r}")
