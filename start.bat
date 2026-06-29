@echo off
REM ---- MOX Collective World Cup Bracket launcher (local, SQLite) ----
cd /d "%~dp0"
REM Uncomment and edit to enable live result sync / custom admin password:
REM set ADMIN_PASSWORD=moxcollective
REM set FOOTBALL_DATA_API_KEY=your_key_here
echo Starting MOX World Cup Bracket on http://localhost:8000 ...
start "" http://localhost:8000
python api\index.py
pause
