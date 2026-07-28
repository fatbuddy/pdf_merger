@echo off
setlocal
cd /d "%~dp0"

echo Installing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo Building PDFMerger.exe...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name PDFMerger ^
  --collect-all customtkinter ^
  --collect-all pymupdf ^
  --collect-all tkinterdnd2 ^
  main.py
if errorlevel 1 exit /b 1

echo.
echo Done. Run: dist\PDFMerger.exe
endlocal
