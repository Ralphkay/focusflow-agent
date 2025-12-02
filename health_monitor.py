# health_monitor.py

import logging
import os
import psutil
import requests
import threading
import time
import sys
from datetime import datetime
from urllib.parse import urljoin
from pathlib import Path

# The health monitor relies on the global CONFIG dictionary and the authenticated session function.
# client_api_service.py provides the function to get a session with the necessary authentication headers.
from client_api_service import get_server_authenticated_session
# Import APP_DATA_PATH to know where the database and logs are stored.
from config import CONFIG, APP_DATA_PATH

logger = logging.getLogger(__name__)

# --- Constants ---
# The interval in seconds for sending a health report to the server.
HEALTH_CHECK_INTERVAL_SECONDS = 300  # 5 minutes
# The API endpoint on the central server for receiving health reports.
CENTRAL_SERVER_HEALTH_ENDPOINT = "api/health/report"

# --- Helper Function to get directory size ---
def get_dir_size(path):
    """Recursively calculates the size of a directory in megabytes."""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                # skip if it is symbolic link
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
    except FileNotFoundError:
        logger.warning(f"Directory not found for size calculation: {path}")
        return 0
    return round(total_size / (1024 * 1024), 2)


# --- Metric Collection Functions ---
def get_system_metrics():
    """Gathers overall system performance indicators."""
    try:
        logger.debug("Gathering system metrics (CPU, memory, disk).")
        cpu_usage = psutil.cpu_percent(interval=1)
        memory_info = psutil.virtual_memory()
        disk_info = psutil.disk_usage('/')

        metrics = {
            "cpu_usage_percent": cpu_usage,
            "memory_usage_percent": memory_info.percent,
            "disk_usage_percent": disk_info.percent,
        }
        logger.info(f"System metrics collected: CPU={cpu_usage}%, Memory={memory_info.percent}%")
        return metrics
    except Exception as e:
        logger.error(f"Failed to gather system metrics: {e}", exc_info=True)
        return None

def get_agent_specific_metrics():
    """
    Gathers metrics specific to the FocusFlow agent process.
    """
    try:
        pid = os.getpid()
        process = psutil.Process(pid)

        # Agent-specific CPU Usage
        agent_cpu_usage = process.cpu_percent(interval=0.5)

        # Agent-specific Memory Usage
        agent_memory_mb = round(process.memory_info().rss / (1024 * 1024), 2)

        # Agent Disk Space (App + Data)
        # Assumes a packaged app (PyInstaller) or running from source
        try:
            # sys.executable is the path to the python interpreter or the frozen executable
            app_dir = Path(sys.executable).parent
        except Exception:
            # Fallback for environments where sys.executable is not reliable
            app_dir = Path(os.path.abspath("."))

        app_folder_size_mb = get_dir_size(app_dir)
        data_folder_size_mb = get_dir_size(APP_DATA_PATH) # From config
        total_disk_space_mb = round(app_folder_size_mb + data_folder_size_mb, 2)

        agent_metrics = {
            "cpu_usage_percent": agent_cpu_usage,
            "memory_used_mb": agent_memory_mb,
            "disk_space_mb": total_disk_space_mb
        }
        logger.info(f"Agent-specific metrics collected: CPU={agent_cpu_usage}%, Memory={agent_memory_mb}MB, Disk={total_disk_space_mb}MB")
        return agent_metrics
    except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError) as e:
        logger.error(f"Could not retrieve agent-specific metrics: {e}", exc_info=True)
        return None

def check_online_status():
    """Checks for an active internet connection."""
    logger.debug("Checking internet connectivity.")
    try:
        # Use a timeout to prevent the check from hanging indefinitely.
        requests.get("http://www.google.com", timeout=5)
        logger.info("Internet connection is active.")
        return True
    except requests.ConnectionError:
        logger.warning("Internet connection check failed; the client appears to be offline.")
        return False


def send_health_report(stop_event):
    """
    Periodically collects and sends a comprehensive health report to the central server.

    Args:
        stop_event (threading.Event): An event that signals the thread to terminate gracefully.
    """
    logger.info(f"Health monitor thread started. Reports will be sent every {HEALTH_CHECK_INTERVAL_SECONDS} seconds.")

    while not stop_event.is_set():
        try:
            # Wait for the specified interval. Using stop_event.wait allows the thread
            # to exit immediately if the stop signal is received during the wait period.
            if stop_event.wait(HEALTH_CHECK_INTERVAL_SECONDS):
                break  # Exit if the event was set

            logger.info("Preparing to collect and send health report.")

            # Step 1: Get an authenticated session for the API call.
            http_session = get_server_authenticated_session() #
            if not http_session:
                logger.error("Could not create an authenticated session. Skipping this health report.")
                continue

            # Step 2: Construct the payload with agent-specific metrics
            payload = {
                "employee_id": CONFIG.get("employee_id"),
                "timestamp": datetime.utcnow().isoformat(),
                "online_status": check_online_status(), #
                "pc_status": "on",
                "application_status": "running",
                "system_metrics": get_system_metrics(), #
                "agent_metrics": get_agent_specific_metrics() #
            }

            # Step 3: Send the report to the central server.
            # The server URL is loaded from environment variables by config.py.
            base_url = os.getenv("CENTRAL_DASHBOARD_URL")
            if not base_url:
                logger.error("CENTRAL_DASHBOARD_URL is not configured. Cannot send health report.")
                continue

            endpoint = urljoin(base_url, CENTRAL_SERVER_HEALTH_ENDPOINT)
            logger.info(f"Sending health report to: {endpoint}")
            logger.debug("Health report payload: %s", payload)

            response = http_session.post(endpoint, json=payload, timeout=30)
            response.raise_for_status()  # Raise an exception for HTTP error codes (4xx or 5xx)

            logger.info(f"Health report successfully sent. Server responded with status code: {response.status_code}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send health report due to a network error: {e}", exc_info=True)
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Server response content: {e.response.text}")
        except Exception as e:
            logger.critical(f"An unexpected critical error occurred in the health monitoring loop: {e}", exc_info=True)
            # Add a short sleep to prevent rapid-fire looping in case of a persistent error.
            time.sleep(60)

    logger.info("Health monitor thread has received the stop signal and is shutting down.")


def start_health_monitor():
    """
    Initializes and starts the health monitor in a dedicated background thread.

    Returns:
        threading.Event: The event object that can be used to stop the monitor thread.
    """
    logger.info("Initializing the background health monitor.")
    stop_event = threading.Event()

    # Run the monitoring function in a daemon thread. Daemon threads will not block
    # the main application from exiting.
    health_thread = threading.Thread(target=send_health_report, args=(stop_event,), daemon=True, name="HealthMonitorThread")
    health_thread.start()

    logger.info("Health monitor thread has been started.")
    return stop_event

# This block allows for direct testing of the health monitor module.
if __name__ == '__main__':
    print("Running health_monitor.py in standalone test mode.")
    # Basic logging configuration for testing purposes.
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - %(name)s - %(levelname)s - %(message)s')

    # Mock the CONFIG and environment variables that the monitor depends on.
    CONFIG['employee_id'] = 'test.employee@example.com'
    # This dependency is loaded by config.py in the main application.
    os.environ['CENTRAL_DASHBOARD_URL'] = 'http://localhost:8080'  # Example URL for testing

    print("Starting the health monitor. Press Ctrl+C to stop.")
    stop_flag = start_health_monitor()

    try:
        # Keep the main thread alive to allow the background thread to run.
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutdown signal received. Stopping health monitor.")
        stop_flag.set()
        # Wait a moment for the thread to shut down.
        time.sleep(2)
        print("Health monitor stopped.")