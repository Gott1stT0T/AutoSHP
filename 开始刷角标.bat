@echo off
chcp 65001 >nul
cd /d "%~dp0"
title GarrisonFarm PC - 明日方舟 PC 端刷角标

net session >nul 2>&1
if not errorlevel 1 goto admin_ok

echo 正在请求管理员权限，请在弹出的“用户账户控制”窗口点“是”...
set "GFPC_SELF=%~f0"
powershell -NoProfile -Command "Start-Process -FilePath $env:GFPC_SELF -Verb RunAs"
if errorlevel 1 goto elevate_failed
exit /b 0

:elevate_failed
echo.
echo 提权没有成功：请右键本文件，选择“以管理员身份运行”。
echo.
pause
exit /b 1

:admin_ok
set "EXE="
if exist "GarrisonFarmPC.exe" set "EXE=%CD%\GarrisonFarmPC.exe"
if defined EXE goto run_exe
for %%F in ("*.exe") do set "EXE=%%~fF"
if defined EXE goto run_exe
goto run_py

:run_exe
echo 正在启动 %EXE% ...
"%EXE%" --menu --show-doc 使用说明.txt
echo.
echo 程序已退出。
pause
exit /b 0

:run_py
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto no_python
%PY% launcher.py --menu --show-doc 使用说明.txt
pause
exit /b 0

:no_python
echo 没有找到 GarrisonFarmPC.exe（或同目录下的 exe），也没有找到 Python。
echo 请把本文件放在 GarrisonFarmPC.exe 同一目录，或先运行 setup.bat。
pause
exit /b 1