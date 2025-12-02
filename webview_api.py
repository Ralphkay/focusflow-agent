# webview_app.py

import logging
from flask import Flask, render_template, request, abort, send_from_directory
from datetime import datetime, timedelta
import os
import threading
import random

# --- Mock Data Setup ---
logging.warning("Using mock data for demonstration.")


class Base:
    def __init__(self, **kwargs):
        for k, v in kwargs.items(): setattr(self, k, v)


class Project(Base): pass


class Task(Base): pass


class TaskActivity(Base): pass  # New mock model


# Mock Data Store
MOCK_TASKS = {
    1: Task(id=1, project_id=1, name='Design navigation sidebar', status='Done', created_at=datetime.now()),
    2: Task(id=2, project_id=1, name='Implement Kanban board', status='In Progress', created_at=datetime.now()),
    3: Task(id=3, project_id=1, name='Create analytics view', status='To Do', created_at=datetime.now()),
    4: Task(id=4, project_id=2, name='Document auth endpoints', status='To Do', created_at=datetime.now())
}
MOCK_PROJECTS = {
    1: Project(id=1, name='FocusFlow UI Revamp', tasks=[MOCK_TASKS[1], MOCK_TASKS[2], MOCK_TASKS[3]]),
    2: Project(id=2, name='API Refactoring', tasks=[MOCK_TASKS[4]])
}
MOCK_TASK_ACTIVITIES = {
    1: TaskActivity(id=1, task_id=2, name="Initial component setup", start_time=datetime.now() - timedelta(hours=2),
                    end_time=datetime.now() - timedelta(hours=1)),
    2: TaskActivity(id=2, task_id=2, name="Connect to mock data API", start_time=datetime.now() - timedelta(minutes=45),
                    end_time=datetime.now() - timedelta(minutes=15)),
}


class MockSession:
    def get(self, model, ident):
        if model.__name__ == 'Project': return MOCK_PROJECTS.get(ident)
        if model.__name__ == 'Task': return MOCK_TASKS.get(ident)

    def query(self, model):
        if model.__name__ == 'Project': return list(MOCK_PROJECTS.values())
        if model.__name__ == 'Task': return list(MOCK_TASKS.values())
        return []

    def add(self, obj):
        if isinstance(obj, TaskActivity):
            new_id = max(MOCK_TASK_ACTIVITIES.keys() or [0]) + 1
            obj.id = new_id
            MOCK_TASK_ACTIVITIES[new_id] = obj

    def commit(self):
        pass


class MockDBContext:
    def __enter__(self): return MockSession()

    def __exit__(self, exc_type, exc_val, exc_tb): pass


get_db_session = MockDBContext
db_lock = threading.Lock()
# --- End Mock Data Setup ---

logger = logging.getLogger(__name__)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_FOLDER = os.path.join(APP_ROOT, 'templates')
STATIC_FOLDER = os.path.join(APP_ROOT, 'static')

app = Flask(__name__, template_folder=TEMPLATE_FOLDER, static_folder=STATIC_FOLDER)
api_object = None


def set_api_object(api):
    global api_object
    api_object = api


# --- Main Routes ---
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)


@app.route('/')
def index():
    return render_template('employee_dashboard.html')


# --- Partial Template Routes ---
@app.route('/planner')
def planner():
    """Renders the new two-panel planner view."""
    with db_lock, get_db_session() as session:
        tasks = session.query(Task)
        active_tasks = [t for t in tasks if t.status in ['To Do', 'In Progress']]
        # Select the first "In Progress" task by default, or the first task
        initial_task = next((t for t in active_tasks if t.status == 'In Progress'),
                            active_tasks[0] if active_tasks else None)

    # Fetch activities for the initial task
    activities = []
    if initial_task:
        activities = [a for a in MOCK_TASK_ACTIVITIES.values() if a.task_id == initial_task.id]

    return render_template('_planner.html', tasks=active_tasks, selected_task=initial_task, activities=activities)


@app.route('/task/<int:task_id>/activity_panel')
def get_activity_panel(task_id):
    """Renders the right-hand activity panel for a selected task."""
    with db_lock, get_db_session() as session:
        task = session.get(Task, task_id)
        if not task:
            return "<div>Task not found.</div>", 404

        activities = [a for a in MOCK_TASK_ACTIVITIES.values() if a.task_id == task_id]

    return render_template('_activity_panel.html', selected_task=task, activities=activities)


# --- Other feature routes (Timeline, Analytics, etc.) remain the same ---
@app.route('/timeline')
def timeline():
    mock_timeline = [
        {'time': '09:05 AM', 'type': 'focus', 'title': 'Focus Session Started',
         'subtitle': 'Project: FocusFlow UI Revamp'},
        {'time': '10:30 AM', 'type': 'app', 'title': 'VS Code', 'subtitle': 'Editing webview_app.py'},
    ]
    return render_template('_timeline.html', timeline_events=mock_timeline)


@app.route('/analytics')
def analytics():
    mock_chart_data = {'labels': ['VS Code', 'Chrome', 'Outlook'], 'data': [4, 2, 1]}
    mock_metrics = {'score': 88, 'focus_time': "5h 12m", 'top_app': 'VS Code'}
    return render_template('_analytics.html', metrics=mock_metrics, chart_data=mock_chart_data)


@app.route('/ai_insights')
def ai_insights():
    mock_insights = [
        {"id": 1, "title": "Morning Peak Productivity", "report_text": "Your focus was highest between 9 AM and 11 AM.",
         "insight_date": "Today"}]
    return render_template('_ai_insights.html', insights=mock_insights)


@app.route('/notifications')
def notifications():
    mock_notifications = [
        {'read': False, 'title': 'New Task Assigned', 'subtitle': 'Deploy to Staging', 'time': '1h ago'}]
    return render_template('_notifications.html', notifications=mock_notifications)


# --- Action Routes ---
@app.route('/task/<int:task_id>/log_activity', methods=['POST'])
def log_activity(task_id):
    """Adds a new TaskActivity and returns the updated activity list."""
    activity_name = request.form.get('activity_name')
    if not activity_name:
        # In a real app, you might return an error message to the user
        abort(400, "Activity name cannot be empty.")

    with db_lock, get_db_session() as session:
        new_activity = TaskActivity(
            task_id=task_id,
            name=activity_name,
            start_time=datetime.now() - timedelta(minutes=random.randint(15, 60)),
            end_time=datetime.now()
        )
        session.add(new_activity)
        session.commit()  # This adds it to our mock store

        # Re-fetch all activities for the task to render the updated list
        activities = [a for a in MOCK_TASK_ACTIVITIES.values() if a.task_id == task_id]

    # This renders *only* the list of activities, which gets swapped into the panel
    return render_template('_activity_list.html', activities=activities)
