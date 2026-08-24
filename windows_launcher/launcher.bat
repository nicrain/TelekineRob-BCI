@echo off
rem ============================================================
rem  O2 System Control — double-click to launch (non-IT entry)
rem  1) Check Python
rem  2) Idempotent replacement: kill a still-alive old instance
rem     (pidfile + command-line check)
rem  3) Windowless start (pythonw; fall back to a minimized window)
rem  4) Wait for last_url.txt, then open the browser
rem ============================================================
cd /d "%~dp0"

rem --- 1) Python must be on PATH ---
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo         Install Python 3 and tick "Add Python to PATH" during setup.
    echo         Then double-click this file again.
    pause
    exit /b 1
)

rem --- 2) Idempotent: if the recorded PID is alive, force-kill it ---
rem     (taskkill /F does not remove the pidfile; the next run overwrites it)
set "PID="
if exist launcher_server.pid set /p PID=<launcher_server.pid
if defined PID (
    rem liveness: tasklist shows a python image for that PID (skip if dead)
    set "ALIVE="
    for /f "delims=" %%a in ('tasklist /FI "PID eq %PID%" 2^>nul ^| findstr /I "python"') do set ALIVE=1
    if defined ALIVE (
        rem command-line check: must mention launcher_server.py (PID-reuse guard)
        for /f "delims=" %%c in ('wmic process where "processid=%PID%" get commandline /value 2^>nul ^| findstr /C:"launcher_server.py"') do (
            taskkill /F /PID %PID% >nul 2>&1
        )
    )
)

rem --- 3) Clear any stale URL, then start the control service ---
rem     (pythonw = windowless; fall back to a minimized console for debugging.
rem      The service writes its own launcher_server.log — ask the user for it
rem      when troubleshooting.)
del last_url.txt 2>nul
where pythonw >nul 2>nul
if errorlevel 1 (
    start /min "" cmd /c "python launcher_server.py"
) else (
    start "" pythonw launcher_server.py
)

rem --- 4) Wait for the service to write last_url.txt, then open the browser ---
set /a tries=0
:wait_url
if exist last_url.txt goto open
set /a tries+=1
if %tries% gtr 30 (
    echo [ERROR] Control service startup timed out. Check launcher_server.log or the minimized window.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_url

:open
set /p URL=<last_url.txt
if not defined URL (
    echo [ERROR] Could not read the service address from last_url.txt.
    pause
    exit /b 1
)
start "" "%URL%"
exit /b 0
