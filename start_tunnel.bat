@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   DocClaw 公网临时演示隧道
echo ============================================================
echo.
echo 请先确保 DocClaw 已启动 (start.bat)，前端 :5173 可访问。
echo 关闭本窗口即停止公网访问。
echo.

set "TOOLS=%~dp0tools"
set "CF=%TOOLS%\cloudflared.exe"
set "USE_LT=0"

if exist "%CF%" goto use_cloudflared
if exist "C:\Program Files (x86)\cloudflared\cloudflared.exe" (
  set "CF=C:\Program Files (x86)\cloudflared\cloudflared.exe"
  goto use_cloudflared
)
if exist "C:\Program Files\cloudflared\cloudflared.exe" (
  set "CF=C:\Program Files\cloudflared\cloudflared.exe"
  goto use_cloudflared
)
where cloudflared >nul 2>&1 && set "CF=cloudflared" && goto use_cloudflared

echo [提示] 未找到 cloudflared，将使用 localtunnel (npx)。
echo        首次访问 loca.lt 链接时可能需要输入隧道密码（见下方）。
echo.
set "USE_LT=1"
goto start_tunnel

:use_cloudflared
echo [方式] Cloudflare Quick Tunnel（推荐，无需密码页）
echo [目标] http://127.0.0.1:5173
echo.
echo 下方出现 https://xxxx.trycloudflare.com 即为演示链接。
echo.
"%CF%" tunnel --url http://127.0.0.1:5173
goto end

:start_tunnel
echo [方式] localtunnel
echo [目标] http://127.0.0.1:5173
echo.
for /f %%i in ('powershell -NoProfile -Command "(Invoke-WebRequest -Uri 'https://api.ipify.org' -UseBasicParsing -TimeoutSec 8).Content"') do set "PUBIP=%%i"
if defined PUBIP (
  echo 若出现密码页，请输入隧道密码: !PUBIP!
  echo 也可在浏览器打开 https://loca.lt/mytunnelpassword 查看密码。
  echo.
)
cd /d "%~dp0frontend"
call npx --yes localtunnel --port 5173

:end
endlocal
