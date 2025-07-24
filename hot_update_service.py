import os
import time
import shutil
import subprocess
import hashlib
import logging
import threading

def hash_folder(folder):
    """Return a hash of all files in the folder (names + mtimes + sizes)."""
    h = hashlib.sha256()
    for root, dirs, files in os.walk(folder):
        for f in sorted(files):
            path = os.path.join(root, f)
            try:
                stat = os.stat(path)
                h.update(f.encode())
                h.update(str(stat.st_mtime).encode())
                h.update(str(stat.st_size).encode())
            except Exception:
                continue
    return h.hexdigest()

def stop_service(service_name):
    subprocess.run(["sc", "stop", service_name], capture_output=True)

def start_service(service_name):
    subprocess.run(["sc", "start", service_name], capture_output=True)

def update_code(src_folder, dst_folder):
    for root, dirs, files in os.walk(src_folder):
        rel = os.path.relpath(root, src_folder)
        dst_root = os.path.join(dst_folder, rel)
        os.makedirs(dst_root, exist_ok=True)
        for f in files:
            src_file = os.path.join(root, f)
            dst_file = os.path.join(dst_root, f)
            shutil.copy2(src_file, dst_file)

def monitor_and_update(watch_folder, service_name, code_folder, poll_interval=2):
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('HotUpdater')
    last_hash = hash_folder(watch_folder)
    logger.info(f"Initial hash: {last_hash}")
    while True:
        time.sleep(poll_interval)
        new_hash = hash_folder(watch_folder)
        if new_hash != last_hash:
            logger.info("Change detected! Stopping service and updating code...")
            stop_service(service_name)
            update_code(watch_folder, code_folder)
            time.sleep(1)
            start_service(service_name)
            logger.info("Service restarted with new code.")
            last_hash = new_hash

if __name__ == "__main__":
    # Example usage: monitor_and_update('\\\\server\\shared\\code', 'ThrottleService', 'C:/Program Files/ThrottleService')
    import sys
    if len(sys.argv) != 4:
        print("Usage: python hot_update_service.py <watch_folder> <service_name> <code_folder>")
        sys.exit(1)
    monitor_and_update(sys.argv[1], sys.argv[2], sys.argv[3])
