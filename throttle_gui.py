import sys
import socket
import json
import tkinter as tk
from tkinter import ttk, messagebox


IPC_HOST = '127.0.0.1'
IPC_PORT = 54321
# Shared secret for local IPC authentication
import os
IPC_AUTH_TOKEN = os.environ.get('THROTTLE_IPC_TOKEN', 'changeme-secret-token')

class ThrottleGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Throttle Service Control Panel")
        self.geometry("600x450")
        self.resizable(False, False)
        self.bandwidth_var = tk.StringVar()
        self.threads_var = tk.StringVar()
        self.mode_var = tk.StringVar(value='auto')
        self.turbo_mode = False
        self.log_lines = []
        self.create_widgets()
        self.refresh_status()
        self.after(2000, self.periodic_refresh)

    def create_widgets(self):
        self.status_label = ttk.Label(self, text="Status: ", font=("Arial", 12))
        self.status_label.pack(pady=10)

        # System resource stats
        self.sys_frame = ttk.Frame(self)
        self.sys_frame.pack(fill=tk.X, padx=10)
        self.cpu_label = ttk.Label(self.sys_frame, text="CPU: N/A")
        self.cpu_label.pack(side=tk.LEFT, padx=5)
        self.ram_label = ttk.Label(self.sys_frame, text="RAM: N/A")
        self.ram_label.pack(side=tk.LEFT, padx=5)
        self.disk_label = ttk.Label(self.sys_frame, text="Disk: N/A")
        self.disk_label.pack(side=tk.LEFT, padx=5)
        self.net_label = ttk.Label(self.sys_frame, text="Net: N/A")
        self.net_label.pack(side=tk.LEFT, padx=5)

        # Bandwidth/thread/mode controls
        self.config_frame = ttk.LabelFrame(self, text="Download Config")
        self.config_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(self.config_frame, text="Bandwidth (bytes/s):").grid(row=0, column=0, sticky=tk.W)
        bw_entry = ttk.Entry(self.config_frame, textvariable=self.bandwidth_var, width=10)
        bw_entry.grid(row=0, column=1, padx=5)
        ttk.Label(self.config_frame, text="Threads:").grid(row=0, column=2, sticky=tk.W)
        threads_entry = ttk.Entry(self.config_frame, textvariable=self.threads_var, width=5)
        threads_entry.grid(row=0, column=3, padx=5)
        ttk.Label(self.config_frame, text="Mode:").grid(row=0, column=4, sticky=tk.W)
        mode_combo = ttk.Combobox(self.config_frame, textvariable=self.mode_var, values=["auto", "manual", "max_speed"], width=10, state="readonly")
        mode_combo.grid(row=0, column=5, padx=5)
        apply_btn = ttk.Button(self.config_frame, text="Apply", command=self.apply_config)
        apply_btn.grid(row=0, column=6, padx=10)
        turbo_btn = ttk.Button(self.config_frame, text="Turbo Mode", command=self.toggle_turbo)
        turbo_btn.grid(row=0, column=7, padx=10)
    def toggle_turbo(self):
        # Turbo mode: set max threads, max bandwidth, and max_speed mode
        if not self.turbo_mode:
            self.bandwidth_var.set(str(10**9))  # 1GB/s (effectively unlimited)
            self.threads_var.set(str(16))  # High thread count for parallelism
            self.mode_var.set('max_speed')
            self.turbo_mode = True
            self.append_log("Turbo Mode enabled: maximizing download speed!")
        else:
            self.bandwidth_var.set("")
            self.threads_var.set("")
            self.mode_var.set('auto')
            self.turbo_mode = False
            self.append_log("Turbo Mode disabled: normal operation.")
        self.apply_config()

        columns = ("pid", "name", "bw", "percent", "score")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        self.tree.heading("pid", text="PID")
        self.tree.heading("name", text="Name")
        self.tree.heading("bw", text="BW (bytes/s)")
        self.tree.heading("percent", text="%")
        self.tree.heading("score", text="Score")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.refresh_btn = ttk.Button(self, text="Refresh", command=self.refresh_status)
        self.refresh_btn.pack(pady=5)

        self.prio_frame = ttk.LabelFrame(self, text="Set Priority Overrides (0-10)")
        self.prio_frame.pack(fill=tk.X, padx=10, pady=5)
        self.prio_entries = {}
        for i, label in enumerate(["installer", "Steam.exe", "XboxApp.exe", "EpicGamesLauncher.exe"]):
            ttk.Label(self.prio_frame, text=label).grid(row=i, column=0, sticky=tk.W)
            entry = ttk.Entry(self.prio_frame, width=5)
            entry.grid(row=i, column=1)
            self.prio_entries[label] = entry
        self.set_prio_btn = ttk.Button(self.prio_frame, text="Apply Overrides", command=self.set_priority)
        self.set_prio_btn.grid(row=0, column=2, rowspan=4, padx=10)

        # Log/status area
        self.log_frame = ttk.LabelFrame(self, text="Log / Status")
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.log_text = tk.Text(self.log_frame, height=5, state="disabled", wrap="word")
        self.log_text.pack(fill=tk.BOTH, expand=True)
    def periodic_refresh(self):
        # Only refresh if window is visible (not minimized)
        if self.state() != 'iconic':
            self.refresh_status(async_mode=True)
        self.after(2000, self.periodic_refresh)
    def apply_config(self):
        # Send config to the throttler service via authenticated IPC
        bw = self.bandwidth_var.get()
        threads = self.threads_var.get()
        mode = self.mode_var.get()
        # Maximize threads and bandwidth if in turbo mode or max_speed
        if mode == 'max_speed' or self.turbo_mode:
            try:
                import multiprocessing
                cpu_count = multiprocessing.cpu_count()
            except Exception:
                cpu_count = 8
            threads = str(max(16, cpu_count * 2))
            bw = str(10**9)  # 1GB/s
        config = {"bandwidth": bw, "threads": threads, "mode": mode}
        def do_apply():
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
                        self.append_log(f"Config applied: {config}")
                        if self.turbo_mode or mode == 'max_speed':
                            messagebox.showinfo("Turbo Mode", "Turbo Mode enabled! Maximum download speed applied.")
                        else:
                            messagebox.showinfo("Config", f"Applied config: {config}")
                    else:
                        self.append_log(f"Failed to apply config: {config}")
                        messagebox.showerror("Config", "Failed to apply config.")
            except Exception as e:
                self.append_log(f"Error applying config: {e}")
                messagebox.showerror("Config", f"Error applying config: {e}")
        self.after(1, do_apply)
    def append_log(self, msg):
        self.log_lines.append(msg)
        if len(self.log_lines) > 100:
            self.log_lines = self.log_lines[-100:]
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, "\n".join(self.log_lines) + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def refresh_status(self, async_mode=False):
        def do_refresh():
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
                self.status_label.config(text=f"Current bandwidth: {state.get('bandwidth', 'N/A')} bytes/s")
                # System stats
                sysload = state.get('system_load', {})
                self.cpu_label.config(text=f"CPU: {sysload.get('cpu', 'N/A')}%")
                self.ram_label.config(text=f"RAM: {sysload.get('ram', 'N/A')}%")
                self.disk_label.config(text=f"Disk: {sysload.get('disk', 'N/A')}%")
                self.net_label.config(text=f"Net: {sysload.get('net', 'N/A')}")
                # Only update tree if changed
                current_rows = [self.tree.item(i)['values'] for i in self.tree.get_children()]
                new_rows = [(d['pid'], d['name'], d['bw'], d['bw_percent'], f"{d['score']:.2f}") for d in state.get('downloads', [])]
                if current_rows != new_rows:
                    self.tree.delete(*self.tree.get_children())
                    self.tree.insert('', 'end', *[{'values': vals} for vals in new_rows])
                # Fill priority entries only if changed
                prio = state.get('priority_overrides', {})
                for k, entry in self.prio_entries.items():
                    val = prio.get(k, "")
                    if entry.get() != str(val):
                        entry.delete(0, tk.END)
                        if val != "":
                            entry.insert(0, str(val))
                self.append_log(f"Status refreshed. Bandwidth: {state.get('bandwidth', 'N/A')} bytes/s")
            except Exception as e:
                self.append_log(f"Failed to get status: {e}")
                if not async_mode:
                    messagebox.showerror("Error", f"Failed to get status: {e}")
        if async_mode:
            self.after(1, do_refresh)
        else:
            do_refresh()

    def set_priority(self):
        def do_set():
            try:
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
                        messagebox.showinfo("Success", "Priority overrides updated.")
                        self.refresh_status(async_mode=True)
                    else:
                        messagebox.showerror("Error", "Failed to set priority overrides.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to set priority: {e}")
        self.after(1, do_set)

if __name__ == "__main__":
    app = ThrottleGUI()
    app.mainloop()
