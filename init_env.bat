@echo off
chcp 65001 > nul
title SmartDiag -- Environment Init

echo ================================================
echo   SmartDiag Init  --  Step 1/5: Create venv
echo ================================================
cd /d "%~dp0backend"

echo [1/5] Creating virtual environment ...
:: 弃用写死的绝对路径，直接调用系统环境变量里的 python
python -m venv .venv
if errorlevel 1 (
    echo [ERROR] 无法创建虚拟环境！请检查是否已正确安装 Python。
    pause
    exit /b 1
)

echo [2/5] Activating .venv ...
call .venv\Scripts\activate.bat

echo [3/5] Installing requirements.txt ...
pip install -r requirements.txt

echo [4/5] Installing python-docx and pandas ...
pip install python-docx pandas

echo [5/5] Running data_parser.py ...
python data_parser.py

echo ================================================
echo   环境初始化与数据清洗全部完成！
echo   请关闭此窗口，双击 start_game.bat 启动系统。
echo ================================================
pause