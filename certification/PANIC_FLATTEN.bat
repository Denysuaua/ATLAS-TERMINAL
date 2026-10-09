@echo off
rem Аварийная кнопка «Атласа»: закрыть все позиции во всех счетах NinjaTrader.
rem Попросит набрать FLATTEN. Ярлык на рабочий стол — для быстрого доступа.
python "%~dp0DZ_KILL_Switch.py" flatten
pause
