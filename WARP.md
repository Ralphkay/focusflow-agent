# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

FocusFlow is a Windows desktop employee monitoring application built in Python. It tracks user activity, application usage, website visits, and productivity metrics. The application runs as a background service with a system tray interface and optional web dashboard.

## Architecture

### Core Components

- **Background Monitor (`background_monitor.py`)**: Main service that orchestrates all monitoring activities, manages the Flask web server, system tray interface, and coordinates data collection
- **Activity Monitor (`activity.py`)**: Tracks user input (keystrokes, clicks, scrolls), active windows, and applications using Win32 APIs and pynput
- **Database Layer (`database.py`, `client_models.py`)**: Uses DuckDB with SQLAlchemy ORM for local data storage
- **Configuration (`config.py`)**: Centralized configuration management with encryption support using Fernet
- **Sync Service (`sync.py`, `client_api_service.py`)**: Handles data synchronization with central dashboard server
- **Web Interface (`dashboard_app.py`, `webview_app.py`)**: Local Flask web server with WebView for employee dashboard

### Data Flow

1. **Activity Collection**: Input listeners capture user activity and window changes
2. **Local Storage**: Raw activities stored in DuckDB database with encryption
3. **Aggregation**: Data aggregated by time periods for analysis (`aggregation.py`)
4. **Synchronization**: Periodic sync with central server via REST API
5. **AI Analysis**: OpenAI integration for productivity insights (`ai_service.py`)

### Key Design Patterns

- **Queue-based Processing**: Activity data batched using Python queues for database writes
- **Thread-safe Operations**: Database operations protected with locks for multi-threading
- **Stealth Mode**: Configurable visibility with system tray integration using pystray
- **Configuration Encryption**: Sensitive data encrypted using Fernet symmetric encryption
- **Single Instance**: Socket-based single instance enforcement

## Development Commands

### Setup and Installation
```powershell
# Install dependencies
pip install -r requirements.txt

# Run setup script (creates local installation)
setup.bat

# Build executables with PyInstaller
python -m PyInstaller FocusFlow.spec --clean --noconfirm
python -m PyInstaller FocusFlowGuard.spec --clean --noconfirm

# Build testing installer (interactive)
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" FocusFlow_Installer.iss

# Build PDQ production installer (silent)
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" FocusFlow_Installer_PDQ.iss
```

### Running the Application
```powershell
# Start main application
python main.py

# Start background monitor directly
python background_monitor.py

# Launch dashboard only
python dashboard_app.py

# Run with WebView interface
python webview_app.py
```

### Development and Debugging
```powershell
# Check application logs
Get-Content $env:APPDATA\FocusFlow\focusflow.log -Tail 20

# Start with debug logging (modify config.py to set log level to DEBUG)
python main.py

# Test database connection
python -c "from database import init_db; init_db()"

# Test sync with central server
python -c "from sync import check_central_server_health; check_central_server_health()"
```

### Database Operations
```powershell
# Reset daily data (development use)
python -c "from cleanup import reset_daily_data; from database import get_db_session; reset_daily_data(get_db_session())"

# Check database schema
python -c "from database import engine; from sqlalchemy import inspect; print(inspect(engine).get_table_names())"
```

### Building Installers
```powershell
# Build testing installer (interactive, NO admin privileges required)
# Perfect for development and testing - can be run by standard users
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" FocusFlow_Installer.iss

# Build PDQ production installer (silent, admin privileges required)
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" FocusFlow_Installer_PDQ.iss

# Results will be in installer/ directory:
# - FocusFlow_Setup.exe (testing - user-space installation)
# - FocusFlow_Setup_PDQ.exe (production - system-wide installation)
```

## Deployment Modes

FocusFlow supports two deployment modes with different behaviors:

### Testing Mode
- **Installer**: `FocusFlow_Setup.exe` (interactive installation)
- **Admin Privileges**: **NONE REQUIRED** - runs with `PrivilegesRequired=lowest`
- **Installation Path**: `%LOCALAPPDATA%\FocusFlow` (user-space)
- **Registry**: User-level (HKCU) startup entries
- **Process Type**: Standard user process (no Windows service)
- **Uninstaller**: Available in Programs & Features
- **Behavior**: Less aggressive restart attempts, can be stopped with Ctrl+C
- **Use Case**: Development, testing, user acceptance testing

### Production Mode (PDQ)
- **Installer**: `FocusFlow_Setup_PDQ.exe` (silent installation)
- **Admin Privileges**: **REQUIRED** - needs `PrivilegesRequired=admin`
- **Installation Path**: `%PROGRAMFILES%\FocusFlow` (system-wide)
- **Registry**: System-level (HKLM) startup entries
- **Process Type**: Windows service via NSSM + registry startup
- **Uninstaller**: None - cannot be easily uninstalled
- **Behavior**: Maximum persistence, ignores termination signals, runs as Windows service
- **Use Case**: Enterprise deployment via PDQ Deploy

**Both modes show system tray icon (transparency) but with no context menus (no user control).**

### Deployment Mode Detection

The application automatically detects its deployment mode at runtime using registry entries:

1. **HKCU Detection (Testing)**: Checks `HKEY_CURRENT_USER\SOFTWARE\FocusFlow\DeploymentMode`
2. **HKLM Detection (Production)**: Checks `HKEY_LOCAL_MACHINE\SOFTWARE\FocusFlow\DeploymentMode`
3. **Fallback Detection**: Checks for uninstaller presence to determine testing mode

This detection allows the same executable to behave differently based on installation context, adjusting persistence levels, restart behavior, and signal handling appropriately.

## Environment Configuration

The application requires several environment variables in `.env`:

- `FOCUSFLOW_ORGANIZATION_API_KEY`: Authentication key for central server
- `CENTRAL_DASHBOARD_URL`: URL of the central dashboard server
- `COMPANY_EMAIL_DOMAIN`: Email domain for employee identification
- `OPENAI_API_KEY`: Required for AI-powered productivity analysis
- `FOCUSFLOW_EMPLOYEE_ID`: Optional employee identifier override
- `FOCUSFLOW_STEALTH_MODE`: Boolean flag for UI visibility

## Key Files and Directories

### Core Application Files
- `main.py`: Application entry point with watchdog launcher
- `background_monitor.py`: Main service orchestrator
- `config.py`: Configuration management with encryption
- `database.py`: Database connection and schema management
- `client_models.py`: SQLAlchemy ORM models

### Monitoring Components
- `activity.py`: User activity tracking and input monitoring
- `aggregation.py`: Data aggregation and analysis
- `health_monitor.py`: System health monitoring
- `watchdog.py`: Process monitoring and auto-restart

### Sync and Communication
- `sync.py`: Data synchronization with central server  
- `client_api_service.py`: REST API client for server communication
- `client_dashboard_bp.py`: Flask blueprint for web interface

### User Interface
- `dashboard_launcher.py`: Dashboard startup logic
- `webview_app.py`: WebView-based local interface
- `templates/employee_dashboard.html`: Web dashboard template
- `static/`: CSS and JavaScript assets
- `assets/`: Application icons and resources

### Build Artifacts
- `FocusFlow.spec`: PyInstaller spec for main application
- `FocusFlowGuard.spec`: PyInstaller spec for watchdog service
- `FocusFlow_Installer.iss`: Inno Setup script for testing installer
- `FocusFlow_Installer_PDQ.iss`: Inno Setup script for PDQ production installer
- `scripts/install_service.bat`: Windows service installation script
- `scripts/uninstall_service.bat`: Windows service removal script
- `tools/nssm.exe`: Non-Sucking Service Manager for service management

## Windows-Specific Considerations

- Uses Win32 APIs for window tracking and process monitoring
- Integrates with Windows startup registry for auto-start
- System tray integration requires Windows-specific libraries
- PyInstaller used for creating standalone executables
- Inno Setup for Windows installer creation

## Security and Privacy

- All sensitive configuration encrypted using Fernet
- Local database file stored in user's AppData directory
- Stealth mode operation with minimal UI presence
- API keys and credentials never logged in plain text
- Single instance enforcement prevents multiple copies running

## Troubleshooting

### Common Issues
- **Database Lock Errors**: Check for multiple instances running
- **Sync Failures**: Verify `CENTRAL_DASHBOARD_URL` and API keys
- **Activity Not Tracking**: Ensure proper Windows permissions for input monitoring
- **High CPU Usage**: Check activity queue processing and batch sizes

### Log Analysis
- Main log file: `%APPDATA%\FocusFlow\focusflow.log`
- Look for "CRITICAL" messages indicating configuration issues
- "WARNING" messages often indicate network or sync problems
- Thread-specific logging helps identify component issues