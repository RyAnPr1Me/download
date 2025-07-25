import subprocess
import sys
import os
import time

def main():
    import threading

    def heartbeat_loop():
        while True:
            try:
                with open('supervisor.heartbeat', 'w') as hb:
                    hb.write(str(time.time()))
            except Exception:
                pass
            time.sleep(2)

    def launch_process(cmd, name):
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    throttle_service_script = os.path.abspath('throttle_service.py')
    download_monitor_script = os.path.abspath('download_monitor.py')
    download_manager_script = os.path.abspath('download_manager.py')
    download_dir = os.getcwd()  # Or set to a specific downloads directory

    threading.Thread(target=heartbeat_loop, daemon=True).start()

    procs = {
        'throttle_service': None,
        'download_monitor': None,
        'download_manager': None
    }

    def start_all():
        procs['throttle_service'] = launch_process([sys.executable, throttle_service_script], 'throttle_service')
        procs['download_monitor'] = launch_process([sys.executable, download_monitor_script], 'download_monitor')
        procs['download_manager'] = launch_process(
            [sys.executable, download_manager_script, '--status', 'http://localhost/dummy', 'dummyfile'],
            'download_manager'
        )

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

    start_all()
    print("[Supervisor] All components launched.")

    try:
        while True:
            time.sleep(2)
            for name, proc in procs.items():
                if proc and proc.poll() is not None:
                    print(f"[Supervisor] {name} exited with code {proc.returncode}. Restarting...")
                    # Restart the process
                    if name == 'throttle_service':
                        procs[name] = launch_process([sys.executable, throttle_service_script], name)
                    elif name == 'download_monitor':
                        procs[name] = launch_process([sys.executable, download_monitor_script], name)
                    elif name == 'download_manager':
                        procs[name] = launch_process(
                            [sys.executable, download_manager_script, '--status', 'http://localhost/dummy', 'dummyfile'],
                            name
                        )
    except KeyboardInterrupt:
        print("[Supervisor] Shutting down all components...")
        terminate_all()
    finally:
        terminate_all()

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
