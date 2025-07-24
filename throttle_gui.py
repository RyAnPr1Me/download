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
        mode_combo = ttk.Combobox(self.config_frame, textvariable=self.mode_var, values=["auto", "manual"], width=7, state="readonly")
        mode_combo.grid(row=0, column=5, padx=5)
        apply_btn = ttk.Button(self.config_frame, text="Apply", command=self.apply_config)
        apply_btn.grid(row=0, column=6, padx=10)

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
        self.refresh_status()
        self.after(2000, self.periodic_refresh)
    def apply_config(self):
        # Send config to the throttler service via authenticated IPC
        bw = self.bandwidth_var.get()
        threads = self.threads_var.get()
        mode = self.mode_var.get()
        config = {"bandwidth": bw, "threads": threads, "mode": mode}
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((IPC_HOST, IPC_PORT))
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
                    messagebox.showinfo("Config", f"Applied config: {config}")
                else:
                    self.append_log(f"Failed to apply config: {config}")
                    messagebox.showerror("Config", "Failed to apply config.")
        except Exception as e:
            self.append_log(f"Error applying config: {e}")
            messagebox.showerror("Config", f"Error applying config: {e}")
    def append_log(self, msg):
        self.log_lines.append(msg)
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def refresh_status(self):
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
            self.status_label.config(text=f"Current bandwidth: {state.get('bandwidth', 'N/A')} bytes/s")
            # System stats
            sysload = state.get('system_load', {})
            self.cpu_label.config(text=f"CPU: {sysload.get('cpu', 'N/A')}%")
            self.ram_label.config(text=f"RAM: {sysload.get('ram', 'N/A')}%")
            self.disk_label.config(text=f"Disk: {sysload.get('disk', 'N/A')}%")
            self.net_label.config(text=f"Net: {sysload.get('net', 'N/A')}")
            for row in self.tree.get_children():
                self.tree.delete(row)
            for d in state.get('downloads', []):
                self.tree.insert('', 'end', values=(d['pid'], d['name'], d['bw'], d['bw_percent'], f"{d['score']:.2f}"))
            # Fill priority entries
            prio = state.get('priority_overrides', {})
            for k, entry in self.prio_entries.items():
                val = prio.get(k, "")
                entry.delete(0, tk.END)
                if val != "":
                    entry.insert(0, str(val))
            self.append_log(f"Status refreshed. Bandwidth: {state.get('bandwidth', 'N/A')} bytes/s")
        except Exception as e:
            self.append_log(f"Failed to get status: {e}")
            messagebox.showerror("Error", f"Failed to get status: {e}")

    def set_priority(self):
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
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((IPC_HOST, IPC_PORT))
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
                    self.refresh_status()
                else:
                    messagebox.showerror("Error", "Failed to set priority overrides.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to set priority: {e}")

if __name__ == "__main__":
    app = ThrottleGUI()
    app.mainloop()
