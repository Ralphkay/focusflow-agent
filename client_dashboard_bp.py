# client_dashboard_bp.py

import json
from flask import Blueprint, render_template, request, jsonify, g
from datetime import date, timedelta, datetime
from sqlalchemy import func as sa_func, distinct
from sqlalchemy.orm import joinedload
from collections import Counter
import ast
from urllib.parse import urlparse

from database import get_db_session, db_lock
from client_models import AggregatedActivity, Project, Task, TaskActivity
from config import CONFIG, load_config
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

client_dashboard_bp = Blueprint('client_dashboard_bp', __name__)

# Define fixed hourly cycles for the workflow timeline
FLOW_CYCLES = {
    "Dawn": {"start": 0, "end": 8},
    "Morning": {"start": 8, "end": 11},
    "Midday": {"start": 11, "end": 14},
    "Afternoon": {"start": 14, "end": 17},
    "Night": {"start": 17, "end": 24}
}


# The main dashboard route for the webview client
@client_dashboard_bp.route('/')
def dashboard_home():
    return render_template('employee_dashboard.html')


@client_dashboard_bp.route('/api/dashboard_data', methods=['GET'])
def get_dashboard_data():
    """
    Provides a high-level overview of the user's profile and current status.
    """
    # Simulate data fetching for the client's profile and tasks
    # The real implementation will query the local database
    employee_id = CONFIG.get('employee_id')

    if not employee_id:
        return jsonify({
            "error": "Client not provisioned. Please contact your administrator."
        }), 403

    # The actual implementation would query the local DB for `EmployeeDetails`
    user_profile = {
        "name": employee_id.split('@')[0],
        "role": "Member"  # Default role for client
    }

    # Simulate tracking status
    tracking_status = {
        "status": "Active",
        "is_on_break": False
    }

    # Simulate fetching tasks from the local DB
    with db_lock, get_db_session() as session:
        tasks_orm = session.query(Task).join(Project).filter(
            Task.status.in_(['To Do', 'In Progress'])
        ).all()

        assigned_tasks = [
            {
                "id": task.id,
                "name": task.task_name,
                "project": task.project.project_name,
                "status": task.status
            } for task in tasks_orm
        ]

    dashboard_data = {
        "user_profile": user_profile,
        "tracking_status": tracking_status,
        "tasks": assigned_tasks,
        "duties": []
    }

    return jsonify(dashboard_data)


@client_dashboard_bp.route('/api/analytics-data', methods=['GET'])
def get_analytics_data():
    """
    Provides detailed analytics for the current user for a given time period.
    This replaces the old `get_analytics_data` in `background_monitor.py`.
    """
    time_period_days = int(request.args.get('time_period', 7))
    employee_id = CONFIG.get('employee_id')

    if not employee_id:
        return jsonify({"error": "Employee ID not configured."}), 500

    end_date = date.today()
    start_date = end_date - timedelta(days=time_period_days) if time_period_days > 0 else end_date

    with db_lock, get_db_session() as session:
        activities = session.query(AggregatedActivity).filter(
            AggregatedActivity.employee_id == employee_id,
            AggregatedActivity.date >= start_date
        ).all()

        # Initialize data structures for aggregation
        total_productive_seconds = 0
        total_unproductive_seconds = 0
        total_neutral_seconds = 0
        app_usage_details = {}
        website_usage_details = {}
        workflow_timeline = {
            cycle: {"productive_seconds": 0, "active_seconds": 0, "idle_seconds": 0}
            for cycle in FLOW_CYCLES
        }

        # Process all activities in the given period
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

                    if category == 'productive':
                        total_productive_seconds += duration
                    elif category == 'unproductive':
                        total_unproductive_seconds += duration
                    else:
                        total_neutral_seconds += duration

                    # Aggregate app usage
                    if app_name and app_name != 'N/A':
                        if app_name not in app_usage_details:
                            app_usage_details[app_name] = {'time_seconds': 0, 'clicks': 0, 'keystrokes': 0,
                                                           'scrolls': 0, 'name': app_name}
                        app_usage_details[app_name]['time_seconds'] += duration
                        app_usage_details[app_name]['clicks'] += clicks
                        app_usage_details[app_name]['keystrokes'] += keystrokes
                        app_usage_details[app_name]['scrolls'] += scrolls

                    # Aggregate website usage
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

                    # Aggregate for workflow timeline
                    if timestamp_str:
                        event_hour = datetime.fromisoformat(timestamp_str).hour
                        for cycle_name, times in FLOW_CYCLES.items():
                            if times["start"] <= event_hour < times["end"]:
                                workflow_timeline[cycle_name]["active_seconds"] += duration
                                if category == 'productive':
                                    workflow_timeline[cycle_name]["productive_seconds"] += duration
                                break
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Could not parse activity_data for {agg_activity.date}")
                continue

        total_activity_seconds = total_productive_seconds + total_unproductive_seconds + total_neutral_seconds

        # Prepare final analytics data
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

        # Process workflow timeline for frontend
        workflow_timeline_list = [
            {'cycle_name': cycle_name, 'productive_seconds': data['productive_seconds'],
             'active_seconds': data['active_seconds'], 'idle_seconds': data['idle_seconds']}
            for cycle_name, data in workflow_timeline.items()
        ]

        analytics_data = {
            "summary": summary,
            "top_apps": top_apps,
            "top_websites": top_websites,
            "workflow_timeline": workflow_timeline_list
        }

    return jsonify(analytics_data)