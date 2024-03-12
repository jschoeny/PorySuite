@echo off
setlocal enabledelayedexpansion

REM Activate the virtual environment
call .\venv\Scripts\activate.bat

REM Loop through all .ui files in ui directory
for %%i in (ui\*.ui) do (
    REM Extract the filename without extension
    set "filename=%%~ni"
    
    REM Define the corresponding .py filename
    set "pyfile=ui\ui_!filename!.py"
    
    REM Check if .ui file is newer than the corresponding .py file
    if not exist "!pyfile!" (
        set "isNewer=1"
    ) else (
        REM We use the /D switch to compare the dates
        xcopy /D /L "%%i" "!pyfile!" >nul 2>&1
        if errorlevel 1 set "isNewer=1" else set "isNewer=0"
    )
    
    REM If .ui file is newer, call pyside6-uic and generate .py file
    if !isNewer! equ 1 (
        pyside6-uic "%%i" -o "!pyfile!"
        echo Generated !pyfile!
    )
)

endlocal
