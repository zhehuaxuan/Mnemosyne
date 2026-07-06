@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo        Git Quick Commit Script
echo ========================================
echo.

echo Select commit type:
echo.
echo   [1] feat     - New feature
echo   [2] fix      - Bug fix
echo   [3] docs     - Documentation
echo   [4] style    - Code style
echo   [5] refactor - Refactoring
echo   [6] perf     - Performance
echo   [7] test     - Testing
echo   [8] chore    - Build/Tools
echo   [9] revert   - Revert
echo.

set /p type_num="Enter number (1-9): "

set "COMMIT_TYPE="
if "%type_num%"=="1" set "COMMIT_TYPE=feat"
if "%type_num%"=="2" set "COMMIT_TYPE=fix"
if "%type_num%"=="3" set "COMMIT_TYPE=docs"
if "%type_num%"=="4" set "COMMIT_TYPE=style"
if "%type_num%"=="5" set "COMMIT_TYPE=refactor"
if "%type_num%"=="6" set "COMMIT_TYPE=perf"
if "%type_num%"=="7" set "COMMIT_TYPE=test"
if "%type_num%"=="8" set "COMMIT_TYPE=chore"
if "%type_num%"=="9" set "COMMIT_TYPE=revert"

if "%COMMIT_TYPE%"=="" (
    echo Invalid selection!
    pause
    exit /b 1
)

for /f "tokens=2 delims==." %%a in ('wmic os get localdatetime /value') do (
    set "dt=%%a"
)
set "DATE=%dt:~0,4%-%dt:~4,2%-%dt:~6,2%"

echo.
set /p message="Enter commit message: "

if "%message%"=="" (
    echo Commit message cannot be empty!
    pause
    exit /b 1
)

set "FULL_COMMIT=[%DATE%] %COMMIT_TYPE%: %message%"

echo.
echo ========================================
echo Ready to commit:
echo.
echo   %FULL_COMMIT%
echo.
echo ========================================
echo.

set /p confirm="Confirm commit? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo Cancelled.
    pause
    exit /b 0
)

echo Staging all changes...
git add .

echo Committing...
git commit -m "%FULL_COMMIT%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo Commit failed!
    pause
    exit /b 1
)

echo.
echo Pushing to remote...
git push

if %ERRORLEVEL% neq 0 (
    echo.
    echo Push failed! Maybe need to pull first.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Done!
echo ========================================
echo.
echo %FULL_COMMIT%
echo.

pause
