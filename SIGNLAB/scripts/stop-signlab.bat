@echo off
title Parar SIGNLAB Server
echo Parando servidor SIGNLAB...
netstat -ano | findstr :8100 > nul
if %errorlevel% == 0 (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8100') do taskkill /pid %%a /f
    echo Servidor parado!
) else (
    echo Servidor nao esta rodando.
)
pause
