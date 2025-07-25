import argparse
import logging
from throttle_service import ThrottleService
from download_manager import DownloadManager

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Secure Installer with Advanced Throttling")
    parser.add_argument('--service', action='store_true', help='Run as throttler service')
    parser.add_argument('--download', nargs=2, metavar=('URL', 'DEST'), help='Download a file with throttling')
    parser.add_argument('--status', action='store_true', help='Show status of all core services and heartbeat files')
    args = parser.parse_args()

    if args.service:
        service = ThrottleService()
        try:
            service.start()
        except KeyboardInterrupt:
            service.running = False
            print("ThrottleService stopped.")
    elif args.download:
        url, dest = args.download
        mgr = DownloadManager(url, dest)
        mgr.download()
    elif args.status:
        import os, time
        services = [
            ("ThrottleService", "throttle_service.heartbeat"),
            ("DownloadMonitor", "download_monitor.heartbeat"),
            ("ThrottleSupervisor", "supervisor.heartbeat"),
            ("DownloadManager", "download_manager.heartbeat"),
            ("Watchdog", "watchdog.heartbeat")
        ]
        print("Service Status:")
        for name, hb in services:
            running = False
            try:
                import subprocess
                out = subprocess.check_output(["sc", "query", name], stderr=subprocess.STDOUT, text=True)
                running = "RUNNING" in out
            except Exception:
                pass
            hb_status = "Missing"
            if os.path.exists(hb):
                try:
                    t = float(open(hb).read().strip())
                    age = time.time() - t
                    if age < 10:
                        hb_status = f"OK ({int(age)}s ago)"
                    else:
                        hb_status = f"STALE ({int(age)}s ago)"
                except Exception:
                    hb_status = "Unreadable"
            print(f"  {name:18} | Service: {'RUNNING' if running else 'STOPPED':8} | Heartbeat: {hb_status}")
    else:
        parser.print_help()
