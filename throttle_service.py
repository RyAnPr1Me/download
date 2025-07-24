import psutil
import time
import socket
import threading
import os
import sys
import logging
from throttle_utils import ThrottleUtils

# List of known large downloaders (add more as needed)
LARGE_DOWNLOADERS = ['Steam.exe', 'XboxApp.exe', 'EpicGamesLauncher.exe']
SMALL_DOWNLOAD_THRESHOLD = 1 * 1024 * 1024 * 1024  # 1GB in bytes

# IPC socket path (for Windows, use localhost TCP; for Linux, can use Unix socket)
IPC_HOST = '127.0.0.1'
IPC_PORT = 54321

class ThrottleService:
    def __init__(self):
        self.bandwidth_allocation = {'installer': None, 'other': None}
        self.running = True
        self.lock = threading.Lock()
        self.utils = ThrottleUtils()
        self.logger = logging.getLogger('ThrottleService')
        logging.basicConfig(level=logging.INFO)

    def detect_downloads(self):
        downloads = self.utils.get_active_downloads()
        large, small = self.utils.classify_downloads(downloads)
        return {'large': large, 'small': small}

    def calculate_bandwidth(self, downloads):
        # Enhanced intelligent bandwidth allocation using multiple factors
        # Use actual available bandwidth from ThrottleUtils
        available_bw = self.utils.get_available_bandwidth(1.0)
        if not available_bw or available_bw < 1_000_000:  # Fallback if measurement fails or is too low
            available_bw = 100 * 1024 * 1024  # 100MB/s default
        all_downloads = []
        # Factor weights (tune as needed)
        WEIGHT_PRIORITY = 0.5
        WEIGHT_SIZE = 0.2
        WEIGHT_TYPE = 0.2
        WEIGHT_ACTIVITY = 0.1
        # Helper to normalize size (log scale for fairness)
        def norm_size(sz):
            import math
            return math.log2(sz + 1) if sz > 0 else 0
        # Build download info with all factors
        for d in downloads['large']:
            prio = self.priority_overrides.get(d.pid, 3) if hasattr(self, 'priority_overrides') else 3
            size_factor = norm_size(d.total_bytes)
            type_factor = 2  # Large download
            activity_factor = 1  # Placeholder, could use I/O rate
            all_downloads.append({'pid': d.pid, 'name': d.name, 'size': d.total_bytes, 'priority': prio,
                                 'size_factor': size_factor, 'type_factor': type_factor, 'activity_factor': activity_factor})
        for d in downloads['small']:
            prio = self.priority_overrides.get(d.pid, 2) if hasattr(self, 'priority_overrides') else 2
            size_factor = norm_size(d.total_bytes)
            type_factor = 1  # Small download
            activity_factor = 1  # Placeholder
            all_downloads.append({'pid': d.pid, 'name': d.name, 'size': d.total_bytes, 'priority': prio,
                                 'size_factor': size_factor, 'type_factor': type_factor, 'activity_factor': activity_factor})
        prio = self.priority_overrides.get('installer', 2) if hasattr(self, 'priority_overrides') else 2
        size_factor = 0  # Installer size not tracked here
        type_factor = 1.5  # Installer gets medium type weight
        activity_factor = 1  # Placeholder
        all_downloads.append({'pid': 'installer', 'name': 'SecureInstaller', 'size': 0, 'priority': prio,
                             'size_factor': size_factor, 'type_factor': type_factor, 'activity_factor': activity_factor})
        # Calculate weighted score for each download
        for d in all_downloads:
            d['score'] = (
                WEIGHT_PRIORITY * d['priority'] +
                WEIGHT_SIZE * d['size_factor'] +
                WEIGHT_TYPE * d['type_factor'] +
                WEIGHT_ACTIVITY * d['activity_factor']
            )
        total_score = sum(d['score'] for d in all_downloads)
        # Allocate bandwidth as a percentage of total score
        for d in all_downloads:
            d['bw'] = int(available_bw * (d['score'] / total_score)) if total_score > 0 else 0
            d['bw_percent'] = round(100 * d['bw'] / available_bw, 2) if available_bw > 0 else 0
        # Find the installer allocation
        installer_bw = next((d['bw'] for d in all_downloads if d['pid'] == 'installer'), None)
        # Log allocations for transparency
        logger = logging.getLogger('ThrottleService')
        logger.info(f"[Bandwidth] Measured available: {available_bw:.2f} bytes/s")
        logger.info("Bandwidth allocations:")
        for d in all_downloads:
            logger.info(f"  {d['name']} (pid={d['pid']}): {d['bw']} bytes/s ({d['bw_percent']}%) [score={d['score']:.2f}]")
        # Add system resource stats for GUI
        sysload = self.utils.get_system_load()
        self.current_state = {
            'bandwidth': installer_bw,
            'downloads': all_downloads,
            'priority_overrides': getattr(self, 'priority_overrides', {}),
            'system_load': sysload
        }
        return {'installer': installer_bw, 'other': available_bw - installer_bw}

    def ipc_server(self):
        # Enhanced: respond to GUI requests with full state and allow priority updates
        import json
        IPC_AUTH_TOKEN = os.environ.get('THROTTLE_IPC_TOKEN', 'changeme-secret-token')
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((IPC_HOST, IPC_PORT))
                s.listen(5)
            except Exception as e:
                self.logger.critical(f"Failed to bind IPC socket: {e}")
                sys.exit(1)
            while self.running:
                try:
                    conn, addr = s.accept()
                except Exception as e:
                    self.logger.error(f"Socket accept error: {e}")
                    continue
                with conn:
                    try:
                        data = conn.recv(65536)
                        if not data:
                            continue
                        # Try to parse as JSON with token
                        try:
                            msg = json.loads(data.decode())
                            token = msg.get('token')
                            if token != IPC_AUTH_TOKEN:
                                self.logger.warning(f"IPC authentication failed from {addr}")
                                conn.sendall(b'AUTH_ERROR')
                                continue
                            event = msg.get('event')
                            if event == 'DOWNLOAD_EVENT':
                                info = msg.get('data', {})
                                if not hasattr(self, 'external_downloads'):
                                    self.external_downloads = []
                                self.external_downloads.append(info)
                                self.logger.info(f"Received download event: {info}")
                                conn.sendall(b'OK')
                                continue
                        except Exception:
                            # Not a JSON message, fall back to legacy protocol
                            pass
                        # Validate and sanitize input (legacy protocol)
                        if data.startswith(b'GUI_SET_PRIO:'):
                            try:
                                overrides = json.loads(data[len(b'GUI_SET_PRIO:'):].decode())
                                if not isinstance(overrides, dict):
                                    raise ValueError("Priority overrides must be a dict")
                                # Only allow int priorities in a safe range
                                for k, v in overrides.items():
                                    if not isinstance(v, int) or not (0 <= v <= 10):
                                        raise ValueError(f"Invalid priority value for {k}: {v}")
                                self.priority_overrides = overrides
                                conn.sendall(b'OK')
                            except Exception as e:
                                self.logger.error(f"Invalid priority override input: {e}")
                                conn.sendall(b'ERROR')
                        elif data.startswith(b'DOWNLOAD_EVENT:'):
                            try:
                                info = json.loads(data[len(b'DOWNLOAD_EVENT:'):].decode())
                                if not hasattr(self, 'external_downloads'):
                                    self.external_downloads = []
                                self.external_downloads.append(info)
                                self.logger.info(f"Received download event: {info}")
                                conn.sendall(b'OK')
                            except Exception as e:
                                self.logger.error(f"Invalid download event input: {e}")
                                conn.sendall(b'ERROR')
                        elif data.startswith(b'GUI_SET_CONFIG:'):
                            try:
                                config = json.loads(data[len(b'GUI_SET_CONFIG:'):].decode())
                                # Validate and apply config
                                bw = config.get('bandwidth')
                                threads = config.get('threads')
                                mode = config.get('mode')
                                # Store config in service (could be used in allocation logic)
                                self.gui_config = {
                                    'bandwidth': int(bw) if bw and str(bw).isdigit() else None,
                                    'threads': int(threads) if threads and str(threads).isdigit() else None,
                                    'mode': mode if mode in ('auto', 'manual') else 'auto'
                                }
                                conn.sendall(b'OK')
                                self.logger.info(f"GUI config updated: {self.gui_config}")
                            except Exception as e:
                                self.logger.error(f"Invalid GUI config input: {e}")
                                conn.sendall(b'ERROR')
                        elif data == b'GUI':
                            try:
                                state = getattr(self, 'current_state', {})
                                conn.sendall(json.dumps(state).encode())
                            except Exception as e:
                                self.logger.error(f"Failed to send GUI state: {e}")
                                conn.sendall(b'{}')
                        else:
                            with self.lock:
                                bw = self.bandwidth_allocation['installer']
                            conn.sendall(str(bw if bw else 'unlimited').encode())
                    except Exception as e:
                        self.logger.error(f"IPC error: {e}")

    def monitor_loop(self):
        try:
            while self.running:
                try:
                    downloads = self.detect_downloads()
                    allocation = self.calculate_bandwidth(downloads)
                    with self.lock:
                        self.bandwidth_allocation = allocation
                    self.logger.info(f"[ThrottleService] Allocation: {allocation}")
                except Exception as e:
                    self.logger.error(f"Monitor loop error: {e}")
                time.sleep(2)
        except Exception as e:
            self.logger.critical(f"Fatal error in monitor loop: {e}")
            self.running = False

    def start(self):
        # Watchdog: restart service if it crashes
        while True:
            try:
                t = threading.Thread(target=self.ipc_server, daemon=True)
                t.start()
                self.monitor_loop()
            except Exception as e:
                self.logger.critical(f"Service crashed: {e}. Restarting in 5 seconds...")
                time.sleep(5)
            if not self.running:
                break

if __name__ == "__main__":
    service = ThrottleService()
    try:
        service.start()
    except KeyboardInterrupt:
        service.running = False
        print("ThrottleService stopped.")
    except Exception as e:
        service.logger.critical(f"Fatal error in main: {e}")
        sys.exit(1)
