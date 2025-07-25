REM Check for admin rights
openfiles >nul 2>&1
if %errorlevel% NEQ 0 (
    echo ERROR: This script must be run as administrator.
    pause
    exit /b 1
)

REM --- Uninstall Mode ---
if /I "%1"=="uninstall" goto :uninstall


REM Set up error logging
set LOGFILE=%~dp0install_log.txt
echo Install started at %DATE% %TIME% > "%LOGFILE%"

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
if not %errorlevel%==3 (
    echo Stopping %SERVICE_NAME% for update...
    nssm stop %SERVICE_NAME% >> "%LOGFILE%" 2>&1
)

if %errorlevel%==3 (
    echo Installing %SERVICE_NAME%...
    nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%SCRIPT_PATH%" >> "%LOGFILE%" 2>&1
) else (
    echo Updating %SERVICE_NAME%...
    nssm set %SERVICE_NAME% Application "%PYTHON_EXE%" >> "%LOGFILE%" 2>&1
    nssm set %SERVICE_NAME% AppParameters "%SCRIPT_PATH%" >> "%LOGFILE%" 2>&1
)
REM Ensure service is set to auto start on boot
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START >> "%LOGFILE%" 2>&1
nssm set %SERVICE_NAME% ObjectName LocalSystem >> "%LOGFILE%" 2>&1
nssm set %SERVICE_NAME% AppEnvironmentExtra THROTTLE_IPC_TOKEN=%THROTTLE_IPC_TOKEN% >> "%LOGFILE%" 2>&1
echo Starting %SERVICE_NAME%...
nssm start %SERVICE_NAME% >> "%LOGFILE%" 2>&1

REM --- Install or Update DownloadMonitor ---
set SERVICE_NAME=DownloadMonitor
set SCRIPT_PATH=%~dp0download_monitor.py
nssm status %SERVICE_NAME% >nul 2>nul
if not %errorlevel%==3 (
    echo Stopping %SERVICE_NAME% for update...
    nssm stop %SERVICE_NAME% >> "%LOGFILE%" 2>&1
)
if %errorlevel%==3 (
    echo Installing %SERVICE_NAME%...
    nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%SCRIPT_PATH%" >> "%LOGFILE%" 2>&1
) else (
    echo Updating %SERVICE_NAME%...
    nssm set %SERVICE_NAME% Application "%PYTHON_EXE%" >> "%LOGFILE%" 2>&1
    nssm set %SERVICE_NAME% AppParameters "%SCRIPT_PATH%" >> "%LOGFILE%" 2>&1
)
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START >> "%LOGFILE%" 2>&1
nssm set %SERVICE_NAME% ObjectName LocalSystem >> "%LOGFILE%" 2>&1
nssm set %SERVICE_NAME% AppEnvironmentExtra THROTTLE_IPC_TOKEN=%THROTTLE_IPC_TOKEN% >> "%LOGFILE%" 2>&1
echo Starting %SERVICE_NAME%...
nssm start %SERVICE_NAME% >> "%LOGFILE%" 2>&1

REM --- Install or Update ThrottleSupervisor ---
set SERVICE_NAME=ThrottleSupervisor
set SCRIPT_PATH=%~dp0supervisor.py
nssm status %SERVICE_NAME% >nul 2>nul
if not %errorlevel%==3 (
    echo Stopping %SERVICE_NAME% for update...
    nssm stop %SERVICE_NAME% >> "%LOGFILE%" 2>&1
)
if %errorlevel%==3 (
    echo Installing %SERVICE_NAME%...
    nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%SCRIPT_PATH%" >> "%LOGFILE%" 2>&1
) else (
    echo Updating %SERVICE_NAME%...
    nssm set %SERVICE_NAME% Application "%PYTHON_EXE%" >> "%LOGFILE%" 2>&1
    nssm set %SERVICE_NAME% AppParameters "%SCRIPT_PATH%" >> "%LOGFILE%" 2>&1
)
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START >> "%LOGFILE%" 2>&1
nssm set %SERVICE_NAME% ObjectName LocalSystem >> "%LOGFILE%" 2>&1
nssm set %SERVICE_NAME% AppEnvironmentExtra THROTTLE_IPC_TOKEN=%THROTTLE_IPC_TOKEN% >> "%LOGFILE%" 2>&1
echo Starting %SERVICE_NAME%...
nssm start %SERVICE_NAME% >> "%LOGFILE%" 2>&1

REM --- Install or Update DownloadManager ---
set SERVICE_NAME=DownloadManager
set SCRIPT_PATH=%~dp0download_manager.py
nssm status %SERVICE_NAME% >nul 2>nul
if not %errorlevel%==3 (
    echo Stopping %SERVICE_NAME% for update...
    nssm stop %SERVICE_NAME% >> "%LOGFILE%" 2>&1
)
if %errorlevel%==3 (
    echo Installing %SERVICE_NAME%...
    nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%SCRIPT_PATH%" >> "%LOGFILE%" 2>&1
) else (
    echo Updating %SERVICE_NAME%...
    nssm set %SERVICE_NAME% Application "%PYTHON_EXE%" >> "%LOGFILE%" 2>&1
    nssm set %SERVICE_NAME% AppParameters "%SCRIPT_PATH%" >> "%LOGFILE%" 2>&1
)
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START >> "%LOGFILE%" 2>&1
nssm set %SERVICE_NAME% ObjectName LocalSystem >> "%LOGFILE%" 2>&1
nssm set %SERVICE_NAME% AppEnvironmentExtra THROTTLE_IPC_TOKEN=%THROTTLE_IPC_TOKEN% >> "%LOGFILE%" 2>&1
echo Starting %SERVICE_NAME%...
nssm start %SERVICE_NAME% >> "%LOGFILE%" 2>&1

REM --- Install or Update Watchdog ---
set SERVICE_NAME=Watchdog
set SCRIPT_PATH=%~dp0watchdog.py
nssm status %SERVICE_NAME% >nul 2>nul
if not %errorlevel%==3 (
    echo Stopping %SERVICE_NAME% for update...
    nssm stop %SERVICE_NAME% >> "%LOGFILE%" 2>&1
)
if %errorlevel%==3 (
    echo Installing %SERVICE_NAME%...
    nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%SCRIPT_PATH%" >> "%LOGFILE%" 2>&1
) else (
    echo Updating %SERVICE_NAME%...
    nssm set %SERVICE_NAME% Application "%PYTHON_EXE%" >> "%LOGFILE%" 2>&1
    nssm set %SERVICE_NAME% AppParameters "%SCRIPT_PATH%" >> "%LOGFILE%" 2>&1
)
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START >> "%LOGFILE%" 2>&1
nssm set %SERVICE_NAME% ObjectName LocalSystem >> "%LOGFILE%" 2>&1
nssm set %SERVICE_NAME% AppEnvironmentExtra THROTTLE_IPC_TOKEN=%THROTTLE_IPC_TOKEN% >> "%LOGFILE%" 2>&1
echo Starting %SERVICE_NAME%...
nssm start %SERVICE_NAME% >> "%LOGFILE%" 2>&1


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

echo.
echo All core services installed, updated, and started as SYSTEM.
echo See install_log.txt for details and errors.
echo.
sc query ThrottleService | findstr /I /C:"STATE"
sc query DownloadMonitor | findstr /I /C:"STATE"
sc query ThrottleSupervisor | findstr /I /C:"STATE"
sc query DownloadManager | findstr /I /C:"STATE"
sc query Watchdog | findstr /I /C:"STATE"

echo.
set /p REBOOT=Would you like to restart your computer now? (y/n): 
if /I "%REBOOT%"=="y" (
    echo Restarting system...
    shutdown /r /t 5
    exit /b 0
)
echo Install/update complete. You may need to restart your computer for all changes to take effect.

goto :eof

:uninstall
echo Uninstalling all throttler services...
set SERVICES=ThrottleService DownloadMonitor ThrottleSupervisor DownloadManager Watchdog
for %%S in (%SERVICES%) do (
    echo Stopping %%S...
    nssm stop %%S >nul 2>&1
    echo Removing %%S...
    nssm remove %%S confirm >nul 2>&1
)
REM Remove desktop shortcut
set SHORTCUT_NAME=Conductor.lnk
set DESKTOP=%USERPROFILE%\Desktop
if exist "%DESKTOP%\%SHORTCUT_NAME%" del "%DESKTOP%\%SHORTCUT_NAME%"
echo Uninstall complete. Services removed and shortcut deleted.
exit /b 0
