import tkinter as tk
from tkinter import ttk, messagebox
from download_manager import DownloadManager
import threading
import os
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
        self.throttle_tab = ttk.Frame(notebook)
        notebook.add(self.download_tab, text="Download")
        notebook.add(self.throttle_tab, text="Throttle Settings")
        notebook.pack(fill=tk.BOTH, expand=True)

        # --- Download Tab ---
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
        # Progress bar and download button
        self.progress_bar = ttk.Progressbar(self.download_tab, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=20, pady=5)
        download_btn = ttk.Button(self.download_tab, text="Start Download(s)", command=self.start_download)
        download_btn.pack(pady=10)

        # --- Throttle Tab ---
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
        # --- Status Bar ---
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

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
        if not urls or not dest_folder:
            messagebox.showerror("Error", "Please enter at least one URL and a destination folder.")
            return
        self.set_status("Starting download(s)...")
        self.progress_var.set(0)
        threading.Thread(target=self._run_downloads, args=(urls, dest_folder, ssl_verify, virus_scan, sig_check, game_prio, chunk_size), daemon=True).start()

    def _run_downloads(self, urls, dest_folder, ssl_verify, virus_scan, sig_check, game_prio, chunk_size):
        try:
            import tqdm
            orig_tqdm = tqdm.tqdm
            def gui_tqdm(*args, **kwargs):
                kwargs['leave'] = False
                kwargs['file'] = open(os.devnull, 'w')
                bar = orig_tqdm(*args, **kwargs)
                total = kwargs.get('total', 0) or 1
                def update_bar(n):
                    percent = (n / total) * 100 if total else 0
                    self.progress_var.set(percent)
                    self.set_status(f"Downloading... {percent:.1f}%")
                    self.update_idletasks()
                bar.update = lambda n=1, orig=bar.update: (orig(n), update_bar(bar.n))
                return bar
            tqdm.tqdm = gui_tqdm
            total_files = len(urls)
            for idx, url in enumerate(urls, 1):
                filename = os.path.basename(url.split('?')[0]) or f"file{idx}"
                dest = os.path.join(dest_folder, filename)
                mgr = DownloadManager(url, dest, ssl_verify=ssl_verify, chunk_size=chunk_size)
                # Download file first
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
            messagebox.showinfo("Success", f"All downloads complete.")
        except Exception as e:
            self.set_status(f"Download failed: {e}")
            messagebox.showerror("Download Failed", str(e))
        finally:
            self.progress_var.set(0)

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
            net = psutil.net_io_counters()
            bandwidth = (net.bytes_sent + net.bytes_recv) / (1024*1024)  # MB since boot
            threads = multiprocessing.cpu_count()
            self.cpu_label.config(text=f"CPU: {cpu:.1f}%")
            self.ram_label.config(text=f"RAM: {ram:.0f} MB free")
            self.disk_label.config(text=f"Disk: {disk:.1f}% used")
            self.bandwidth_label.config(text=f"Bandwidth: {bandwidth:.1f} MB (total)")
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

