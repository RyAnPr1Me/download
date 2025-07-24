import argparse
import logging
from throttle_service import ThrottleService
from download_manager import DownloadManager

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Secure Installer with Advanced Throttling")
    parser.add_argument('--service', action='store_true', help='Run as throttler service')
    parser.add_argument('--download', nargs=2, metavar=('URL', 'DEST'), help='Download a file with throttling')
    args = parser.parse_args()

    if args.service:
        service = ThrottleService()
        try:
            service.start()
        except KeyboardInterrupt:
            service.running = False
            print("ThrottleService stopped.")
    elif args.download:
        url, dest = args.download
        mgr = DownloadManager(url, dest)
        mgr.download()
    else:
        parser.print_help()
