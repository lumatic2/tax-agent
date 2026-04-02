"""QA runner for one-shot practical smoke tests.

변경 이유:
- `pyproject.toml`의 [project.scripts]는 쉘 명령 체인을 직접 등록할 수 없다.
- 따라서 `eval_scenarios.py` + `rehearsal_income_tax.py`를 한 번에 실행하는
  Python 엔트리포인트를 제공해 실사용 전 검증을 표준화한다.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _safe_write(text: str, is_err: bool = False) -> None:
    # 변경 이유:
    # - Windows cp949 콘솔에서 일부 유니코드 문자가 '?'로 깨져 로그 가독성이 떨어진다.
    # - 테스트 로그 의미를 유지하는 범위에서 ASCII 대체문자로 정규화한다.
    text = (
        text.replace("—", "-")
        .replace("✓ ", "")
        .replace("✓", "")
        .replace("→", "->")
    )
    stream = sys.stderr if is_err else sys.stdout
    encoding = stream.encoding or "utf-8"
    data = text.encode(encoding, errors="replace")
    target = sys.stderr.buffer if is_err else sys.stdout.buffer
    target.write(data)
    target.flush()


def _run(script_name: str) -> int:
    root = Path(__file__).resolve().parent
    script_path = root / script_name
    # 변경 이유:
    # - Windows 콘솔 코드페이지와 스크립트 UTF-8 출력이 충돌하면 한글이 깨질 수 있다.
    # - UTF-8로 캡처한 뒤 부모 프로세스에서 다시 출력해 표시 안정성을 높인다.
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        },
    )
    if completed.stdout:
        _safe_write(completed.stdout, is_err=False)
    if completed.stderr:
        _safe_write(completed.stderr, is_err=True)
    return int(completed.returncode or 0)


def smoke() -> None:
    """Run core regression + practical rehearsal tests in sequence."""
    codes = [
        _run("eval_scenarios.py"),
        _run("rehearsal_income_tax.py"),
    ]
    if any(code != 0 for code in codes):
        raise SystemExit(1)


if __name__ == "__main__":
    smoke()
