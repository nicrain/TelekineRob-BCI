@echo off
rem ============================================================
rem  O2 系统总控台 —— 双击本文件即可（非 IT 操作者入口）
rem  1) 检查 Python
rem  2) 幂等替换：上次服务还活着 → 强杀（pidfile + 命令行校验）
rem  3) 无窗口启动（pythonw；无 pythonw 回退最小化窗口）
rem  4) 等服务把地址写到 last_url.txt，再打开浏览器
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

rem --- 2) 幂等替换：pidfile 里的旧服务还活着 → 强杀，保证单实例 + 最新代码 ---
rem     （taskkill /F 不会清 pidfile，下一轮启动覆盖，无害）
set "PID="
if exist launcher_server.pid set /p PID=<launcher_server.pid
if defined PID (
    rem 存活校验：tasklist 该 PID 且镜像名含 python（PID 已失效则跳过）
    set "ALIVE="
    for /f "delims=" %%a in ('tasklist /FI "PID eq %PID%" 2^>nul ^| findstr /I "python"') do set ALIVE=1
    if defined ALIVE (
        rem 命令行校验：必须含 launcher_server.py，防 PID 复用误杀别的进程
        for /f "delims=" %%c in ('wmic process where "processid=%PID%" get commandline /value 2^>nul ^| findstr /C:"launcher_server.py"') do (
            taskkill /F /PID %PID% >nul 2>&1
        )
    )
)

rem --- 3) 清掉上次残留地址，再启动控制服务 ---
rem     （pythonw 无窗口；无 pythonw 时回退最小化窗口保留调试能力。
rem      日志由服务自己写到 launcher_server.log，排查时让用户贴该文件）
del last_url.txt 2>nul
where pythonw >nul 2>nul
if errorlevel 1 (
    start /min "" cmd /c "python launcher_server.py"
) else (
    start "" pythonw launcher_server.py
)

rem --- 4) 等服务把地址写进 last_url.txt，再开浏览器 ---
set /a tries=0
:wait_url
if exist last_url.txt goto open
set /a tries+=1
if %tries% gtr 30 (
    echo [错误] 控制服务启动超时，请检查 launcher_server.log 或最小化窗口。
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
