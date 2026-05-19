@echo off
chcp 65001 >nul
title FastAPI Server
cd /d %~dp0
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
py -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pause
