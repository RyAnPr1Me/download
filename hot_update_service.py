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
    try:
        subprocess.run(["sc", "stop", service_name], capture_output=True)
    except Exception as e:
        logging.error(f"Failed to stop {service_name}: {e}")

def start_service(service_name):
    try:
        subprocess.run(["sc", "start", service_name], capture_output=True)
    except Exception as e:
        logging.error(f"Failed to start {service_name}: {e}")

def update_code(src_folder, dst_folder):
    for root, dirs, files in os.walk(src_folder):
        rel = os.path.relpath(root, src_folder)
        dst_root = os.path.join(dst_folder, rel)
        os.makedirs(dst_root, exist_ok=True)
        for f in files:
            src_file = os.path.join(root, f)
            dst_file = os.path.join(dst_root, f)
            shutil.copy2(src_file, dst_file)

def monitor_service(entry, poll_interval=2):
    logger = logging.getLogger(f"HotUpdater.{entry['service_name']}")
    watch_folder = entry['watch_folder']
    service_name = entry['service_name']
    code_folder = entry['code_folder']
    last_hash = hash_folder(watch_folder)
    logger.info(f"Initial hash: {last_hash}")
    while True:
        time.sleep(poll_interval)
        try:
            new_hash = hash_folder(watch_folder)
            if new_hash != last_hash:
                logger.info("Change detected! Stopping service and updating code...")
                stop_service(service_name)
                update_code(watch_folder, code_folder)
                time.sleep(1)
                start_service(service_name)
                logger.info("Service restarted with new code.")
                last_hash = new_hash
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")

def load_services_config(config_path):
    import json
    with open(config_path, 'r') as f:
        return json.load(f)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Hot update multiple services from config file.")
    parser.add_argument('--config', type=str, default='services.json', help='Path to services config JSON')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    services = load_services_config(args.config)
    threads = []
    for entry in services:
        t = threading.Thread(target=monitor_service, args=(entry,), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
