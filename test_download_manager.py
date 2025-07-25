import os
import tempfile
import shutil
import time
from download_manager import DownloadManager

def test_http_download():
    url = "https://speed.hetzner.de/100MB.bin"
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, "100MB.bin")
        mgr = DownloadManager(url, dest, ssl_verify=True, chunk_size=1024*1024)
        mgr.download()
        assert os.path.exists(dest), "File not downloaded!"
        assert os.path.getsize(dest) > 0, "Downloaded file is empty!"
        print("HTTP download test passed.")

def test_https_download():
    url = "https://speed.hetzner.de/10MB.bin"
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, "10MB.bin")
        mgr = DownloadManager(url, dest, ssl_verify=True, chunk_size=1024*512)
        mgr.download()
        assert os.path.exists(dest), "File not downloaded!"
        assert os.path.getsize(dest) > 0, "Downloaded file is empty!"
        print("HTTPS download test passed.")

def test_invalid_url():
    url = "http://invalid.url/doesnotexist.bin"
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, "fail.bin")
        try:
            mgr = DownloadManager(url, dest, ssl_verify=True, chunk_size=1024*512)
            mgr.download()
        except Exception as e:
            print(f"Invalid URL test passed: {e}")
            return
        assert False, "Invalid URL did not raise exception!"

def test_chunk_size():
    url = "https://speed.hetzner.de/1MB.bin"
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, "1MB.bin")
        mgr = DownloadManager(url, dest, ssl_verify=True, chunk_size=1024)
        mgr.download()
        assert os.path.exists(dest), "File not downloaded!"
        assert os.path.getsize(dest) > 0, "Downloaded file is empty!"
        print("Chunk size test passed.")

def run_all():
    test_http_download()
    test_https_download()
    test_invalid_url()
    test_chunk_size()
    print("All download manager tests passed.")

if __name__ == "__main__":
    run_all()
