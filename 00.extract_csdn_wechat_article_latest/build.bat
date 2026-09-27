@echo off
setlocal
cd /d "%~dp0"

echo [1/2] Installing dependencies...
python -m pip install -r requirements.txt || goto :error

echo [2/2] Building exe with PyInstaller...
python -m PyInstaller --noconfirm --clean --windowed --onefile ^
  --name Article2Markdown ^
  --hidden-import markdownify ^
  --hidden-import bs4 ^
  --hidden-import lxml ^
  main.py || goto :error

echo.
echo Build finished: dist\Article2Markdown.exe
pause
exit /b 0

:error
echo Build failed.
pause
exit /b 1
