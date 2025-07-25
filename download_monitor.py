
import os
import socket
import json
import threading
import time
import logging
import hashlib
from virus_check_utils import is_signed
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


IPC_HOST = '127.0.0.1'
IPC_PORT = 54321
# Shared secret for local IPC authentication
IPC_AUTH_TOKEN = os.environ.get('THROTTLE_IPC_TOKEN', 'changeme-secret-token')


class DownloadEventHandler(FileSystemEventHandler):
    def __init__(self, monitor, skip_dirs):
        super().__init__()
        self.monitor = monitor
        self.skip_dirs = skip_dirs

    def _handle_event(self, event):
        if event.is_directory:
            return
        fpath = event.src_path
        # Skip system/hidden folders for performance and safety
        if any(x in fpath.lower() for x in self.skip_dirs):
            self.monitor.logger.debug(f"Skipped (skip_dirs): {fpath}")
            return
        try:
            if not os.path.isfile(fpath):
                self.monitor.logger.debug(f"Skipped (not a file): {fpath}")
                return
            size = os.path.getsize(fpath)
            # Ignore empty, huge, or system files
            if size == 0 or size > 50*1024*1024*1024:
                self.monitor.logger.debug(f"Skipped (size): {fpath} size={size}")
                return
            # Heuristic: skip temp/partial/incomplete downloads
            partial_exts = ['.part', '.crdownload', '.tmp', '.download', '.partial']
            if any(fpath.lower().endswith(ext) for ext in partial_exts):
                self.monitor.logger.debug(f"Skipped (partial/incomplete): {fpath}")
                return
            # Heuristic: only consider likely download file types
            likely_exts = ['.exe', '.msi', '.zip', '.rar', '.7z', '.iso', '.dmg', '.pdf', '.mp4', '.mp3', '.jpg', '.png', '.apk', '.bin']
            likely = any(fpath.lower().endswith(ext) for ext in likely_exts)
            import mimetypes
            mime, _ = mimetypes.guess_type(fpath)
            if not likely and (not mime or not (mime.startswith('application') or mime.startswith('video') or mime.startswith('audio'))):
                self.monitor.logger.debug(f"Skipped (not likely download type): {fpath}")
                return
            signed = is_signed(fpath)
            # Try to get download URL from .meta file
            url = None
            meta_path = fpath + '.meta'
            if os.path.exists(meta_path):
                try:
                    import json
                    with open(meta_path, 'r') as mf:
                        meta = json.load(mf)
                        url = meta.get('url')
                except Exception as e:
                    self.monitor.logger.warning(f"Failed to read meta file for {fpath}: {e}")
            # Optionally, get PID if available (not always possible)
            pid = None
            # Send takeover request to DownloadManager
            try:
                takeover_payload = {
                    'token': IPC_AUTH_TOKEN,
                    'url': url,
                    'file_path': fpath,
                    'pid': pid
                }
                with socket.create_connection(('127.0.0.1', 54323), timeout=2) as s:
                    s.sendall(json.dumps(takeover_payload).encode())
                    resp = s.recv(4096)
                    self.monitor.logger.info(f"Takeover response for {fpath}: {resp.decode()}")
            except Exception as e:
                self.monitor.logger.error(f"Failed to send takeover request for {fpath}: {e}")
        except Exception as e:
            self.monitor.logger.error(f"Error handling event for {fpath}: {e}")

class DownloadMonitor:
    def __init__(self):
        self.logger = logging.getLogger('DownloadMonitor')
        logging.basicConfig(level=logging.INFO)
        self.running = True
        self.downloads = {}
        self.lock = threading.Lock()
        self.observer = None

    def monitor_filesystem(self, root_dirs=None):
        """Efficiently monitor the file system for new downloads using watchdog with platform-specific optimizations."""
        import platform
        from watchdog.observers import Observer, PollingObserver, WindowsApiObserver
        # Allow user to specify monitored folders, else use common download locations
        if root_dirs is None:
            root_dirs = []
            if os.name == 'nt':
                # Only monitor user folders and Downloads by default
                user_profile = os.environ.get('USERPROFILE', 'C:\\Users\\Default')
                downloads = os.path.join(user_profile, 'Downloads')
                desktop = os.path.join(user_profile, 'Desktop')
                root_dirs = [downloads, desktop]
            else:
                home = os.path.expanduser('~')
                root_dirs = [os.path.join(home, 'Downloads'), os.path.join(home, 'Desktop')]
        # Exclude system/large folders by default
        skip_dirs = ['windows', 'program files', 'system32', 'recycle', 'appdata', 'tmp', 'temp', 'cache', 'proc', 'sys', 'dev', 'node_modules', 'venv', 'env']
        event_handler = DownloadEventHandler(self, skip_dirs)
        # Use the most efficient observer for the platform
        if os.name == 'nt':
            try:
                self.observer = WindowsApiObserver()
                self.logger.info("Using WindowsApiObserver for efficient monitoring.")
            except Exception:
                self.observer = Observer()
        else:
            try:
                self.observer = Observer()
            except Exception:
                self.observer = PollingObserver()
        # Schedule only the selected folders
        for root in root_dirs:
            if not os.path.exists(root):
                continue
            try:
                self.observer.schedule(event_handler, root, recursive=True)
                self.logger.info(f"Started monitoring {root}")
            except Exception as e:
                self.logger.error(f"Failed to monitor {root}: {e}")
        self.observer.start()
        # Event batching/debounce to reduce load
        try:
            last_event = 0
            debounce = 0.5  # seconds
            while self.running:
                time.sleep(0.1)
                now = time.time()
                if now - last_event < debounce:
                    continue
                last_event = now
        except KeyboardInterrupt:
            self.running = False
        finally:
            self.observer.stop()
            self.observer.join()

    def identify_source(self, fpath):
        # Try to get the download source from an alternate data stream (Windows) or a .meta file
        # Fallback to heuristics if not available
        # 1. Check for a .meta file (cross-platform, written by download manager)
        meta_path = fpath + '.meta'
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as mf:
                    meta = json.load(mf)
                    url = meta.get('url', '')
                    if url:
                        return self._origin_from_url(url)
            except Exception:
                pass
        # 2. On Windows, check for Zone.Identifier ADS (URLZONE)
        if os.name == 'nt':
            try:
                ads_path = fpath + ':Zone.Identifier'
                if os.path.exists(ads_path):
                    with open(ads_path, 'r', encoding='utf-8', errors='ignore') as ads:
                        for line in ads:
                            if line.strip().startswith('HostUrl='):
                                url = line.strip().split('=', 1)[-1]
                                return self._origin_from_url(url)
            except Exception:
                pass
        # 3. Fallback to filename/folder heuristics
        fname = os.path.basename(fpath).lower()
        if 'steam' in fname or 'steam' in fpath.lower():
            return 'Steam'
        if 'xbox' in fname or 'xbox' in fpath.lower():
            return 'Xbox'
        if 'epic' in fname or 'epic' in fpath.lower():
            return 'EpicGames'
        return 'Unknown'

    def _origin_from_url(self, url):
        # Map known domains to sources
        if 'steampowered.com' in url or 'steam' in url:
            return 'Steam'
        if 'xbox' in url or 'microsoft.com' in url:
            return 'Xbox'
        if 'epicgames.com' in url or 'epic' in url:
            return 'EpicGames'
        if url:
            return url  # Return the URL if unknown
        return 'Unknown'

    def report_download(self, info):
        # Send info to throttler service with authentication token
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((IPC_HOST, IPC_PORT))
                # Prepend token to the message for authentication
                payload = {
                    'token': IPC_AUTH_TOKEN,
                    'event': 'DOWNLOAD_EVENT',
                    'data': info
                }
                msg = json.dumps(payload).encode()
                s.sendall(msg)
        except Exception as e:
            self.logger.error(f"Failed to report download: {e}")

if __name__ == "__main__":
    import argparse
    import threading
    def heartbeat_loop():
        while True:
            try:
                with open('download_monitor.heartbeat', 'w') as hb:
                    hb.write(str(time.time()))
            except Exception:
                pass
            time.sleep(2)
    parser = argparse.ArgumentParser(description="Download Monitor for Throttler")
    parser.add_argument('--roots', nargs='*', help='Root directories to scan (default: all drives or /)')
    args = parser.parse_args()
    mon = DownloadMonitor()
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    try:
        mon.monitor_filesystem(args.roots)
    except KeyboardInterrupt:
        mon.running = False
        print("Stopped.")
