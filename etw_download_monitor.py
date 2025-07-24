
import logging
import threading
import time
import sys
import socket
import json
import os

try:
    from etw import ETW, trace
    from etw.descriptors import FileIoWrite
except ImportError:
    print("You must install the 'etw' Python package: pip install etw")
    sys.exit(1)

# IPC config (reuse from download_manager.py)
IPC_HOST = '127.0.0.1'
IPC_PORT = 54321
IPC_AUTH_TOKEN = os.environ.get('THROTTLE_IPC_TOKEN', 'changeme-secret-token')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('ETWDownloadMonitor')

MONITORED_FOLDERS = ['\\Downloads', '\\Desktop']
KNOWN_DOWNLOADERS = ['chrome.exe', 'firefox.exe', 'msedge.exe', 'steam.exe', 'epicgameslauncher.exe']

def report_download(file_name, proc_name, pid):
    info = {
        'path': file_name,
        'size': None,
        'signed': None,
        'source': proc_name,
        'url': None,
        'mime': None,
        'hash': None,
        'event_type': 'etw_file_write',
        'ctime': None,
        'mtime': None,
        'pid': pid
    }
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((IPC_HOST, IPC_PORT))
            payload = {
                'token': IPC_AUTH_TOKEN,
                'event': 'DOWNLOAD_EVENT',
                'data': info
            }
            msg = json.dumps(payload).encode()
            s.sendall(msg)
    except Exception as e:
        logger.error(f"Failed to report download: {e}")

def on_file_write(event):
    file_name = getattr(event, 'file_name', '')
    proc_name = getattr(event, 'process_name', '').lower()
    pid = getattr(event, 'process_id', None)
    if any(folder.lower() in file_name.lower() for folder in MONITORED_FOLDERS):
        if any(downloader in proc_name for downloader in KNOWN_DOWNLOADERS):
            logger.info(f"Possible download: {file_name} by {proc_name} (pid={pid})")
            report_download(file_name, proc_name, pid)
        else:
            logger.debug(f"File write in monitored folder: {file_name} by {proc_name}")

def start_etw_monitor():
    etw = ETW(providers=[FileIoWrite()], event_callback=on_file_write)
    logger.info("Starting ETW download monitor (requires admin)")
    etw.start()

if __name__ == "__main__":
    try:
        t = threading.Thread(target=start_etw_monitor, daemon=True)
        t.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("ETW download monitor stopped.")
