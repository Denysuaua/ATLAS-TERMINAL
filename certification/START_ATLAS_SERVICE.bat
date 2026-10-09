@echo off
rem Служба оптимизатора «Атласа». Окно не закрывайте, пока идут расчёты.
cd /d "%~dp0"
python DZ_ATLAS_Service.py --port 8090
pause
