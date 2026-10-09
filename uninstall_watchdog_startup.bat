@echo off
rem Снимает автозапуск сторожа. Уже запущенный процесс завершите в Диспетчере задач (pythonw.exe).
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\DZ_Atlas_Watchdog.vbs" 2>nul
echo Автозапуск снят.
pause
