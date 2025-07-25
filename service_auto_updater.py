import os
import time
import hashlib
import subprocess
import shutil
import sys

# CONFIGURATION
SERVICE_NAMES = ["ThrottleService", "DownloadMonitor", "ThrottleSupervisor", "DownloadManager", "Watchdog"]
WATCH_FOLDER = os.path.dirname(os.path.abspath(__file__))
CHECK_INTERVAL = 2  # seconds
CODE_EXTENSIONS = {'.py', '.exe', '.dll'}  # Files to watch for changes

def hash_folder(folder, exts):
    h = hashlib.sha256()
    for root, dirs, files in os.walk(folder):
        for f in files:
            if os.path.splitext(f)[1].lower() in exts:
                path = os.path.join(root, f)
                try:
                    with open(path, 'rb') as fp:
                        while True:
                            chunk = fp.read(8192)
                            if not chunk:
                                break
                            h.update(chunk)
                except Exception:
                    continue
    return h.hexdigest()

def stop_service(name):
    subprocess.run(["sc", "stop", name], capture_output=True)
    time.sleep(2)

def start_service(name):
    subprocess.run(["sc", "start", name], capture_output=True)
    time.sleep(2)

def main():
    print(f"Watching {WATCH_FOLDER} for code changes...")
    last_hash = hash_folder(WATCH_FOLDER, CODE_EXTENSIONS)
    while True:
        time.sleep(CHECK_INTERVAL)
        new_hash = hash_folder(WATCH_FOLDER, CODE_EXTENSIONS)
        if new_hash != last_hash:
            print("Change detected! Stopping all services, updating code, and restarting...")
            for svc in SERVICE_NAMES:
                stop_service(svc)
            # Here you could pull new code from a remote location, e.g.:
            # subprocess.run(["git", "pull"], cwd=WATCH_FOLDER)
            # Or copy from a network share, etc.
            # For now, just restart the services
            for svc in SERVICE_NAMES:
                start_service(svc)
            print("All services restarted with updated code.")
            last_hash = new_hash

if __name__ == "__main__":
    main()
