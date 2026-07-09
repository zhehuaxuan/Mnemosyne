@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo ========================================
echo        Git Quick Commit Script
echo ========================================
echo.

echo Select commit type:
echo.
echo   1 - feat     - New feature
echo   2 - fix      - Bug fix
echo   3 - docs     - Documentation
echo   4 - style    - Code style
echo   5 - refactor - Refactoring
echo   6 - perf     - Performance
echo   7 - test     - Testing
echo   8 - chore    - Build/Tools
echo   9 - revert   - Revert
echo.

set /p type_num="Enter number (1-9): "

if "%type_num%"=="1" set "COMMIT_TYPE=feat"
if "%type_num%"=="2" set "COMMIT_TYPE=fix"
if "%type_num%"=="3" set "COMMIT_TYPE=docs"
if "%type_num%"=="4" set "COMMIT_TYPE=style"
if "%type_num%"=="5" set "COMMIT_TYPE=refactor"
if "%type_num%"=="6" set "COMMIT_TYPE=perf"
if "%type_num%"=="7" set "COMMIT_TYPE=test"
if "%type_num%"=="8" set "COMMIT_TYPE=chore"
if "%type_num%"=="9" set "COMMIT_TYPE=revert"

if not defined COMMIT_TYPE (
    echo Invalid selection!
    echo.
    echo Press any key to exit...
    pause >nul
    exit
)

for /f %%a in ('powershell -command "(Get-Date).ToString('yyyy-MM-dd')"') do set "DATE=%%a"

echo.
set /p message="Enter commit message: "

if not defined message (
    echo Commit message cannot be empty!
    echo.
    echo Press any key to exit...
    pause >nul
    exit
)

set "FULL_COMMIT=[%DATE%] %COMMIT_TYPE%: %message%"

echo.
echo Ready to commit: %FULL_COMMIT%
echo.
set /p confirm="Confirm? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo Cancelled.
    echo.
    echo Press any key to exit...
    pause >nul
    exit
)

echo.
echo Staging...
git add .

echo Committing...
git commit -m "%FULL_COMMIT%"
if errorlevel 1 (
    echo Commit failed!
    echo.
    echo Press any key to exit...
    pause >nul
    exit
)

set /a MAX_RETRIES=3
set /a retry_count=0

echo Pushing...
:push_retry
git push
if errorlevel 1 (
    set /a retry_count+=1
    if !retry_count! lss %MAX_RETRIES% (
        echo Push failed, retrying (!retry_count!/!MAX_RETRIES!)...
        echo Pulling latest changes first...
        git pull --rebase
        goto push_retry
    ) else (
        echo Push failed after %MAX_RETRIES% retries!
        echo.
        echo Press any key to exit...
        pause >nul
        exit
    )
)

echo.
echo Done: %FULL_COMMIT%
pause
