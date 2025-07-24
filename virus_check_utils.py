import psutil
import threading
import statistics
import platform
import re
# --- Gaming Latency Monitor and Bandwidth Recommendation ---
def get_known_game_processes():
    """
    Return a list of known game process names (lowercase, no extension).
    Extend this list as needed.
    """
    return [
        'steam', 'steamwebhelper', 'gameoverlayui',
        'battle.net', 'battlenet', 'blizzard',
        'epicgameslauncher', 'epicgames',
        'origin', 'eaapp',
        'xboxapp', 'xbox', 'gamelaunchhelper',
        'riotclientservices', 'valorant', 'leagueclient',
        'csgo', 'dota2', 'fortnite', 'apex', 'overwatch',
        'eldenring', 'starfield', 'starcraft', 'diablo',
        'rocketleague', 'pubg', 'minecraft', 'roblox',
        'gta5', 'rdr2', 'fifa', 'nba2k', 'cod', 'warzone',
        # Add more as needed
    ]

def find_running_games():
    """
    Return a list of running game process names (case-insensitive, no extension).
    """
    games = get_known_game_processes()
    running = set()
    for proc in psutil.process_iter(['name']):
        try:
            name = proc.info['name']
            if not name:
                continue
            name = name.lower().split('.')[0]
            if name in games:
                running.add(name)
        except Exception:
            continue
    return list(running)

def measure_latency(host='8.8.8.8', count=5, timeout=1.0):
    """
    Measure average ping latency (ms) to a host. Returns (avg, stdev, all_samples).
    """
    import subprocess
    plat = platform.system().lower()
    if plat == 'windows':
        cmd = ['ping', '-n', str(count), '-w', str(int(timeout*1000)), host]
        regex = r'Average = (\d+)ms'
    else:
        cmd = ['ping', '-c', str(count), '-W', str(int(timeout)), host]
        regex = r'avg = ([\d.]+) ms'
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout*count+2)
        output = result.stdout
        # Parse all latency samples
        samples = [int(x) for x in re.findall(r'(\d+)ms', output)]
        avg = statistics.mean(samples) if samples else None
        stdev = statistics.stdev(samples) if len(samples) > 1 else 0
        return avg, stdev, samples
    except Exception as e:
        logging.getLogger('VirusCheck').warning(f"Latency measurement failed: {e}")
        return None, None, []

def recommend_bandwidth_allocation_for_gaming(latency_threshold=60, min_bw_games=10*1024*1024, max_bw_games=100*1024*1024):
    """
    If games are running and latency is high, recommend more bandwidth for games and throttle others.
    Returns a dict: { 'games': [list], 'latency': ms, 'recommendation': str, 'allocate_bw': int }
    """
    games = find_running_games()
    if not games:
        return {'games': [], 'latency': None, 'recommendation': 'No games running', 'allocate_bw': None}
    avg_latency, stdev, samples = measure_latency()
    if avg_latency is None:
        return {'games': games, 'latency': None, 'recommendation': 'Could not measure latency', 'allocate_bw': None}
    if avg_latency > latency_threshold:
        # Recommend more bandwidth for games, throttle others
        rec = f"High latency detected ({avg_latency}ms). Allocate more bandwidth to games: {games}"
        allocate_bw = max_bw_games
    else:
        rec = f"Latency normal ({avg_latency}ms). Maintain current allocation."
        allocate_bw = min_bw_games
    return {
        'games': games,
        'latency': avg_latency,
        'latency_samples': samples,
        'recommendation': rec,
        'allocate_bw': allocate_bw
    }
import subprocess
import os
import logging

def is_signed(file_path):
    logger = logging.getLogger('VirusCheck')
    try:
        if not os.path.exists(file_path):
            logger.error(f"File not found for signature check: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")
        cmd = [
            'powershell',
            '-Command',
            f"(Get-AuthenticodeSignature '{file_path}').Status"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            logger.error(f"PowerShell signature check failed for {file_path}: {result.stderr.strip()}")
            raise RuntimeError(f"Signature check failed: {result.stderr.strip()}")
        if 'Valid' in result.stdout:
            return True
        return False
    except subprocess.TimeoutExpired:
        logger.error(f"Signature check timed out for {file_path}")
        raise
    except Exception as e:
        logger.exception(f"Error during signature check for {file_path}: {e}")
        raise

def quick_defender_scan(file_path):
    logger = logging.getLogger('VirusCheck')
    defender_path = r'C:\Program Files\Windows Defender\MpCmdRun.exe'
    if not os.path.exists(defender_path):
        logger.error(f"Windows Defender not found at {defender_path}")
        raise FileNotFoundError(f"Windows Defender not found at {defender_path}")
    try:
        if not os.path.exists(file_path):
            logger.error(f"File not found for Defender scan: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")
        cmd = [
            defender_path,
            '-Scan', '-ScanType', '3', '-File', file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logger.error(f"Defender scan failed for {file_path}: {result.stderr.strip()}")
            raise RuntimeError(f"Defender scan failed: {result.stderr.strip()}")
        if 'No threats' in result.stdout:
            return True
        elif 'threat' in result.stdout.lower() or 'detected' in result.stdout.lower():
            logger.error(f"Threat detected in {file_path}: {result.stdout.strip()}")
            return False
        else:
            logger.warning(f"Unexpected Defender output for {file_path}: {result.stdout.strip()}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"Defender scan timed out for {file_path}")
        raise
    except Exception as e:
        logger.exception(f"Error during Defender scan for {file_path}: {e}")
        raise

def scan_if_unsigned(file_path):
    logger = logging.getLogger('VirusCheck')
    try:
        if not os.path.exists(file_path):
            logger.error(f"File not found for virus check: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")
        if not is_signed(file_path):
            logger.info(f"[VirusCheck] Scanning unsigned file: {file_path}")
            if not quick_defender_scan(file_path):
                logger.error(f"Virus detected in {file_path}!")
                raise Exception(f"Virus detected in {file_path}!")
            logger.info(f"[VirusCheck] File clean: {file_path}")
        else:
            logger.info(f"[VirusCheck] File is signed, skipping scan: {file_path}")
    except Exception as e:
        logger.exception(f"Error in scan_if_unsigned for {file_path}: {e}")
        raise

