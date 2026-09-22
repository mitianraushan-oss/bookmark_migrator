@echo off
REM Build a standalone Windows .exe for Bookmark Migrator.
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip pyinstaller

pyinstaller --noconfirm --onefile --windowed --name BookmarkMigrator bookmark_migrator_new.py

echo.
echo Done. The exe is at dist\BookmarkMigrator.exe
