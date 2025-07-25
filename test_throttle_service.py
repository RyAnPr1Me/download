import subprocess
import time
import os
import sys

def run_throttle_service():
    # Start throttle_service.py in a subprocess
    proc = subprocess.Popen([sys.executable, 'throttle_service.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(3)  # Give it time to start
    return proc

def stop_throttle_service(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

def test_bandwidth_allocation():
    import socket
    import json
    # Connect to the IPC server and request GUI state
    with socket.create_connection(('127.0.0.1', 54321), timeout=5) as s:
        s.sendall(b'GUI')
        data = s.recv(65536)
        state = json.loads(data.decode())
        assert 'bandwidth' in state, 'No bandwidth in state!'
        assert 'downloads' in state, 'No downloads in state!'
        print('Bandwidth allocation:', state['bandwidth'])
        print('Active downloads:', state['downloads'])
        print('Bandwidth allocation test passed.')

def main():
    print('Starting ThrottleService for test...')
    proc = run_throttle_service()
    try:
        test_bandwidth_allocation()
    finally:
        stop_throttle_service(proc)
        print('ThrottleService stopped.')

if __name__ == '__main__':
    main()
