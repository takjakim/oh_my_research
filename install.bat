@echo off
REM ============================================================
REM  oh-my-research — install.bat
REM  Windows 얇은 심 파일: PowerShell을 통해 install.ps1을 실행합니다.
REM  실행 정책 오류가 발생하면 이 파일을 오른쪽 클릭하여
REM  "관리자 권한으로 실행"을 선택하세요.
REM ============================================================

echo oh-my-research 설치 프로그램 (Windows)
echo PowerShell 설치 프로그램을 시작합니다...
echo.

REM Try pwsh (PowerShell 7+) first, then fall back to powershell (5.x)
where pwsh >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    pwsh -ExecutionPolicy Bypass -NoLogo -File "%~dp0install.ps1" %*
) else (
    powershell -ExecutionPolicy Bypass -NoLogo -File "%~dp0install.ps1" %*
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [omr 오류] 설치에 실패했습니다. 위의 메시지를 확인하세요.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo 설치가 완료되었습니다. 아무 키나 눌러 이 창을 닫으세요.
pause >nul
