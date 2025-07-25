
import os
import tkinter as tk
from tkinter import ttk, messagebox
from download_manager import DownloadManager
import threading
import socket
import json

IPC_HOST = '127.0.0.1'
IPC_PORT = 54321
IPC_AUTH_TOKEN = os.environ.get('THROTTLE_IPC_TOKEN', 'changeme-secret-token')

class DownloadManagerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Secure Installer Download Manager")
        self.geometry("600x400")
        self.resizable(False, False)
        self.status_var = tk.StringVar(value="Ready.")
        self.progress_var = tk.DoubleVar(value=0)
        self._build_ui()

    def _build_ui(self):
        notebook = ttk.Notebook(self)
        self.download_tab = ttk.Frame(notebook)
        # --- Throttle Tab ---
        self.throttle_tab = ttk.Frame(notebook)
        notebook.add(self.download_tab, text="Download")
        notebook.add(self.throttle_tab, text="Throttle Settings")
        # Add a new Status tab
        self.status_tab = ttk.Frame(notebook)
        notebook.add(self.status_tab, text="Status")
        notebook.pack(fill=tk.BOTH, expand=True)

        # --- Download Tab UI ---
        self.ssl_var = tk.BooleanVar(value=True)
        self.virus_scan_var = tk.BooleanVar(value=True)
        self.sig_check_var = tk.BooleanVar(value=True)
        self.game_prio_var = tk.BooleanVar(value=True)
        self.chunk_size_var = tk.StringVar(value="1048576")  # 1MB default
        self.urls_var = tk.StringVar()
        self.dest_folder_var = tk.StringVar(value=os.path.expanduser("~"))
        ttk.Label(self.download_tab, text="Download URLs (one per line):").pack(pady=(10,0))
        urls_entry = tk.Text(self.download_tab, height=4, width=60)
        urls_entry.pack(pady=2)
        self.urls_entry = urls_entry
        ttk.Label(self.download_tab, text="Destination Folder:").pack(pady=(10,0))
        folder_frame = ttk.Frame(self.download_tab)
        folder_frame.pack(pady=2)
        dest_entry = ttk.Entry(folder_frame, textvariable=self.dest_folder_var, width=48)
        dest_entry.pack(side=tk.LEFT, padx=(0,5))
        browse_btn = ttk.Button(folder_frame, text="Browse", command=self._browse_folder)
        browse_btn.pack(side=tk.LEFT)
        # Security options
        sec_frame = ttk.LabelFrame(self.download_tab, text="Security Options")
        sec_frame.pack(fill=tk.X, padx=10, pady=5)
        ssl_checkbox = ttk.Checkbutton(sec_frame, text="Enable SSL Verification", variable=self.ssl_var)
        ssl_checkbox.grid(row=0, column=0, sticky=tk.W, padx=5)
        virus_checkbox = ttk.Checkbutton(sec_frame, text="Scan with Windows Defender", variable=self.virus_scan_var)
        virus_checkbox.grid(row=0, column=1, sticky=tk.W, padx=5)
        sig_checkbox = ttk.Checkbutton(sec_frame, text="Require Digital Signature", variable=self.sig_check_var)
        sig_checkbox.grid(row=0, column=2, sticky=tk.W, padx=5)
        game_checkbox = ttk.Checkbutton(sec_frame, text="Prioritize Games (Latency Monitor)", variable=self.game_prio_var)
        game_checkbox.grid(row=0, column=3, sticky=tk.W, padx=5)
        # Chunk size
        chunk_frame = ttk.Frame(self.download_tab)
        chunk_frame.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(chunk_frame, text="Chunk Size (bytes):").pack(side=tk.LEFT)
        chunk_entry = ttk.Entry(chunk_frame, textvariable=self.chunk_size_var, width=10)
        chunk_entry.pack(side=tk.LEFT, padx=5)
        # --- Code Auto-Update Tab ---
        self.update_tab = ttk.Frame(notebook)
        notebook.add(self.update_tab, text="Auto-Update")
        self.update_folder_var = tk.StringVar()
        self.service_name_var = tk.StringVar(value="ThrottleService")
        self.code_folder_var = tk.StringVar(value=os.getcwd())
        self.update_status_var = tk.StringVar(value="Idle.")
        ttk.Label(self.update_tab, text="Folder to Monitor for Updates:").pack(pady=(10,0))
        update_folder_frame = ttk.Frame(self.update_tab)
        update_folder_frame.pack(pady=2)
        update_entry = ttk.Entry(update_folder_frame, textvariable=self.update_folder_var, width=44)
        update_entry.pack(side=tk.LEFT, padx=(0,5))
        update_browse_btn = ttk.Button(update_folder_frame, text="Browse", command=self._browse_update_folder)
        update_browse_btn.pack(side=tk.LEFT)
        ttk.Label(self.update_tab, text="Service Name:").pack(pady=(10,0))
        service_entry = ttk.Entry(self.update_tab, textvariable=self.service_name_var, width=30)
        service_entry.pack(pady=2)
        ttk.Label(self.update_tab, text="Code Folder (to update):").pack(pady=(10,0))
        code_entry = ttk.Entry(self.update_tab, textvariable=self.code_folder_var, width=50)
        code_entry.pack(pady=2)
        ttk.Label(self.update_tab, textvariable=self.update_status_var).pack(pady=5)
        self.update_btn = ttk.Button(self.update_tab, text="Start Monitoring", command=self.toggle_update_monitor)
        self.update_btn.pack(pady=10)
        self.update_monitor_thread = None
        self.update_monitor_running = False
        # Progress bar, speed label, and download button
        self.progress_bar = ttk.Progressbar(self.download_tab, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=20, pady=5)
        self.speed_var = tk.StringVar(value="Speed: 0.00 MB/s")
        self.speed_label = ttk.Label(self.download_tab, textvariable=self.speed_var)
        self.speed_label.pack(pady=(0, 5))
        self.download_btn = ttk.Button(self.download_tab, text="Start Download(s)", command=self.start_download)
        self.download_btn.pack(pady=10)

        # --- External Download Monitor Section ---
        self.external_dl_frame = ttk.LabelFrame(self.download_tab, text="Background DownloadMonitor Progress")
        self.external_dl_frame.pack(fill=tk.X, padx=10, pady=10)
        self.external_dl_status = tk.StringVar(value="No background downloads detected.")
        self.external_dl_progress = tk.DoubleVar(value=0)
        self.external_dl_label = ttk.Label(self.external_dl_frame, textvariable=self.external_dl_status)
        self.external_dl_label.pack(side=tk.LEFT, padx=5)
        self.external_dl_bar = ttk.Progressbar(self.external_dl_frame, variable=self.external_dl_progress, maximum=100, length=200)
        self.external_dl_bar.pack(side=tk.LEFT, padx=10)
        # Start polling for external download status after all widgets are created
        self._poll_external_download_status()
    def _poll_external_download_status(self):
        # Only poll and update status, do not create any widgets or tabs here
        try:
            with socket.create_connection((IPC_HOST, 54322), timeout=1) as s:
                payload = {
                    'token': IPC_AUTH_TOKEN,
                    'event': 'GUI_QUERY_PROGRESS',
                    'data': None
                }
                msg = json.dumps(payload).encode()
                s.sendall(msg)
                data = s.recv(4096)
                resp = json.loads(data.decode())
                if resp.get('active'):
                    fname = resp.get('filename', 'Unknown')
                    percent = float(resp.get('progress', 0))
                    speed = resp.get('speed', None)
                    if speed is not None:
                        speed_str = f" @ {speed:.2f} MB/s"
                    else:
                        speed_str = ""
                    self.external_dl_status.set(f"Downloading: {fname} ({percent:.1f}%)" + speed_str)
                    self.external_dl_progress.set(percent)
                else:
                    self.external_dl_status.set("No background downloads detected.")
                    self.external_dl_progress.set(0)
        except Exception:
            self.external_dl_status.set("No background downloads detected.")
            self.external_dl_progress.set(0)
        self.after(2000, self._poll_external_download_status)

        # --- Throttle Tab UI ---
        self.bandwidth_var = tk.StringVar()
        self.threads_var = tk.StringVar()
        self.mode_var = tk.StringVar(value='auto')
        self.throttle_log_lines = []
        # Resource display
        self.resource_frame = ttk.LabelFrame(self.throttle_tab, text="Current Resources")
        self.resource_frame.pack(fill=tk.X, padx=10, pady=5)
        self.cpu_label = ttk.Label(self.resource_frame, text="CPU: N/A")
        self.cpu_label.grid(row=0, column=0, padx=5, sticky=tk.W)
        self.ram_label = ttk.Label(self.resource_frame, text="RAM: N/A")
        self.ram_label.grid(row=0, column=1, padx=5, sticky=tk.W)
        self.disk_label = ttk.Label(self.resource_frame, text="Disk: N/A")
        self.disk_label.grid(row=0, column=2, padx=5, sticky=tk.W)
        self.bandwidth_label = ttk.Label(self.resource_frame, text="Bandwidth: N/A")
        self.bandwidth_label.grid(row=0, column=3, padx=5, sticky=tk.W)
        self.threads_label = ttk.Label(self.resource_frame, text="Threads: N/A")
        self.threads_label.grid(row=0, column=4, padx=5, sticky=tk.W)
        self._update_resource_display()
        # --- Throttle Config ---
        config_frame = ttk.LabelFrame(self.throttle_tab, text="Download Config")
        config_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(config_frame, text="Bandwidth (bytes/s):").grid(row=0, column=0, sticky=tk.W)
        bw_entry = ttk.Entry(config_frame, textvariable=self.bandwidth_var, width=10)
        bw_entry.grid(row=0, column=1, padx=5)
        ttk.Label(config_frame, text="Threads:").grid(row=0, column=2, sticky=tk.W)
        threads_entry = ttk.Entry(config_frame, textvariable=self.threads_var, width=5)
        threads_entry.grid(row=0, column=3, padx=5)
        ttk.Label(config_frame, text="Mode:").grid(row=0, column=4, sticky=tk.W)
        mode_combo = ttk.Combobox(config_frame, textvariable=self.mode_var, values=["auto", "manual", "max_speed"], width=10, state="readonly")
        mode_combo.grid(row=0, column=5, padx=5)
        apply_btn = ttk.Button(config_frame, text="Apply", command=self.apply_throttle_config)
        apply_btn.grid(row=0, column=6, padx=10)
        refresh_btn = ttk.Button(config_frame, text="Refresh", command=self.refresh_throttle_status)
        refresh_btn.grid(row=0, column=7, padx=10)
        turbo_btn = ttk.Button(config_frame, text="Turbo Mode", command=self._turbo_mode)
        turbo_btn.grid(row=0, column=8, padx=10)
        # Priority overrides
        prio_frame = ttk.LabelFrame(self.throttle_tab, text="Priority Overrides (0-10)")
        prio_frame.pack(fill=tk.X, padx=10, pady=5)
        self.prio_entries = {}
        for i, label in enumerate(["installer", "Steam.exe", "XboxApp.exe", "EpicGamesLauncher.exe"]):
            ttk.Label(prio_frame, text=label).grid(row=i, column=0, sticky=tk.W)
            entry = ttk.Entry(prio_frame, width=5)
            entry.grid(row=i, column=1)
            self.prio_entries[label] = entry
        set_prio_btn = ttk.Button(prio_frame, text="Apply Overrides", command=self.set_priority)
        set_prio_btn.grid(row=0, column=2, rowspan=4, padx=10)
        # Log/status area
        self.throttle_log_frame = ttk.LabelFrame(self.throttle_tab, text="Log / Status")
        self.throttle_log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.throttle_log_text = tk.Text(self.throttle_log_frame, height=8, state="disabled", wrap="word")
        self.throttle_log_text.pack(fill=tk.BOTH, expand=True)

        # --- Service Status Bar (now at bottom of Throttle Settings tab) ---
        # --- Service Status Bar (now in Status tab, with more services) ---
        status_bar = ttk.Frame(self.status_tab)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=0, pady=0)
        self.throttle_status_var = tk.StringVar(value="ThrottleService: Checking...")
        self.throttle_status_label = ttk.Label(status_bar, textvariable=self.throttle_status_var, foreground="orange")
        self.throttle_status_label.pack(side=tk.LEFT, padx=10)
        self.dlmgr_status_var = tk.StringVar(value="DownloadManager: Checking...")
        self.dlmgr_status_label = ttk.Label(status_bar, textvariable=self.dlmgr_status_var, foreground="orange")
        self.dlmgr_status_label.pack(side=tk.LEFT, padx=10)
        self.dlmon_status_var = tk.StringVar(value="DownloadMonitor: Checking...")
        self.dlmon_status_label = ttk.Label(status_bar, textvariable=self.dlmon_status_var, foreground="orange")
        self.dlmon_status_label.pack(side=tk.LEFT, padx=10)
        self.watchdog_status_var = tk.StringVar(value="Watchdog: Checking...")
        self.watchdog_status_label = ttk.Label(status_bar, textvariable=self.watchdog_status_var, foreground="orange")
        self.watchdog_status_label.pack(side=tk.LEFT, padx=10)
        self.supervisor_status_var = tk.StringVar(value="Supervisor: Checking...")
        self.supervisor_status_label = ttk.Label(status_bar, textvariable=self.supervisor_status_var, foreground="orange")
        self.supervisor_status_label.pack(side=tk.LEFT, padx=10)
        self._service_status_update_thread = None
        self._service_status_update_stop = False
        self._start_service_status_thread()
    def _start_service_status_thread(self):
        import threading
        def check_services():
            import time
            while not self._service_status_update_stop:
                results = {}
                for name, port, var, label in [
                    ("ThrottleService", IPC_PORT, self.throttle_status_var, self.throttle_status_label),
                    ("DownloadManager", 54323, self.dlmgr_status_var, self.dlmgr_status_label),
                    ("DownloadMonitor", 54322, self.dlmon_status_var, self.dlmon_status_label),
                    ("Watchdog", 54324, self.watchdog_status_var, self.watchdog_status_label),
                    ("Supervisor", 54325, self.supervisor_status_var, self.supervisor_status_label),
                ]:
                    try:
                        with socket.create_connection((IPC_HOST, port), timeout=1):
                            results[name] = ("Active", "green")
                    except Exception:
                        results[name] = ("Inactive", "red")
                def update_labels():
                    for name, port, var, label in [
                        ("ThrottleService", IPC_PORT, self.throttle_status_var, self.throttle_status_label),
                        ("DownloadManager", 54323, self.dlmgr_status_var, self.dlmgr_status_label),
                        ("DownloadMonitor", 54322, self.dlmon_status_var, self.dlmon_status_label),
                        ("Watchdog", 54324, self.watchdog_status_var, self.watchdog_status_label),
                        ("Supervisor", 54325, self.supervisor_status_var, self.supervisor_status_label),
                    ]:
                        status, color = results[name]
                        var.set(f"{name}: {status}")
                        label.config(foreground=color)
                self.after(0, update_labels)
                for _ in range(50):
                    if self._service_status_update_stop:
                        break
                    time.sleep(0.1)
        self._service_status_update_thread = threading.Thread(target=check_services, daemon=True)
        self._service_status_update_thread.start()

    def destroy(self):
        self._service_status_update_stop = True
        if self._service_status_update_thread:
            self._service_status_update_thread.join(timeout=2)
        super().destroy()
    def _browse_update_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(initialdir=self.update_folder_var.get() or os.getcwd())
        if folder:
            self.update_folder_var.set(folder)

    def toggle_update_monitor(self):
        if not self.update_monitor_running:
            folder = self.update_folder_var.get().strip()
            service = self.service_name_var.get().strip()
            code_folder = self.code_folder_var.get().strip()
            if not folder or not service or not code_folder:
                self.update_status_var.set("Please fill all fields.")
                return
            self.update_monitor_running = True
            self.update_btn.config(text="Stop Monitoring")
            self.update_status_var.set("Monitoring for code updates...")
            import threading
            self.update_monitor_thread = threading.Thread(target=self._run_update_monitor, args=(folder, service, code_folder), daemon=True)
            self.update_monitor_thread.start()
        else:
            self.update_monitor_running = False
            self.update_btn.config(text="Start Monitoring")
            self.update_status_var.set("Stopped.")

    def _run_update_monitor(self, watch_folder, service_name, code_folder):
        import hashlib, os, time, shutil, subprocess, threading
        def hash_folder(folder):
            h = hashlib.sha256()
            for root, dirs, files in os.walk(folder):
                for f in sorted(files):
                    if f == 'throttle_service.heartbeat':
                        continue
                    path = os.path.join(root, f)
                    try:
                        stat = os.stat(path)
                        h.update(f.encode())
                        h.update(str(stat.st_mtime).encode())
                        h.update(str(stat.st_size).encode())
                    except Exception:
                        continue
            return h.hexdigest()
        def stop_service(service_name):
            subprocess.run(["sc", "stop", service_name], capture_output=True)
        def start_service(service_name):
            subprocess.run(["sc", "start", service_name], capture_output=True)
        def update_code(src_folder, dst_folder):
            for root, dirs, files in os.walk(src_folder):
                rel = os.path.relpath(root, src_folder)
                dst_root = os.path.join(dst_folder, rel)
                os.makedirs(dst_root, exist_ok=True)
                for f in files:
                    src_file = os.path.join(root, f)
                    dst_file = os.path.join(dst_root, f)
                    shutil.copy2(src_file, dst_file)
        last_hash = hash_folder(watch_folder)
        while self.update_monitor_running:
            time.sleep(2)
            try:
                new_hash = hash_folder(watch_folder)
                if new_hash != last_hash:
                    self.update_status_var.set("Change detected! Updating service in background...")
                    def do_update():
                        try:
                            update_code(watch_folder, code_folder)
                            # Restart all relevant Windows services after code update
                            for svc in [service_name, "DownloadMonitor", "ThrottleSupervisor"]:
                                stop_service(svc)
                            time.sleep(1)
                            for svc in [service_name, "DownloadMonitor", "ThrottleSupervisor"]:
                                start_service(svc)
                            self.update_status_var.set("Service(s) updated and restarted.")
                        except Exception as e:
                            self.update_status_var.set(f"Update failed: {e}")
                    threading.Thread(target=do_update, daemon=True).start()
                    last_hash = new_hash
            except Exception as e:
                self.update_status_var.set(f"Monitor error: {e}")
        self.update_status_var.set("Stopped.")

    def _turbo_mode(self):
        # Set max threads, max bandwidth, and max_speed mode
        self.bandwidth_var.set(str(10**9))
        self.threads_var.set(str(16))
        self.mode_var.set('max_speed')
        self.apply_throttle_config()

    def set_priority(self):
        # Send priority overrides to throttle service
        overrides = {}
        for k, entry in self.prio_entries.items():
            val = entry.get()
            if val:
                try:
                    ival = int(val)
                    if 0 <= ival <= 10:
                        overrides[k] = ival
                except ValueError:
                    continue
        try:
            with socket.create_connection((IPC_HOST, IPC_PORT), timeout=2) as s:
                payload = {
                    'token': IPC_AUTH_TOKEN,
                    'event': 'GUI_SET_PRIO',
                    'data': overrides
                }
                msg = json.dumps(payload).encode()
                s.sendall(msg)
                resp = s.recv(1024)
                if resp == b'OK':
                    self.append_throttle_log("Priority overrides updated.")
                    self.set_status("Priority overrides updated.")
                else:
                    self.append_throttle_log("Failed to set priority overrides.")
                    self.set_status("Failed to set priority overrides.")
        except Exception as e:
            self.append_throttle_log(f"Error setting priority: {e}")
            self.set_status(f"Priority set error: {e}")

    def set_status(self, msg):
        self.status_var.set(msg)
        self.update_idletasks()

    def _browse_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(initialdir=self.dest_folder_var.get())
        if folder:
            self.dest_folder_var.set(folder)

    def start_download(self):
        urls = self.urls_entry.get("1.0", tk.END).strip().splitlines()
        urls = [u.strip() for u in urls if u.strip()]
        dest_folder = self.dest_folder_var.get().strip()
        ssl_verify = self.ssl_var.get()
        virus_scan = self.virus_scan_var.get()
        sig_check = self.sig_check_var.get()
        game_prio = self.game_prio_var.get()
        chunk_size = int(self.chunk_size_var.get() or 1048576)
        # Removed duplicate creation of update_tab and notebook.add
        self.set_status("Starting download(s)...")
        self.progress_var.set(0)
        threading.Thread(target=self._run_downloads, args=(urls, dest_folder, ssl_verify, virus_scan, sig_check, game_prio, chunk_size), daemon=True).start()

    def _run_downloads(self, urls, dest_folder, ssl_verify, virus_scan, sig_check, game_prio, chunk_size):
        try:
            import tqdm
            import time
            orig_tqdm = tqdm.tqdm
            total_files = len(urls)
            for idx, url in enumerate(urls, 1):
                filename = os.path.basename(url.split('?')[0]) or f"file{idx}"
                dest = os.path.join(dest_folder, filename)
                mgr = DownloadManager(url, dest, ssl_verify=ssl_verify, chunk_size=chunk_size)
                # Download file with real-time speed update
                last_bytes = [0]
                last_time = [time.time()]
                def gui_tqdm(*args, **kwargs):
                    kwargs['leave'] = False
                    kwargs['file'] = open(os.devnull, 'w')
                    bar = orig_tqdm(*args, **kwargs)
                    total = kwargs.get('total', 0) or 1
                    def update_bar(n):
                        percent = (n / total) * 100 if total else 0
                        self.progress_var.set(percent)
                        now = time.time()
                        elapsed = now - last_time[0]
                        bytes_now = n
                        speed = 0.0
                        if elapsed > 0.5:
                            speed = (bytes_now - last_bytes[0]) / elapsed / (1024*1024)
                            self.speed_var.set(f"Speed: {speed:.2f} MB/s")
                            last_time[0] = now
                            last_bytes[0] = bytes_now
                        self.set_status(f"Downloading... {percent:.1f}%")
                        self.update_idletasks()
                    bar.update = lambda n=1, orig=bar.update: (orig(n), update_bar(bar.n))
                    return bar
                tqdm.tqdm = gui_tqdm
                try:
                    mgr.download()
                except Exception as e:
                    self.set_status(f"Download failed for {filename}: {e}")
                    messagebox.showerror("Download Failed", f"{filename}: {e}")
                    continue
                # Security: signature check and virus scan
                if sig_check or virus_scan:
                    try:
                        from virus_check_utils import is_signed, quick_defender_scan
                        signed = is_signed(dest) if sig_check else True
                        if not signed:
                            if virus_scan:
                                scan_result = quick_defender_scan(dest)
                                if scan_result is not None and scan_result is not True:
                                    raise Exception(f"Defender scan failed: {scan_result}")
                            else:
                                raise Exception(f"File {filename} is not signed and virus scan is disabled.")
                        elif virus_scan:
                            scan_result = quick_defender_scan(dest)
                            if scan_result is not None and scan_result is not True:
                                raise Exception(f"Defender scan failed: {scan_result}")
                    except Exception as se:
                        self.set_status(f"Security/virus check failed: {se}")
                        messagebox.showerror("Security/Virus Check Failed", f"{filename}: {se}")
                        continue
                self.progress_var.set((idx / total_files) * 100)
                self.set_status(f"Downloaded {idx}/{total_files}: {filename}")
                self.speed_var.set("Speed: 0.00 MB/s")
                # Game prioritization: notify throttle service if enabled
                if game_prio:
                    try:
                        with socket.create_connection((IPC_HOST, IPC_PORT), timeout=2) as s:
                            payload = {
                                'token': IPC_AUTH_TOKEN,
                                'event': 'GUI_GAME_PRIO',
                                'data': None
                            }
                            msg = json.dumps(payload).encode()
                            s.sendall(msg)
                    except Exception:
                        pass
            tqdm.tqdm = orig_tqdm
            self.progress_var.set(100)
            self.set_status(f"All downloads complete.")
            self.speed_var.set("Speed: 0.00 MB/s")
            messagebox.showinfo("Success", f"All downloads complete.")
        except Exception as e:
            self.set_status(f"Download failed: {e}")
            self.speed_var.set("Speed: 0.00 MB/s")
            messagebox.showerror("Download Failed", str(e))
        finally:
            self.progress_var.set(0)
            self.speed_var.set("Speed: 0.00 MB/s")

    def append_throttle_log(self, msg):
        self.throttle_log_lines.append(msg)
        if len(self.throttle_log_lines) > 100:
            self.throttle_log_lines = self.throttle_log_lines[-100:]
        self.throttle_log_text.config(state="normal")
        self.throttle_log_text.delete(1.0, tk.END)
        self.throttle_log_text.insert(tk.END, "\n".join(self.throttle_log_lines) + "\n")
        self.throttle_log_text.see(tk.END)
        self.throttle_log_text.config(state="disabled")

    def refresh_throttle_status(self):
        try:
            with socket.create_connection((IPC_HOST, IPC_PORT), timeout=2) as s:
                payload = {
                    'token': IPC_AUTH_TOKEN,
                    'event': 'GUI',
                    'data': None
                }
                msg = json.dumps(payload).encode()
                s.sendall(msg)
                data = s.recv(65536)
                state = json.loads(data.decode())
            if not isinstance(state, dict):
                raise ValueError(f"Invalid throttler response: {state}")
            self.bandwidth_var.set(str(state.get('bandwidth', '')))
            self.threads_var.set(str(state.get('threads', '')))
            self.mode_var.set(state.get('mode', 'auto'))
            self.append_throttle_log(f"Status refreshed. Bandwidth: {state.get('bandwidth', 'N/A')} bytes/s")
            self.set_status("Throttle status refreshed.")
        except Exception as e:
            self.append_throttle_log(f"Failed to get status: {e}")
            self.set_status(f"Throttle status error: {e}")

    def apply_throttle_config(self):
        bw = self.bandwidth_var.get()
        threads = self.threads_var.get()
        mode = self.mode_var.get()
        config = {"bandwidth": bw, "threads": threads, "mode": mode}
        try:
            with socket.create_connection((IPC_HOST, IPC_PORT), timeout=2) as s:
                payload = {
                    'token': IPC_AUTH_TOKEN,
                    'event': 'GUI_SET_CONFIG',
                    'data': config
                }
                msg = json.dumps(payload).encode()
                s.sendall(msg)
                resp = s.recv(1024)
                if resp == b'OK':
                    self.append_throttle_log(f"Config applied: {config}")
                    self.set_status("Throttle config applied.")
                    messagebox.showinfo("Config", f"Applied config: {config}")
                else:
                    self.append_throttle_log(f"Failed to apply config: {config}")
                    self.set_status("Throttle config failed.")
                    messagebox.showerror("Config", "Failed to apply config.")
        except Exception as e:
            self.append_throttle_log(f"Error applying config: {e}")
            self.set_status(f"Throttle config error: {e}")
            messagebox.showerror("Config", f"Error applying config: {e}")

    def _update_resource_display(self):
        try:
            import psutil
            import multiprocessing
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().available / (1024*1024)
            disk = psutil.disk_usage('/').percent
            threads = multiprocessing.cpu_count()
            # Calculate current network speed (MB/s)
            if not hasattr(self, '_last_net'):  # store last counters and time
                self._last_net = psutil.net_io_counters()
                self._last_time = psutil.time.time()
                self._last_speed = 0.0
            net = psutil.net_io_counters()
            now = psutil.time.time()
            elapsed = now - self._last_time
            if elapsed > 0:
                bytes_sent = net.bytes_sent - self._last_net.bytes_sent
                bytes_recv = net.bytes_recv - self._last_net.bytes_recv
                speed = (bytes_sent + bytes_recv) / elapsed / (1024*1024)
                self._last_speed = speed
            else:
                speed = self._last_speed
            self._last_net = net
            self._last_time = now
            self.cpu_label.config(text=f"CPU: {cpu:.1f}%")
            self.ram_label.config(text=f"RAM: {ram:.0f} MB free")
            self.disk_label.config(text=f"Disk: {disk:.1f}% used")
            self.bandwidth_label.config(text=f"Bandwidth: {speed:.2f} MB/s")
            self.threads_label.config(text=f"Threads: {threads}")
        except Exception as e:
            self.cpu_label.config(text="CPU: N/A")
            self.ram_label.config(text="RAM: N/A")
            self.disk_label.config(text="Disk: N/A")
            self.bandwidth_label.config(text="Bandwidth: N/A")
            self.threads_label.config(text="Threads: N/A")
        self.after(1000, self._update_resource_display)

if __name__ == "__main__":
    app = DownloadManagerGUI()
    app.mainloop()

