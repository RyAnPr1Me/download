# Advanced Kernel-Aware Download Throttler: Implementation Plan & Documentation (Reorganized)

## 1. System Architecture

**Components:**
- ThrottleService (core bandwidth controller, always-on)
- DownloadManager (multi-protocol, multi-threaded, secure downloader)
- DownloadMonitor (file system/ETW-based download detection)
- ThrottleGUI (Tkinter-based control panel)
- Supervisor/Watchdog (service/process health and restart)

**Communication:**
- All components use authenticated local TCP IPC (JSON messages with token)

**Security:**
- All downloads are scanned if unsigned
- All IPC is authenticated
- All events and errors are logged

---

## 2. Setup & Installation

1. Install Python 3.9+ and all dependencies:
   ```
   pip install -r requirements.txt
   ```
2. (Windows) Install as services with `install_throttle_service.bat` (run as Administrator)
3. Start the GUI with `python throttle_gui.py`
4. Use `python main.py --download <URL> <DEST>` for CLI downloads

---

## 3. Operation & Features

### a. System & Process Monitoring
- Uses `psutil` to monitor CPU, RAM, disk, and per-process network I/O
- Detects large/small downloads by process name and I/O

### b. Persistent Service
- ThrottleService runs as a background service/daemon
- Supervisor/Watchdog ensures all services are always running

### c. Download Manager
- Supports HTTP(S), FTP, SFTP, SMB, file, data URLs, torrents
- Multi-threaded, chunked, and adaptive downloads
- Writes .meta files for correlation and security

### d. Download Monitor
- Monitors file system (watchdog/ETW) for new/growing downloads
- Identifies source (Steam, Xbox, Epic, etc.)

### e. Bandwidth Throttling & Allocation
- Dynamically allocates bandwidth based on system load, download size, and running games
- Prioritizes gaming traffic if latency is high
- User can override priorities and bandwidth via GUI

### f. User Configuration & Feedback
- GUI for real-time status, config, and logs
- CLI flags for advanced users

### g. Robustness & Logging
- All events, errors, and security actions are logged
- Services are auto-restarted if they fail

---

## 4. Extensibility & Customization

- Add new downloaders to `throttle_utils.py` for detection/classification
- Extend protocol support in `download_manager.py`
- Adjust thresholds and weights in `throttle_service.py` for custom allocation logic
- Add new security checks in `virus_check_utils.py`

---

## 5. Development & Contribution

- All code is modular and well-documented
- See `USER_GUIDE.md` for user-facing documentation
- Open issues or pull requests for bugs, features, or improvements

---

## 6. Dependencies
- See `requirements.txt` for all required and optional packages
