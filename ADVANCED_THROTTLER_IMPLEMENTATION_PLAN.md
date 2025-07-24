
# Advanced Kernel-Aware Download Throttler: Full Implementation Plan & Documentation

## Overview
This document describes the design and implementation plan for an advanced, kernel-aware download throttler that runs as a persistent system process/service. It dynamically manages bandwidth for your installer based on system resource usage and the presence of other large or small downloads (e.g., Steam, Xbox). It also supports multi-core downloads and intelligent bandwidth allocation.

---

## 1. Objectives
- Dynamically throttle or maximize download speed based on system resource usage and the presence of other large/small downloads.
- If a small download (<1GB) is detected, allocate 50% of available bandwidth to it and 50% to your installer until the small download completes.
- Enable multi-threaded (multi-core) downloading for large downloads when system conditions allow.
- The throttler should always be running as a background system process/service, managing bandwidth for the installer and monitoring system activity.
- Provide user feedback and allow configuration.

---

## 2. Key Features & Components

### a. System & Process Monitoring
- Use `psutil` to monitor:
  - CPU, RAM, disk, and network usage.
  - Active processes, especially known downloaders (Steam, Xbox, etc.).
  - Per-process network I/O to estimate download size and activity.

### b. Persistent System Service/Process
- Implement the throttler as a background service/daemon:
  - On Windows: Use `pythonw.exe` or create a Windows Service (using `pywin32` or `nssm`).
  - On Linux/Mac: Use a systemd service or launch as a background daemon.
- The service should start on boot or user login and always be running.


### c. Download Manager
- Refactor the downloader to:
  - Support chunked and multi-threaded downloads (using `requests`, `concurrent.futures.ThreadPoolExecutor`, or similar).
  - Allow dynamic adjustment of bandwidth (bytes/sec) and thread count, as instructed by the throttler service.
  - Report download start, progress, and completion events to the throttler for real-time monitoring.
  - Integrate with the virus check utility to scan files before installation if unsigned.
  - Provide download metadata (URL, destination, size, signature status, and source) to the throttler and GUI.

### c2. Download Monitor
- Implement a separate script/module (`download_monitor.py`) to:
  - Monitor the entire file system for new or growing files (downloads) in real time, not just specific folders.
  - For each detected file, determine:
    - File path, size, and last modification time.
    - Whether the file is digitally signed (using `virus_check_utils.is_signed`).
    - The likely source of the download (Steam, Xbox, Epic, or Unknown) using heuristics.
  - Report each detected download event to the throttler service via IPC, including all metadata.
  - Optionally, use OS-level hooks or platform-specific APIs for more robust detection and to minimize performance impact.

### d. Bandwidth Throttling & Allocation Logic
- The throttler service should:
  - Maintain a list of active downloads, including those reported by the download monitor and the download manager.
  - Use download metadata (size, source, signature status) to inform bandwidth allocation and prioritization.
  - Optionally, deprioritize unsigned or suspicious downloads, or require user confirmation via the GUI.

### d. Bandwidth Throttling & Allocation Logic
- Implement a controller that:
  - Detects large downloads (by process name and network I/O).
  - Detects small downloads (<1GB) and their completion.
  - If a small download is active, allocate 50% of available bandwidth to it and 50% to your installer.
  - If a large download is active, maximize bandwidth and enable multi-threading for your installer.
  - Otherwise, use adaptive throttling based on system load.


### e. Inter-Process Communication (IPC)
- The throttler service, download manager, download monitor, and GUI communicate via a local TCP socket (IPC):
  - The service listens for commands and events (priority overrides, config changes, download events, status requests).
  - The download manager and monitor send download events and status updates.
  - The GUI can send config changes and request real-time status, including system resource stats and download metadata.
  - All IPC messages are JSON-encoded and prefixed with a command (e.g., `GUI_SET_PRIO:`, `GUI_SET_CONFIG:`, `DOWNLOAD_EVENT:`).


### f. User Configuration & Feedback
- Add CLI flags or GUI options for:
  - Throttling mode (auto/manual).
  - Max bandwidth and thread count.
  - Status display (current mode, detected downloads, system resource usage, and download metadata).
  - Real-time log/status area in the GUI for user feedback and troubleshooting.
  - Ability to set and apply priority overrides for specific downloaders or the installer.


### g. Robustness & Logging
- Log all throttling events, detected downloads, download events from the monitor, and resource stats.
- Handle errors gracefully and provide user feedback in both CLI and GUI.
- Ensure all IPC errors, download errors, and scan failures are logged and surfaced to the user.

---


## 3. Technical Steps (Expanded)

### 1. Dependencies
- Add to `requirements.txt`:
  - `psutil` (system/process monitoring)
  - `requests` (HTTP downloads)
  - `tqdm` (progress bar, optional)
  - `pywin32` (for Windows service, if needed)


### 2. Process & Network Monitoring
- Implement a module/class to:
  - List all running processes.
  - For each, check if it matches known downloaders.
  - Monitor their network I/O and estimate download size (using `proc.io_counters()` and `proc.connections()`).
  - Track new/finished downloads and their sizes.
  - Integrate with the download monitor to receive external download events and metadata.

### 3. Persistent Throttler Service
- Implement a Python script that runs as a background service/daemon.
- On Windows, register as a service or use a background process.
- On Linux/Mac, provide a systemd service file or daemonize.


### 4. Download Manager
- Refactor download logic to:
  - Download in chunks (e.g., 1MB).
  - Support multi-threaded downloads for large files (split file into ranges, download in parallel).
  - After each chunk, check throttling controller for sleep time or thread adjustment.
  - Report download start, progress, and completion to the throttler service.
  - Integrate with the virus check utility to scan files before installation if unsigned.
  - Provide download metadata (URL, destination, size, signature status, and source) to the throttler and GUI.


### 5. Bandwidth Allocation Logic
- If a small download (<1GB) is active:
  - Allocate 50% of available bandwidth to it, 50% to your installer.
- If a large download is active:
  - Maximize bandwidth and enable multi-threading for your installer.
- Otherwise:
  - Use adaptive throttling based on CPU/disk/network load.
- Use download metadata (size, source, signature status) to inform allocation and prioritization.
- Optionally, deprioritize unsigned or suspicious downloads, or require user confirmation via the GUI.


### 6. IPC Implementation
- Use a local TCP socket for communication between the throttler service, download manager, download monitor, and GUI.
- The service sends real-time bandwidth allocation instructions to the installer.
- The download monitor and manager send download events and status updates to the service.
- The GUI can send config changes, priority overrides, and request real-time status.


### 7. User Interface/Config
- Add CLI flags or GUI options for:
  - Max bandwidth, thread count, and mode.
  - Status display (current throttling mode, detected downloads, system resource usage, and download metadata).
  - Real-time log/status area in the GUI for user feedback and troubleshooting.
  - Ability to set and apply priority overrides for specific downloaders or the installer.

### 8. Testing & Validation
- Simulate large and small downloads (can use dummy processes or test files).
- Validate that throttling and prioritization work as intended.
- Test on different system loads and with various downloaders active.

---

## 4. Example Module Structure

- `throttle_service.py` — Persistent system service for monitoring and bandwidth allocation.
- `throttle_utils.py` — Resource/process monitoring and throttling logic.
- `download_manager.py` — Chunked/multi-threaded download logic.
- `main.py` or `download_and_install.py` — Integration and user interface.

---

## 5. Example Pseudocode

```python
# throttle_service.py
import psutil, socket

def monitor_and_allocate():
    while True:
        # Detect small/large downloads
        # Calculate available bandwidth
        # Allocate 50% to small download, 50% to installer if needed
        # Send allocation to installer via IPC
        pass

# download_manager.py
def download_with_throttle(url, dest, bandwidth_limit):
    # Download in chunks, sleep as needed to respect bandwidth_limit
    pass
```

---

## 6. Deliverables
- New/updated modules: `throttle_service.py`, `throttle_utils.py`, `download_manager.py`, integration in main script.
- Updated requirements.txt.
- Documentation for configuration, service setup, and usage.
- Logging and test scripts.

---

## 7. Service Setup (Windows Example)
- Use `pywin32` to register the throttler as a Windows Service, or use `nssm` to wrap the Python script as a service.
- Ensure the service starts on boot or user login.
- Provide scripts for installation and removal of the service.

---

## 8. User Configuration & Usage
- CLI/GUI options for bandwidth, thread count, and throttling mode.
- Status display for current throttling mode, detected downloads, and resource usage.
- Logging for diagnostics and troubleshooting.

---

## 9. Testing & Validation
- Simulate various download scenarios (large/small/none).
- Validate bandwidth allocation and prioritization.
- Test on different system loads and with various downloaders active.

---

## 10. Future Enhancements
- Machine learning-based prediction of optimal bandwidth allocation.
- Integration with more downloaders and protocols.
- Advanced user policies and scheduling.

---

## 11. Optional Security: Fast Virus Checker for Unsigned Files

### Overview
- Integrate a lightweight virus scanning step using Windows Defender (or platform equivalent).
- Only scan files that are unsigned (i.e., do not have a valid digital signature).
- Ensure the scan is fast and does not block the main download/installation process for long files or signed files.

### Implementation Steps
- Use Python's `subprocess` module to call Windows Defender's command-line interface (`MpCmdRun.exe`).
- Before launching or installing any downloaded file, check if it is digitally signed:
  - Use `signtool` (Windows SDK) or `Get-AuthenticodeSignature` (PowerShell) to check signature status.
- If the file is unsigned:
  - Run a quick scan with Windows Defender:  
    `MpCmdRun.exe -Scan -ScanType 3 -File <file_path>`
  - Parse the result and only proceed if the file is clean.
- If the file is signed, skip the scan for speed.
- Log all scan results and alert the user if a threat is detected.

### Example Pseudocode
```python
import subprocess

def is_signed(file_path):
    # Use PowerShell to check signature
    cmd = [
        'powershell',
        '-Command',
        f"(Get-AuthenticodeSignature '{file_path}').Status"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return 'Valid' in result.stdout

def quick_defender_scan(file_path):
    cmd = [
        r'C:\Program Files\Windows Defender\MpCmdRun.exe',
        '-Scan', '-ScanType', '3', '-File', file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return 'No threats' in result.stdout

# Usage:
if not is_signed(downloaded_file):
    if not quick_defender_scan(downloaded_file):
        raise Exception('Virus detected!')
```

### Integration Points
- Add this check to the download manager or installer launch step.
- Only activate for unsigned files to minimize performance impact.
- Optionally, allow user to disable/enable this feature via config.

### Notes
- On non-Windows platforms, skip or use platform-appropriate AV tools.
- Ensure the scan is non-blocking and does not delay the user experience for signed files.
- Log all scan actions and results for audit and troubleshooting.

---

## 12. Intelligent Bandwidth Distribution Algorithm & GUI Integration

### Intelligent Bandwidth Distribution
- Implement a dynamic algorithm that:
  - Assigns a priority score to each detected download (e.g., user-initiated, system, background, known app, etc.).
  - Considers download size, type (large/small), and user/application priority.
  - Distributes available bandwidth proportionally:
    - Higher priority and larger downloads get more bandwidth.
    - Small, low-priority, or background downloads get less.
    - User can override priorities via GUI.
- Algorithm steps:
  1. Detect all active downloads and their sizes/types.
  2. Assign a priority (e.g., Steam/game = high, Windows Update = medium, background = low).
  3. Calculate total available bandwidth.
  4. Allocate bandwidth: `allocation = (priority * size_weight) / total_priority_weight`.
  5. Continuously adjust as downloads start/stop or system load changes.
- Example pseudocode:
```python
# downloads: list of dicts with 'pid', 'name', 'size', 'priority'
total_priority = sum(d['priority'] for d in downloads)
for d in downloads:
    d['bw'] = available_bw * (d['priority'] / total_priority)
```

### GUI Integration
- Add a cross-platform GUI (using PyQt5, Tkinter, or similar) to:
  - Display all detected downloads, their sizes, priorities, and current bandwidth allocation.
  - Allow user to adjust priorities (drag/drop, slider, or dropdown).
  - Show real-time graphs of bandwidth usage, system load, and throttling status.
  - Provide controls to pause/resume downloads, override auto-throttling, or set manual limits.
  - Display security/virus scan results for each file.
- GUI should communicate with the throttler service (via IPC or shared state) to update priorities and reflect real-time status.
- Add a new module: `throttle_gui.py` for the GUI logic.

### Implementation Steps
1. Refactor `throttle_service.py` to:
   - Track all downloads with priority and size.
   - Use the new intelligent allocation algorithm.
   - Expose current state and allow updates via IPC for GUI.
2. Create `throttle_gui.py`:
   - Build a dashboard for download/process monitoring and control.
   - Implement user controls for priority and bandwidth.
   - Show real-time stats and logs.
3. Update documentation and main entry point to support launching the GUI.

---

---

## 13. Hardening for Production & Privileged Service Use

### Overview
To make this system fully robust, secure, and suitable for running as a privileged system service (but not as a kernel driver), the following steps are recommended:

### Security Hardening
- Validate all IPC, file, and process operations to prevent privilege escalation, injection, and race conditions.
- Sanitize and validate all user input and IPC messages.
- Run the service with the minimum required privileges (avoid SYSTEM unless absolutely necessary).
- Use secure temp file handling and avoid exposing sensitive data.
- Consider code signing for all executables and installers.

### Service Robustness
- Add watchdog/restart logic to ensure the service recovers from crashes.
- Ensure graceful shutdown and cleanup of all resources.
- Handle all exceptions and log them securely.

### Service Registration & Management
- Provide robust Windows Service installer/uninstaller scripts (using `pywin32` or `nssm`).
- Ensure the service starts on boot and recovers from failures.

### Testing & Validation
- Add automated tests for all critical paths (bandwidth allocation, virus scanning, IPC, GUI).
- Fuzz test IPC and file handling.
- Simulate failure scenarios (network loss, Defender unavailable, etc.).

### Documentation & User Guidance
- Provide clear documentation for setup, permissions, and troubleshooting.
- Warn users about the risks of running as a privileged service.

### Kernel-Level Note
- This implementation is user-space only. True kernel-level operation requires a Windows driver written in C/C++ and is not recommended for this use case.

---

**End of Implementation Plan**
