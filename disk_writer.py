import os
import threading
import time
import logging

class DiskWriter:
    """
    Efficient, thread-safe, optionally throttled disk writing utility for large files and streaming data.
    Handles chunked writes, adaptive buffering, throttling, error recovery, and resource management.
    Usage:
        with DiskWriter(...) as writer:
            writer.write(f, data)
    """
    def __init__(self, throttle_bps=None, chunk_size=1024*1024, fsync_interval=5, logger=None, adaptive=True, use_directio=False, prefetch=False, max_performance=False):
        if chunk_size < 4096 or chunk_size > 128*1024*1024:
            raise ValueError("chunk_size must be between 4KB and 128MB")
        self.throttle_bps = throttle_bps if (throttle_bps is None or throttle_bps > 0) else None
        self.chunk_size = chunk_size
        self.fsync_interval = max(1, fsync_interval)  # seconds between fsyncs
        self.logger = logger or logging.getLogger('DiskWriter')
        self._lock = threading.Lock()
class DiskWriter:
    """
    Efficient, thread-safe, optionally throttled disk writing utility for large files and streaming data.
    Handles chunked writes, adaptive buffering, throttling, error recovery, and resource management.
    Usage:
        with DiskWriter(...) as writer:
            writer.write(f, data)
    """
    def __init__(self, throttle_bps=None, chunk_size=1024*1024, fsync_interval=5, logger=None, adaptive=True, use_directio=False, prefetch=False, max_performance=False):
        if chunk_size < 4096 or chunk_size > 128*1024*1024:
            raise ValueError("chunk_size must be between 4KB and 128MB")
        self.throttle_bps = throttle_bps if (throttle_bps is None or throttle_bps > 0) else None
        self.chunk_size = chunk_size
        self.fsync_interval = max(1, fsync_interval)  # seconds between fsyncs
        self.logger = logger or logging.getLogger('DiskWriter')
        self._lock = threading.Lock()
        self.adaptive = adaptive
        self.use_directio = use_directio
        self.prefetch = prefetch
        self.max_performance = max_performance
        if max_performance:
            self.throttle_bps = None
            self.adaptive = True
            self.prefetch = True
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self._closed = True
        # No resources to release, but method is here for API completeness

    def write(self, f, data):
        """
        Write bytes or file-like object to file object f efficiently, with adaptive chunking and optional direct I/O.
        Raises ValueError for invalid input, OSError for disk errors.
        Returns total bytes written.
        """
        if self._closed:
            raise RuntimeError("DiskWriter is closed")
        if not hasattr(f, 'write') or not hasattr(f, 'flush'):
            raise ValueError("f must be a writable file-like object")
        last_fsync = time.time()
        total_written = 0
        chunk_size = self.chunk_size
        min_chunk = 64 * 1024
        max_chunk = 8 * 1024 * 1024
        last_time = time.time()
        last_bytes = 0
        offset = 0
        def get_chunk():
            if hasattr(data, 'read'):
                try:
                    return data.read(chunk_size)
                except Exception as e:
                    self.logger.error(f"Error reading from stream: {e}")
                    raise
            elif isinstance(data, (bytes, bytearray)):
                nonlocal offset
                if offset >= len(data):
                    return b''
                chunk = data[offset:offset+chunk_size]
                offset += len(chunk)
                return chunk
            else:
                raise ValueError("Unsupported data type for DiskWriter.write")
        # Optionally use direct I/O (Windows: FILE_FLAG_NO_BUFFERING, Linux: O_DIRECT)
        # Not implemented here for cross-platform safety, but can be added if needed
        if self.prefetch and hasattr(data, 'read'):
            import queue
            q = queue.Queue(maxsize=2)
            stop = object()
            def prefetcher():
                while True:
                    try:
                        chunk = data.read(chunk_size)
                        q.put(chunk)
                        if not chunk:
                            break
                    except Exception as e:
                        self.logger.error(f"Prefetch error: {e}")
                        q.put(b'')
                        break
            t = threading.Thread(target=prefetcher, daemon=True)
            t.start()
            def get_chunk():
                chunk = q.get()
                return chunk
        try:
            while True:
                chunk = get_chunk()
                if not chunk:
                    break
                self._write_chunk(f, chunk)
                total_written += len(chunk)
                now = time.time()
                # Adaptive chunk size logic: increase if fast, decrease if slow
                if self.adaptive and now - last_time > 0.5:
                    speed = (total_written - last_bytes) / (now - last_time)
                    target_time = 0.3
                    new_chunk = int(speed * target_time)
                    new_chunk = max(min_chunk, min(max_chunk, new_chunk))
                    if abs(new_chunk - chunk_size) > min_chunk:
                        chunk_size = new_chunk
                    last_time = now
                    last_bytes = total_written
                if self.throttle_bps:
                    time.sleep(len(chunk) / self.throttle_bps)
                if time.time() - last_fsync > self.fsync_interval:
                    try:
                        os.fsync(f.fileno())
                    except Exception as e:
                        self.logger.debug(f"fsync failed: {e}")
                    last_fsync = time.time()
            try:
                os.fsync(f.fileno())
            except Exception as e:
                self.logger.debug(f"Final fsync failed: {e}")
            return total_written
        except Exception as e:
            self.logger.error(f"Disk write failed: {e}")
            raise

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
        # Optionally flush logs or stats here if needed
        Returns True on success, False on failure.
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
                f.flush()
            except Exception as e:
                self.logger.error(f"Disk write failed: {e}")
                raise

    def safe_write(self, path, data, mode='wb', retries=3):
        """
        Write to a file path with retries and atomic replacement.
        Returns True on success, False on failure.
        """
        tmp_path = path + ".part"
        for attempt in range(retries):
            try:
                with open(tmp_path, mode) as f:
                    self.write(f, data)
                os.replace(tmp_path, path)
                self.logger.info(f"safe_write succeeded for {path} on attempt {attempt+1}")
                return True
            except Exception as e:
                self.logger.warning(f"Write attempt {attempt+1} failed: {e}")
                time.sleep(1)
        self.logger.error(f"Failed to write {path} after {retries} attempts.")
        return False
