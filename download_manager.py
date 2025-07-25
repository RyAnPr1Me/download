
import os
import requests
import socket
import time
import logging
import threading
import base64
import json
import shutil
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
    lt = None
    HAS_TORRENT = False
from virus_check_utils import scan_if_unsigned
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from disk_writer import DiskWriter

# --- DownloadManager class definition ---


# --- DownloadManager Takeover Server ---
TAKEOVER_PORT = 54323
# Set this token securely in your environment for production use!
TAKEOVER_TOKEN = os.environ.get('THROTTLE_IPC_TOKEN', 'super-secure-random-token-2025')

# Track active downloads by dest path
active_downloads = {}

def handle_takeover(conn):
    try:
        data = conn.recv(4096)
        req = json.loads(data.decode())
        if req.get('token') != TAKEOVER_TOKEN:
            conn.sendall(b'{"status":"error","msg":"auth failed"}')
            return
        url = req.get('url')
        file_path = req.get('file_path')
        pid = req.get('pid')
        # Kill the original process if a valid PID is provided
        if pid is not None:
            try:
                import psutil
                p = psutil.Process(int(pid))
                p.terminate()
                try:
                    p.wait(timeout=5)
                except Exception:
                    p.kill()
                msg = f"Killed process {pid} before takeover."
                print(f"[Takeover] {msg}")
            except Exception as e:
                print(f"[Takeover] Failed to kill process {pid}: {e}")

        # If url is available, check if a download is already in progress for this dest
        if url:
            dest = file_path or os.path.basename(url.split('?')[0])
            # If already downloading this dest, update the process
            mgr = active_downloads.get(dest)
            if mgr:
                # Update parameters if needed (e.g., url, virus_check, etc.)
                print(f"[Takeover] Updating existing download for {dest}")
                mgr.url = url
                # Optionally update other parameters here
                # You could also implement a method to update bandwidth, threads, etc.
                conn.sendall(b'{"status":"ok","msg":"updated existing download"}')
            else:
                try:
                    mgr = DownloadManager(url, dest)
                    active_downloads[dest] = mgr
                    mgr.download()
                    del active_downloads[dest]
                    conn.sendall(b'{"status":"ok","msg":"downloaded"}')
                except Exception as e:
                    if dest in active_downloads:
                        del active_downloads[dest]
                    conn.sendall(json.dumps({"status":"error","msg":str(e)}).encode())
        elif file_path:
            # Scan/move file, apply security checks
            try:
                scan_if_unsigned(file_path)
                conn.sendall(b'{"status":"ok","msg":"scanned"}')
            except Exception as e:
                conn.sendall(json.dumps({"status":"error","msg":str(e)}).encode())
        else:
            conn.sendall(b'{"status":"error","msg":"no url or file_path"}')
    except Exception as e:
        try:
            conn.sendall(json.dumps({"status":"error","msg":str(e)}).encode())
        except Exception:
            pass
    finally:
        conn.close()

def start_takeover_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('127.0.0.1', TAKEOVER_PORT))
    s.listen(5)
    print(f"[DownloadManager] Takeover server listening on {TAKEOVER_PORT}")
    while True:
        conn, _ = s.accept()
        threading.Thread(target=handle_takeover, args=(conn,), daemon=True).start()

class DownloadManager:
    def _auto_tune(self, total_size):
        import multiprocessing
        cpu_count = multiprocessing.cpu_count()
        if total_size >= 2 * 1024 * 1024 * 1024:
            threads = min(32, cpu_count * 2)
            chunk_size = 8 * 1024 * 1024
        elif total_size >= 512 * 1024 * 1024:
            threads = min(16, cpu_count)
            chunk_size = 4 * 1024 * 1024
        else:
            threads = min(8, cpu_count)
            chunk_size = 1 * 1024 * 1024
        return threads, chunk_size

    def download(self):
        parsed = urlparse(self.url)
        scheme = parsed.scheme.lower()
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
            total_size = 0
            try:
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

    def download_ftp(self):
        from ftplib import FTP
        parsed = urlparse(self.url)
        ftp = FTP(parsed.hostname)
        if parsed.username:
            ftp.login(parsed.username, parsed.password or '')
        else:
            ftp.login()
        writer = self._get_disk_writer()
        with open(self.dest, 'wb') as f:
            def callback(data):
                writer.write(f, data)
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
        writer = self._get_disk_writer()
        with open(self.dest, 'wb') as out_f:
            with sftp.open(parsed.path, 'rb') as in_f:
                writer.write(out_f, in_f)
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
        writer = self._get_disk_writer()
        with smbclient.open_file(self.url, mode='rb') as src, open(self.dest, 'wb') as dst:
            writer.write(dst, src)
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
        writer = self._get_disk_writer()
        with open(src_path, 'rb') as src, open(self.dest, 'wb') as dst:
            writer.write(dst, src)
        logging.info(f"File URL copy complete: {self.dest}")
        if self.virus_check:
            try:
                scan_if_unsigned(self.dest)
            except Exception as e:
                logging.error(f"Virus scan failed: {e}")
        self.cleanup_temp_files()
        self.spin_down()

    def download_data_url(self):
        header, encoded = self.url.split(',', 1)
        if ';base64' in header:
            data = base64.b64decode(encoded)
        else:
            data = encoded.encode()
        writer = self._get_disk_writer()
        with open(self.dest, 'wb') as f:
            writer.write(f, data)
        logging.info(f"Data URL download complete: {self.dest}")
        if self.virus_check:
            try:
                scan_if_unsigned(self.dest)
            except Exception as e:
                logging.error(f"Virus scan failed: {e}")
        self.cleanup_temp_files()
        self.spin_down()

    def download_torrent(self):
        if not lt:
            logging.error("libtorrent is not installed. Torrent support is unavailable.")
            return
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
        for f in info.files():
            src = os.path.join(os.path.dirname(self.dest), f.path)
            dst = os.path.join(self.dest, f.path)
            os.rename(src, dst)
        logging.info(f"Torrent download complete: {self.dest}")
        if self.virus_check:
            scan_if_unsigned(self.dest)
        self.cleanup_temp_files()
        self.spin_down()

    def cleanup_temp_files(self):
        temp_files = [self.dest + ".part", self.dest + ".tmp", self.dest + ".meta"]
        for f in temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
                    logging.info(f"Removed temp file: {f}")
            except Exception as e:
                logging.warning(f"Failed to remove temp file {f}: {e}")

    def spin_down(self):
        self.logger.info("DownloadManager entering idle/background mode.")
        # Placeholder for actual idle logic

    def print_status(self):
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
        min_chunk = 64 * 1024
        max_chunk = 8 * 1024 * 1024
        chunk_size = CHUNK_SIZE
        writer = self._get_disk_writer()
        try:
            with requests.get(self.url, stream=True, verify=False) as r, open(self.dest, 'wb') as f, tqdm(
                total=total_size, unit='B', unit_scale=True, desc=os.path.basename(self.dest)) as pbar:
                r.raise_for_status()
                last_time = time.time()
                last_bytes = 0
                chunk_size = CHUNK_SIZE
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if not self.running:
                        break
                    writer.write(f, chunk)
                    pbar.update(len(chunk))
                    now = time.time()
                    elapsed = now - last_time
                    if elapsed > 0.5:
                        speed = (pbar.n - last_bytes) / elapsed
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
        import httpx
        threads, chunk_size = self._auto_tune(total_size)
        if self.mode == 'max_speed':
            threads = max(32, threads)
            chunk_size = max(8 * 1024 * 1024, chunk_size)
        url = self.url
        results = [None] * threads
        ranges = [(i * (total_size // threads), (i + 1) * (total_size // threads) - 1 if i < threads - 1 else total_size - 1, i)
                  for i in range(threads)]
        def download_range(start, end, idx):
            headers = {'Range': f'bytes={start}-{end}'}
            try:
                with httpx.Client(http2=True, timeout=30, verify=False) as client:
                    r = client.get(url, headers=headers)
                    r.raise_for_status()
                    return idx, r.content
            except Exception as e:
                logging.error(f"Thread {idx} failed: {e}")
                try:
                    r = requests.get(url, headers=headers, stream=True, timeout=30, verify=False)
                    r.raise_for_status()
                    return idx, r.content
                except Exception as e2:
                    logging.error(f"Thread {idx} fallback failed: {e2}")
                    return idx, b''
        with ThreadPoolExecutor(max_workers=threads) as executor, tqdm(
            total=total_size, unit='B', unit_scale=True, desc=os.path.basename(self.dest)) as pbar:
            futures = {executor.submit(download_range, start, end, idx): idx for start, end, idx in ranges}
            for future in as_completed(futures):
                idx, data = future.result()
                results[idx] = data
                pbar.update(len(data))
        try:
            writer = self._get_disk_writer()
            with open(self.dest, 'wb') as f:
                for part in results:
                    if part:
                        writer.write(f, part)
        except Exception as e:
            logging.error(f"Failed to write file: {e}")

    def _get_disk_writer(self):
        return DiskWriter()
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
        self.running = True

    def is_torrent(self):
        return (self.url.startswith('magnet:') or self.url.endswith('.torrent'))

    # Add all other methods here as needed (auto_tune, download_ftp, download_sftp, download_smb, download_file_url, download_data_url, download_torrent, cleanup_temp_files, download, spin_down, print_status, _download_singlethreaded, _download_multithreaded)

    # For brevity, only the class skeleton and is_torrent are restored here. The rest of the methods should be restored from previous working versions if needed.



# Cleaned up imports
import os
import requests
import socket
import time
import logging
import threading
import base64
import json
import shutil
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
    lt = None
    HAS_TORRENT = False
from virus_check_utils import scan_if_unsigned
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from disk_writer import DiskWriter

CHUNK_SIZE = 1024 * 1024  # 1MB default chunk size
# Placeholders for IPC constants (define these elsewhere as needed)
IPC_HOST = '127.0.0.1'
IPC_PORT = 5000
IPC_AUTH_TOKEN = 'changeme'

# --- Main entrypoint: start takeover server if run as main ---
if __name__ == "__main__":
    threading.Thread(target=start_takeover_server, daemon=True).start()
    # Optionally, you can add CLI/interactive logic here, or just keep the server running
    print("[DownloadManager] Ready for takeover requests.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("[DownloadManager] Shutting down.")
