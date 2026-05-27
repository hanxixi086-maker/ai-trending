@echo off
chcp 65001 >nul 2>&1
title AI 热点 & Vibe Coding 日报

:: ── 进入 web/ 目录（服务器必须从此处启动，否则数据路径错误）──────────────
cd /d "%~dp0web"

:: ── 端口选择：8000 被占就换 8001，再被占换 8080 ──────────────────────────
set PORT=8000
netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set PORT=8001
    netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set PORT=8080
    )
)

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║     AI 热点 ^& Vibe Coding 日报           ║
echo  ║                                          ║
echo  ║  地址: http://localhost:%PORT%              ║
echo  ║  关闭: 直接关掉本窗口即可                ║
echo  ╚══════════════════════════════════════════╝
echo.

:: ── 延迟 1 秒后打开浏览器，确保服务器先启动 ─────────────────────────────
ping 127.0.0.1 -n 2 >nul
start "" "http://localhost:%PORT%"

:: ── 启动服务器（阻塞，关窗口 = 停服务器）────────────────────────────────
python -m http.server %PORT%

pause
