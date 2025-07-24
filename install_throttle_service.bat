@echo off
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

REM Install Python dependencies
if exist requirements.txt (
    echo Installing Python dependencies...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
)

REM Install ThrottleService as SYSTEM
set SERVICE_NAME=ThrottleService
set SCRIPT_PATH=%~dp0throttle_service.py
nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%SCRIPT_PATH%"
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm set %SERVICE_NAME% ObjectName LocalSystem

REM Install DownloadMonitor as SYSTEM
set SERVICE_NAME=DownloadMonitor
set SCRIPT_PATH=%~dp0download_monitor.py
nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%SCRIPT_PATH%"
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm set %SERVICE_NAME% ObjectName LocalSystem

REM Install Supervisor as SYSTEM
set SERVICE_NAME=ThrottleSupervisor
set SCRIPT_PATH=%~dp0supervisor.py
nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%SCRIPT_PATH%"
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm set %SERVICE_NAME% ObjectName LocalSystem


REM Create desktop shortcut for GUI as 'Conductor'
set GUI_SCRIPT=%~dp0gui.py
set SHORTCUT_NAME=Conductor.lnk
set DESKTOP=%USERPROFILE%\Desktop
if exist "%DESKTOP%" (
    echo Creating desktop shortcut for GUI as 'Conductor'...
    powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%DESKTOP%\\%SHORTCUT_NAME%');$s.TargetPath='%PYTHON_EXE%';$s.Arguments='\"%GUI_SCRIPT%\"';$s.WorkingDirectory='%~dp0';$s.IconLocation='%~dp0icon.ico';$s.Save()"
    echo Shortcut created on desktop as 'Conductor'.
)

echo All core services installed as SYSTEM. You can start them from Services or with:
echo    nssm start ThrottleService
echo    nssm start DownloadMonitor
echo    nssm start ThrottleSupervisor
