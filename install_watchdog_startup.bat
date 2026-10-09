@echo off
rem Автозапуск сторожа Атласа при входе в Windows, без окна. Прав администратора не требует.
set "SCRIPT=%~dp0DZ_WATCHDOG_Backup.py"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
where pythonw >nul 2>nul || (echo Не найден pythonw. Установите Python и добавьте его в PATH. & pause & exit /b 1)
> "%STARTUP%\DZ_Atlas_Watchdog.vbs" echo CreateObject("WScript.Shell").Run "pythonw ""%SCRIPT%""", 0, False
echo Автозапуск установлен: "%STARTUP%\DZ_Atlas_Watchdog.vbs"
start "" pythonw "%SCRIPT%"
echo Сторож запущен в фоне.
pause
