@echo off
echo DocClaw Phase 5 Acceptance
echo.
cd /d %~dp0backend
py -3.11 scripts/e2e_acceptance.py %*
exit /b %ERRORLEVEL%
