@echo off
chcp 65001 >nul
title Stock Market Analyzer

cd /d %~dp0

echo ========================================
echo  Stock Market Analyzer
echo ========================================
echo.

echo [1/2] Starting FastAPI server...
start "FastAPI Server" %~dp0start_api.bat

timeout /t 3 /nobreak >nul

echo [2/2] Starting Streamlit dashboard...
start "Streamlit Dashboard" %~dp0start_dashboard.bat

echo.
echo ========================================
echo  FastAPI:    http://localhost:8000
echo  API Docs:   http://localhost:8000/docs
echo  Dashboard:  http://localhost:8501
echo ========================================
echo.
pause
