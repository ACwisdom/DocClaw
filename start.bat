@echo off
echo Starting DocClaw Backend (Medical API :8000)...
start "DocClaw Backend" cmd /k "cd /d %~dp0backend && pip install -r requirements.txt && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak > nul
echo Starting DocClaw Harness (MCP :8001 + Agent API :8090)...
start "DocClaw Harness" cmd /k "cd /d %~dp0backend && py -3.11 -m pip install -r requirements-agent.txt && py -3.11 start_agent.py"
timeout /t 3 /nobreak > nul
echo Starting DocClaw Frontend...
start "DocClaw Frontend" cmd /k "cd /d %~dp0frontend && npm install && npm run dev"
echo.
echo DocClaw is starting...
echo Frontend (本机):   http://localhost:5173
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /i "IPv4"') do set LAN_IP=%%i
set LAN_IP=%LAN_IP: =%
if defined LAN_IP echo Frontend (局域网): http://%LAN_IP%:5173
echo Medical API: http://localhost:8000/docs
echo Agent API:   http://localhost:8090/docs
echo MCP Server:  http://127.0.0.1:8001/mcp
echo.
echo 同一 WiFi 下的手机/平板请用「局域网」地址访问；若无法打开请在 Windows 防火墙中允许端口 5173。
