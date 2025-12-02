# sync.py (Final Corrected Version)
import asyncio
import logging
import json
import os
import requests
import threading
from sqlalchemy.orm import joinedload
from urllib.parse import urljoin

from client_api_service import sync_with_central_server
from config import CONFIG, save_config
from database import get_db_session, db_lock
from client_models import AggregatedActivity, Project, Task, ManualBreak, LeavePeriod, EmployeeDetails, TaskActivity

logger = logging.getLogger(__name__)

sync_session = requests.Session()


def check_central_server_health():
    """
    Performs a simple API call to the central server to check for connectivity.
    Returns True if the server is reachable and responsive, False otherwise.
    """
    base_url = os.getenv("CENTRAL_DASHBOARD_URL")
    print(base_url, "sync.py")
    logger.debug(f"Checking central server health at: {base_url}")
    if not base_url:
        logger.error("CENTRAL_DASHBOARD_URL is not configured. Cannot perform health check.")
        return False

    health_check_endpoint = urljoin(base_url, "api/provision/csrf_token")
    print("sync.py=>",base_url)
    try:
        logger.info(f"Performing health check on central server at: {health_check_endpoint}")
        response = sync_session.get(health_check_endpoint, timeout=10)
        response.raise_for_status()
        logger.info("Central server is healthy.")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Central server health check failed: {e}", exc_info=True)
        return False


def _get_csrf_token_for_sync():
    """
    Fetches a CSRF token from the central server's dedicated endpoint.
    Uses the global sync_session.
    """
    base_url = os.getenv("CENTRAL_DASHBOARD_URL")
    if not base_url:
        logger.error("CENTRAL_DASHBOARD_URL is not configured. Cannot fetch CSRF token.")
        return None

    csrf_fetch_endpoint = urljoin(base_url, "api/provision/csrf_token")

    try:
        logger.debug(f"Attempting to fetch CSRF token for sync from: {csrf_fetch_endpoint}")
        csrf_api_response = sync_session.get(csrf_fetch_endpoint, timeout=10)
        csrf_api_response.raise_for_status()
        api_data = csrf_api_response.json()
        if 'csrf_token' in api_data:
            logger.debug("CSRF token obtained for sync operations.")
            return api_data['csrf_token']
        else:
            logger.warning(f"CSRF API endpoint did not return 'csrf_token' for sync. Response: {api_data}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching CSRF token for sync from {csrf_fetch_endpoint}: {e}", exc_info=True)
        return None


async def sync_task_activities(activities_payload):
    """
    Syncs new task activities to the central server.
    This function will be called by the background monitor's API endpoint.
    """
    logger.info(f"Attempting to sync {len(activities_payload)} task activities.")

    central_dashboard_url = os.getenv("CENTRAL_DASHBOARD_URL") or "http://127.0.0.1:5000"
    permanent_client_api_key = CONFIG.get('permanent_client_api_key')

    if not central_dashboard_url or not permanent_client_api_key:
        logger.error("Central server URL or API key is not configured for syncing.")
        return {'error': 'Server configuration error'}, 500

    endpoint = urljoin(central_dashboard_url, 'api/sync/tasks')
    csrf_token = _get_csrf_token_for_sync()
    if not csrf_token:
        logger.error("CSRF token missing for task activity sync. Aborting sync.")
        return {'error': 'CSRF token missing'}, 500

    headers = {
        "Authorization": f"Bearer {permanent_client_api_key}",
        "Content-Type": "application/json",
        "X-CSRFToken": csrf_token
    }

    try:
        logger.debug(f"Task activities sync payload: {json.dumps(activities_payload, indent=2)}")
        response = sync_session.post(endpoint, json=activities_payload, headers=headers, timeout=20)
        response.raise_for_status()
        logger.info(f"Successfully synced {len(activities_payload)} task activities.")
        return response.json(), response.status_code
    except requests.exceptions.RequestError as e:
        logger.error(
            f"Network error during task activity sync: {e} - Response: {e.response.text if e.response else 'No response text'}",
            exc_info=True)
        return {'error': 'Failed to sync task activities to central server'}, 500


async def sync_data():
    """
    Syncs aggregated activities from local DuckDB to remote server via API.
    This is the 'push_activities' job.
    """
    logger.info("Attempting to sync aggregated activity data (push_activities job).")
    activities_to_sync = []
    try:
        with db_lock, get_db_session() as session:
            activities_to_sync = session.query(AggregatedActivity).filter(
                AggregatedActivity.synced == False
            ).limit(10).all()
            for activity in activities_to_sync:
                session.expunge(activity)
    except Exception as e:
        logger.error(f"Failed to read from local DB for aggregated activity sync: {e}", exc_info=True)
        return

    if not activities_to_sync:
        logger.info("No unsynced aggregated activities to sync.")
        return

    central_dashboard_url = os.getenv("CENTRAL_DASHBOARD_URL")
    if not central_dashboard_url:
        logger.error("CENTRAL_DASHBOARD_URL is not configured. Aborting aggregated activity sync.")
        return

    endpoint = urljoin(central_dashboard_url, 'api/sync/activities')

    permanent_client_api_key = CONFIG.get('permanent_client_api_key')
    if not permanent_client_api_key:
        logger.error(
            "Permanent client API key not found. Cannot sync aggregated activities. Please provision client first.")
        return

    csrf_token = _get_csrf_token_for_sync()
    if not csrf_token:
        logger.error("CSRF token missing for aggregated activity sync. Aborting sync.")
        return

    headers = {
        "Authorization": f"Bearer {permanent_client_api_key}",
        "Content-Type": "application/json",
        "X-CSRFToken": csrf_token
    }

    payload_batch = []
    for activity in activities_to_sync:
        logger.debug(
            f"Preparing activity for sync: Date={activity.date}, Employee={activity.employee_id}, Total Active Time={activity.total_active_time_seconds}")
        
        # Parse and filter activity_data to remove entries with blank app names
        raw_activity_data = json.loads(activity.activity_data) if activity.activity_data else []
        filtered_activity_data = [
            event for event in raw_activity_data 
            if event.get("app_name") and event.get("app_name").strip() not in ["", ".exe", None]
        ]
        
        # Log if we filtered any entries
        if len(filtered_activity_data) < len(raw_activity_data):
            logger.warning(f"Filtered out {len(raw_activity_data) - len(filtered_activity_data)} activities with blank app names for {activity.date}")
        
        payload_batch.append({
            "employee_id": activity.employee_id,
            "date": activity.date.isoformat(),
            "total_active_time_seconds": activity.total_active_time_seconds,
            "total_idle_time_seconds": activity.total_idle_time_seconds,
            "activity_data": filtered_activity_data,
            "inactive_periods": json.loads(activity.inactive_periods) if activity.inactive_periods else [],
            "total_keystrokes": activity.total_keystrokes,
            "total_clicks": activity.total_clicks,
            "total_scrolls": activity.total_scrolls,
            "manual_breaks": json.loads(activity.manual_breaks) if activity.manual_breaks else [],
            "leave_periods": json.loads(activity.leave_periods) if activity.leave_periods else []
        })

    try:
        logger.info(f"Sending {len(payload_batch)} aggregated activities to {endpoint}")
        logger.debug(f"Aggregated activities sync payload: {json.dumps(payload_batch, indent=2)}")
        response = sync_session.post(endpoint, json=payload_batch, headers=headers, timeout=60)
        response.raise_for_status()
        logger.info(f"Sync API response status code: {response.status_code}")
        logger.debug(f"Sync API response body: {response.text}")
        response.raise_for_status()

        synced_ids = [activity.id for activity in activities_to_sync]
        if synced_ids:
            with db_lock, get_db_session() as session:
                session.query(AggregatedActivity).filter(
                    AggregatedActivity.id.in_(synced_ids)
                ).update({"synced": True}, synchronize_session=False)
                session.commit()
            logger.info(f"Successfully marked {len(synced_ids)} aggregated activities as synced in local DB.")

    except requests.exceptions.HTTPError as http_err:
        logger.error(
            f"HTTP error during aggregated activity sync: {http_err} - Response: {http_err.response.text if http_err.response else 'No response text'}",
            exc_info=True)
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(
            f"Connection error during aggregated activity sync (Is central server running and accessible?): {conn_err}",
            exc_info=True)
    except requests.exceptions.Timeout as timeout_err:
        logger.error(f"Timeout error during aggregated activity sync: {timeout_err}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred during aggregated activity sync: {e}", exc_info=True)


async def sync_projects_and_tasks():
    """
    Syncs unsynced projects and tasks from the local database to the central server.
    This is the 'push_projects_tasks' job.
    """
    logger.info("Starting project and task sync (push_projects_tasks job).")
    base_url = CONFIG.get("CENTRAL_DASHBOARD_URL")
    employee_id = CONFIG.get('employee_id')
    if not employee_id:
        logger.warning("Cannot sync projects/tasks, employee_id not configured.")
        return

    permanent_client_api_key = CONFIG.get('permanent_client_api_key')
    if not permanent_client_api_key:
        logger.error("Permanent client API key not found. Cannot sync projects/tasks. Please provision client first.")
        return

    csrf_token = _get_csrf_token_for_sync()
    if not csrf_token:
        logger.error("CSRF token missing for project/task sync. Aborting sync.")
        return

    headers = {
        "Authorization": f"Bearer {permanent_client_api_key}",
        "Content-Type": "application/json",
        "X-CSRFToken": csrf_token
    }

    projects_to_sync = []
    project_ids_to_mark_synced = []
    try:
        with db_lock, get_db_session() as session:
            projects = session.query(Project).filter(
                Project.employee_id == employee_id,
                Project.synced == False
            ).all()

            if projects:
                for p in projects:
                    projects_to_sync.append({
                        "employee_id": p.employee_id,
                        "project_name": p.project_name,
                        "status": p.status,
                        "server_project_id": p.server_project_id
                    })
                    project_ids_to_mark_synced.append(p.id)
                session.expunge_all()

        if projects_to_sync:
            logger.info(f"Found {len(projects_to_sync)} unsynced projects to sync.")
            endpoint = urljoin(base_url, "api/sync/projects")
            logger.debug(f"Projects sync payload: {json.dumps(projects_to_sync, indent=2)}")
            response = sync_session.post(endpoint, json=projects_to_sync, headers=headers,
                                         timeout=20)
            response.raise_for_status()

            with db_lock, get_db_session() as session:
                session.query(Project).filter(
                    Project.id.in_(project_ids_to_mark_synced)
                ).update({"synced": True}, synchronize_session=False)
                session.commit()
            logger.info(f"Successfully synced {len(projects_to_sync)} projects.")
        else:
            logger.info("No unsynced projects to sync.")

    except requests.exceptions.RequestException as e:
        logger.error(
            f"Network error during project sync: {e} - Response: {e.response.text if e.response else 'No response text'}",
            exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred during project sync: {e}", exc_info=True)

    tasks_to_sync = []
    task_ids_to_mark_synced = []
    try:
        with db_lock, get_db_session() as session:
            tasks = session.query(Task, Project.project_name).join(Project).filter(
                Project.employee_id == employee_id,
                Task.synced == False
            ).all()

            if tasks:
                for task, project_name in tasks:
                    tasks_to_sync.append({
                        "employee_id": employee_id,
                        "project_name": project_name,
                        "task_name": task.task_name,
                        "due_date": task.due_date.isoformat() if task.due_date else None,
                        "status": task.status,
                        "server_task_id": task.server_task_id
                    })
                    task_ids_to_mark_synced.append(task.id)
                session.expunge_all()

        if tasks_to_sync:
            logger.info(f"Found {len(tasks_to_sync)} unsynced tasks to sync.")
            endpoint = urljoin(base_url, 'api/sync/tasks')
            logger.debug(f"Tasks sync payload: {json.dumps(tasks_to_sync, indent=2)}")
            response = sync_session.post(endpoint, json=tasks_to_sync, headers=headers, timeout=20)
            response.raise_for_status()

            with db_lock, get_db_session() as session:
                session.query(Task).filter(
                    Task.id.in_(task_ids_to_mark_synced)
                ).update({"synced": True}, synchronize_session=False)
                session.commit()
            logger.info(f"Successfully synced {len(tasks_to_sync)} tasks.")
        else:
            logger.info("No unsynced tasks to sync.")

    except requests.exceptions.RequestException as e:
        logger.error(
            f"Network error during task sync: {e} - Response: {e.response.text if e.response else 'No response text'}",
            exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred during task sync: {e}", exc_info=True)


async def sync_status_data():
    """
    Syncs local break and leave periods to the server via API.
    This is the 'push_status' job.
    """
    logger.info("Performing break and leave status sync via API (push_status job).")
    breaks_to_sync, leaves_to_sync = [], []
    try:
        with db_lock, get_db_session() as session:
            breaks_to_sync = session.query(ManualBreak).filter(ManualBreak.synced == False,
                                                               ManualBreak.deleted == False).all()
            leaves_to_sync = session.query(LeavePeriod).filter(LeavePeriod.synced == False,
                                                               LeavePeriod.deleted == False).all()
            session.expunge_all()
    except Exception as e:
        logger.error(f"ORM Error reading status data for sync: {e}", exc_info=True)
        return

    if not breaks_to_sync and not leaves_to_sync:
        logger.info("No new status data (breaks/leaves) to sync.")
        return

    base_url = CONFIG.get("CENTRAL_DASHBOARD_URL")
    endpoint = urljoin(base_url, "api/sync/status")

    permanent_client_api_key = CONFIG.get('permanent_client_api_key')
    if not permanent_client_api_key:
        logger.error("Permanent client API key not found. Cannot sync status data. Please provision client first.")
        return

    csrf_token = _get_csrf_token_for_sync()
    if not csrf_token:
        logger.error("CSRF token missing for status data sync. Aborting sync.")
        return

    headers = {
        "Authorization": f"Bearer {permanent_client_api_key}",
        "Content-Type": "application/json",
        "X-CSRFToken": csrf_token
    }

    payload = {
        'breaks': [
            {"employee_id": b.employee_id, "start_time": b.start_time.isoformat(), "end_time": b.end_time.isoformat(),
             "duration_minutes": b.duration_minutes, "deleted": b.deleted}
            for b in breaks_to_sync
        ],
        'leaves': [
            {"employee_id": l.employee_id, "start_date": l.start_date.isoformat(), "end_date": l.end_date.isoformat(),
             "status": "pending", "deleted": l.deleted}
            for l in leaves_to_sync
        ]
    }

    try:
        logger.info(f"Sending {len(breaks_to_sync)} breaks and {len(leaves_to_sync)} leaves to {endpoint}")
        logger.debug(f"Status sync payload: {json.dumps(payload, indent=2)}")
        response = sync_session.post(endpoint, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        logger.info(f"Status sync API response status code: {response.status_code}")
        logger.debug(f"Status sync API response body: {response.text}")
        response.raise_for_status()

        with db_lock, get_db_session() as session:
            if breaks_to_sync:
                break_ids = [b.id for b in breaks_to_sync]
                session.query(ManualBreak).filter(ManualBreak.id.in_(break_ids)).update(
                    {"synced": True}, synchronize_session=False)
            if leaves_to_sync:
                leave_ids = [l.id for l in leaves_to_sync]
                session.query(LeavePeriod).filter(LeavePeriod.id.in_(leave_ids)).update(
                    {"synced": True}, synchronize_session=False)
            session.commit()
        logger.info(f"Successfully synced {len(breaks_to_sync)} breaks and {len(leaves_to_sync)} leaves.")

    except requests.exceptions.RequestError as e:
        logger.error(
            f"Network error during status data sync: {e} - Response: {e.response.text if e.response else 'No response text'}",
            exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error during status data sync: {e}", exc_info=True)


async def sync_employee_details():
    """
    Syncs local employee details to the central server via API.
    This is the 'push_details' job.
    """
    logger.info("Starting employee details sync (push_details job).")
    details_data, details_id = None, None
    try:
        with db_lock, get_db_session() as session:
            details_to_sync = session.query(EmployeeDetails).filter(EmployeeDetails.synced == False).first()
            if details_to_sync:
                details_id = details_to_sync.employee_id
                details_data = {
                    "employee_id": details_to_sync.employee_id, "full_name": details_to_sync.full_name,
                    "role": details_to_sync.role, "gender": details_to_sync.gender,
                    "date_of_birth": details_to_sync.date_of_birth.strftime(
                        '%Y-%m-%d') if details_to_sync.date_of_birth else None,
                    "workgroup": details_to_sync.workgroup, "department": details_to_sync.department
                }
                session.expunge(details_to_sync)
    except Exception as e:
        logger.error(f"ORM Error reading employee details for sync: {e}", exc_info=True)
        return

    if not details_data:
        logger.info("No unsynced employee details to sync.")
        return

    base_url = CONFIG.get("CENTRAL_DASHBOARD_URL")
    endpoint = urljoin(base_url, "api/sync/details")

    permanent_client_api_key = CONFIG.get('permanent_client_api_key')
    if not permanent_client_api_key:
        logger.error("Permanent client API key not found. Cannot sync employee details. Please provision client first.")
        return

    csrf_token = _get_csrf_token_for_sync()
    if not csrf_token:
        logger.error("CSRF token missing for employee details sync. Aborting sync.")
        return

    headers = {
        "Authorization": f"Bearer {permanent_client_api_key}",
        "Content-Type": "application/json",
        "X-CSRFToken": csrf_token
    }

    try:
        logger.info(f"Sending employee details for {details_id} to {endpoint}")
        response = sync_session.post(endpoint, json=details_data, headers=headers, timeout=30)
        response.raise_for_status()
        logger.info("Successfully synced employee details via API.")

        with db_lock, get_db_session() as session:
            session.query(EmployeeDetails).filter_by(employee_id=details_id).update({"synced": True},
                                                                                    synchronize_session=False)
            session.commit()
        logger.info(f"Marked employee details for {details_id} as synced in local DB.")
    except requests.exceptions.RequestError as e:
        logger.error(
            f"Network error during employee details sync: {e} - Response: {e.response.text if e.response else 'No response text'}",
            exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred during employee details sync: {e}", exc_info=True)


def sync_status_data_immediately():
    threading.Thread(target=lambda: asyncio.run(sync_status_data()), daemon=True,
                     name="ImmediateStatusSyncThread").start()


def sync_employee_details_immediately():
    threading.Thread(target=lambda: asyncio.run(sync_employee_details()), daemon=True,
                     name="ImmediateDetailsSyncThread").start()


def run_sync_in_background():
    """
    Runs the sync process in a separate thread to avoid blocking the main application.
    This is called by APScheduler.
    """
    sync_thread = threading.Thread(target=sync_with_central_server, daemon=True, name="CentralSyncPullThread")
    sync_thread.start()
    logger.debug("Started new thread for central server data pull.")