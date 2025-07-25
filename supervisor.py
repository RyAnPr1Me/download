import subprocess
import sys
import os
import time

def main():
    import threading
    from download_manager_pool import DownloadManagerPool

    def heartbeat_loop():
        while True:
            try:
                with open('supervisor.heartbeat', 'w') as hb:
                    hb.write(str(time.time()))
            except Exception:
                pass
            time.sleep(2)

    throttle_service_script = os.path.abspath('throttle_service.py')
    download_monitor_script = os.path.abspath('download_monitor.py')
    download_dir = os.getcwd()  # Or set to a specific downloads directory

    threading.Thread(target=heartbeat_loop, daemon=True).start()

    procs = {
        'throttle_service': None,
        'download_monitor': None
    }

    def launch_process(cmd, name):
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def start_all():
        procs['throttle_service'] = launch_process([sys.executable, throttle_service_script], 'throttle_service')
        procs['download_monitor'] = launch_process([sys.executable, download_monitor_script], 'download_monitor')

    def terminate_all():
        for p in procs.values():
            if p and p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
        for p in procs.values():
            if p:
                try:
                    p.wait(timeout=5)
                except Exception:
                    pass

    # Initialize the download manager pool
    pool = DownloadManagerPool()

    start_all()
    print("[Supervisor] All components launched.")

    # Example: Add downloads to the pool (replace with actual download logic as needed)
    pool.add_download("https://speed.hetzner.de/100MB.bin", "100MB.bin", size=120*1024*1024)
    pool.add_download("https://speed.hetzner.de/1MB.bin", "1MB.bin", size=1*1024*1024)
    pool.add_download("https://speed.hetzner.de/2MB.bin", "2MB.bin", size=2*1024*1024)

    try:
        while True:
            time.sleep(2)
            for name, proc in procs.items():
                if proc and proc.poll() is not None:
                    print(f"[Supervisor] {name} exited with code {proc.returncode}. Restarting...")
                    if name == 'throttle_service':
                        procs[name] = launch_process([sys.executable, throttle_service_script], name)
                    elif name == 'download_monitor':
                        procs[name] = launch_process([sys.executable, download_monitor_script], name)
            # Optionally, monitor and add downloads to the pool here

    except KeyboardInterrupt:
        print("[Supervisor] Shutting down all components...")
        terminate_all()
        pool.stop()
    finally:
        terminate_all()
        pool.stop()

# --- Windows Service Wrapper ---
try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    import threading

    class SupervisorService(win32serviceutil.ServiceFramework):
        _svc_name_ = "SupervisorService"
        _svc_display_name_ = "Supervisor Service"
        _svc_description_ = "Supervisor for SecureInstaller components."

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
            self.thread = None

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            os._exit(0)
            win32event.SetEvent(self.hWaitStop)

        def SvcDoRun(self):
            servicemanager.LogInfoMsg("SupervisorService is starting.")
            self.thread = threading.Thread(target=main, daemon=True)
            self.thread.start()
            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
            servicemanager.LogInfoMsg("SupervisorService is stopping.")

except ImportError:
    SupervisorService = None

if __name__ == "__main__":
    if 'win32serviceutil' in sys.modules and len(sys.argv) == 1:
        win32serviceutil.HandleCommandLine(SupervisorService)
    else:
        main()
