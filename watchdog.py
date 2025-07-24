import os
import sys
import time
import logging
import threading
import psutil
import subprocess

WATCHDOG_LOG = 'watchdog.log'
MONITOR_INTERVAL = 5  # seconds
SUSPICIOUS_EXTENSIONS = ['.exe', '.dll', '.bat', '.cmd', '.scr', '.ps1']

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    handlers=[
        logging.FileHandler(WATCHDOG_LOG),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('Watchdog')

def is_suspicious_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    return ext in SUSPICIOUS_EXTENSIONS

def monitor_downloads(download_dir, stop_event):
    known_files = set()
    while not stop_event.is_set():
        try:
            for root, dirs, files in os.walk(download_dir):
                for f in files:
                    full_path = os.path.join(root, f)
                    if full_path not in known_files:
                        known_files.add(full_path)
                        if is_suspicious_file(full_path):
                            logger.info(f"New suspicious file detected: {full_path}")
                            # Optionally, scan with Defender
                            try:
                                result = subprocess.run([
                                    r'C:\Program Files\Windows Defender\MpCmdRun.exe',
                                    '-Scan', '-ScanType', '3', '-File', full_path
                                ], capture_output=True, text=True, timeout=60)
                                if 'No threats' not in result.stdout:
                                    logger.warning(f"Threat detected in {full_path}: {result.stdout.strip()}")
                                else:
                                    logger.info(f"File clean: {full_path}")
                            except Exception as e:
                                logger.error(f"Defender scan failed for {full_path}: {e}")
        except Exception as e:
            logger.error(f"Error in download monitoring: {e}")
        time.sleep(MONITOR_INTERVAL)

def start_watchdog(target_script, download_dir):
    stop_event = threading.Event()
    monitor_thread = threading.Thread(target=monitor_downloads, args=(download_dir, stop_event), daemon=True)
    monitor_thread.start()
    logger.info(f"Watchdog started. Monitoring {download_dir} and process {target_script}")

    HEARTBEAT_FILE = 'service_heartbeat.txt'  # The main service should update this file regularly
    HEARTBEAT_TIMEOUT = 15  # seconds

    while True:
        try:
            proc = subprocess.Popen([sys.executable, target_script], shell=False)
            logger.info(f"Started monitored process {target_script} (pid={proc.pid})")
            while proc.poll() is None:
                # Health check: verify heartbeat file is fresh
                if os.path.exists(HEARTBEAT_FILE):
                    last_beat = os.path.getmtime(HEARTBEAT_FILE)
                    age = time.time() - last_beat
                    if age > HEARTBEAT_TIMEOUT:
                        logger.error(f"Health check failed: Heartbeat file too old (age={age:.1f}s). Restarting {target_script}.")
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except Exception:
                            proc.kill()
                        break  # Restart process
                else:
                    logger.warning(f"Heartbeat file {HEARTBEAT_FILE} not found. Waiting for service to create it.")
                time.sleep(2)
            logger.warning(f"Monitored process {target_script} exited with code {proc.returncode}. Restarting...")
        except Exception as e:
            logger.critical(f"Failed to start or monitor process: {e}")
        time.sleep(5)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python watchdog.py <main_service.py> <download_dir>")
        sys.exit(1)
    target_script = sys.argv[1]
    download_dir = sys.argv[2]
    start_watchdog(target_script, download_dir)
