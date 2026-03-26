# test_focusflow.py
# Comprehensive test script for FocusFlow Agent — validates all components
# and generates sample data payloads

import sys
import os
import json
import traceback
from datetime import datetime, date

# Ensure we can import project modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("  FocusFlow Agent — Comprehensive Test Suite")
print("=" * 70)
print()

results = []

def test(name, func):
    """Run a test and record the result."""
    print(f"[TEST] {name}...")
    try:
        result = func()
        if result:
            print(f"  ✅ PASS: {result}")
            results.append(("PASS", name, result))
        else:
            print(f"  ✅ PASS")
            results.append(("PASS", name, ""))
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        traceback.print_exc()
        results.append(("FAIL", name, str(e)))


# ===================================================================
# TEST 1: Imports
# ===================================================================
def test_imports():
    from config import CONFIG, APP_DATA_PATH, init_logging
    from database import init_db, engine, get_db_session, db_lock
    from client_models import (Base, RawActivity, AggregatedActivity, EmployeeDetails,
                               Task, Project, TaskActivity, AppConfig, LocationRecord)
    from activity import get_active_window_title, get_active_application_name, get_idle_duration
    from location_tracker import get_current_wifi_ssid, get_ip_geolocation, resolve_location
    from utils import extract_domain_or_title, clean_incognito_markers
    return "All modules imported successfully"

test("Module imports", test_imports)


# ===================================================================
# TEST 2: Database initialization with new LocationRecord table
# ===================================================================
def test_database_init():
    from database import init_db, engine
    from sqlalchemy import inspect

    init_db()
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    expected_tables = [
        'raw_activities', 'aggregated_activities', 'employee_details',
        'projects', 'tasks', 'task_activities', 'app_configs',
        'location_records'  # NEW
    ]

    missing = [t for t in expected_tables if t not in tables]
    if missing:
        raise Exception(f"Missing tables: {missing}")

    # Verify LocationRecord columns
    location_cols = [c['name'] for c in inspector.get_columns('location_records')]
    expected_cols = ['id', 'employee_id', 'timestamp', 'location_type',
                     'wifi_ssid', 'location_name', 'city', 'country',
                     'latitude', 'longitude', 'ip_address', 'synced']
    missing_cols = [c for c in expected_cols if c not in location_cols]
    if missing_cols:
        raise Exception(f"Missing columns in location_records: {missing_cols}")

    return f"DB initialized with {len(tables)} tables. location_records has {len(location_cols)} columns"

test("Database initialization (with LocationRecord)", test_database_init)


# ===================================================================
# TEST 3: WiFi SSID detection
# ===================================================================
def test_wifi_ssid():
    from location_tracker import get_current_wifi_ssid
    ssid = get_current_wifi_ssid()
    if ssid:
        return f"Connected to WiFi: '{ssid}'"
    else:
        return "No WiFi detected (Ethernet or disconnected) — fallback will be used"

test("WiFi SSID detection", test_wifi_ssid)


# ===================================================================
# TEST 4: IP Geolocation
# ===================================================================
def test_ip_geolocation():
    from location_tracker import get_ip_geolocation
    geo = get_ip_geolocation()
    if geo:
        return f"IP Geo: {geo['city']}, {geo['country']} (IP: {geo['ip_address']})"
    else:
        return "IP Geolocation unavailable (offline?) — location_type will be 'unknown'"

test("IP Geolocation fallback", test_ip_geolocation)


# ===================================================================
# TEST 5: Full location resolution (hybrid)
# ===================================================================
def test_resolve_location():
    from location_tracker import resolve_location
    location = resolve_location()
    return (
        f"type={location['location_type']}, "
        f"name={location['location_name']}, "
        f"ssid={location.get('wifi_ssid')}, "
        f"city={location.get('city')}"
    )

test("Hybrid location resolution", test_resolve_location)


# ===================================================================
# TEST 6: Activity tracking (window/app detection)
# ===================================================================
def test_activity_tracking():
    from activity import get_active_window_title, get_active_application_name, get_idle_duration

    title = get_active_window_title()
    app = get_active_application_name()
    idle = get_idle_duration()

    if not title and not app:
        raise Exception("Both window title and app name are empty")

    return f"App: {app}, Title: {title[:50]}..., Idle: {idle:.1f}s"

test("Activity tracking (Win32 APIs)", test_activity_tracking)


# ===================================================================
# TEST 7: Utils — domain extraction and incognito stripping
# ===================================================================
def test_utils():
    from utils import extract_domain_or_title, clean_incognito_markers

    # Test incognito stripping
    stripped = clean_incognito_markers("Gmail - Google Chrome - Incognito")
    assert "Incognito" not in stripped, f"Incognito not stripped: {stripped}"

    stripped2 = clean_incognito_markers("Bing - Microsoft Edge - InPrivate")
    assert "InPrivate" not in stripped2, f"InPrivate not stripped: {stripped2}"

    # Test domain extraction
    domain = extract_domain_or_title("Google - www.google.com - Google Chrome", "chrome.exe")
    assert "google" in domain.lower(), f"Domain extraction failed: {domain}"

    # Test non-browser passthrough
    title = extract_domain_or_title("Document1 - Microsoft Word", "winword.exe")
    assert title == "Document1 - Microsoft Word", f"Non-browser passthrough failed: {title}"

    return "Incognito stripping ✓, Domain extraction ✓, Non-browser passthrough ✓"

test("Utils (domain extraction, incognito stripping)", test_utils)


# ===================================================================
# TEST 8: Location recording to database
# ===================================================================
def test_location_db_write():
    from database import get_db_session, db_lock
    from client_models import LocationRecord, EmployeeDetails
    from location_tracker import resolve_location

    test_employee_id = "test.user@cbg.com.gh"

    with db_lock, get_db_session() as session:
        # Ensure test employee exists
        existing = session.query(EmployeeDetails).filter_by(employee_id=test_employee_id).first()
        if not existing:
            session.add(EmployeeDetails(
                employee_id=test_employee_id,
                full_name="Test User",
                synced=False
            ))
            session.commit()

        # Resolve and write location
        location = resolve_location()
        record = LocationRecord(
            employee_id=test_employee_id,
            timestamp=datetime.now(),
            location_type=location["location_type"],
            wifi_ssid=location.get("wifi_ssid"),
            location_name=location.get("location_name"),
            city=location.get("city"),
            country=location.get("country"),
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
            ip_address=location.get("ip_address"),
            synced=False,
        )
        session.add(record)
        session.commit()

        # Verify it was stored
        stored = session.query(LocationRecord).filter_by(
            employee_id=test_employee_id
        ).order_by(LocationRecord.id.desc()).first()

        if not stored:
            raise Exception("LocationRecord not found in database after write")

        return f"Stored: id={stored.id}, type={stored.location_type}, name={stored.location_name}"

test("Location record DB write & read", test_location_db_write)


# ===================================================================
# TEST 9: Generate sample PUSH payloads
# ===================================================================
def test_sample_push_data():
    """Generate realistic sample data showing what gets pushed to the central server."""
    from location_tracker import resolve_location

    print()
    print("=" * 70)
    print("  SAMPLE DATA PUSHED TO CENTRAL SERVER (Edge Agent)")
    print("=" * 70)

    # --- Sample 1: Aggregated Activity Push Payload ---
    sample_activity_push = {
        "employee_id": "ralph.kayode@cbg.com.gh",
        "date": date.today().isoformat(),
        "total_active_time_seconds": 21600,
        "total_idle_time_seconds": 3600,
        "total_keystrokes": 8542,
        "total_clicks": 1234,
        "total_scrolls": 567,
        "activity_data": [
            {
                "app_name": "chrome.exe",
                "window_title": "mail.google.com",
                "category": "Productive",
                "duration": 3600.0,
                "timestamp": datetime.now().isoformat(),
                "keystrokes": 2150,
                "clicks": 340,
                "scrolls": 120
            },
            {
                "app_name": "excel.exe",
                "window_title": "Q4 Financial Report.xlsx - Excel",
                "category": "Productive",
                "duration": 5400.0,
                "timestamp": datetime.now().isoformat(),
                "keystrokes": 4200,
                "clicks": 580,
                "scrolls": 200
            },
            {
                "app_name": "teams.exe",
                "window_title": "Microsoft Teams",
                "category": "Productive",
                "duration": 1800.0,
                "timestamp": datetime.now().isoformat(),
                "keystrokes": 850,
                "clicks": 120,
                "scrolls": 50
            },
            {
                "app_name": "msedge.exe",
                "window_title": "youtube.com",
                "category": "Unproductive",
                "duration": 900.0,
                "timestamp": datetime.now().isoformat(),
                "keystrokes": 42,
                "clicks": 85,
                "scrolls": 150
            }
        ],
        "inactive_periods": [
            {
                "start_time": "2026-03-18T12:00:00",
                "end_time": "2026-03-18T12:15:00",
                "duration_seconds": 900
            }
        ],
        "manual_breaks": [],
        "leave_periods": []
    }

    print("\n📊 1. AGGREGATED ACTIVITY PUSH (POST /api/sync/activities)")
    print("-" * 60)
    print(json.dumps(sample_activity_push, indent=2))

    # --- Sample 2: Location Data Push Payload ---
    current_location = resolve_location()
    sample_location_push = [
        {
            "employee_id": "ralph.kayode@cbg.com.gh",
            "timestamp": datetime.now().isoformat(),
            "location_type": current_location["location_type"],
            "wifi_ssid": current_location.get("wifi_ssid"),
            "location_name": current_location.get("location_name"),
            "city": current_location.get("city"),
            "country": current_location.get("country"),
            "latitude": current_location.get("latitude"),
            "longitude": current_location.get("longitude"),
            "ip_address": current_location.get("ip_address"),
        }
    ]

    print("\n\n📍 2. LOCATION DATA PUSH (POST /api/sync/location)")
    print("-" * 60)
    print(json.dumps(sample_location_push, indent=2))

    # --- Sample 3: Health Report Push Payload ---
    import psutil
    sample_health_push = {
        "employee_id": "ralph.kayode@cbg.com.gh",
        "timestamp": datetime.utcnow().isoformat(),
        "online_status": True,
        "pc_status": "on",
        "application_status": "running",
        "system_metrics": {
            "cpu_usage_percent": psutil.cpu_percent(interval=0.5),
            "memory_usage_percent": psutil.virtual_memory().percent,
            "disk_usage_percent": psutil.disk_usage('/').percent,
        },
        "agent_metrics": {
            "cpu_usage_percent": psutil.Process(os.getpid()).cpu_percent(interval=0.5),
            "memory_used_mb": round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 2),
            "disk_space_mb": 45.2
        }
    }

    print("\n\n💓 3. HEALTH REPORT PUSH (POST /api/health/report)")
    print("-" * 60)
    print(json.dumps(sample_health_push, indent=2))

    # --- Sample 4: Employee Details Push Payload ---
    sample_details_push = {
        "employee_id": "ralph.kayode@cbg.com.gh",
        "full_name": "Ralph Kayode",
        "role": "Software Engineer",
        "gender": "Male",
        "date_of_birth": "1990-05-15",
        "workgroup": "IT Department",
        "department": "Digital Banking"
    }

    print("\n\n👤 4. EMPLOYEE DETAILS PUSH (POST /api/sync/details)")
    print("-" * 60)
    print(json.dumps(sample_details_push, indent=2))

    # --- Sample 5: Task Activities Push ---
    sample_task_push = [
        {
            "task_id": 42,
            "project_id": 7,
            "user_id": 15,
            "name": "Review Q3 Financial Report",
            "start_time": "2026-03-18T09:00:00",
            "end_time": "2026-03-18T10:30:00",
            "duration_minutes": 90,
            "status": "Done",
            "manager_approval_status": "pending_review",
            "client_local_id": 1
        }
    ]

    print("\n\n📋 5. TASK ACTIVITIES PUSH (POST /api/sync/tasks)")
    print("-" * 60)
    print(json.dumps(sample_task_push, indent=2))

    return "All 5 sample payloads generated"

test("Generate sample PUSH payloads", test_sample_push_data)


# ===================================================================
# TEST 10: Last known location query
# ===================================================================
def test_last_known_location():
    from location_tracker import get_last_known_location

    test_employee_id = "test.user@cbg.com.gh"
    result = get_last_known_location(test_employee_id)

    if result is None:
        raise Exception("get_last_known_location returned None — expected a record from TEST 8")

    # Verify required keys exist
    required_keys = [
        "employee_id", "timestamp", "last_seen", "location_type",
        "location_name", "wifi_ssid", "city", "country",
        "latitude", "longitude", "ip_address"
    ]
    missing = [k for k in required_keys if k not in result]
    if missing:
        raise Exception(f"Missing keys in result: {missing}")

    if not result.get("last_seen"):
        raise Exception("'last_seen' field is empty")

    return (
        f"employee={result['employee_id']}, "
        f"location={result['location_name']}, "
        f"type={result['location_type']}, "
        f"last_seen={result['last_seen']}"
    )

test("Last known location query", test_last_known_location)


# ===================================================================
# SUMMARY
# ===================================================================
print()
print()
print("=" * 70)
print("  TEST RESULTS SUMMARY")
print("=" * 70)

passes = sum(1 for r in results if r[0] == "PASS")
fails = sum(1 for r in results if r[0] == "FAIL")

for status, name, detail in results:
    icon = "✅" if status == "PASS" else "❌"
    print(f"  {icon} {name}")

print()
print(f"  Total: {len(results)} tests | ✅ {passes} passed | ❌ {fails} failed")
print("=" * 70)

