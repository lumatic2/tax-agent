# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Tax Agent (onefile).

빌드: uv run pyinstaller packaging/tax_agent.spec --clean --noconfirm
산출: dist/TaxAgent.exe
"""

from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent  # tax-agent/
APP = ROOT / 'app'
AGENT = ROOT / 'agent'
SE = ROOT / 'strategy_engine'

# Streamlit 전체 수집
st_datas, st_binaries, st_hiddenimports = collect_all('streamlit')

hidden = [
    *st_hiddenimports,
    *collect_submodules('langchain_core'),
    *collect_submodules('langchain_ollama'),
    *collect_submodules('langgraph'),
    *collect_submodules('strategy_engine'),
    *collect_submodules('agent'),
    'pywebview',
    'httpx',
    'dotenv',
    'yaml',
    'tax_calculator',
    'corporate_tax_calculator',
    'inheritance_gift_calculator',
]

datas = [
    *st_datas,
    # 루트 계산 모듈
    (str(ROOT / 'tax_calculator.py'), '.'),
    (str(ROOT / 'corporate_tax_calculator.py'), '.'),
    (str(ROOT / 'inheritance_gift_calculator.py'), '.'),
    # strategy_engine 패키지 (Python 모듈 + YAML rules)
    (str(SE), 'strategy_engine'),
    # agent 패키지 전체
    (str(AGENT), 'agent'),
    # Streamlit 대시보드 (subprocess로 실행)
    (str(APP / 'tax_dashboard.py'), 'app'),
    # 아이콘
    (str(ROOT / 'assets' / 'icon.ico'), 'assets'),
]

# 법령 코퍼스 캐시 (있으면 번들)
corpus_cache = ROOT / 'data' / 'tax_law_corpus.json'
if corpus_cache.exists():
    datas.append((str(corpus_cache), 'data'))

a = Analysis(
    [str(APP / 'tax_app.py')],
    pathex=[str(ROOT)],
    binaries=st_binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'scipy', 'sklearn', 'torch', 'tensorflow',
        'IPython', 'notebook', 'jupyterlab',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TaxAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / 'assets' / 'icon.ico') if (ROOT / 'assets' / 'icon.ico').exists() else None,
)
