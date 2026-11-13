@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3.12 is required. Install it from python.org first.
  pause
  exit /b 1
)

py -3.12 -m venv .venv-win-build
if errorlevel 1 exit /b 1
call .venv-win-build\Scripts\activate.bat

python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1

if not exist dist\win mkdir dist\win
python -m PyInstaller --noconfirm --clean --distpath dist\win --workpath build\windows AI语音提词器-windows.spec
if errorlevel 1 exit /b 1

powershell -NoProfile -Command "Compress-Archive -Path 'dist\win\汪同学的AI语音提词器' -DestinationPath 'dist\win\汪同学的AI语音提词器-Windows便携版.zip' -Force"
echo.
echo Build complete: dist\win\汪同学的AI语音提词器\汪同学的AI语音提词器.exe
pause
