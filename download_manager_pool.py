import threading
import queue
import os
from download_manager import DownloadManager
from throttle_utils import SMALL_DOWNLOAD_THRESHOLD

class DownloadManagerPool:
    def __init__(self):
        self.large_threads = []  # Each large file gets its own thread/instance
        self.small_queue = queue.Queue()
        self.small_thread = None
        self.lock = threading.Lock()
        self.running = True

    def add_download(self, url, dest, size=None, **kwargs):
        # If size is not provided, treat as small (or could probe with HEAD request)
        is_large = size is not None and size >= SMALL_DOWNLOAD_THRESHOLD
        if is_large:
            t = threading.Thread(target=self._run_large, args=(url, dest, kwargs), daemon=True)
            t.start()
            with self.lock:
                self.large_threads.append(t)
        else:
            self.small_queue.put((url, dest, kwargs))
            with self.lock:
                if self.small_thread is None or not self.small_thread.is_alive():
                    self.small_thread = threading.Thread(target=self._run_small_batch, daemon=True)
                    self.small_thread.start()

    def _run_large(self, url, dest, kwargs):
        mgr = DownloadManager(url, dest, **kwargs)
        mgr.download()

    def _run_small_batch(self):
        while not self.small_queue.empty() and self.running:
            url, dest, kwargs = self.small_queue.get()
            try:
                mgr = DownloadManager(url, dest, **kwargs)
                mgr.download()
            except Exception as e:
                print(f"Small download failed: {url} -> {e}")
            self.small_queue.task_done()

    def wait_all(self):
        # Wait for all large downloads
        for t in self.large_threads:
            t.join()
        # Wait for small downloads
        if self.small_thread:
            self.small_thread.join()

    def stop(self):
        self.running = False
        # Optionally, clear the queue
        while not self.small_queue.empty():
            self.small_queue.get()
            self.small_queue.task_done()

# Example usage:
if __name__ == "__main__":
    pool = DownloadManagerPool()
    # Add a large file (simulate with size)
    pool.add_download("https://speed.hetzner.de/100MB.bin", "100MB.bin", size=120*1024*1024)
    # Add small files
    pool.add_download("https://speed.hetzner.de/1MB.bin", "1MB.bin", size=1*1024*1024)
    pool.add_download("https://speed.hetzner.de/2MB.bin", "2MB.bin", size=2*1024*1024)
    pool.wait_all()
    print("All downloads complete.")
