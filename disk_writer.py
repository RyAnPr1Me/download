import os
import threading
import time
import logging

class DiskWriter:
    """
    Efficient, thread-safe, optionally throttled disk writing utility for large files and streaming data.
    Handles chunked writes, adaptive buffering, throttling, and error recovery.
    """
    def __init__(self, throttle_bps=None, chunk_size=1024*1024, fsync_interval=5, logger=None):
        self.throttle_bps = throttle_bps
        self.chunk_size = chunk_size
        self.fsync_interval = fsync_interval  # seconds between fsyncs
        self.logger = logger or logging.getLogger('DiskWriter')
        self._lock = threading.Lock()

    def write(self, f, data):
        """
        Write bytes or file-like object to file object f efficiently.
        """
        last_fsync = time.time()
        total_written = 0
        if hasattr(data, 'read'):
            while True:
                chunk = data.read(self.chunk_size)
                if not chunk:
                    break
                self._write_chunk(f, chunk)
                total_written += len(chunk)
                if self.throttle_bps:
                    time.sleep(len(chunk) / self.throttle_bps)
                if time.time() - last_fsync > self.fsync_interval:
                    try:
                        os.fsync(f.fileno())
                    except Exception as e:
                        self.logger.debug(f"fsync failed: {e}")
                    last_fsync = time.time()
        elif isinstance(data, (bytes, bytearray)):
            offset = 0
            total = len(data)
            while offset < total:
                chunk = data[offset:offset+self.chunk_size]
                self._write_chunk(f, chunk)
                total_written += len(chunk)
                if self.throttle_bps:
                    time.sleep(len(chunk) / self.throttle_bps)
                if time.time() - last_fsync > self.fsync_interval:
                    try:
                        os.fsync(f.fileno())
                    except Exception as e:
                        self.logger.debug(f"fsync failed: {e}")
                    last_fsync = time.time()
                offset += len(chunk)
        else:
            raise ValueError("Unsupported data type for DiskWriter.write")
        try:
            os.fsync(f.fileno())
        except Exception as e:
            self.logger.debug(f"Final fsync failed: {e}")
        return total_written

    def _write_chunk(self, f, chunk):
        with self._lock:
            try:
                f.write(chunk)
                f.flush()
            except Exception as e:
                self.logger.error(f"Disk write failed: {e}")
                raise

    def safe_write(self, path, data, mode='wb', retries=3):
        """
        Write to a file path with retries and atomic replacement.
        """
        tmp_path = path + ".part"
        for attempt in range(retries):
            try:
                with open(tmp_path, mode) as f:
                    self.write(f, data)
                os.replace(tmp_path, path)
                return True
            except Exception as e:
                self.logger.warning(f"Write attempt {attempt+1} failed: {e}")
                time.sleep(1)
        self.logger.error(f"Failed to write {path} after {retries} attempts.")
        return False
