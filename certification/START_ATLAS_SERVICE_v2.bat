@echo off
rem Atlas service v2: queue, results, gates, presets, account, emergency OIF.
rem Keep this window open while tasks run. Stop: Ctrl+C (the running task is marked interrupted).
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
python DZ_ATLAS_Service_v2.py %*
pause
