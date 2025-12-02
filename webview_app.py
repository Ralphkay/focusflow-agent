# webview_app.py (Consolidated Client Application)

import logging
import requests
from urllib.parse import urljoin
from flask import Flask, render_template, request, jsonify, abort, send_from_directory
import os
import json
from pathlib import Path
from datetime import date, timedelta
from collections import Counter
from urllib.parse import urlparse
import ast

# Import necessary models and configuration from the local database
from database import get_db_session, db_lock
from client_models import AggregatedActivity, Project, Task, EmployeeDetails
from config import CONFIG

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_FOLDER = os.path.join(APP_ROOT, 'templates')
STATIC_FOLDER = os.path.join(APP_ROOT, 'static')

app = Flask(__name__, template_folder=TEMPLATE_FOLDER, static_folder=STATIC_FOLDER)

# Define fixed hourly cycles for the workflow timeline
FLOW_CYCLES = {
    "Dawn": {"start": 0, "end": 8},
    "Morning": {"start": 8, "end": 11},
    "Midday": {"start": 11, "end": 14},
    "Afternoon": {"start": 14, "end": 17},
    "Night": {"start": 17, "end": 24}
}


# --- Helper function for data preparation (from background_monitor) ---
def _prepare_client_data(time_period_days):
    employee_id = CONFIG.get('employee_id')
    if not employee_id:
        return None

    end_date = date.today()
    start_date = end_date - timedelta(days=time_period_days) if time_period_days > 0 else end_date

    with db_lock, get_db_session() as session:
        # User Profile and Status
        details = session.query(EmployeeDetails).filter(EmployeeDetails.employee_id == employee_id).first()
        user_profile = {
            "name": details.full_name if details and details.full_name else employee_id.split('@')[0],
            "role": details.role if details and details.role else "Member"
        }
        # Simulate tracking status (assuming a function exists in the background monitor)
        # on_leave, on_break = is_on_leave_or_break()
        on_leave, on_break = False, False  # Mocking for now
        status_text = "Active"
        if on_leave:
            status_text = "Inactive - On Leave"
        elif on_break:
            status_text = "Inactive - On Break"
        tracking_status = {"status": status_text, "is_on_break": on_break}

        # Tasks
        tasks_orm = session.query(Task).join(Project).filter(
            Task.status.in_(['To Do', 'In Progress'])
        ).order_by(Task.due_date.asc().nulls_last()).all()
        assigned_tasks = [
            {
                "id": task.id,
                "name": task.task_name,
                "project": task.project.project_name,
                "status": task.status
            } for task in tasks_orm
        ]

        # Analytics data aggregation
        activities = session.query(AggregatedActivity).filter(
            AggregatedActivity.employee_id == employee_id,
            AggregatedActivity.date >= start_date
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

                    if 'chrome' in app_name.lower() or 'firefox' in app_name.lower() or 'edge' in app_name.lower():
                        domain = window_title.split(' - ')[-1].replace('microsoft edge', '').strip()
                        if domain and domain != 'N/A':
                            if domain not in website_usage_details:
                                website_usage_details[domain] = {'time_seconds': 0, 'clicks': 0, 'keystrokes': 0,
                                                                 'scrolls': 0, 'name': domain}
                            website_usage_details[domain]['time_seconds'] += duration
                            website_usage_details[domain]['clicks'] += clicks
                            website_usage_details[domain]['keystrokes'] += keystrokes
                            website_usage_details[domain]['scrolls'] += scrolls

                    if timestamp_str:
                        event_hour = dt.fromisoformat(timestamp_str).hour
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


# --- Main Routes ---
@app.route('/')
def index():
    return render_template('employee_dashboard.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)


@app.route('/api/dashboard_data', methods=['GET'])
def get_dashboard_data():
    """
    Provides the high-level dashboard data directly from this server.
    """
    try:
        time_period_days = int(request.args.get('time_period', 1))
        data = _prepare_client_data(time_period_days)
        if not data:
            return jsonify({
                "error": "Client data not available."
            }), 404

        # We need a separate payload for the high-level dashboard data
        high_level_data = {
            "user_profile": data['user_profile'],
            "tracking_status": data['tracking_status'],
            "tasks": data['tasks'],
            "analytics_summary": data['analytics']['summary']
        }

        return jsonify(high_level_data)
    except Exception as e:
        logger.error(f"Error fetching dashboard data: {e}", exc_info=True)
        return jsonify({"error": "Failed to load dashboard data."}), 500


@app.route('/api/analytics-data', methods=['GET'])
def get_analytics_data():
    """
    Provides the detailed analytics data directly from this server.
    """
    try:
        time_period_days = int(request.args.get('time_period', 7))
        data = _prepare_client_data(time_period_days)
        if not data:
            return jsonify({
                "error": "Client data not available."
            }), 404

        return jsonify(data['analytics'])
    except Exception as e:
        logger.error(f"Error fetching analytics data: {e}", exc_info=True)
        return jsonify({"error": "Failed to load analytics data."}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)