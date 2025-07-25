import threading
import queue
import os
from download_manager import DownloadManager
from throttle_utils import SMALL_DOWNLOAD_THRESHOLD

import socket
import json

COMMAND_PORT = 54506  # Unique port for DownloadManagerPool commands
COMMAND_TOKEN = os.environ.get('THROTTLE_IPC_TOKEN', 'super-secure-random-token-2025')

class DownloadManagerPool:
    def __init__(self):
        self.large_threads = []  # Each large file gets its own thread/instance
        self.small_queue = queue.Queue()
        self.small_thread = None
        self.lock = threading.Lock()
        self.running = True
        self.active_downloads = {}  # Map: dest -> thread or DownloadManager

    def add_download(self, url, dest, size=None, **kwargs):
        # If size is not provided, treat as small (or could probe with HEAD request)
        is_large = size is not None and size >= SMALL_DOWNLOAD_THRESHOLD
        if is_large:
            t = threading.Thread(target=self._run_large, args=(url, dest, kwargs), daemon=True)
            t.start()
            with self.lock:
                self.large_threads.append(t)
                self.active_downloads[dest] = t
        else:
            self.small_queue.put((url, dest, kwargs))
            with self.lock:
                if self.small_thread is None or not self.small_thread.is_alive():
                    self.small_thread = threading.Thread(target=self._run_small_batch, daemon=True)
                    self.small_thread.start()

    def _run_large(self, url, dest, kwargs):
        try:
            mgr = DownloadManager(url, dest, **kwargs)
            with self.lock:
                self.active_downloads[dest] = mgr
            mgr.download()
            with self.lock:
                if dest in self.active_downloads:
                    del self.active_downloads[dest]
        except Exception as e:
            if 'Defender scan failed' in str(e):
                print(f"[Warning] Windows Defender scan failed for {dest}. This may be due to Defender not being available, insufficient permissions, or a system misconfiguration. Skipping scan.")
            else:
                print(f"[Error] Large download failed: {url} -> {e}")

    def _run_small_batch(self):
        while not self.small_queue.empty() and self.running:
            url, dest, kwargs = self.small_queue.get()
            try:
                mgr = DownloadManager(url, dest, **kwargs)
                with self.lock:
                    self.active_downloads[dest] = mgr
                mgr.download()
                with self.lock:
                    if dest in self.active_downloads:
                        del self.active_downloads[dest]
            except Exception as e:
                if 'Defender scan failed' in str(e):
                    print(f"[Warning] Windows Defender scan failed for {dest}. This may be due to Defender not being available, insufficient permissions, or a system misconfiguration. Skipping scan.")
                else:
                    print(f"Small download failed: {url} -> {e}")
            self.small_queue.task_done()

    def wait_all(self):
        # Wait for all large downloads
        for t in self.large_threads:
            t.join()
        # Wait for small downloads
        if self.small_thread:
            self.small_thread.join()

    def spin_down_thread(self, download_id=None, count=1):
        # For demo: just print, real logic would reduce threads for a download
        print(f"[Command] Spinning down {count} thread(s) for download: {download_id}")
        # Implement logic to reduce threads for a given download if possible
        return True

    def pause(self, download_id=None):
        print(f"[Command] Pausing download: {download_id if download_id else 'ALL'}")
        # Implement logic to pause downloads
        return True

    def command_server(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', COMMAND_PORT))
        s.listen(5)
        print(f"[DownloadManagerPool] Command server listening on {COMMAND_PORT}")
        while True:
            conn, _ = s.accept()
            threading.Thread(target=self.handle_command, args=(conn,), daemon=True).start()

    def handle_command(self, conn):
        try:
            data = conn.recv(4096)
            req = json.loads(data.decode())
            if req.get('token') != COMMAND_TOKEN:
                conn.sendall(b'AUTH_ERROR')
                return
            cmd = req.get('command')
            if cmd == 'SPIN_DOWN_THREAD':
                download_id = req.get('download_id')
                count = req.get('count', 1)
                ok = self.spin_down_thread(download_id, count)
                conn.sendall(b'OK' if ok else b'ERROR')
            elif cmd == 'PAUSE':
                download_id = req.get('download_id')
                ok = self.pause(download_id)
                conn.sendall(b'OK' if ok else b'ERROR')
            else:
                conn.sendall(b'UNKNOWN_COMMAND')
        except Exception as e:
            conn.sendall(str(e).encode())
        finally:
            conn.close()

    def stop(self):
        self.running = False
        # Optionally, clear the queue
        while not self.small_queue.empty():
            self.small_queue.get()
            self.small_queue.task_done()

# Example usage:
if __name__ == "__main__":
    pool = DownloadManagerPool()
    threading.Thread(target=pool.command_server, daemon=True).start()
    # Add a large file (simulate with size)
    pool.add_download("https://speed.hetzner.de/100MB.bin", "100MB.bin", size=120*1024*1024)
    # Add small files
    pool.add_download("https://speed.hetzner.de/1MB.bin", "1MB.bin", size=1*1024*1024)
    pool.add_download("https://speed.hetzner.de/2MB.bin", "2MB.bin", size=2*1024*1024)
    pool.wait_all()
    print("All downloads complete.")
