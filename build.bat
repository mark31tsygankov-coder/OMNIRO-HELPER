@echo off
chcp 65001 >nul
echo === OMNIRO HELPER: сборка EXE ===
python -m pip install -r requirements.txt || goto :err
python tools\init_security.py || goto :err
pyinstaller --noconfirm --clean --onefile --noconsole --name OMNIRO_HELPER --icon assets\icon.ico --add-data "assets;assets" --add-data "data;data" --add-data "security\pubkey.json;security" main.py || goto :err
echo Готово: dist\OMNIRO_HELPER.exe
pause
exit /b 0
:err
echo ОШИБКА сборки.
pause
exit /b 1
