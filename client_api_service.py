# client_api_service.py

import logging
from datetime import datetime, date
from urllib.parse import urljoin
import requests
import os
import threading
import json
from pathlib import Path
import uuid
import time

from sqlalchemy.orm import joinedload

from config import CONFIG, save_config, load_config
from database import get_db_session, db_lock
from client_models import (Project, Task, EmployeeDetails, TaskActivity, AppConfig,
                           AggregatedActivity, ManualBreak, LeavePeriod)

logger = logging.getLogger(__name__)


# ==============================================================================
# SECTION 1: PROVISIONING AND CONFIGURATION (PULL FROM SERVER)
# ==============================================================================

def _get_machine_id():
    """Generates a stable, unique machine identifier using the MAC address."""
    mac_num = uuid.getnode()
    mac = ':'.join(('%012X' % mac_num)[i:i + 2] for i in range(0, 12, 2))
    return f"mac_{mac}"


def _provision_client():
    """
    Handles the new agent auto-provisioning orchestration.
    This is a critical step to get the permanent API key and the server-side user ID.
    """
    if CONFIG.get('permanent_client_api_key') and CONFIG.get('employee_id'):
        logger.info("Client already has credentials. Skipping provisioning.")
        return True

    logger.info("No permanent key or employee_id found. Starting auto-provisioning process.")

    base_url = os.getenv("CENTRAL_DASHBOARD_URL")
    org_key = CONFIG.get('organization_api_key')
    company_domain = CONFIG.get('company_email_domain', '')

    if not base_url or not org_key:
        logger.error("Organization API key or Central URL not configured. Cannot provision client.")
        return False

    machine_id = _get_machine_id()
    employee_email = os.getlogin().lower() + company_domain
    payload = {
        "organization_api_key": org_key,
        "machine_id": machine_id,
        "employee_email": employee_email
    }

    register_endpoint = urljoin(base_url, "api/provision/register_agent")
    headers = {'Content-Type': 'application/json'}

    try:
        logger.info(f"Sending agent registration request to {register_endpoint} for user '{employee_email}'.")
        response = requests.post(register_endpoint, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()
        permanent_key = data.get('permanent_api_key')
        official_employee_id = data.get('employee_id')
        user_server_id = data.get('user_id')

        if permanent_key and official_employee_id and user_server_id:
            with get_db_session() as local_session:
                CONFIG['permanent_client_api_key'] = permanent_key
                CONFIG['employee_id'] = official_employee_id
                CONFIG['user_server_id'] = user_server_id
                save_config(CONFIG, local_session)
                load_config(local_session)

                # FIX: Create the local EmployeeDetails record immediately after provisioning
                existing_details = local_session.query(EmployeeDetails).filter_by(
                    employee_id=official_employee_id).first()
                if not existing_details:
                    new_details = EmployeeDetails(
                        employee_id=official_employee_id,
                        full_name=official_employee_id.split('@')[0],
                        synced=True
                    )
                    local_session.add(new_details)
                    local_session.commit()
                    logger.info("Created local EmployeeDetails record after successful provisioning.")

            logger.info(
                f"Successfully provisioned client for user '{official_employee_id}' with server ID {user_server_id}.")
            return True
        else:
            logger.error(f"Registration response was invalid. Missing key, email, or user_id. Response: {data}")
            return False
    except requests.exceptions.RequestException as e:
        if e.response:
            logger.error(f"Error during agent registration: {e}. Server responded with: {e.response.text}",
                         exc_info=True)
        else:
            logger.error(f"Error during agent registration: {e}", exc_info=True)
        return False


def _pull_app_config_from_central_server():
    base_url = os.getenv("CENTRAL_DASHBOARD_URL")
    permanent_key = CONFIG.get('permanent_client_api_key')

    if not base_url or not permanent_key:
        logger.warning("Central server URL or permanent API key is missing. Skipping config pull.")
        return False

    endpoint = urljoin(base_url, 'api/config/global')
    headers = {'X-API-Key': permanent_key}

    try:
        logger.info(f"Attempting to pull global config from central server at: {endpoint}")
        response = requests.get(endpoint, headers=headers, timeout=10)
        response.raise_for_status()

        config_data = response.json()
        if config_data:
            with get_db_session() as load_config_session:
                CONFIG.update(config_data)
                save_config(CONFIG, load_config_session)
            logger.info("Successfully pulled and updated local config from central server.")
            return True
        else:
            logger.info("No global configuration found on central server. Using local defaults.")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Error pulling config from central server: {e}", exc_info=True)
        return False


# ==============================================================================
# SECTION 2: PULLING PROJECTS & TASKS FROM SERVER
# ==============================================================================

def _fetch_projects_and_tasks():
    permanent_key = CONFIG.get('permanent_client_api_key')
    if not permanent_key:
        logger.warning("Cannot fetch data from central server: Permanent API key is missing.")
        return None

    user_server_id = CONFIG.get('user_server_id')
    if not user_server_id:
        logger.warning("Cannot fetch data from central server: user_server_id is missing.")
        return None

    base_url = os.getenv("CENTRAL_DASHBOARD_URL")
    endpoint = urljoin(base_url, "api/client/user_projects")
    headers = {'X-API-Key': permanent_key, 'Content-Type': 'application/json', 'Accept': 'application/json'}

    try:
        logger.info("Fetching projects and tasks from central server...")
        response = requests.get(endpoint, headers=headers, timeout=30)
        
        if response.status_code == 400:
            logger.warning("Server returned 400 Bad Request for user_projects endpoint. This endpoint may not be available or configured. Continuing without project data.")
            return None
        elif response.status_code == 404:
            logger.warning("Server returned 404 Not Found for user_projects endpoint. Endpoint may not exist. Continuing without project data.")
            return None
        elif response.status_code == 405:
            logger.warning("Server returned 405 Method Not Allowed for user_projects endpoint. Continuing without project data.")
            return None
        
        response.raise_for_status()
        data = response.json()
        logger.info(f"Successfully fetched {data.get('total_projects', 0)} projects from the server.")
        return data.get('projects', [])
    except requests.exceptions.RequestException as e:
        logger.warning(f"Could not fetch projects/tasks from central server: {e}. Continuing without project data.")
        return None


def _update_local_database(projects_data):
    if projects_data is None:
        logger.info("No project data provided to update local database.")
        return

    logger.info(f"Starting local database update with {len(projects_data)} projects.")
    try:
        with db_lock, get_db_session() as session:
            employee_id = CONFIG.get('employee_id')
            if not employee_id:
                logger.error("Employee ID is not configured. Cannot update local database.")
                return

            for proj_data in projects_data:
                server_project_id = proj_data.get('id')
                if not server_project_id:
                    logger.warning(f"Skipping project record from server because it is missing an 'id': {proj_data}")
                    continue

                existing_project = session.query(Project).filter_by(server_project_id=server_project_id).first()
                project_to_update = existing_project or Project(server_project_id=server_project_id)

                project_to_update.project_name = proj_data.get('name')
                project_to_update.status = proj_data.get('status', 'Active')

                merged_project = session.merge(project_to_update)
                session.flush()

                for task_data in proj_data.get('tasks', []):
                    server_task_id = task_data.get('id')
                    if not server_task_id:
                        logger.warning(f"  Skipping malformed task record from server: {task_data}")
                        continue

                    existing_task = session.query(Task).filter_by(server_task_id=server_task_id).first()
                    task_to_update = existing_task or Task(server_task_id=server_task_id)

                    task_to_update.task_name = task_data.get('name')
                    task_to_update.status = task_data.get('status', 'To Do')
                    task_to_update.due_date = datetime.fromisoformat(task_data['due_date']).date() if task_data.get(
                        'due_date') else None
                    task_to_update.project_id = merged_project.id

                    session.merge(task_to_update)

                    # =================================================================
                    # === START OF NEWLY ADDED CODE TO FIX THE COMMUNICATION GAP ===
                    # =================================================================
                    # After updating the task, sync the status of its activities.
                    for activity_data in task_data.get('task_activities', []):
                        server_activity_id = activity_data.get('id')
                        if not server_activity_id:
                            logger.warning(
                                f"  Skipping activity from server because it is missing an 'id': {activity_data}")
                            continue

                        # Find the local activity by the server's unique ID to update it.
                        local_activity = session.query(TaskActivity).filter_by(
                            server_activity_id=server_activity_id).first()

                        if local_activity:
                            logger.debug(
                                f"  Updating local activity ID {local_activity.id} (Server ID: {server_activity_id}) with new statuses.")
                            # The server is the source of truth for statuses after manager review.
                            local_activity.status = activity_data.get('status', local_activity.status)
                            local_activity.manager_approval_status = activity_data.get('manager_approval_status',
                                                                                       local_activity.manager_approval_status)
                        else:
                            # This case handles activities logged by other users on the same task.
                            # We can ignore them as the primary goal is to update the user's *own* activities.
                            logger.debug(
                                f"  Found activity with Server ID {server_activity_id} that is not present locally. Ignoring.")
                    # ===============================================================
                    # === END OF NEWLY ADDED CODE ===
                    # ===============================================================

            session.commit()
            logger.info("Local database successfully updated with data from central server.")
    except Exception as e:
        logger.error(f"Failed to update local database with central data: {e}", exc_info=True)


def sync_with_central_server():
    """Main function to PULL all necessary data from the central server."""
    logger.info("Starting sync with central server (pulling projects/tasks)...")

    if not CONFIG.get('permanent_client_api_key'):
        logger.warning("No permanent client API key found. Initiating provisioning process.")
        if not _provision_client():
            logger.error("Halting sync (pull): Client provisioning failed.")
            return

    _pull_app_config_from_central_server()
    projects_data = _fetch_projects_and_tasks()

    if projects_data:
        _update_local_database(projects_data)
    else:
        logger.warning("No project data fetched from central server. Skipping local database update.")

    logger.info("Sync with central server (pull) finished.")


# ==============================================================================
# SECTION 3: PUSHING LOCAL DATA TO SERVER
# ==============================================================================
def get_server_authenticated_session():
    """Returns a requests session with the permanent API key in headers."""
    permanent_key = CONFIG.get('permanent_client_api_key')
    if not permanent_key:
        logger.error("Cannot create authenticated session: Permanent API key is missing.")
        return None

    s = requests.Session()
    s.headers.update({'X-API-Key': permanent_key, 'Content-Type': 'application/json'})
    return s


def _serialize_object(obj, session):
    """Converts a SQLAlchemy model instance into a dictionary."""
    data = {}
    for c in obj.__table__.columns:
        val = getattr(obj, c.name)
        if isinstance(val, (datetime, date)):
            data[c.name] = val.isoformat()
        else:
            data[c.name] = val

    # Add related server IDs for the payload
    if isinstance(obj, TaskActivity):
        task = session.query(Task).options(joinedload(Task.project)).filter(Task.id == obj.task_id).first()
        if task and task.project:
            data['project_id'] = task.project.server_project_id
            data['task_id'] = task.server_task_id
        else:
            data['project_id'] = None
            data['task_id'] = None
        data['user_id'] = CONFIG.get('user_server_id')
    return data


async def sync_task_assigned_activities():
    """
    Finds unsynced TaskActivity records and pushes them to the central server.
    This corresponds to the /api/sync/tasks endpoint on sync_bp.
    """
    http_session = get_server_authenticated_session()
    if not http_session:
        logger.error("Failed to get authenticated session")
        return

    with get_db_session() as session:
        # FIX: The `with_for_update` clause is not supported by DuckDB. Removed it.
        unsynced_activities = session.query(TaskActivity).filter_by(synced=False).all()

        if not unsynced_activities:
            logger.info("No new task activities to sync.")
            return

        user_server_id = CONFIG.get('user_server_id')
        if not user_server_id:
            logger.error("Cannot sync task activities: user_server_id is not configured. Attempting to provision.")
            if not _provision_client():
                return
            user_server_id = CONFIG.get('user_server_id')
            if not user_server_id:
                logger.error("user_server_id still missing after re-provisioning attempt.")
                return

        payload = []
        for activity in unsynced_activities:
            serialized_activity = _serialize_object(activity, session)
            # NEW: Add a local ID to map the response back to the local record
            serialized_activity['client_local_id'] = activity.id
            payload.append(serialized_activity)

        # Filter out activities that couldn't be properly serialized with server IDs
        payload = [p for p in payload if p.get('task_id') and p.get('project_id')]

        if not payload:
            logger.warning("No task activities with valid server-side project/task IDs to sync.")
            return

        logger.info(f"Syncing {len(payload)} task activities to the server.")

        base_url = os.getenv("CENTRAL_DASHBOARD_URL")
        if not base_url:
            logger.error("CENTRAL_DASHBOARD_URL environment variable is not set")
            return

        endpoint = urljoin(base_url, "api/sync/tasks")

        try:
            logger.debug(f"Sending payload: {payload}")
            response = http_session.post(endpoint, json=payload, timeout=30)

            if response.status_code == 400:
                logger.error(f"Bad request error. Response content: {response.text}")
                return

            response.raise_for_status()

            response_data = response.json()
            synced_activities_list = response_data.get('synced_activities', [])

            with db_lock:
                # Update the local records with the server IDs
                for sync_map in synced_activities_list:
                    local_id = sync_map.get('client_local_id')
                    server_id = sync_map.get('server_activity_id')
                    if local_id and server_id:
                        local_activity = session.query(TaskActivity).filter_by(id=local_id).first()
                        if local_activity:
                            local_activity.server_activity_id = server_id
                            local_activity.synced = True
                session.commit()
            logger.info("Successfully synced task activities and updated local database with server IDs.")

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to sync task activities: {e}", exc_info=True)
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text}")


def sync_general_activities():
    """Pushes general aggregated activity data to the server."""
    http_session = get_server_authenticated_session()
    if not http_session:
        return

    with get_db_session() as session:
        unsynced_records = session.query(AggregatedActivity).filter_by(synced=False).all()
        if not unsynced_records:
            logger.info("No new general activities to sync.")
            return

        payload = [_serialize_object(rec, session) for rec in unsynced_records]
        logger.info(f"Syncing {len(payload)} general activity records.")

        base_url = os.getenv("CENTRAL_DASHBOARD_URL")
        endpoint = urljoin(base_url, "api/sync/activities")

        try:
            response = http_session.post(endpoint, json=payload, timeout=30)
            response.raise_for_status()

            with db_lock:
                for rec in unsynced_records:
                    rec.synced = True
                session.commit()
            logger.info("Successfully synced general activities.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to sync general activities: {e}", exc_info=True)


def sync_status_data():
    """Pushes manual breaks and leave periods to the server."""
    http_session = get_server_authenticated_session()
    if not http_session:
        return

    with get_db_session() as session:
        unsynced_breaks = session.query(ManualBreak).filter_by(synced=False).all()
        unsynced_leaves = session.query(LeavePeriod).filter_by(synced=False).all()

        if not unsynced_breaks and not unsynced_leaves:
            logger.info("No new status updates (breaks/leaves) to sync.")
            return

        payload = {
            "breaks": [_serialize_object(b, session) for b in unsynced_breaks],
            "leaves": [_serialize_object(l, session) for l in unsynced_leaves]
        }
        logger.info(f"Syncing {len(payload['breaks'])} breaks and {len(payload['leaves'])} leaves.")

        base_url = os.getenv("CENTRAL_DASHBOARD_URL")
        endpoint = urljoin(base_url, "api/sync/status")

        try:
            response = http_session.post(endpoint, json=payload, timeout=30)
            response.raise_for_status()

            with db_lock:
                for b in unsynced_breaks:
                    b.synced = True
                for l in unsynced_leaves:
                    l.synced = True
                session.commit()
            logger.info("Successfully synced status updates.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to sync status updates: {e}", exc_info=True)


def sync_employee_details():
    """Pushes local employee details to the server."""
    http_session = get_server_authenticated_session()
    if not http_session:
        return

    with get_db_session() as session:
        details_to_sync = session.query(EmployeeDetails).filter_by(synced=False).first()
        if not details_to_sync:
            logger.info("No new employee details to sync.")
            return

        payload = _serialize_object(details_to_sync, session)
        logger.info(f"Syncing employee details for {payload.get('employee_id')}.")

        base_url = os.getenv("CENTRAL_DASHBOARD_URL")
        endpoint = urljoin(base_url, "api/sync/details")

        try:
            response = http_session.post(endpoint, json=payload, timeout=30)
            response.raise_for_status()

            with db_lock:
                details_to_sync.synced = True
                session.commit()
            logger.info("Successfully synced employee details.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to sync employee details: {e}", exc_info=True)


# NEW FUNCTION: Pushes an AI-generated task plan to the server.
def push_ai_task_plan(task_id, activities):
    """Pushes an AI-generated task plan to the central server."""
    http_session = get_server_authenticated_session()
    if not http_session:
        return False

    base_url = os.getenv("CENTRAL_DASHBOARD_URL")
    endpoint = urljoin(base_url, "api/sync/ai/task-plan")

    payload = {
        "task_id": task_id,
        "activities": activities
    }

    try:
        response = http_session.post(endpoint, json=payload, timeout=30)
        response.raise_for_status()
        logger.info("Successfully synced AI task plan to central server.")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to sync AI task plan: {e}")
        return False


# ==============================================================================
# SECTION 4: BACKGROUND THREAD MANAGEMENT
# ==============================================================================

def run_sync_in_background():
    """Main function to PULL data in a background thread."""
    sync_thread = threading.Thread(target=sync_with_central_server, daemon=True, name="CentralSyncPullThread")
    sync_thread.start()
    logger.debug("Started new thread for central server data pull.")