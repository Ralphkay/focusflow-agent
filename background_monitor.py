# background_monitor.py (Corrected Version)

import threading
import logging
import time
import os
import sys
import socket
import subprocess

import requests
import webview
from pystray import Icon, Menu, MenuItem
from PIL import Image
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
from flask import Flask, jsonify, request, render_template
from datetime import datetime, timedelta, date
from sqlalchemy.exc import SQLAlchemyError
import traceback
import json
from collections import Counter
import ast
from urllib.parse import urlparse
from sqlalchemy import func

# --- App Imports ---
from activity import (collect_and_log_activity, start_input_listeners, batch_write_activities_from_queue,
                      stop_input_listeners, is_on_leave_or_break, is_tracking_active)
from aggregation import aggregate_daily_data
from database import init_db, engine, get_db_session, db_lock
from client_api_service import (run_sync_in_background, sync_with_central_server, sync_task_assigned_activities,
                                get_server_authenticated_session, push_ai_task_plan)
from cleanup import reset_daily_data
from sync import sync_data, sync_employee_details, sync_projects_and_tasks, sync_status_data, \
    check_central_server_health
from config import CONFIG, load_config, handle_encryption_key, init_logging, init_app_config
from client_models import EmployeeDetails, AggregatedActivity, Task, Project, TaskActivity, RawActivity
from health_monitor import start_health_monitor # Import the health monitor

# --- Logging and Global Setup ---
init_logging()
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH_RUNNING = os.path.join(BASE_DIR, 'assets', 'running.ico')
ICON_PATH_STOPPED = os.path.join(BASE_DIR, 'assets', 'stopped.ico')
TEMPLATE_FOLDER = os.path.join(BASE_DIR, 'templates')
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')

# Shutdown signal file for PDQ updates - placed in app directory
SHUTDOWN_SIGNAL_FILE = os.path.join(BASE_DIR, '.shutdown_signal')
# Alternative location in AppData for when app is installed
APPDATA_SHUTDOWN_SIGNAL = os.path.join(os.getenv('APPDATA', ''), 'FocusFlow', '.shutdown_signal')

# --- Global Variables ---
icon = None
scheduler = None
stop_event = threading.Event()
health_monitor_stop_event = None # To control the health monitor thread
single_instance_socket = monitor_api = Flask(__name__, template_folder=TEMPLATE_FOLDER, static_folder=STATIC_FOLDER)
MONITOR_API_PORT = 5000

# Define fixed hourly cycles for the workflow timeline
FLOW_CYCLES = {
    "Dawn": {"start": 0, "end": 8},
    "Morning": {"start": 8, "end": 11},
    "Midday": {"start": 11, "end": 14},
    "Afternoon": {"start": 14, "end": 17},
    "Night": {"start": 17, "end": 24}
}


# --- Helper function for data preparation (from employee_hub_bp.py logic) ---
def _prepare_client_data(time_period_days):
    employee_id = CONFIG.get('employee_id')
    if not employee_id:
        return None

    today = date.today()
    if time_period_days == 1:
        activity_start_date = today
    else:
        activity_start_date = today - timedelta(days=time_period_days - 1)
    activity_end_date = today + timedelta(days=1)

    with db_lock, get_db_session() as session:
        # User Profile and Status
        details = session.query(EmployeeDetails).filter(EmployeeDetails.employee_id == employee_id).first()
        user_profile = {
            "name": details.full_name if details and details.full_name else employee_id.split('@')[0],
            "role": details.role if details and details.role else "Member",
            "employee_id": employee_id
        }
        on_leave, on_break = False, False
        status_text = "Active"
        if on_leave:
            status_text = "Inactive - On Leave"
        elif on_break:
            status_text = "Inactive - On Break"
        tracking_status = {"status": status_text, "is_on_break": on_break}

        # Tasks and their related Activities
        tasks_orm = session.query(Task).join(Project).filter(
            Task.status.in_(['To Do', 'In Progress', 'Done'])
        ).order_by(Task.due_date.asc().nulls_last()).all()

        assigned_tasks = {
            'To Do': [],
            'In Progress': [],
            'Done': [],
        }
        for task_orm in tasks_orm:
            task_activities_orm = session.query(TaskActivity).filter_by(task_id=task_orm.id).order_by(
                TaskActivity.start_time.desc()).all()

            task_activities_list = [
                {
                    "id": activity.id,
                    "name": activity.name,
                    "status": activity.status,
                    "start_time": activity.start_time.isoformat(),
                    "end_time": activity.end_time.isoformat()
                } for activity in task_activities_orm
            ]

            task_data = {
                "id": task_orm.id,
                "name": task_orm.task_name,
                "project": task_orm.project.project_name,
                "status": task_orm.status,
                "task_activities": task_activities_list
            }
            assigned_tasks[task_orm.status].append(task_data)

        # Analytics data aggregation
        activities = session.query(AggregatedActivity).filter(
            AggregatedActivity.employee_id == employee_id,
            AggregatedActivity.date >= activity_start_date
        ).all()

        total_productive_seconds = 0
        total_unproductive_seconds = 0
        total_neutral_seconds = 0
        total_active_seconds = 0
        app_usage_details = {}
        website_usage_details = {}
        workflow_timeline_data = {
            cycle: {"productive_seconds": 0, "active_seconds": 0, "idle_seconds": 0}
            for cycle in FLOW_CYCLES
        }

        for agg_activity in activities:
            try:
                activity_events = json.loads(agg_activity.activity_data or '[]')
                for event in activity_events:
                    duration = float(event.get('duration', 0))
                    category = event.get('category', 'Neutral').lower()
                    app_name = event.get('app_name', 'Unknown')
                    window_title = event.get('window_title', '')
                    timestamp_str = event.get('timestamp')
                    clicks = int(event.get('clicks', 0))
                    keystrokes = int(event.get('keystrokes', 0))
                    scrolls = int(event.get('scrolls', 0))

                    total_active_seconds += duration

                    if category == 'productive':
                        total_productive_seconds += duration
                    elif category == 'unproductive':
                        total_unproductive_seconds += duration
                    else:
                        total_neutral_seconds += duration

                    if app_name and app_name != 'N/A':
                        if app_name not in app_usage_details:
                            app_usage_details[app_name] = {'time_seconds': 0, 'clicks': 0, 'keystrokes': 0,
                                                           'scrolls': 0, 'name': app_name}
                        app_usage_details[app_name]['time_seconds'] += duration
                        app_usage_details[app_name]['clicks'] += clicks
                        app_usage_details[app_name]['keystrokes'] += keystrokes
                        app_usage_details[app_name]['scrolls'] += scrolls

                    # --- FIX: More robust logic to extract the website title ---
                    if any(browser in app_name.lower() for browser in ['chrome', 'firefox', 'edge']):
                        site_title = window_title.strip()
                        parts = site_title.split(' - ')
                        if len(parts) > 1:
                            last_part_lower = parts[-1].lower()
                            if 'google chrome' in last_part_lower or 'microsoft edge' in last_part_lower or 'mozilla firefox' in last_part_lower:
                                site_title = ' - '.join(parts[:-1]).strip()
                        if site_title and site_title != 'N/A' and site_title.lower() not in ['new tab']:
                            if site_title not in website_usage_details:
                                website_usage_details[site_title] = {'time_seconds': 0, 'clicks': 0, 'keystrokes': 0,
                                                                     'scrolls': 0, 'name': site_title}
                            website_usage_details[site_title]['time_seconds'] += duration
                            website_usage_details[site_title]['clicks'] += clicks
                            website_usage_details[site_title]['keystrokes'] += keystrokes
                            website_usage_details[site_title]['scrolls'] += scrolls
                    # --- END FIX ---

                    if timestamp_str:
                        event_hour = datetime.fromisoformat(timestamp_str).hour
                        for cycle_name, times in FLOW_CYCLES.items():
                            if times["start"] <= event_hour < times["end"]:
                                workflow_timeline_data[cycle_name]["active_seconds"] += duration
                                if category == 'productive':
                                    workflow_timeline_data[cycle_name]["productive_seconds"] += duration
                                break
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Could not parse activity_data for {agg_activity.date}")
                continue

        # Summarize for analytics
        total_activity_seconds = total_productive_seconds + total_unproductive_seconds + total_neutral_seconds
        summary = {
            "productive_percent": round(
                (total_productive_seconds / total_activity_seconds * 100) if total_activity_seconds > 0 else 0, 1),
            "unproductive_percent": round(
                (total_unproductive_seconds / total_activity_seconds * 100) if total_activity_seconds > 0 else 0, 1),
            "neutral_percent": round(
                (total_neutral_seconds / total_activity_seconds * 100) if total_activity_seconds > 0 else 0, 1)
        }

        top_apps = sorted(
            [{'name': app['name'], 'minutes': round(app['time_seconds'] / 60, 2), 'clicks': app['clicks'],
              'keystrokes': app['keystrokes'], 'scrolls': app['scrolls']}
             for app in app_usage_details.values()],
            key=lambda x: x['minutes'], reverse=True
        )[:10]

        top_websites = sorted(
            [{'name': site['name'], 'minutes': round(site['time_seconds'] / 60, 2), 'clicks': site['clicks'],
              'keystrokes': site['keystrokes'], 'scrolls': site['scrolls']}
             for site in website_usage_details.values()],
            key=lambda x: x['minutes'], reverse=True
        )[:10]

        workflow_timeline_list = [
            {'cycle_name': cycle_name, 'productive_seconds': data['productive_seconds'],
             'active_seconds': data['active_seconds'], 'idle_seconds': data['idle_seconds']}
            for cycle_name, data in workflow_timeline_data.items()
        ]

    return {
        "user_profile": user_profile,
        "tracking_status": tracking_status,
        "tasks": assigned_tasks,
        "analytics": {
            "summary": summary,
            "top_apps": top_apps,
            "top_websites": top_websites,
            "workflow_timeline": workflow_timeline_list
        }
    }


def _fetch_coaching_notes_from_server(user_id):
    try:
        s = get_server_authenticated_session()
        base_url = os.getenv("CENTRAL_DASHBOARD_URL")
        response = s.get(f"{base_url}/employee-hub/{user_id}/notes")
        response.raise_for_status()
        return response.json().get('notes', [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching coaching notes for {user_id}: {e}")
        return []


def _fetch_performance_scores_from_server(user_id):
    """
    Fetches performance scores for the user from the central server.
    Correctly uses the dedicated API endpoint for client applications.
    """
    try:
        s = get_server_authenticated_session()
        base_url = os.getenv("CENTRAL_DASHBOARD_URL")

        # --- FIX: Use the correct API endpoint for client-side analytics ---
        api_endpoint = f"{base_url}/api/client/analytics/performance_scores"

        # We need to make sure the user_id is passed as a query parameter for the correct API
        response = s.get(api_endpoint, params={'user_id': user_id})
        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching performance scores for {user_id} from central API: {e}")
        return []


# --- Webview routes (consolidated API) ---
@monitor_api.route('/')
def index():
    # In stealth mode, don't serve dashboard
    if CONFIG.get('stealth_mode', True):
        return "Access denied", 403
    return render_template('employee_dashboard.html')


@monitor_api.route('/api/health')
def health_check():
    return jsonify({"status": "ok"}), 200


@monitor_api.route('/api/dashboard-analytics', methods=['GET'])
def get_dashboard_analytics_data():
    """
    Serves all dashboard data from the local database.
    """
    # In stealth mode, deny dashboard access
    if CONFIG.get('stealth_mode', True):
        return jsonify({"error": "Access denied"}), 403
        
    try:
        time_period_days = int(request.args.get('time_period', 7))
        data = _prepare_client_data(time_period_days)

        if not data:
            return jsonify({"error": "Failed to load dashboard data."}), 500

        return jsonify(data)

    except Exception as e:
        logger.error(f"Error serving local dashboard data: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred while fetching dashboard data from the local DB."}), 500


@monitor_api.route('/api/coaching-notes', methods=['GET'])
def get_coaching_notes_route():
    user_id = CONFIG.get('employee_id')
    if not user_id:
        return jsonify({"error": "User ID not configured."}), 400
    notes = _fetch_coaching_notes_from_server(user_id)
    return jsonify({'notes': notes}), 200


@monitor_api.route('/api/coaching-notes/<int:note_id>/reply', methods=['POST'])
def send_coaching_note_reply(note_id):
    user_id = CONFIG.get('employee_id')
    note_text = request.json.get('note_text')
    if not user_id or not note_text:
        return jsonify({"error": "User ID and note text are required."}), 400
    try:
        s = get_server_authenticated_session()
        base_url = os.getenv("CENTRAL_DASHBOARD_URL")
        response = s.post(
            f"{base_url}/employee-hub/{user_id}/send-note",
            json={'note_id': note_id, 'note_text': note_text}
        )
        response.raise_for_status()
        return jsonify({'message': 'Response sent successfully.'}), 200
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending note reply for {user_id}: {e}")
        return jsonify({'error': 'Failed to send note reply.'}), 500


@monitor_api.route('/api/performance-scores', methods=['GET'])
def get_performance_scores_route():
    user_id = CONFIG.get('employee_id')
    if not user_id:
        return jsonify({"error": "User ID not configured."}), 400
    scores = _fetch_performance_scores_from_server(user_id)
    return jsonify({'scores': scores}), 200


@monitor_api.route('/api/task-activity/', methods=['POST'])
def add_task_activity():
    try:
        data = request.json
        if data is None:
            return jsonify({"error": "Invalid JSON payload."}), 400
    except Exception as e:
        return jsonify({"error": "Failed to parse JSON from request."}), 500

    required_keys = ['task_id', 'name', 'status', 'start_time', 'end_time']
    if not all(k in data for k in required_keys):
        return jsonify({"error": "Missing one or more required fields."}), 400

    try:
        with db_lock, get_db_session() as session:
            parent_task = session.query(Task).get(data['task_id'])
            if not parent_task:
                return jsonify({"error": "Parent task not found in local database."}), 404

            new_activity = TaskActivity(
                task_id=parent_task.id,
                name=data.get("name"),
                start_time=datetime.fromisoformat(data['start_time']),
                end_time=datetime.fromisoformat(data['end_time']),
                status=data.get('status'),
                synced=False
            )
            session.add(new_activity)
            session.commit()
            return jsonify({"success": True, "message": "Task activity added successfully."}), 201

    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"SQLAlchemyError: Failed to save task activity: {e}", exc_info=True)
        return jsonify({"error": "Failed to save the task activity due to a database error."}), 500
    except Exception as e:
        logger.error(f"Failed to save task activity: {e}", exc_info=True)
        return jsonify({"error": "Failed to save the task activity."}), 500


@monitor_api.route('/api/task-activity/<int:activity_id>', methods=['PUT', 'DELETE'])
def manage_task_activity(activity_id):
    with db_lock, get_db_session() as session:
        activity = session.query(TaskActivity).get(activity_id)
        if not activity:
            return jsonify({"error": "Task activity not found."}), 404

        if request.method == 'PUT':
            try:
                data = request.json
                if 'name' in data:
                    activity.name = data['name']
                if 'status' in data:
                    activity.status = data['status']
                if 'start_time' in data:
                    activity.start_time = datetime.fromisoformat(data['start_time'])
                if 'end_time' in data:
                    activity.end_time = datetime.fromisoformat(data['end_time'])

                activity.synced = False
                session.commit()
                return jsonify({"message": "Task activity updated successfully."}), 200
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to update task activity: {e}", exc_info=True)
                return jsonify({"error": "Failed to update task activity."}), 500

        elif request.method == 'DELETE':
            try:
                session.delete(activity)
                session.commit()
                return jsonify({"message": "Task activity deleted successfully."}), 200
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to delete task activity: {e}", exc_info=True)
                return jsonify({"error": "Failed to delete task activity."}), 500


@monitor_api.route('/api/ai/plan', methods=['POST'])
def ai_plan_task():
    try:
        data = request.json
        if data is None:
            return jsonify({"error": "Invalid JSON payload."}), 400
    except Exception as e:
        return jsonify({"error": "Failed to parse JSON from request."}), 500

    task_id = data.get('task_id')
    user_message = data.get('user_message')

    if not task_id or not user_message:
        return jsonify({"error": "Missing task ID or user message."}), 400

    # In a real scenario, `get_ai_response` would be an external API call
    # For now, we assume it's an internal function that returns a dict.
    ai_response = {"type": "task_activities", "activities": [{"task_name": "Review Q3 report", "status": "To Do"}]}

    if 'error' in ai_response:
        return jsonify(ai_response), 500

    if ai_response.get("type") != "task_activities":
        return jsonify({"error": ai_response.get('response', 'The AI did not return a valid task plan.')}), 500

    activities = ai_response.get('activities', [])
    if not activities:
        return jsonify({"error": "AI generated an empty plan."}), 500

    try:
        with db_lock, get_db_session() as session:
            parent_task = session.query(Task).get(task_id)
            if not parent_task:
                return jsonify({"error": "Parent task not found in local database."}), 404

            for activity_data in activities:
                new_activity = TaskActivity(
                    task_id=parent_task.id,
                    name=activity_data.get("task_name"),
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    status="To Do",
                    synced=False
                )
                session.add(new_activity)
                session.flush()

                # Push the plan to the central server
                push_ai_task_plan(parent_task.server_task_id, [activity_data])

            session.commit()
            return jsonify({"success": True, "message": "Plan generated and saved successfully."})

    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"SQLAlchemyError: Failed to save AI plan to database: {e}", exc_info=True)
        return jsonify({"error": "Failed to save the generated plan due to a database error."}), 500
    except Exception as e:
        logger.error(f"Failed to save AI plan to database: {e}", exc_info=True)
        return jsonify({"error": "Failed to save the generated plan."}), 500


def run_monitor_api_server():
    # In stealth mode, disable API server to prevent local access
    if CONFIG.get('stealth_mode', True):
        logger.info("API server disabled in stealth mode")
        return
        
    try:
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        monitor_api.run(port=MONITOR_API_PORT, threaded=True)
    except Exception as e:
        logger.error(f"Failed to start internal monitor API: {e}", exc_info=True)


# --- Main Application Logic ---
def show_dashboard():
    """Launches the dashboard UI as a separate, independent process."""
    # In stealth mode, dashboard is disabled
    if CONFIG.get('stealth_mode', True):
        logger.warning("Dashboard access blocked - running in stealth mode")
        return
        
    try:
        webview.create_window('FocusFlow Dashboard', f'http://127.0.0.1:{MONITOR_API_PORT}/')
        webview.start(debug=True)
    except Exception as e:
        logger.error(f"Failed to launch webview: {e}", exc_info=True)


def check_shutdown_signal():
    """Check if a shutdown signal file exists (used by PDQ for updates)."""
    return os.path.exists(SHUTDOWN_SIGNAL_FILE) or os.path.exists(APPDATA_SHUTDOWN_SIGNAL)


def clear_shutdown_signal():
    """Remove shutdown signal files after processing."""
    try:
        if os.path.exists(SHUTDOWN_SIGNAL_FILE):
            os.remove(SHUTDOWN_SIGNAL_FILE)
        if os.path.exists(APPDATA_SHUTDOWN_SIGNAL):
            os.remove(APPDATA_SHUTDOWN_SIGNAL)
    except Exception as e:
        logger.warning(f"Could not remove shutdown signal file: {e}")


def shutdown_signal_monitor():
    """Background thread that monitors for shutdown signals from PDQ updates."""
    global icon
    logger.info("Shutdown signal monitor started.")
    while not stop_event.is_set():
        if check_shutdown_signal():
            logger.info("Shutdown signal detected - initiating graceful shutdown for update.")
            clear_shutdown_signal()
            stop_application(icon)
            break
        time.sleep(2)
    logger.info("Shutdown signal monitor stopped.")


def stop_application(icon_instance=None, item=None):
    """Performs a graceful shutdown of all application components."""
    global scheduler, single_instance_socket, health_monitor_stop_event
    logger.info("Initiating graceful application shutdown.")
    stop_event.set()
    if health_monitor_stop_event:
        health_monitor_stop_event.set()
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
    stop_input_listeners()
    if engine:
        engine.dispose()
    if single_instance_socket:
        try:
            single_instance_socket.close()
        except:
            pass
    if icon_instance:
        icon_instance.stop()
    # Clean up any shutdown signal files
    clear_shutdown_signal()


def create_menu():
    # Always return None - no menu for both testing and production
    # Users can see the icon (transparency) but cannot control the application
    return None  # No menu - users cannot interact with the icon


def start_tray_icon():
    global icon
    
    if not os.path.exists(ICON_PATH_RUNNING):
        logger.critical(f"Icon file not found: {ICON_PATH_RUNNING}. The application cannot start.")
        sys.exit(1)

    image = Image.open(ICON_PATH_RUNNING)
    menu = create_menu()  # Always None - no menu for any deployment mode

    # Always show tray icon for transparency, but never with menu
    # Users can see the application is running but cannot control it
    logger.info("Showing non-interactive tray icon - monitoring active")
    icon = Icon("FocusFlow", image, "FocusFlow - Monitoring Active", menu=menu)
    
    icon.run()


def run_async_job(job):
    try:
        # Check if job is already a coroutine
        if asyncio.iscoroutine(job):
            return asyncio.run(job)
        # Check if job() returns a coroutine
        result = job()
        if asyncio.iscoroutine(result):
            return asyncio.run(result)
        # If job is synchronous, just return its result
        return result
    except Exception as e:
        logger.error(f"Error running async job {getattr(job, '__name__', 'unknown')}: {e}",
                    exc_info=True)


def check_for_missed_cleanup():
    """
    Checks if there are old RawActivity records that were missed by a previous
    cleanup job and triggers the cleanup if found.
    """
    logger.info("Checking for missed cleanup jobs at startup.")
    try:
        with db_lock, get_db_session() as session:
            old_raw_activities = session.query(RawActivity).filter(
                func.date(RawActivity.timestamp) < date.today()
            ).first()

            if old_raw_activities:
                logger.warning("Found raw activities from a previous day. A cleanup job was likely missed.")
                reset_daily_data()
            else:
                logger.info("No missed cleanup jobs detected.")

    except Exception as e:
        logger.error(f"Error during missed cleanup check: {e}", exc_info=True)


def run_monitoring():
    global scheduler
    start_input_listeners()
    activity_writer_thread = threading.Thread(target=batch_write_activities_from_queue, args=(stop_event,), daemon=True,
                                              name="ActivityWriterThread")
    activity_writer_thread.start()

    scheduler = BackgroundScheduler(timezone="Africa/Accra")
    scheduler.add_job(collect_and_log_activity, 'interval', seconds=5, name='ActivitySampler')
    scheduler.add_job(aggregate_daily_data, 'interval', minutes=1, name='DailyAggregator')
    scheduler.add_job(lambda: run_async_job(sync_data), 'interval', minutes=5, name='PushAggregatedActivity')
    scheduler.add_job(lambda: run_async_job(sync_task_assigned_activities), 'interval', minutes=5,
                      name='PushTaskActivities')
    scheduler.add_job(lambda: run_async_job(sync_employee_details), 'interval', minutes=5, name='PushEmployeeDetails')
    scheduler.add_job(lambda: run_async_job(sync_status_data), 'interval', minutes=5, name='PushStatusData')
    scheduler.add_job(run_sync_in_background, 'interval', minutes=5, name='PullFromServer')
    scheduler.add_job(reset_daily_data, 'cron', hour=0, minute=1, name='DailyCleanup')

    scheduler.start()
    logger.info("Background monitoring and all sync jobs are now scheduled and running.")


def check_single_instance():
    global single_instance_socket
    try:
        single_instance_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        single_instance_socket.bind(("127.0.0.1", 60124))
        return True
    except OSError:
        logger.warning("Another instance of the background monitor is already running. Exiting.")
        return False


def main():
    if not check_single_instance():
        sys.exit(1)

    init_db()

    with db_lock, get_db_session() as session:
        init_app_config(session)
        load_config(session)
        if not os.getenv("CENTRAL_DASHBOARD_URL") or not CONFIG.get("organization_api_key"):
            logger.critical(
                "CRITICAL: Initial provisioning keys are missing. Please ensure configuration is set in the DB. Exiting."
            )
            sys.exit(1)
        if not CONFIG.get("employee_id"):
            logger.critical(
                "CRITICAL: Employee ID is not configured in the local database. Exiting."
            )
            sys.exit(1)

    logger.info("Performing initial synchronous sync with central server...")
    try:
        sync_with_central_server()
        logger.info("Initial sync completed successfully.")
    except Exception as e:
        logger.error(f"Initial sync failed: {e}", exc_info=True)
        pass

    with db_lock, get_db_session() as session:
        employee_id = CONFIG.get('employee_id')
        existing_details = session.query(EmployeeDetails).filter_by(employee_id=employee_id).first()
        if not existing_details:
            user_server_id = CONFIG.get('user_server_id')
            if user_server_id:
                new_details = EmployeeDetails(
                    employee_id=employee_id,
                    full_name=employee_id.split('@')[0],
                    synced=False
                )
                session.add(new_details)
                session.commit()
                logger.info(f"Fallback: Created missing EmployeeDetails record for {employee_id}.")
            else:
                logger.error("Fallback failed: user_server_id not found in config. Provisioning must run first.")

    if not check_central_server_health():
        logger.critical("CRITICAL: Failed to connect to the central server during startup health check. Exiting.")
        sys.exit(1)

    handle_encryption_key()

    # Check for missed cleanup (e.g., if PC was off at midnight)
    check_for_missed_cleanup()

    global health_monitor_stop_event
    health_monitor_stop_event = start_health_monitor()

    # Start shutdown signal monitor for PDQ updates
    shutdown_monitor_thread = threading.Thread(target=shutdown_signal_monitor, daemon=True, name="ShutdownSignalMonitor")
    shutdown_monitor_thread.start()
    logger.info("Shutdown signal monitor started for PDQ updates")

    # Only start API server if not in stealth mode
    if not CONFIG.get('stealth_mode', True):
        api_thread = threading.Thread(target=run_monitor_api_server, daemon=True, name="MonitorAPIThread")
        api_thread.start()
        logger.info("API server started for dashboard access")
    else:
        logger.info("API server disabled - running in stealth mode")

    run_monitoring()
    start_tray_icon()
    logger.info("Application has been shut down.")


if __name__ == "__main__":
    main()