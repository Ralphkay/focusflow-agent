# main.py

import logging
import sys
import os
import subprocess

from background_monitor import main as background_main
from dashboard_app import check_single_instance

logger = logging.getLogger(__name__)

def main():
    """
    Main entry point for the client monitoring application.
    This simply starts the background monitor process.
    """

    # --- ADD THIS BLOCK TO LAUNCH THE WATCHDOG ---
    try:
        watchdog_path = os.path.join(os.path.dirname(sys.executable), 'FocusFlowGuard.exe')
        if os.path.exists(watchdog_path):
            subprocess.Popen([watchdog_path])
    except Exception as e:
        # Using logger if available, otherwise print
        # logger.error(f"Main App: Could not start watchdog. Error: {e}")
        print(f"Main App: Could not start watchdog. Error: {e}")
    # --- END OF ADDED BLOCK ---

    if not check_single_instance():
        sys.exit(1)

    background_main()


if __name__ == "__main__":
    main()