@echo off
title Texto para Libras
cd /d "%~dp0"

python app.py

if errorlevel 1 (
    echo.
    echo [ERRO] O app encerrou com erro. Leia a mensagem acima.
    pause
)
