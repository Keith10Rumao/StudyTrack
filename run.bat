@echo off
REM Quick start for StudyTrack on Windows.
cd /d "%~dp0"
pip install -r requirements.txt
python app.py
pause
