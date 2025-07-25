import os
import sys
import time
import threading
import ssl
import socket
import logging
import secrets
import json

SERVICE_NAMES = [
    "ThrottleService",
    "DownloadMonitor",
    "DownloadManager",
    "DownloadManagerPool",
    "ThrottleSupervisor",
    "Watchdog"
]
WORKFLOW_ORDER = [
    "ThrottleService",
    "DownloadMonitor",
    "DownloadManager",
    "DownloadManagerPool",
    "ThrottleSupervisor",
    "Watchdog"
]
SERVICE_PORTS = {
    "ThrottleService": 54501,
    "DownloadMonitor": 54502,
    "DownloadManager": 54503,
    "DownloadManagerPool": 54506,
    "ThrottleSupervisor": 54504,
    "Watchdog": 54505,
}
SUPERVISOR_HOST = '127.0.0.1'
SUPERVISOR_PORT = 54444  # Supervisor listens here for restart commands
IPC_TOKEN_FILE = ".env"
CERT_DIR = "certs"
CERT_FILE = os.path.join(CERT_DIR, "system_manager.pem")
KEY_FILE = os.path.join(CERT_DIR, "system_manager.key")
TLS_PORT = 54443

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SystemManager")

def ensure_certificates():
    if not os.path.exists(CERT_DIR):
        os.makedirs(CERT_DIR)
    if not (os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE)):
        logger.info("Generating self-signed certificate for encrypted communication...")
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from datetime import datetime, timedelta

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"SecureInstaller"),
            x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
        ])
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=3650)
        ).add_extension(
            x509.SubjectAlternativeName([x509.DNSName(u"localhost")]),
            critical=False,
        ).sign(key, hashes.SHA256())
        with open(CERT_FILE, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        with open(KEY_FILE, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
        logger.info("Certificate and key generated.")

def ensure_ipc_token():
    if not os.path.exists(IPC_TOKEN_FILE):
        token = secrets.token_hex(32)
        with open(IPC_TOKEN_FILE, "w") as f:
            f.write(f"THROTTLE_IPC_TOKEN={token}\n")
        logger.info("Generated new IPC token.")
    else:
        logger.info("IPC token already exists.")

def distribute_credentials():
    # Copy cert and .env to all service folders if needed (here, just ensure in cwd)
    pass  # Extend as needed for multi-folder deployments

def is_service_running(service_name):
    try:
        import subprocess
        result = subprocess.run(
            ["sc", "query", service_name],
            capture_output=True, text=True, timeout=5
        )
        return "RUNNING" in result.stdout
    except Exception:
        return False

def send_command(service_name, command, extra=None):
    """Send an encrypted command to a service (not just supervisor)."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    token = None
    # Load token from .env
    try:
        with open(IPC_TOKEN_FILE, "r") as f:
            for line in f:
                if line.startswith("THROTTLE_IPC_TOKEN="):
                    token = line.strip().split("=", 1)[1]
    except Exception:
        token = None
    if not token:
        logger.error("IPC token not found, cannot send command.")
        return
    port = SERVICE_PORTS.get(service_name)
    if not port:
        logger.error(f"No port configured for {service_name}")
        return
    try:
        with socket.create_connection((SUPERVISOR_HOST, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=SUPERVISOR_HOST) as ssock:
                msg = {"token": token, "command": command}
                if extra:
                    msg.update(extra)
                ssock.sendall(json.dumps(msg).encode())
                resp = ssock.recv(1024)
                if resp == b'OK':
                    logger.info(f"{service_name} acknowledged command {command}")
                else:
                    logger.warning(f"{service_name} did not acknowledge command {command}")
    except Exception as e:
        logger.error(f"Failed to send command {command} to {service_name}: {e}")

def tls_server():
    # Secure TLS server for diagnostics and workflow enforcement
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0) as sock:
        sock.bind(('127.0.0.1', TLS_PORT))
        sock.listen(5)
        with context.wrap_socket(sock, server_side=True) as ssock:
            logger.info(f"SystemManager TLS server listening on 127.0.0.1:{TLS_PORT}")
            while True:
                conn, addr = ssock.accept()
                with conn:
                    try:
                        data = conn.recv(4096)
                        if not data:
                            continue
                        try:
                            req = json.loads(data.decode())
                        except Exception:
                            req = {}
                        if req.get("command") == "status":
                            status = {}
                            for name in SERVICE_NAMES:
                                status[name] = is_service_running(name)
                            conn.sendall(json.dumps(status).encode())
                        else:
                            conn.sendall(b'UNKNOWN_COMMAND')
                    except Exception as e:
                        logger.error(f"TLS server error: {e}")

def workflow_monitor():
    """Monitor and enforce the workflow order for all services via commands."""
    while True:
        time.sleep(3)
        # 1. Ensure ThrottleService is running
        if not is_service_running("ThrottleService"):
            logger.warning("ThrottleService not running. Requesting Supervisor to restart and instructing dependents to pause...")
            send_command("ThrottleSupervisor", "RESTART", {"target": "ThrottleService"})
            for dep in ["DownloadMonitor", "DownloadManager"]:
                send_command(dep, "PAUSE")
            continue  # Wait for next cycle before starting dependents

        # 2. Ensure DownloadMonitor and DownloadManager are running
        for dep in ["DownloadMonitor", "DownloadManager"]:
            if not is_service_running(dep):
                logger.warning(f"{dep} not running. Requesting Supervisor to restart...")
                send_command("ThrottleSupervisor", "RESTART", {"target": dep})

        # 3. Supervisor and Watchdog are optional, just restart if exited
        for opt in ["ThrottleSupervisor", "Watchdog"]:
            if not is_service_running(opt):
                logger.info(f"{opt} not running. Requesting Supervisor to restart...")
                send_command("ThrottleSupervisor", "RESTART", {"target": opt})

        # 4. Example: If DownloadManagerPool spins up 2 threads for one download, instruct it to spin down one
        # (This is just an example; in a real system, this would be triggered by a real check or event)
        # send_command("DownloadManager", "SPIN_DOWN_THREAD", {"download_id": "xyz", "count": 1})

def main():
    ensure_certificates()
    ensure_ipc_token()
    distribute_credentials()
    # Start TLS server for diagnostics
    threading.Thread(target=tls_server, daemon=True).start()
    # Monitor and enforce workflow
    try:
        workflow_monitor()
    except KeyboardInterrupt:
        logger.info("SystemManager shutting down.")

if __name__ == "__main__":
    main()
