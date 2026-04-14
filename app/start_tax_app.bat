@echo off
REM T2 Tax Agent 데스크톱 런처 - 더블클릭 실행용
cd /d %~dp0..
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
python infrastructure\tax_app.py
if errorlevel 1 pause
