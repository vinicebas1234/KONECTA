@echo off
REM ============================================
REM KONECTA V3 - Parar Todos os Servidores
REM ============================================

echo.
echo ============================================
echo KONECTA V3 - PARANDO SERVIDORES
echo ============================================
echo.

REM Kill Python processes (Backend + Frontend)
echo [1/1] Matando processos Python...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq KONECTA*" 2>nul
taskkill /F /IM python.exe 2>nul

echo.
echo ============================================
echo TODOS OS SERVIDORES FORAM PARADOS
echo ============================================
echo.

pause
