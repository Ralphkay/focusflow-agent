# location_tracker.py
# Hybrid WiFi SSID + IP Geolocation location tracking module for FocusFlow

import logging
import subprocess
import re
import time
import threading
import json
from datetime import datetime

import requests

from config import CONFIG
from database import get_db_session, db_lock

logger = logging.getLogger(__name__)

# --- Module-level state ---
_last_location = None
_location_lock = threading.Lock()

# Default known office mappings (can be overridden by server config)
DEFAULT_OFFICE_MAPPINGS = {
    # Example: "CBG-HQ-5G": "Head Office, Accra"
    # These will be synced from the central server via config pull
}

# IP Geolocation API (free, no API key required, 45 requests/minute limit)
IP_GEO_API_URL = "http://ip-api.com/json/?fields=status,message,country,regionName,city,lat,lon,isp,query"
IP_GEO_TIMEOUT = 10  # seconds


def get_current_wifi_ssid():
    """
    Detects the currently connected WiFi SSID on Windows using netsh.
    Returns the SSID string or None if not connected to WiFi.
    """
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        if result.returncode != 0:
            logger.debug("netsh wlan command failed or no WiFi adapter found.")
            return None

        output = result.stdout

        # Look for the "SSID" line (but not "BSSID")
        for line in output.splitlines():
            line_stripped = line.strip()
            # Match "SSID" but not "BSSID"
            if line_stripped.startswith("SSID") and not line_stripped.startswith("BSSID"):
                parts = line_stripped.split(":", 1)
                if len(parts) == 2:
                    ssid = parts[1].strip()
                    if ssid:
                        logger.debug(f"Detected WiFi SSID: {ssid}")
                        return ssid

        logger.debug("No WiFi SSID found — may be on Ethernet or disconnected.")
        return None

    except subprocess.TimeoutExpired:
        logger.warning("WiFi SSID detection timed out.")
        return None
    except FileNotFoundError:
        logger.warning("netsh command not found — not a Windows system?")
        return None
    except Exception as e:
        logger.error(f"Error detecting WiFi SSID: {e}", exc_info=True)
        return None


def get_ip_geolocation():
    """
    Gets approximate location via IP geolocation (fallback method).
    Returns a dict with location data or None on failure.
    """
    try:
        response = requests.get(IP_GEO_API_URL, timeout=IP_GEO_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            geo_data = {
                "city": data.get("city", "Unknown"),
                "region": data.get("regionName", "Unknown"),
                "country": data.get("country", "Unknown"),
                "latitude": data.get("lat"),
                "longitude": data.get("lon"),
                "isp": data.get("isp", "Unknown"),
                "ip_address": data.get("query", "Unknown"),
            }
            logger.debug(f"IP Geolocation resolved: {geo_data['city']}, {geo_data['country']}")
            return geo_data
        else:
            logger.warning(f"IP Geolocation API returned failure: {data.get('message', 'Unknown error')}")
            return None

    except requests.exceptions.Timeout:
        logger.warning("IP Geolocation request timed out.")
        return None
    except requests.exceptions.ConnectionError:
        logger.warning("IP Geolocation request failed — no internet connection.")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"IP Geolocation request error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in IP Geolocation: {e}", exc_info=True)
        return None


def resolve_location():
    """
    Resolves the current location using a hybrid approach:
    1. Try WiFi SSID → known office mapping (primary)
    2. Fall back to IP Geolocation (secondary)

    Returns a dict with standardized location data.
    """
    # Load office mappings from config (can be updated from server)
    office_mappings = CONFIG.get("office_wifi_mappings", DEFAULT_OFFICE_MAPPINGS)

    # --- Primary: WiFi SSID ---
    ssid = get_current_wifi_ssid()
    if ssid:
        location_name = office_mappings.get(ssid)
        if location_name:
            logger.info(f"Location resolved via WiFi SSID '{ssid}' → '{location_name}'")
            return {
                "location_type": "wifi_mapped",
                "wifi_ssid": ssid,
                "location_name": location_name,
                "city": None,
                "country": None,
                "latitude": None,
                "longitude": None,
                "ip_address": None,
            }
        else:
            # Known SSID but not mapped — still record it
            logger.info(f"WiFi SSID '{ssid}' detected but not mapped to a known office.")
            return {
                "location_type": "wifi_unknown",
                "wifi_ssid": ssid,
                "location_name": f"WiFi: {ssid}",
                "city": None,
                "country": None,
                "latitude": None,
                "longitude": None,
                "ip_address": None,
            }

    # --- Fallback: IP Geolocation ---
    geo = get_ip_geolocation()
    if geo:
        logger.info(f"Location resolved via IP Geolocation → {geo['city']}, {geo['country']}")
        return {
            "location_type": "ip_geo",
            "wifi_ssid": None,
            "location_name": f"{geo['city']}, {geo['country']}",
            "city": geo["city"],
            "country": geo["country"],
            "latitude": geo["latitude"],
            "longitude": geo["longitude"],
            "ip_address": geo["ip_address"],
        }

    # --- Neither method worked ---
    logger.warning("Could not resolve location via WiFi or IP Geolocation.")
    return {
        "location_type": "unknown",
        "wifi_ssid": None,
        "location_name": "Unknown",
        "city": None,
        "country": None,
        "latitude": None,
        "longitude": None,
        "ip_address": None,
    }


def _has_location_changed(new_location):
    """
    Checks if the location has changed from the last recorded location.
    Avoids storing duplicate records when the user stays in the same place.
    """
    global _last_location
    with _location_lock:
        if _last_location is None:
            return True
        # Compare the meaningful fields
        return (
            _last_location.get("wifi_ssid") != new_location.get("wifi_ssid")
            or _last_location.get("location_name") != new_location.get("location_name")
            or _last_location.get("ip_address") != new_location.get("ip_address")
        )


def collect_location_data():
    """
    Collects the current location and stores it in the database.
    Called by APScheduler every 5 minutes.
    Only writes a new record if the location has changed.
    """
    global _last_location
    from client_models import LocationRecord  # Import here to avoid circular imports

    employee_id = CONFIG.get("employee_id")
    if not employee_id:
        logger.debug("Location tracking skipped: employee_id not configured.")
        return

    try:
        location = resolve_location()

        if not _has_location_changed(location):
            logger.debug("Location unchanged — skipping database write.")
            return

        # Write to database
        with db_lock, get_db_session() as session:
            record = LocationRecord(
                employee_id=employee_id,
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
            logger.info(
                f"Location recorded: {location['location_name']} "
                f"(type={location['location_type']}, ssid={location.get('wifi_ssid')})"
            )

        # Update the cached last-known location
        with _location_lock:
            _last_location = location

    except Exception as e:
        logger.error(f"Error collecting location data: {e}", exc_info=True)


def get_last_known_location(employee_id=None):
    """
    Returns the most recent location record for the given employee.
    If no employee_id is provided, uses the configured employee_id.
    Returns a dict with location details and a human-readable 'last_seen' string,
    or None if no records exist.
    """
    from client_models import LocationRecord

    if not employee_id:
        employee_id = CONFIG.get("employee_id")
    if not employee_id:
        logger.debug("get_last_known_location: No employee_id available.")
        return None

    try:
        with db_lock, get_db_session() as session:
            record = session.query(LocationRecord)\
                .filter(LocationRecord.employee_id == employee_id)\
                .order_by(LocationRecord.timestamp.desc())\
                .first()

            if not record:
                logger.debug(f"No location records found for employee {employee_id}.")
                return None

            # Calculate human-readable "last seen" string
            now = datetime.now()
            delta = now - record.timestamp
            minutes_ago = int(delta.total_seconds() / 60)

            if minutes_ago < 1:
                last_seen = "Just now"
            elif minutes_ago < 60:
                last_seen = f"{minutes_ago} minute{'s' if minutes_ago != 1 else ''} ago"
            elif minutes_ago < 1440:
                hours = minutes_ago // 60
                last_seen = f"{hours} hour{'s' if hours != 1 else ''} ago"
            else:
                days = minutes_ago // 1440
                last_seen = f"{days} day{'s' if days != 1 else ''} ago"

            result = {
                "employee_id": record.employee_id,
                "timestamp": record.timestamp.isoformat(),
                "last_seen": last_seen,
                "location_type": record.location_type,
                "location_name": record.location_name,
                "wifi_ssid": record.wifi_ssid,
                "city": record.city,
                "country": record.country,
                "latitude": record.latitude,
                "longitude": record.longitude,
                "ip_address": record.ip_address,
            }
            logger.info(
                f"Last known location for {employee_id}: "
                f"{record.location_name} ({record.location_type}), {last_seen}"
            )
            return result

    except Exception as e:
        logger.error(f"Error fetching last known location: {e}", exc_info=True)
        return None
