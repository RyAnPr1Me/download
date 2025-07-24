import psutil
import threading
import time
import logging

# Utility functions for resource and process monitoring

LARGE_DOWNLOADERS = ['Steam.exe', 'XboxApp.exe', 'EpicGamesLauncher.exe']
SMALL_DOWNLOAD_THRESHOLD = 1 * 1024 * 1024 * 1024  # 1GB

class DownloadProcessInfo:
    def __init__(self, pid, name, total_bytes):
        self.pid = pid
        self.name = name
        self.total_bytes = total_bytes

class ThrottleUtils:
    def get_available_bandwidth(self, interval=1.0):
        """
        Measures the actual available network bandwidth (bytes/sec) over the given interval.
        Returns: measured bandwidth in bytes/sec (float)
        """
        net1 = psutil.net_io_counters()
        time.sleep(interval)
        net2 = psutil.net_io_counters()
        bytes_sent = net2.bytes_sent - net1.bytes_sent
        bytes_recv = net2.bytes_recv - net1.bytes_recv
        total_bytes = bytes_sent + bytes_recv
        bandwidth = total_bytes / interval
        self.logger.debug(f"Measured available bandwidth: {bandwidth} bytes/sec over {interval}s")
        return bandwidth
    def __init__(self):
        self.logger = logging.getLogger('ThrottleUtils')

    def get_active_downloads(self):
        """
        Returns a list of DownloadProcessInfo for known downloaders.
        """
        downloads = []
        for proc in psutil.process_iter(['pid', 'name', 'io_counters']):
            try:
                if proc.info['name'] in LARGE_DOWNLOADERS:
                    io = proc.info.get('io_counters')
                    if io:
                        total_bytes = io.read_bytes + io.write_bytes
                        downloads.append(DownloadProcessInfo(proc.info['pid'], proc.info['name'], total_bytes))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return downloads

    def classify_downloads(self, downloads):
        """
        Classifies downloads as large or small based on threshold.
        Returns: (large: list, small: list)
        """
        large = []
        small = []
        for d in downloads:
            if d.total_bytes >= SMALL_DOWNLOAD_THRESHOLD:
                large.append(d)
            else:
                small.append(d)
        return large, small

    def get_system_load(self):
        """
        Returns a dict with CPU, RAM, disk, and network usage.
        """
        return {
            'cpu': psutil.cpu_percent(),
            'ram': psutil.virtual_memory().percent,
            'disk': psutil.disk_usage('/').percent,
            'net': psutil.net_io_counters().bytes_sent + psutil.net_io_counters().bytes_recv,
            'bandwidth': self.get_available_bandwidth(0.5)  # quick sample for GUI/stats
        }

# Example usage
if __name__ == "__main__":
    utils = ThrottleUtils()
    downloads = utils.get_active_downloads()
    large, small = utils.classify_downloads(downloads)
    print(f"Large: {[d.name for d in large]}")
    print(f"Small: {[d.name for d in small]}")
    print(f"System load: {utils.get_system_load()}")
