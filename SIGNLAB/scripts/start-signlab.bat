@echo off
title SIGNLAB Server
cd /d "%~dp0\.."
python -m uvicorn app.backend.main:app --port 8100 --reload
pause
