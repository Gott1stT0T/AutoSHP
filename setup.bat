@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在创建虚拟环境 .venv ...
python -m venv .venv || goto :err
.venv\Scripts\python.exe -m pip install -U pip
.venv\Scripts\python.exe -m pip install -r requirements.txt || goto :err
echo.
echo 安装完成。运行 开始刷角标.bat 或 .venv\Scripts\python.exe launcher.py --check 自检。
pause
exit /b 0

:err
echo.
echo 安装失败：请确认已安装 Python 3.10+ 并加入 PATH。
pause
exit /b 1
