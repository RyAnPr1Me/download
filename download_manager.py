import base64
import shutil
import threading
from urllib.parse import urlparse
try:
    import paramiko  # For SFTP
except ImportError:
    paramiko = None
try:
    import smbclient  # For SMB
except ImportError:
    smbclient = None
try:
    import libtorrent as lt
    HAS_TORRENT = True
except ImportError:
    HAS_TORRENT = False

import os
import socket
import time
import requests
import logging
from virus_check_utils import scan_if_unsigned
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import threading  # Ensure threading is imported for all uses

# IPC client config

IPC_HOST = '127.0.0.1'
IPC_PORT = 54321
# Shared secret for local IPC authentication
import os
import json
IPC_AUTH_TOKEN = os.environ.get('THROTTLE_IPC_TOKEN', 'changeme-secret-token')


CHUNK_SIZE = 1024 * 1024  # 1MB

# Disk write utility for robust, optionally throttled writes
def disk_write_util(f, data, throttle_bps=None, chunk_size=CHUNK_SIZE):
    """
    Write data to file object f in chunks, optionally throttling to throttle_bps (bytes/sec).
    Accepts bytes or file-like object (for streaming).
    """
    import time
    if hasattr(data, 'read'):
        # Stream from file-like
        while True:
            chunk = data.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            f.flush()
            if throttle_bps:
                time.sleep(len(chunk) / throttle_bps)
    elif isinstance(data, (bytes, bytearray)):
        total = len(data)
        offset = 0
        while offset < total:
            chunk = data[offset:offset+chunk_size]
            f.write(chunk)
            f.flush()
            if throttle_bps:
                time.sleep(len(chunk) / throttle_bps)
            offset += len(chunk)
    else:
        raise ValueError("Unsupported data type for disk_write_util")

class DownloadManager:
    def download_ftp(self):
        from ftplib import FTP
        parsed = urlparse(self.url)
        ftp = FTP(parsed.hostname)
        if parsed.username:
            ftp.login(parsed.username, parsed.password or '')
        else:
            ftp.login()
        with open(self.dest, 'wb') as f:
            def callback(data):
                disk_write_util(f, data, throttle_bps=self.get_bandwidth_limit())
            ftp.retrbinary(f'RETR {parsed.path}', callback)
        ftp.quit()
        logging.info(f"FTP download complete: {self.dest}")
        if self.virus_check:
            try:
                scan_if_unsigned(self.dest)
            except Exception as e:
                logging.error(f"Virus scan failed: {e}")
        self.cleanup_temp_files()
        self.spin_down()

    def download_sftp(self):
        if not paramiko:
            logging.error("paramiko is not installed. SFTP not supported.")
            return
        parsed = urlparse(self.url)
        transport = paramiko.Transport((parsed.hostname, parsed.port or 22))
        transport.connect(username=parsed.username, password=parsed.password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        with open(self.dest, 'wb') as out_f:
            with sftp.open(parsed.path, 'rb') as in_f:
                disk_write_util(out_f, in_f, throttle_bps=self.get_bandwidth_limit())
        sftp.close()
        transport.close()
        logging.info(f"SFTP download complete: {self.dest}")
        if self.virus_check:
            try:
                scan_if_unsigned(self.dest)
            except Exception as e:
                logging.error(f"Virus scan failed: {e}")
        self.cleanup_temp_files()
        self.spin_down()

    def download_smb(self):
        if not smbclient:
            logging.error("smbclient is not installed. SMB not supported.")
            return
        parsed = urlparse(self.url)
        with smbclient.open_file(self.url, mode='rb') as src, open(self.dest, 'wb') as dst:
            disk_write_util(dst, src, throttle_bps=self.get_bandwidth_limit())
        logging.info(f"SMB download complete: {self.dest}")
        if self.virus_check:
            try:
                scan_if_unsigned(self.dest)
            except Exception as e:
                logging.error(f"Virus scan failed: {e}")
        self.cleanup_temp_files()
        self.spin_down()

    def download_file_url(self):
        parsed = urlparse(self.url)
        src_path = parsed.path
        with open(src_path, 'rb') as src, open(self.dest, 'wb') as dst:
            disk_write_util(dst, src, throttle_bps=self.get_bandwidth_limit())
        logging.info(f"File URL copy complete: {self.dest}")
        if self.virus_check:
            try:
                scan_if_unsigned(self.dest)
            except Exception as e:
                logging.error(f"Virus scan failed: {e}")
        self.cleanup_temp_files()
        self.spin_down()

    def download_data_url(self):
        # data:[<mediatype>][;base64],<data>
        header, encoded = self.url.split(',', 1)
        if ';base64' in header:
            data = base64.b64decode(encoded)
        else:
            data = encoded.encode()
        with open(self.dest, 'wb') as f:
            disk_write_util(f, data, throttle_bps=self.get_bandwidth_limit())
        logging.info(f"Data URL download complete: {self.dest}")
        if self.virus_check:
            try:
                scan_if_unsigned(self.dest)
            except Exception as e:
                logging.error(f"Virus scan failed: {e}")
        self.cleanup_temp_files()
        self.spin_down()
    def is_torrent(self):
        # Detect if the URL is a magnet link or a .torrent file
        return (self.url.startswith('magnet:') or self.url.endswith('.torrent'))

    def download_torrent(self):
        """Download a torrent file using libtorrent if available."""
        # Optional dependency: libtorrent (python-libtorrent)
        import libtorrent as lt
        ses = lt.session()
        ses.listen_on(6881, 6891)
        info = lt.torrent_info(self.url)
        params = { 'save_path': os.path.dirname(self.dest), 'ti': info }
        h = ses.add_torrent(params)
        logging.info(f"Starting torrent download: {self.url}")
        while not h.is_seed():
            s = h.status()
            logging.info(f"Torrent progress: {s.progress * 100:.2f}%")
            time.sleep(1)
        # Move to final destination
        for f in info.files():
            src = os.path.join(os.path.dirname(self.dest), f.path)
            dst = os.path.join(self.dest, f.path)
            os.rename(src, dst)
        logging.info(f"Torrent download complete: {self.dest}")
        if self.virus_check:
            scan_if_unsigned(self.dest)
        self.cleanup_temp_files()
        self.spin_down()
        ses = lt.session()
        ses.listen_on(6881, 6891)
        params = { 'save_path': os.path.dirname(self.dest) or '.', 'storage_mode': lt.storage_mode_t(2) }
        if self.url.startswith('magnet:'):
            h = lt.add_magnet_uri(ses, self.url, params)
        else:
            info = lt.torrent_info(self.url)
            h = ses.add_torrent({'ti': info, 'save_path': params['save_path']})
        logging.info(f"Starting torrent download: {self.url}")
        pbar = None
        while not h.is_seed():
            s = h.status()
            if not pbar:
                pbar = tqdm(total=s.total_wanted, unit='B', unit_scale=True, desc=os.path.basename(self.dest))
            pbar.n = s.total_done
            pbar.refresh()
            # Throttle bandwidth if needed
            bw = self.get_bandwidth_limit()
            if bw:
                ses.set_download_rate_limit(int(bw))
            else:
                ses.set_download_rate_limit(0)
            time.sleep(1)
        if pbar:
            pbar.close()
        # Move the largest file to self.dest
        files = h.get_torrent_info().files()
        largest = max(range(files.num_files()), key=lambda i: files.file_size(i))
        src_path = os.path.join(params['save_path'], files.file_path(largest))
        try:
            os.rename(src_path, self.dest)
            logging.info(f"Torrent download complete: {self.dest}")
        except Exception as e:
            logging.error(f"Failed to move torrent file: {e}")
        if self.virus_check:
            try:
                scan_if_unsigned(self.dest)
            except Exception as e:
                logging.error(f"Virus scan failed: {e}")
        self.cleanup_temp_files()
        self.spin_down()
    def cleanup_temp_files(self):
        """Remove any leftover temp files from partial/incomplete downloads."""
        temp_files = [self.dest + ".part", self.dest + ".tmp", self.dest + ".meta"]
        for f in temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
                    logging.info(f"Removed temp file: {f}")
            except Exception as e:
                logging.warning(f"Failed to remove temp file {f}: {e}")

    def __init__(self, url, dest, virus_check=True, threads=1, manual_bandwidth=None, mode='auto', status=False):
        self.url = url
        self.dest = dest
        self.virus_check = virus_check
        self.threads = threads
        self.manual_bandwidth = manual_bandwidth
        self.mode = mode
        self.status = status
        self.idle_event = threading.Event()
        self.shutdown_event = threading.Event()
        self.last_activity = time.time()
        self.logger = logging.getLogger('DownloadManager')

    def get_bandwidth_limit(self):
        """Get bandwidth limit from throttler service or use manual override."""
        if self.manual_bandwidth:
            return self.manual_bandwidth
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((IPC_HOST, IPC_PORT))
                payload = {
                    'token': IPC_AUTH_TOKEN,
                    'event': 'BANDWIDTH_QUERY',
                    'data': {'pid': os.getpid(), 'url': self.url, 'dest': self.dest}
                }
                msg = json.dumps(payload).encode()
                s.sendall(msg)
                data = s.recv(65536)
                resp = json.loads(data.decode())
                return resp.get('bandwidth', None)
        except Exception as e:
            self.logger.warning(f"Could not query throttler for bandwidth: {e}")
            return None

    def download(self):
        """Main download entry point. Handles all supported protocols and reports events."""
        parsed = urlparse(self.url)
        scheme = parsed.scheme.lower()
        # Write .meta file for monitor correlation
        try:
            meta = {
                'url': self.url,
                'dest': self.dest,
                'ctime': time.time(),
                'pid': os.getpid(),
                'protocol': scheme
            }
            with open(self.dest + '.meta', 'w') as mf:
                json.dump(meta, mf)
        except Exception as e:
            self.logger.warning(f"Failed to write .meta file: {e}")

        try:
            if self.is_torrent():
                self.download_torrent()
                return
            if scheme in ('ftp', 'ftps'):
                self.download_ftp()
                return
            if scheme == 'sftp':
                self.download_sftp()
                return
            if scheme == 'smb':
                self.download_smb()
                return
            if scheme == 'file':
                self.download_file_url()
                return
            if self.url.startswith('data:'):
                self.download_data_url()
                return
            # Default: HTTP/HTTPS
            total_size = 0
            try:
                import requests
                with requests.get(self.url, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    total_size = int(r.headers.get('content-length', 0))
            except Exception as e:
                self.logger.error(f"Failed to get HTTP headers: {e}")
                total_size = 0
            if self.status:
                self.print_status()
            if self.threads > 1 and total_size > 0:
                self._download_multithreaded(total_size)
            else:
                self._download_singlethreaded(total_size)
            if self.virus_check:
                try:
                    scan_if_unsigned(self.dest)
                except Exception as e:
                    self.logger.error(f"Virus scan failed: {e}")
            self.cleanup_temp_files()
            self.spin_down()
        except Exception as e:
            self.logger.error(f"Download failed: {e}")
            self.cleanup_temp_files()
            self.spin_down()

    def spin_down(self):
        """Enter idle/background mode. Wait for new download event via IPC or shutdown."""
        def idle_loop():
            self.logger.info("DownloadManager entering idle/background mode.")
            # Listen for IPC events to wake up
            while not self.shutdown_event.is_set():
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(60)
                        s.connect((IPC_HOST, IPC_PORT))
                        payload = {
                            'token': IPC_AUTH_TOKEN,
                            'event': 'IDLE_WAIT',
                            'data': {'pid': os.getpid()}
                        }
                        msg = json.dumps(payload).encode()
                        s.sendall(msg)
                        data = s.recv(4096)
                        resp = json.loads(data.decode())
                        if resp.get('event') == 'WAKE_DOWNLOAD':
                            self.logger.info("Received new download event. Waking up.")
                            self.idle_event.set()
                            break
                except socket.timeout:
                    continue
                except Exception as e:
                    self.logger.warning(f"Idle wait failed: {e}")
                    time.sleep(10)
        t = threading.Thread(target=idle_loop, daemon=True)
        t.start()

    def print_status(self):
        # Query throttler for current state using authenticated IPC
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((IPC_HOST, IPC_PORT))
                payload = {
                    'token': IPC_AUTH_TOKEN,
                    'event': 'GUI',
                    'data': None
                }
                msg = json.dumps(payload).encode()
                s.sendall(msg)
                data = s.recv(65536)
                state = json.loads(data.decode())
                print("\n--- Throttler Status ---")
                print(f"Current bandwidth allocation: {state.get('bandwidth', 'N/A')} bytes/s")
                print("Detected downloads:")
                for d in state.get('downloads', []):
                    print(f"  {d['name']} (pid={d['pid']}): {d.get('bw','?')} bytes/s ({d.get('bw_percent','?')}%) [score={d.get('score',0):.2f}]")
                print(f"Priority overrides: {state.get('priority_overrides', {})}")
                print("------------------------\n")
        except Exception as e:
            print(f"[Status] Could not retrieve throttler status: {e}")

    def _download_singlethreaded(self, total_size):
        # Adaptive chunk sizing: start small, increase if bandwidth is high, decrease if slow
        min_chunk = 64 * 1024  # 64KB
        max_chunk = 8 * 1024 * 1024  # 8MB
        chunk_size = CHUNK_SIZE
        try:
            with requests.get(self.url, stream=True) as r, open(self.dest, 'wb') as f, tqdm(
                total=total_size, unit='B', unit_scale=True, desc=os.path.basename(self.dest)) as pbar:
                r.raise_for_status()
                last_time = time.time()
                last_bytes = 0
                chunk_size = CHUNK_SIZE
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if not self.running:
                        break
                    disk_write_util(f, chunk, throttle_bps=self.get_bandwidth_limit(), chunk_size=chunk_size)
                    pbar.update(len(chunk))
                    # Adaptive chunk size logic
                    now = time.time()
                    elapsed = now - last_time
                    if elapsed > 0.5:
                        speed = (pbar.n - last_bytes) / elapsed
                        # Adjust chunk size based on speed (target: 0.2-0.5s per chunk)
                        if speed > 0:
                            target_time = 0.3
                            new_chunk = int(speed * target_time)
                            new_chunk = max(64 * 1024, min(8 * 1024 * 1024, new_chunk))
                            if abs(new_chunk - chunk_size) > 64 * 1024:
                                chunk_size = new_chunk
                        last_time = now
                        last_bytes = pbar.n
        except Exception as e:
            logging.error(f"Download failed: {e}")

    def _download_multithreaded(self, total_size):
        # Multi-threaded download using HTTP Range requests
        def download_range(start, end, idx):
            headers = {'Range': f'bytes={start}-{end}'}
            try:
                r = requests.get(self.url, headers=headers, stream=True)
                r.raise_for_status()
                return idx, r.content
            except Exception as e:
                logging.error(f"Thread {idx} failed: {e}")
                return idx, b''
        part_size = total_size // self.threads
        ranges = [(i * part_size, (i + 1) * part_size - 1 if i < self.threads - 1 else total_size - 1, i)
                  for i in range(self.threads)]
        results = [None] * self.threads
        with ThreadPoolExecutor(max_workers=self.threads) as executor, tqdm(
            total=total_size, unit='B', unit_scale=True, desc=os.path.basename(self.dest)) as pbar:
            futures = {executor.submit(download_range, start, end, idx): idx for start, end, idx in ranges}
            for future in as_completed(futures):
                idx, data = future.result()
                results[idx] = data
                pbar.update(len(data))
        try:
            with open(self.dest, 'wb') as f:
                for part in results:
                    if part:
                        disk_write_util(f, part, throttle_bps=self.get_bandwidth_limit())
        except Exception as e:
            logging.error(f"Failed to write file: {e}")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
        handlers=[
            logging.FileHandler("download_manager.log"),
            logging.StreamHandler()
        ]
    )
    import argparse
    parser = argparse.ArgumentParser(description="Advanced Download Manager")
    parser.add_argument('url', help='Download URL')
    parser.add_argument('dest', help='Destination file path')
    parser.add_argument('--threads', type=int, default=1, help='Number of download threads (for large files)')
    parser.add_argument('--no-virus-check', action='store_true', help='Disable virus scan after download')
    parser.add_argument('--bandwidth', type=int, default=None, help='Manual bandwidth limit in bytes/sec (overrides throttler if set)')
    parser.add_argument('--mode', choices=['auto', 'manual'], default='auto', help='Throttling mode: auto (use service) or manual (fixed bandwidth)')
    parser.add_argument('--status', action='store_true', help='Show current throttling status and exit')
    args = parser.parse_args()
    dm = DownloadManager(
        args.url,
        args.dest,
        virus_check=not args.no_virus_check,
        threads=args.threads,
        manual_bandwidth=args.bandwidth,
        mode=args.mode,
        status=args.status
    )
    if args.status:
        dm.print_status()
    else:
        dm.download()
