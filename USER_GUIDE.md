# Secure Installer & Advanced Throttler: User Guide

## Overview
This application suite provides a secure, high-performance download manager and a kernel-aware bandwidth throttler. It dynamically manages download speed, prioritizes gaming and critical applications, and protects your system from malicious files. It is designed for Windows but is extensible to other platforms.

---

## Workflow Summary
- **Supervisor** launches and monitors all core services: ThrottleService, DownloadMonitor, and DownloadManager.
- **ThrottleService** dynamically allocates bandwidth and enforces throttling policies.
- **DownloadMonitor** detects new downloads on the filesystem and can trigger secure takeover by DownloadManager.
- **DownloadManager** handles all downloads, supports multiple protocols, and performs security checks.
- **GUI** provides real-time status, configuration, and control.
- All components communicate via authenticated local TCP IPC and are monitored via heartbeat files.
- If any service fails, Supervisor will automatically restart it.

---

## Features
- **Dynamic Bandwidth Throttling:** Automatically allocates bandwidth based on system load, download size, and running applications (e.g., Steam, Xbox, Epic).
- **Multi-Protocol Support:** HTTP(S), FTP, SFTP, SMB, file, data URLs, and torrents.
- **Multi-Threaded & Chunked Downloads:** Maximizes speed using parallel connections and adaptive chunk sizing.
- **Gaming Latency Protection:** Detects running games and prioritizes their network traffic to minimize lag.
- **Virus & Signature Checks:** Scans unsigned files with Windows Defender and checks digital signatures.
- **Persistent Services:** Runs as background Windows services for always-on protection and management.
- **GUI Control Panel:** Real-time status, configuration, and priority overrides via a modern Tkinter GUI.
- **Robust Logging & Error Handling:** All events, errors, and security actions are logged for transparency.

---

## Quick Start
1. **Install Python 3.9+** and all dependencies:
   ```
   pip install -r requirements.txt
   ```
2. **Install as Windows Services (optional, recommended):**
   - Run `install_throttle_service.bat` as Administrator.
   - This will install the ThrottleService, DownloadMonitor, and Supervisor as persistent services.
3. **Start the GUI:**
   ```
   python throttle_gui.py
   ```
4. **Download a file from the command line:**
   ```
   python main.py --download <URL> <DEST>
   ```
5. **Run the throttler service manually (for testing):**
   ```
   python main.py --service
   ```

---

## GUI Usage
- **Status Panel:** Shows current bandwidth allocation, system resource usage, and all detected downloads.
- **Download Config:** Set bandwidth, thread count, and throttling mode. Use "Turbo Mode" for maximum speed.
- **Priority Overrides:** Assign priorities (0-10) to the installer or known downloaders (e.g., Steam.exe).
- **Log/Status Area:** View recent events, errors, and security actions.

---

## Security & Safety
- **All downloads are scanned if unsigned.**
- **Suspicious files are flagged and logged.**
- **All IPC is authenticated with a shared secret.**
- **Services are monitored and auto-restarted if they fail.**

---

## Troubleshooting
- **Missing Dependencies:**
  - Run `pip install -r requirements.txt` to install all required and optional packages.
- **Service Fails to Start:**
  - Check `download_manager.log` and `watchdog.log` for errors.
  - Ensure you have Administrator rights for service installation.
- **Slow Downloads:**
  - Use Turbo Mode in the GUI or increase thread count/bandwidth.
  - Check for other large downloads or high system load.
- **Virus Scan Fails:**
  - Ensure Windows Defender is installed and enabled.

---

## Advanced Configuration
- **Edit `requirements.txt`** to add or remove protocol support.
- **Edit `ADVANCED_THROTTLER_IMPLEMENTATION_PLAN.md`** for technical details and customization.
- **Modify `throttle_utils.py`** to add new downloaders or change classification logic.

---

## Support
For issues, feature requests, or contributions, please contact the project maintainer or open an issue on the repository.

---

# Thank you for using Secure Installer & Advanced Throttler!
