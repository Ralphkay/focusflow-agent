# activity.py (Final Corrected Version with Humanistic Logging)

import threading
import time
import logging
from datetime import datetime, date, timedelta
import queue
import json

import psutil
import win32gui
import win32process
import ctypes

# Import pynput for input monitoring
from pynput import keyboard, mouse

from sqlalchemy import insert
from sqlalchemy.sql.functions import func

from database import get_db_session, db_lock
from client_models import RawActivity, ManualBreak, LeavePeriod, EmployeeDetails
from config import CONFIG, LOG_FILE
# Import the new function from utils.py
from utils import extract_domain_or_title

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - %(name)s - %(levelname)s - %(message)s',
                    encoding='utf-8',
                    handlers=[logging.FileHandler(LOG_FILE, encoding='utf-8'), logging.StreamHandler()])
logger = logging.getLogger(__name__)

# --- Queue for batch database writing ---
activity_queue = queue.Queue()
input_events_queue = queue.Queue()  # NEW: Queue for raw input events

# --- Global state for input tracking ---
input_counts = {
    "keystrokes": 0,
    "clicks": 0,
    "scrolls": 0,
}
last_active_time = time.time()
active_window_info = {
    "app_name": "Desktop",
    "window_title": "Desktop"
}


# --- Windows-specific imports for last input time ---
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]


# --- Helper Functions ---
def get_active_window_title():
    try:
        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd)
    except Exception:
        return "Unknown Title"


def get_active_application_name():
    """
    Gets the name of the currently active application using multiple fallback methods.
    Returns the executable name (e.g., 'chrome.exe') or a friendly name if available.
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return "Desktop"
        
        # Method 1: Get process name via process ID
        try:
            _, proc_id = win32process.GetWindowThreadProcessId(hwnd)
            if proc_id and proc_id > 0:
                process = psutil.Process(proc_id)
                proc_name = process.name()
                if proc_name and proc_name.lower() not in ['', 'system', 'idle']:
                    return proc_name
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        
        # Method 2: Try to get the executable path and extract the filename
        try:
            _, proc_id = win32process.GetWindowThreadProcessId(hwnd)
            if proc_id and proc_id > 0:
                process = psutil.Process(proc_id)
                exe_path = process.exe()
                if exe_path:
                    import os
                    return os.path.basename(exe_path)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
            pass
        
        # Method 3: Get window class name as fallback
        try:
            class_name = win32gui.GetClassName(hwnd)
            if class_name and class_name not in ['', 'Windows.UI.Core.CoreWindow', 'ApplicationFrameWindow']:
                # Map common window class names to friendly app names
                class_to_app = {
                    'Chrome_WidgetWin_1': 'chrome.exe',
                    'MozillaWindowClass': 'firefox.exe',
                    'IEFrame': 'iexplore.exe',
                    'OpusApp': 'winword.exe',
                    'XLMAIN': 'excel.exe',
                    'PPTFrameClass': 'powerpnt.exe',
                    'rctrl_renwnd32': 'outlook.exe',
                    'Notepad': 'notepad.exe',
                    'ConsoleWindowClass': 'cmd.exe',
                    'CASCADIA_HOSTING_WINDOW_CLASS': 'windowsterminal.exe',
                    'PseudoConsoleWindow': 'powershell.exe',
                    'SunAwtFrame': 'java.exe',
                    'SALFRAME': 'soffice.exe',
                    'Vim': 'vim.exe',
                    'Emacs': 'emacs.exe',
                }
                if class_name in class_to_app:
                    return class_to_app[class_name]
                # For UWP apps, try to get a better name
                if class_name == 'ApplicationFrameWindow':
                    window_title = win32gui.GetWindowText(hwnd)
                    if window_title:
                        # Extract app name from UWP window title pattern
                        return f"{window_title.split(' - ')[0].split(' |')[0].strip()}.exe" if window_title else "UWPApp.exe"
        except Exception:
            pass
        
        # Method 4: Use window title to derive app name as last resort
        try:
            window_title = win32gui.GetWindowText(hwnd)
            if window_title:
                # Common patterns: "Document - Application" or "Application"
                parts = window_title.split(' - ')
                if len(parts) > 1:
                    app_hint = parts[-1].strip()
                    # Clean up common suffixes
                    for suffix in [' (Administrator)', ' (Not Responding)', ' [Administrator]']:
                        app_hint = app_hint.replace(suffix, '')
                    if app_hint and len(app_hint) < 50:
                        return f"{app_hint}.exe"
        except Exception:
            pass
        
        return "Desktop"
    except Exception as e:
        logger.debug(f"Error getting active application name: {e}")
        return "Desktop"


def get_idle_duration():
    """
    Retrieves the system idle time.
    Returns the idle time in seconds.
    """
    try:
        li = LASTINPUTINFO()
        li.cbSize = ctypes.sizeof(LASTINPUTINFO)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li))
        millis = ctypes.windll.kernel32.GetTickCount() - li.dwTime
        return millis / 1000.0
    except Exception as e:
        logger.error(f"Error getting system idle time: {e}", exc_info=True)
        return -1


# --- Input Listener Callbacks ---
def on_key_press(key):
    global last_active_time
    input_events_queue.put(("keystroke", None))
    last_active_time = time.time()


def on_mouse_click(x, y, button, pressed):
    global last_active_time
    if pressed:
        input_events_queue.put(("click", None))
        last_active_time = time.time()


def on_mouse_scroll(x, y, dx, dy):
    global last_active_time
    input_events_queue.put(("scroll", None))
    last_active_time = time.time()


# --- Background worker to process input events and write to DB ---
def batch_write_activities_from_queue(stop_event):
    """
    Consumes from a queue of activity records and writes them to the DB in batches.
    """
    logger.info("Activity writer thread started.")
    while not stop_event.is_set():
        batch = []
        try:
            item = activity_queue.get(timeout=5)
            batch.append(item)
            while len(batch) < 50:
                try:
                    batch.append(activity_queue.get_nowait())
                except queue.Empty:
                    break
        except queue.Empty:
            continue

        if batch:
            try:
                employee_id = CONFIG.get('employee_id')
                if not employee_id:
                    logger.error("Employee ID is not configured. Cannot write activities.")
                    continue

                for record in batch:
                    record['employee_id'] = employee_id

                with db_lock, get_db_session() as session:
                    session.execute(insert(RawActivity), batch)
                    session.commit()
                    logger.info(f"Successfully wrote {len(batch)} raw activities to the database.")
            except Exception as e:
                logger.error(f"Error writing activity batch to database: {e}", exc_info=True)
    logger.info("Activity writer thread stopped.")


# --- Core Monitoring Logic ---
def is_on_leave_or_break():
    """Checks the database to see if the user is currently on scheduled leave or a manual break."""
    employee_id = CONFIG.get('employee_id')
    if not employee_id:
        return False, False
    try:
        with db_lock, get_db_session() as session:
            on_leave = session.query(LeavePeriod).filter(
                LeavePeriod.employee_id == employee_id,
                LeavePeriod.start_date <= date.today(),
                LeavePeriod.end_date >= date.today(),
                LeavePeriod.deleted == False
            ).first() is not None
            on_break = session.query(ManualBreak).filter(
                ManualBreak.employee_id == employee_id,
                ManualBreak.start_time <= datetime.now(),
                ManualBreak.end_time >= datetime.now(),
                ManualBreak.deleted == False
            ).first() is not None
        return on_leave, on_break
    except Exception as e:
        logger.error(f"Error checking leave/break status: {e}", exc_info=True)
        return False, False


def is_tracking_active():
    """Determines if activity should be tracked based on leave and break status, and logs the status of the EmployeeDetails record."""
    employee_id = CONFIG.get('employee_id')
    if not employee_id:
        logger.debug("Tracking is inactive: Employee ID not configured.")
        return False
    try:
        with db_lock, get_db_session() as session:
            employee_exists = session.query(EmployeeDetails).filter(EmployeeDetails.employee_id == employee_id).first()

            if not employee_exists:
                logger.warning(
                    f"Tracking is inactive: EmployeeDetails record for '{employee_id}' not found in local DB.")
                return False
            else:
                logger.debug(
                    f"EmployeeDetails record for '{employee_id}' was found in the local DB. Checking leave/break status.")

        on_leave, on_break = is_on_leave_or_break()
        if on_leave:
            logger.info("Tracking is inactive: User is on leave.")
        if on_break:
            logger.info("Tracking is inactive: User is on a manual break.")

        tracking_status = not on_leave and not on_break
        logger.debug(f"Tracking status: {tracking_status}. On Leave: {on_leave}, On Break: {on_break}")
        return tracking_status
    except Exception as e:
        logger.error(f"Error checking tracking status: {e}", exc_info=True)
        return False


def start_input_listeners():
    """Starts pynput keyboard and mouse listeners in separate threads."""
    global keyboard_listener, mouse_listener
    logger.info("Starting pynput listeners for keyboard and mouse.")
    keyboard_listener = keyboard.Listener(on_press=on_key_press)
    mouse_listener = mouse.Listener(on_click=on_mouse_click, on_scroll=on_mouse_scroll)
    keyboard_listener.start()
    mouse_listener.start()

    # Start a thread to process the input event queue
    input_processor_thread = threading.Thread(target=process_input_events, daemon=True, name="InputProcessorThread")
    input_processor_thread.start()


def stop_input_listeners():
    """Stops the pynput listeners."""
    global keyboard_listener, mouse_listener
    if 'keyboard_listener' in globals() and keyboard_listener.running:
        keyboard_listener.stop()
        logger.info("Keyboard listener stopped.")
    if 'mouse_listener' in globals() and mouse_listener.running:
        mouse_listener.stop()
        logger.info("Mouse listener stopped.")


def process_input_events():
    """Processes input events from the queue and updates global counters."""
    global input_counts
    while True:
        try:
            event_type, event_data = input_events_queue.get(block=True, timeout=1)
            if event_type == "keystroke":
                input_counts["keystrokes"] += 1
            elif event_type == "click":
                input_counts["clicks"] += 1
            elif event_type == "scroll":
                input_counts["scrolls"] += 1
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"Error processing input event: {e}", exc_info=True)


def log_input_activity():
    """
    Logs the total input activity collected in the last sampling period.
    This provides humanistic logs without being overly verbose.
    """
    global input_counts
    keystrokes = input_counts["keystrokes"]
    clicks = input_counts["clicks"]
    scrolls = input_counts["scrolls"]

    if keystrokes > 0 or clicks > 0 or scrolls > 0:
        logger.info(f"Detected user input: {keystrokes} keystrokes, {clicks} clicks, {scrolls} scrolls.")
    else:
        logger.debug("No user input detected in the last minute.")


def collect_and_log_activity():
    """
    This function runs periodically to sample user activity based on system idle time.
    It adds a single record to the queue every 5 seconds.
    """
    global input_counts, last_active_time, active_window_info

    if not is_tracking_active():
        logger.debug("Activity collection skipped: Tracking is inactive.")
        return

    now = datetime.now()
    idle_threshold = CONFIG.get('idle_threshold_seconds', 300)

    # Update active window info only when the user is active
    if time.time() - last_active_time < idle_threshold:
        app_name = get_active_application_name()
        window_title = get_active_window_title()
        # Process the window title using the robust function from utils.py
        processed_title = extract_domain_or_title(window_title, app_name)
        active_window_info["app_name"] = app_name
        active_window_info["window_title"] = processed_title

    # Check for idle time
    idle_seconds = time.time() - last_active_time

    try:
        if idle_seconds > idle_threshold:
            # User is idle, log an inactive record
            record_data = {
                "timestamp": now,
                "activity_type": 'inactive',
                "value": json.dumps({"idle_duration": idle_seconds}),
                "application_name": 'System',
                "window_title": 'Idle',
                "end_time": now
            }
            activity_queue.put(record_data)
            logger.info(f"User is idle ({idle_seconds:.2f}s). Added 'inactive' record to queue.")
        else:
            # User is active, log an active record with aggregated input counts
            record_data = {
                "timestamp": now,
                "activity_type": 'active',
                "value": json.dumps({
                    "active_duration": 5,  # The duration of the sample interval
                    "keystrokes": input_counts["keystrokes"],
                    "clicks": input_counts["clicks"],
                    "scrolls": input_counts["scrolls"]
                }),
                "application_name": active_window_info["app_name"],
                "window_title": active_window_info["window_title"],
                "end_time": now + timedelta(seconds=5)
            }
            activity_queue.put(record_data)
            logger.info(
                f"User is active. Added 'active' record to queue. App: {active_window_info['app_name']}, Title: {active_window_info['window_title']}. (K:{input_counts['keystrokes']}, C:{input_counts['clicks']}, S:{input_counts['scrolls']})")

            # Reset counts after logging
            input_counts["keystrokes"] = 0
            input_counts["clicks"] = 0
            input_counts["scrolls"] = 0

    except Exception as e:
        logger.error(f"Error handling activity detection: {e}", exc_info=True)