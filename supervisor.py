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

    # Service names must match those registered with Windows
    SERVICES = [
        "ThrottleService",
        "DownloadMonitorService",
        "DownloadManagerService"
    ]

    def is_service_running(service_name):
        try:
            result = subprocess.run(
                ["sc", "query", service_name],
                capture_output=True, text=True, timeout=5
            )
            return "RUNNING" in result.stdout
        except Exception:
            return False

    def start_service(service_name):
        try:
            subprocess.run(["sc", "start", service_name], capture_output=True, timeout=10)
        except Exception:
            pass

    def stop_service(service_name):
        try:
            subprocess.run(["sc", "stop", service_name], capture_output=True, timeout=10)
        except Exception:
            pass

    threading.Thread(target=heartbeat_loop, daemon=True).start()

    # Ensure all services are running
    for svc in SERVICES:
        if not is_service_running(svc):
            print(f"[Supervisor] Starting {svc}...")
            start_service(svc)

    try:
        while True:
            time.sleep(2)
            for svc in SERVICES:
                if not is_service_running(svc):
                    print(f"[Supervisor] Detected {svc} stopped. Restarting...")
                    start_service(svc)
    except KeyboardInterrupt:
        print("[Supervisor] Shutting down all managed services...")
        for svc in SERVICES:
            stop_service(svc)

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
