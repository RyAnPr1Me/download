
import subprocess
import sys
import os
import time

def main():
    # Launch watchdog.py to monitor throttle_service.py
    throttle_service_script = os.path.abspath('throttle_service.py')
    download_dir = os.getcwd()  # Or set to a specific downloads directory
    print("[Supervisor] Launching watchdog for throttle_service.py...")
    watchdog_proc = subprocess.Popen([sys.executable, 'watchdog.py', throttle_service_script, download_dir])

    # Launch DownloadMonitor and DownloadManager as persistent background processes
    download_monitor_proc = subprocess.Popen([sys.executable, 'download_monitor.py'])
    download_manager_proc = subprocess.Popen([sys.executable, 'download_manager.py', '--status', 'http://localhost/dummy', 'dummyfile'])

    try:
        # Wait for the watchdog (throttle_service) to exit, then shut down others
        watchdog_proc.wait()
    except KeyboardInterrupt:
        print("[Supervisor] Shutting down all components...")
    finally:
        for proc in [watchdog_proc, download_monitor_proc, download_manager_proc]:
            try:
                proc.terminate()
            except Exception:
                pass
        for proc in [watchdog_proc, download_monitor_proc, download_manager_proc]:
            try:
                proc.wait(timeout=5)
            except Exception:
                pass

if __name__ == "__main__":
    main()
