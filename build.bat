@echo off
setlocal
cd /d "%~dp0"

echo Installing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo Building PDFMerger.exe...
python -m PyInstaller --noconfirm --clean --windowed --name PDFMerger ^
  --collect-all customtkinter ^
  --collect-all pymupdf ^
  --hidden-import windnd ^
  main.py
if errorlevel 1 exit /b 1

echo.
echo Done. Run: dist\PDFMerger\PDFMerger.exe
endlocal
