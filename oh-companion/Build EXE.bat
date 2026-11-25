@echo off
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "OH-Companion" --icon oh_companion.ico --version-file version_info.txt ^
 --add-data "oh_thai_db.json;." --add-data "oh_web.json;." --add-data "bo_data.json;." --add-data "hideic;hideic" ^
 --add-data "oh_companion.png;." --add-data "oh_companion.ico;." --add-data "thai_tooltip.png;." --add-data "build_overlay.png;." ^
 --add-data "vision_logo.png;." --add-data "vision.ico;." ^
 --paths . --collect-all rapidocr --collect-all omegaconf --collect-all antlr4 ^
 --hidden-import PIL._tkinter_finder --hidden-import pystray._win32 ^
 --hidden-import oc_ctx --hidden-import mod_vision --hidden-import mod_thai --hidden-import mod_build ^
 --hidden-import engine --hidden-import detect --hidden-import bo_read --hidden-import bo_match ^
 --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide6 --exclude-module matplotlib ^
 --exclude-module scipy --exclude-module pandas --exclude-module torch --exclude-module paddle ^
 "OH Companion.pyw"
pause
