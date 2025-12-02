import subprocess
import time
import sys
import os
import psutil
import logging
import threading
import signal
import winreg
from pathlib import Path

# Enhanced configuration with deployment mode detection
MAIN_APP_EXE = "FocusFlow.exe"
SERVICE_NAME = "FocusFlowGuard"
CHECK_INTERVAL = 10  # seconds
RESTART_DELAY = 2   # seconds before restart
MAX_RESTART_ATTEMPTS = 5
RESTART_COOLDOWN = 60  # seconds

# Determine the application directory
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    APP_DIR = os.path.dirname(sys.executable)
else:
    # Running as script
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

EXE_PATH = os.path.join(APP_DIR, MAIN_APP_EXE)
LOG_PATH = os.path.join(APP_DIR, "logs", "watchdog.log")

# Deployment mode detection
def detect_deployment_mode():
    """Detect if this is a testing deployment or production deployment"""
    # Check deployment mode registry key - try HKCU first (testing), then HKLM (production)
    
    # Check HKCU (testing installation)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                           r"SOFTWARE\FocusFlow",
                           0, winreg.KEY_READ) as key:
            mode, _ = winreg.QueryValueEx(key, "DeploymentMode")
            if mode in ["TESTING", "PRODUCTION"]:
                return mode
    except (FileNotFoundError, OSError):
        pass
    
    # Check HKLM (production installation)
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                           r"SOFTWARE\FocusFlow",
                           0, winreg.KEY_READ) as key:
            mode, _ = winreg.QueryValueEx(key, "DeploymentMode")
            if mode in ["TESTING", "PRODUCTION"]:
                return mode
    except (FileNotFoundError, OSError):
        pass
    
    # Check if uninstall registry key exists (indicates testing mode)
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                           r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{8B5F5A72-3C4D-4E8F-9A1B-2C3D4E5F6789}_is1",
                           0, winreg.KEY_READ):
            return "TESTING"
    except FileNotFoundError:
        pass
    
    # Check if installed via Inno Setup (has uninstaller)
    uninstaller_path = os.path.join(APP_DIR, "unins000.exe")
    if os.path.exists(uninstaller_path):
        return "TESTING"
    
    # Default to production mode
    return "PRODUCTION"

DEPLOYMENT_MODE = detect_deployment_mode()

# Setup logging
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FocusFlowWatchdog:
    def __init__(self):
        self.running = True
        self.restart_count = 0
        self.last_restart_time = 0
        self.deployment_mode = DEPLOYMENT_MODE
        
        # Adjust behavior based on deployment mode
        if self.deployment_mode == "TESTING":
            # Less aggressive in testing mode
            self.check_interval = 15  # Slower monitoring
            self.max_restart_attempts = 3  # Fewer restart attempts
            logger.info("Running in TESTING mode - user-friendly behavior")
        else:
            # More aggressive in production mode
            self.check_interval = CHECK_INTERVAL
            self.max_restart_attempts = MAX_RESTART_ATTEMPTS
            logger.info("Running in PRODUCTION mode - maximum persistence")
            
            # Setup signal handlers to prevent easy termination (production only)
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"FocusFlow Watchdog started. Monitoring: {EXE_PATH}")
        logger.info(f"Deployment mode: {self.deployment_mode}")
    
    def _signal_handler(self, signum, frame):
        """Handle termination signals - ignore them in production mode"""
        if self.deployment_mode == "PRODUCTION":
            logger.warning(f"Received signal {signum}. Watchdog continues running (Production Mode).")
            # Don't actually terminate in production
        else:
            logger.info(f"Received signal {signum}. Shutting down (Testing Mode).")
            self.running = False
    
    def is_process_running(self, process_name):
        """Check if the main application is running"""
        try:
            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    proc_info = proc.info
                    if (process_name.lower() in proc_info['name'].lower() or 
                        (proc_info['exe'] and EXE_PATH.lower() in proc_info['exe'].lower())):
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as e:
            logger.error(f"Error checking process: {e}")
        return False
    
    def start_application(self):
        """Start the main application with error handling"""
        if not os.path.exists(EXE_PATH):
            logger.error(f"Application executable not found: {EXE_PATH}")
            return False
        
        try:
            # Start the application in a new process group
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
            if self.deployment_mode == "PRODUCTION":
                # Additional isolation in production mode
                creation_flags |= subprocess.CREATE_NO_WINDOW
            
            process = subprocess.Popen(
                [EXE_PATH],
                cwd=APP_DIR,
                creationflags=creation_flags
            )
            logger.info(f"Started {MAIN_APP_EXE} with PID: {process.pid}")
            return True
        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            return False
    
    def check_restart_limit(self):
        """Check if we've exceeded restart limits"""
        current_time = time.time()
        
        # Reset restart count if enough time has passed
        if current_time - self.last_restart_time > RESTART_COOLDOWN:
            self.restart_count = 0
        
        if self.restart_count >= self.max_restart_attempts:
            logger.warning(f"Maximum restart attempts ({self.max_restart_attempts}) reached. Waiting {RESTART_COOLDOWN} seconds.")
            time.sleep(RESTART_COOLDOWN)
            self.restart_count = 0
        
        return self.restart_count < self.max_restart_attempts
    
    def register_as_startup_program(self):
        """Register in Windows startup registry"""
        if self.deployment_mode == "PRODUCTION":
            # Use HKLM in production (system-wide, harder to remove)
            registry_key = winreg.HKEY_LOCAL_MACHINE
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        else:
            # Use HKCU in testing (user-specific, easier to remove)
            registry_key = winreg.HKEY_CURRENT_USER
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
            
        try:
            with winreg.OpenKey(registry_key, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, SERVICE_NAME, 0, winreg.REG_SZ, f'"{sys.executable}"')
            logger.info(f"Registered in Windows startup registry ({registry_key})")
        except Exception as e:
            logger.warning(f"Could not register in startup registry: {e}")
    
    def run_watchdog(self):
        """Main watchdog loop"""
        self.register_as_startup_program()
        
        while self.running:
            try:
                if not self.is_process_running(MAIN_APP_EXE):
                    logger.info(f"{MAIN_APP_EXE} is not running. Attempting restart...")
                    
                    if self.check_restart_limit():
                        time.sleep(RESTART_DELAY)  # Brief delay before restart
                        
                        if self.start_application():
                            self.restart_count += 1
                            self.last_restart_time = time.time()
                        else:
                            logger.error("Failed to restart application")
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                if self.deployment_mode == "TESTING":
                    logger.info("Keyboard interrupt received - shutting down (Testing Mode)")
                    break
                else:
                    logger.info("Keyboard interrupt received - ignoring (Production Mode)")
                    continue
            except Exception as e:
                logger.error(f"Unexpected error in watchdog loop: {e}")
                time.sleep(self.check_interval)
                continue

def run_watchdog():
    """Entry point for backward compatibility"""
    watchdog = FocusFlowWatchdog()
    watchdog.run_watchdog()

if __name__ == '__main__':
    run_watchdog()
