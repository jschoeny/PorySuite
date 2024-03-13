@echo off
setlocal enabledelayedexpansion

REM Activate the virtual environment
call .\venv\Scripts\activate.bat

REM Loop through all .qrc files in res directory
for %%i in (res\*.qrc) do (
    REM Extract the filename without extension
    set "filename=%%~ni"
    
    REM Define the corresponding .py filename
    set "pyfile=res\!filename!_rc.py"
    
    REM Check if .qrc file is newer than the corresponding .py file
    if not exist "!pyfile!" (
        set "isNewer=1"
    ) else (
        REM We use the /D switch to compare the dates
        xcopy /D /L "%%i" "!pyfile!" >nul 2>&1
        if errorlevel 1 set "isNewer=1" else set "isNewer=0"
    )
    
    REM If .qrc file is newer, call pyside6-rcc and generate .py file
    if !isNewer! equ 1 (
        pyside6-rcc "%%i" -o "!pyfile!"
        echo Generated !pyfile!
    )
)

endlocal
