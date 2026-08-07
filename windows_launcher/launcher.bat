@echo off
rem ============================================================
rem  O2 系统总控台 —— 双击本文件即可（非 IT 操作者入口）
rem  1) 检查 Python
rem  2) 最小化窗口启动控制服务
rem  3) 等服务把地址写到 last_url.txt，再打开浏览器
rem ============================================================
cd /d "%~dp0"

rem --- 1) Python 必须在 PATH 上 ---
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 Python。
    echo        请先安装 Python 3，安装时勾选 "Add Python to PATH"。
    echo        装好后重新双击本文件。
    pause
    exit /b 1
)

rem --- 2) 启动控制服务（最小化窗口，日志留在那里） ---
start /min "" python launcher_server.py

rem --- 3) 等服务把地址写进 last_url.txt，再开浏览器 ---
set /a tries=0
:wait_url
if exist last_url.txt goto open
set /a tries+=1
if %tries% gtr 30 (
    echo [错误] 控制服务启动超时，请检查最小化窗口里的日志。
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_url

:open
set /p URL=<last_url.txt
if not defined URL (
    echo [错误] 无法读取服务地址。
    pause
    exit /b 1
)
start "" "%URL%"
exit /b 0
