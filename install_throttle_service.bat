
@echo off
REM Change to the directory where this script is located
cd /d "%~dp0"
REM Install ThrottleService, DownloadMonitor, and Supervisor as Windows services using nssm
REM Prerequisites: nssm.exe must be in the same directory or in PATH

REM Ensure nssm is available
where nssm >nul 2>nul
if errorlevel 1 (
    echo ERROR: nssm.exe not found in PATH or current directory.
    echo Please download from https://nssm.cc/download and place nssm.exe in this folder or in your PATH.
    exit /b 1
)

REM Ensure Python is available
where pythonw >nul 2>nul
if errorlevel 1 (
    echo ERROR: pythonw.exe not found in PATH.
    exit /b 1
)
set PYTHON_EXE=pythonw.exe



REM Generate a secure IPC key and store in .env if not present
if not exist .env (
    powershell -Command "$k=[guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N'); Set-Content -Path .env -Value \"THROTTLE_IPC_TOKEN=$k\""
    echo Generated secure IPC key in .env
)

REM Load the IPC token from .env
for /f "tokens=2 delims==" %%A in ('findstr THROTTLE_IPC_TOKEN .env') do set THROTTLE_IPC_TOKEN=%%A
if "%THROTTLE_IPC_TOKEN%"=="" (
    echo ERROR: Could not load THROTTLE_IPC_TOKEN from .env
    exit /b 1
)

REM Install Python dependencies
if exist requirements.txt (
    echo Installing Python dependencies...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
)


REM --- Install or Update ThrottleService ---
set SERVICE_NAME=ThrottleService
set SCRIPT_PATH=%~dp0throttle_service.py
nssm status %SERVICE_NAME% >nul 2>nul
if %errorlevel%==3 (
    echo Installing %SERVICE_NAME%...
    nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%SCRIPT_PATH%"
) else (
    echo Updating %SERVICE_NAME%...
    nssm set %SERVICE_NAME% Application "%PYTHON_EXE%"
    nssm set %SERVICE_NAME% AppParameters "%SCRIPT_PATH%"
)
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm set %SERVICE_NAME% ObjectName LocalSystem
nssm set %SERVICE_NAME% AppEnvironmentExtra THROTTLE_IPC_TOKEN=%THROTTLE_IPC_TOKEN%

REM --- Install or Update DownloadMonitor ---
set SERVICE_NAME=DownloadMonitor
set SCRIPT_PATH=%~dp0download_monitor.py
nssm status %SERVICE_NAME% >nul 2>nul
if %errorlevel%==3 (
    echo Installing %SERVICE_NAME%...
    nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%SCRIPT_PATH%"
) else (
    echo Updating %SERVICE_NAME%...
    nssm set %SERVICE_NAME% Application "%PYTHON_EXE%"
    nssm set %SERVICE_NAME% AppParameters "%SCRIPT_PATH%"
)
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm set %SERVICE_NAME% ObjectName LocalSystem
nssm set %SERVICE_NAME% AppEnvironmentExtra THROTTLE_IPC_TOKEN=%THROTTLE_IPC_TOKEN%

REM --- Install or Update ThrottleSupervisor ---
set SERVICE_NAME=ThrottleSupervisor
set SCRIPT_PATH=%~dp0supervisor.py
nssm status %SERVICE_NAME% >nul 2>nul
if %errorlevel%==3 (
    echo Installing %SERVICE_NAME%...
    nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%SCRIPT_PATH%"
) else (
    echo Updating %SERVICE_NAME%...
    nssm set %SERVICE_NAME% Application "%PYTHON_EXE%"
    nssm set %SERVICE_NAME% AppParameters "%SCRIPT_PATH%"
)
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm set %SERVICE_NAME% ObjectName LocalSystem
nssm set %SERVICE_NAME% AppEnvironmentExtra THROTTLE_IPC_TOKEN=%THROTTLE_IPC_TOKEN%

REM --- Install or Update DownloadManager ---
set SERVICE_NAME=DownloadManager
set SCRIPT_PATH=%~dp0download_manager.py
nssm status %SERVICE_NAME% >nul 2>nul
if %errorlevel%==3 (
    echo Installing %SERVICE_NAME%...
    nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%SCRIPT_PATH%"
) else (
    echo Updating %SERVICE_NAME%...
    nssm set %SERVICE_NAME% Application "%PYTHON_EXE%"
    nssm set %SERVICE_NAME% AppParameters "%SCRIPT_PATH%"
)
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm set %SERVICE_NAME% ObjectName LocalSystem
nssm set %SERVICE_NAME% AppEnvironmentExtra THROTTLE_IPC_TOKEN=%THROTTLE_IPC_TOKEN%

REM --- Install or Update Watchdog ---
set SERVICE_NAME=Watchdog
set SCRIPT_PATH=%~dp0watchdog.py
nssm status %SERVICE_NAME% >nul 2>nul
if %errorlevel%==3 (
    echo Installing %SERVICE_NAME%...
    nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%SCRIPT_PATH%"
) else (
    echo Updating %SERVICE_NAME%...
    nssm set %SERVICE_NAME% Application "%PYTHON_EXE%"
    nssm set %SERVICE_NAME% AppParameters "%SCRIPT_PATH%"
)
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm set %SERVICE_NAME% ObjectName LocalSystem
nssm set %SERVICE_NAME% AppEnvironmentExtra THROTTLE_IPC_TOKEN=%THROTTLE_IPC_TOKEN%


REM Create desktop shortcut for GUI as 'Conductor'
set GUI_SCRIPT=%~dp0gui.py
set SHORTCUT_NAME=Conductor.lnk
set DESKTOP=%USERPROFILE%\Desktop
set ICON_PATH=%~dp0icon.ico
if exist "%DESKTOP%" (
    echo Creating desktop shortcut for GUI as 'Conductor' with icon.ico...
    powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%DESKTOP%\\%SHORTCUT_NAME%');$s.TargetPath='%PYTHON_EXE%';$s.Arguments='\"%GUI_SCRIPT%\"';$s.WorkingDirectory='%~dp0';$s.IconLocation='%ICON_PATH%';$s.Save()"
    echo Shortcut created on desktop as 'Conductor'.
)

echo All core services installed as SYSTEM. You can start them from Services or with:
echo    nssm start ThrottleService
echo    nssm start DownloadMonitor
echo    nssm start ThrottleSupervisor
echo    nssm start DownloadManager
echo    nssm start Watchdog
