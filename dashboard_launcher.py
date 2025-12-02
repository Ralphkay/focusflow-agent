# dashboard_launcher.py
import webview
import logging
import sys
import os

# Set up logging for this specific script
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.log')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    encoding='utf-8', handlers=[logging.FileHandler(LOG_FILE, encoding='utf-8'), logging.StreamHandler()])
logger = logging.getLogger(__name__)

MONITOR_API_PORT = 5000

def launch_dashboard():
    """Launches the dashboard UI in its own process."""
    try:
        # Use a non-blocking way to start the webview
        logger.info(f"Launching dashboard UI connected to http://127.0.0.1:{MONITOR_API_PORT}/")
        webview.create_window('FocusFlow Dashboard', f'http://127.0.0.1:{MONITOR_API_PORT}/')
        webview.start(debug=True)
        logger.info("Dashboard UI window closed.")
    except Exception as e:
        logger.error(f"Failed to launch webview: {e}", exc_info=True)

if __name__ == '__main__':
    launch_dashboard()