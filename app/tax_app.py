"""T2 — Tax Agent 데스크톱 런처.

Streamlit을 백그라운드 프로세스로 기동하고 pywebview 창에 붙여
'윈도우 앱' 형태로 실행한다. 창을 닫으면 Streamlit 프로세스도 함께 종료.

PyInstaller onefile 모드:
    TaxAgent.exe              → pywebview GUI (메인)
    TaxAgent.exe --streamlit  → Streamlit 서버 (자식 프로세스)

Usage:
    python infrastructure/tax_app.py
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

# frozen GUI(console=False): stdout/stderr가 None이거나 cp949
if getattr(sys, 'frozen', False):
    for _stream_name in ('stdout', 'stderr'):
        _stream = getattr(sys, _stream_name, None)
        if _stream is None:
            setattr(sys, _stream_name, open(os.devnull, 'w', encoding='utf-8'))
        elif hasattr(_stream, 'reconfigure'):
            try:
                _stream.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass


def _base_dir() -> Path:
    """PyInstaller onefile: _MEIPASS 임시폴더. 일반 실행: 프로젝트 루트."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parents[1]


ROOT = _base_dir()
DASHBOARD = ROOT / 'app' / 'tax_dashboard.py'
ICON = ROOT / 'assets' / 'icon.ico'
PORT = 8502
HOST = '127.0.0.1'
URL = f'http://{HOST}:{PORT}'

OLLAMA_PORT = 11434
OLLAMA_CANDIDATES = [
    Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Ollama' / 'ollama.exe',
    Path('C:/Program Files/Ollama/ollama.exe'),
    Path('C:/Program Files (x86)/Ollama/ollama.exe'),
]


# ── Streamlit 자식 프로세스 모드 ────────────────────────────────────────────
def _run_streamlit() -> int:
    """frozen exe가 --streamlit 플래그로 재실행됐을 때 Streamlit 서버 기동."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from streamlit.web.cli import main_run
    # main_run은 Click Command — standalone_mode=False + 인자는 리스트 첫 번째로
    main_run(
        [
            str(DASHBOARD),
            '--server.port', str(PORT),
            '--server.address', HOST,
            '--server.headless', 'true',
            '--browser.gatherUsageStats', 'false',
            '--global.developmentMode', 'false',
        ],
        standalone_mode=False,
    )
    return 0


# ── 포트 유틸 ───────────────────────────────────────────────────────────────
def _port_open(host: str, port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def wait_for_port(timeout: float = 30.0, host: str = HOST, port: int = PORT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _port_open(host, port):
            return True
        time.sleep(0.3)
    return False


# ── Ollama 기동 ─────────────────────────────────────────────────────────────
def _find_ollama_exe() -> Path | None:
    """PATH 또는 표준 설치 경로에서 ollama.exe 탐색."""
    import shutil
    cli = shutil.which('ollama')
    if cli:
        return Path(cli)
    for p in OLLAMA_CANDIDATES:
        if p.exists():
            return p
    return None


def ensure_ollama() -> subprocess.Popen | None:
    """Ollama 서버가 미기동이면 백그라운드로 기동. 이미 떠 있으면 None."""
    if _port_open(HOST, OLLAMA_PORT):
        print(f'[tax_app] Ollama 이미 기동 중 (port {OLLAMA_PORT})')
        return None

    exe = _find_ollama_exe()
    if not exe:
        print(f'[tax_app] Ollama 실행 파일을 찾지 못함 — 수동 기동 필요', file=sys.stderr)
        return None

    print(f'[tax_app] Ollama 기동: {exe}')
    creationflags = 0
    if sys.platform == 'win32':
        creationflags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS

    proc = subprocess.Popen(
        [str(exe), 'serve'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
    )
    if not wait_for_port(timeout=20.0, port=OLLAMA_PORT):
        print(f'[tax_app] Ollama 기동 대기 초과 — 계속 진행 (대시보드에서 재시도 가능)',
              file=sys.stderr)
    return proc


# ── Streamlit 기동 ──────────────────────────────────────────────────────────
def launch_streamlit() -> subprocess.Popen:
    env = os.environ.copy()
    if getattr(sys, 'frozen', False):
        # frozen: exe 자신을 --streamlit 모드로 재실행
        cmd = [sys.executable, '--streamlit']
    else:
        cmd = [
            sys.executable, '-m', 'streamlit', 'run', str(DASHBOARD),
            '--server.port', str(PORT),
            '--server.address', HOST,
            '--server.headless', 'true',
            '--browser.gatherUsageStats', 'false',
            '--global.developmentMode', 'false',
        ]
    return subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ── 메인 (pywebview GUI) ───────────────────────────────────────────────────
def main() -> int:
    import webview

    ensure_ollama()

    if _port_open(HOST, PORT):
        print(f'[tax_app] 포트 {PORT} 이미 사용 중 -- 기존 Streamlit 재사용')
        proc = None
    else:
        print(f'[tax_app] Streamlit 기동: {DASHBOARD}')
        proc = launch_streamlit()
        if not wait_for_port(timeout=45.0):
            if proc:
                proc.terminate()
            print(f'[tax_app] Streamlit 기동 실패 -- {URL} 응답 없음', file=sys.stderr)
            return 2

    try:
        window = webview.create_window(
            title='Tax Agent',
            url=URL,
            width=1280,
            height=860,
            min_size=(1024, 720),
            confirm_close=False,
        )

        def _force_foreground():
            """Windows API로 창을 강제 포커스."""
            time.sleep(2.0)
            try:
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = user32.FindWindowW(None, 'Tax Agent')
                if hwnd:
                    SW_RESTORE = 9
                    user32.ShowWindow(hwnd, SW_RESTORE)
                    # Alt 키 시뮬레이션 — Windows의 포그라운드 제한 우회
                    user32.keybd_event(0x12, 0, 0, 0)  # Alt down
                    user32.keybd_event(0x12, 0, 2, 0)  # Alt up
                    user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

        import threading
        threading.Thread(target=_force_foreground, daemon=True).start()

        icon_arg = str(ICON) if ICON.exists() else None
        start_kwargs = {}
        if icon_arg:
            start_kwargs['icon'] = icon_arg
        webview.start(**start_kwargs)
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    return 0


if __name__ == '__main__':
    # --streamlit 플래그 → Streamlit 서버 모드
    if '--streamlit' in sys.argv:
        raise SystemExit(_run_streamlit())
    raise SystemExit(main())
