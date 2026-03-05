@echo off
chcp 65001 > nul
title SmartDiag Launcher

:: Check env
if not exist "%~dp0backend\.venv\Scripts\activate.bat" (
    echo [ERROR] venv not found! Run init_env.bat first!
    pause
    exit /b 1
)

echo ================================================
echo    SmartDiag Medical AI System  --  Starting...
echo ================================================
echo [1/2] Launching Backend  (FastAPI + Uvicorn) ...
echo [2/2] Launching Frontend (Vue3  + Vite) ...

start "SmartDiag Backend" cmd /k "cd /d "%~dp0backend" && call .venv\Scripts\activate.bat && uvicorn main:app --reload --host 0.0.0.0 --port 28080"

start "SmartDiag Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ================================================
echo   Backend : http://localhost:28080
echo   Frontend: http://localhost:5173
echo ================================================
pause
