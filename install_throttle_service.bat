@echo off
REM Install ThrottleService, DownloadMonitor, and Supervisor as Windows services using nssm
REM Prerequisites: nssm.exe must be in the same directory or in PATH

set PYTHON_EXE=%~dp0pythonw.exe

REM Install ThrottleService
set SERVICE_NAME=ThrottleService
set SCRIPT_PATH=%~dp0throttle_service.py
nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%SCRIPT_PATH%"
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START

REM Install DownloadMonitor
set SERVICE_NAME=DownloadMonitor
set SCRIPT_PATH=%~dp0download_monitor.py
nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%SCRIPT_PATH%"
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START

REM Install Supervisor (manages all core services)
set SERVICE_NAME=ThrottleSupervisor
set SCRIPT_PATH=%~dp0supervisor.py
nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%SCRIPT_PATH%"
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START

echo All core services installed. You can start them from Services or with:
echo    nssm start ThrottleService
echo    nssm start DownloadMonitor
echo    nssm start ThrottleSupervisor
