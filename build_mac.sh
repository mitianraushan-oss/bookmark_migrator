#!/bin/bash
# Build a standalone macOS .app for Bookmark Migrator.
# Run this ON A MAC (PyInstaller cannot cross-compile from Windows/Linux to macOS).
set -e

python3 -m venv .venv-mac
source .venv-mac/bin/activate
pip install --upgrade pip pyinstaller

pyinstaller --noconfirm --windowed --name "BookmarkMigrator" bookmark_migrator_new.py

echo ""
echo "Done. The app bundle is at dist/BookmarkMigrator.app"
echo "Double-click it to run, or right-click > Open the first time (Gatekeeper will warn since it's unsigned)."
