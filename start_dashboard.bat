@echo off
chcp 65001 >nul
title Streamlit Dashboard
cd /d %~dp0
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
py -m streamlit run app/dashboard/streamlit_app.py --server.port 8501
pause
