import os
import threading
import time
import logging

class DiskWriter:
    """
    Efficient, thread-safe, optionally throttled disk writing utility for large files and streaming data.
    Handles chunked writes, adaptive buffering, throttling, and error recovery.
    """
    def __init__(self, throttle_bps=None, chunk_size=1024*1024, fsync_interval=5, logger=None, adaptive=True, use_directio=False, prefetch=False, max_performance=False):
        self.throttle_bps = throttle_bps
        self.chunk_size = chunk_size
        self.fsync_interval = fsync_interval  # seconds between fsyncs
        self.logger = logger or logging.getLogger('DiskWriter')
        self._lock = threading.Lock()
        self.adaptive = adaptive
        self.use_directio = use_directio
        self.prefetch = prefetch
        self.max_performance = max_performance
        if max_performance:
            self.throttle_bps = None
            self.chunk_size = 8 * 1024 * 1024
            self.fsync_interval = 60  # fsync rarely

    def write(self, f, data):
        """
        Write bytes or file-like object to file object f efficiently, with adaptive chunking and optional direct I/O.
        Improved error handling and logging.
        """
        last_fsync = time.time()
        total_written = 0
        chunk_size = self.chunk_size
        min_chunk = 64 * 1024
        max_chunk = 8 * 1024 * 1024
        if self.max_performance:
            chunk_size = max_chunk
        last_time = time.time()
        last_bytes = 0
        offset = 0
        def get_chunk():
            try:
                if hasattr(data, 'read'):
                    return data.read(chunk_size)
                elif isinstance(data, (bytes, bytearray, memoryview)):
                    nonlocal offset
                    if offset >= len(data):
                        return b''
                    mv = memoryview(data)[offset:offset+chunk_size]
                    offset += len(mv)
                    return mv.tobytes() if not isinstance(mv, bytes) else mv
                else:
                    raise ValueError("Unsupported data type for DiskWriter.write")
            except Exception as e:
                self.logger.error(f"Error getting chunk: {e}")
                raise
        # Optionally use direct I/O (Windows: FILE_FLAG_NO_BUFFERING, Linux: O_DIRECT)
        # Not implemented here for cross-platform safety, but can be added if needed
        if self.prefetch and hasattr(data, 'read'):
            try:
                import queue
                q = queue.Queue(maxsize=2)
                stop = object()
                def prefetcher():
                    try:
                        while True:
                            chunk = data.read(chunk_size)
                            q.put(chunk)
                            if not chunk:
                                break
                    except Exception as e:
                        self.logger.error(f"Prefetcher error: {e}")
                t = threading.Thread(target=prefetcher, daemon=True)
                t.start()
                def get_chunk():
                    try:
                        chunk = q.get()
                        return chunk
                    except Exception as e:
                        self.logger.error(f"Prefetch queue error: {e}")
                        return b''
            except Exception as e:
                self.logger.error(f"Prefetch setup error: {e}")
        try:
            while True:
                chunk = get_chunk()
                if not chunk:
                    break
                try:
                    self._write_chunk(f, chunk)
                except Exception as e:
                    self.logger.error(f"Write chunk failed: {e}")
                    raise
                total_written += len(chunk)
                now = time.time()
                # Adaptive chunk size logic: increase if fast, decrease if slow
                if self.adaptive and not self.max_performance and now - last_time > 0.5:
                    try:
                        speed = (total_written - last_bytes) / (now - last_time)
                        target_time = 0.3
                        new_chunk = int(speed * target_time)
                        new_chunk = max(min_chunk, min(max_chunk, new_chunk))
                        if abs(new_chunk - chunk_size) > min_chunk:
                            chunk_size = new_chunk
                        last_time = now
                        last_bytes = total_written
                    except Exception as e:
                        self.logger.debug(f"Adaptive chunk size error: {e}")
                if self.throttle_bps:
                    try:
                        time.sleep(len(chunk) / self.throttle_bps)
                    except Exception as e:
                        self.logger.debug(f"Throttle sleep error: {e}")
                if not self.max_performance and time.time() - last_fsync > self.fsync_interval:
                    try:
                        os.fsync(f.fileno())
                    except Exception as e:
                        self.logger.debug(f"fsync failed: {e}")
                    last_fsync = time.time()
            if not self.max_performance:
                try:
                    os.fsync(f.fileno())
                except Exception as e:
                    self.logger.debug(f"Final fsync failed: {e}")
            return total_written
        except Exception as e:
            self.logger.error(f"DiskWriter.write failed: {e}")
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
