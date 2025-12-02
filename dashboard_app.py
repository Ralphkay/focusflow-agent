# dashboard_app.py (The Corrected Launcher)

import logging
import sys
import os
import subprocess
import socket
from threading import Thread
import time

logger = logging.getLogger(__name__)


def check_single_instance():
    """Ensures only one instance of the entire application is running."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 60123))
        return s
    except OSError:
        return None


def main():
    """Main entry point for the entire application, starting the background monitor."""
    # Check if stealth mode is enabled
    try:
        from config import CONFIG, init_logging
        init_logging()
        if CONFIG.get('stealth_mode', True):
            logger.info("Application running in stealth mode - no dashboard access")
    except Exception as e:
        logger.debug(f"Could not check stealth mode: {e}")
    
    instance_socket = check_single_instance()
    if not instance_socket:
        logger.warning("Another instance of the application is already running. Exiting.")
        sys.exit(0)

    # We will simply launch the background monitor process, which handles everything.
    python_executable = sys.executable
    monitor_script = os.path.join(os.path.dirname(__file__), 'background_monitor.py')

    logger.info("Launching background monitor process.")
    subprocess.Popen([python_executable, monitor_script])

    # The launcher process can now safely exit.
    instance_socket.close()


if __name__ == "__main__":
    main()