# client_models.py

from sqlalchemy import (Column, Integer, String, DateTime, ForeignKey,
                          Boolean, Date, Float, Sequence, Text, JSON)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, date

Base = declarative_base()

# Define sequences for each table's primary key
raw_activities_id_seq = Sequence('raw_activities_id_seq')
aggregated_activities_id_seq = Sequence('aggregated_activities_id_seq')
projects_id_seq = Sequence('projects_id_seq')
tasks_id_seq = Sequence('tasks_id_seq')
task_activities_id_seq = Sequence('task_activities_id_seq')
leave_periods_id_seq = Sequence('leave_periods_id_seq')
manual_breaks_id_seq = Sequence('manual_breaks_id_seq')
inactive_periods_id_seq = Sequence('inactive_periods_id_seq')
employee_ai_insights_id_seq = Sequence('employee_ai_insights_id_seq')
business_processes_id_seq = Sequence('business_processes_id_seq')
process_tasks_id_seq = Sequence('process_tasks_id_seq')
app_config_id_seq = Sequence('app_config_id_seq')


class RawActivity(Base):
    __tablename__ = 'raw_activities'
    id = Column(Integer, raw_activities_id_seq, server_default=raw_activities_id_seq.next_value(), primary_key=True)
    employee_id = Column(String, ForeignKey('employee_details.employee_id'), nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    activity_type = Column(String)
    value = Column(String)
    application_name = Column(String)
    window_title = Column(String)
    end_time = Column(DateTime, nullable=True)
    processed = Column(Boolean, default=False, nullable=False)


class AggregatedActivity(Base):
    __tablename__ = 'aggregated_activities'
    id = Column(Integer, aggregated_activities_id_seq, server_default=aggregated_activities_id_seq.next_value(), primary_key=True)
    employee_id = Column(String, ForeignKey('employee_details.employee_id'))
    workgroup = Column(String)
    date = Column(Date, default=date.today)
    total_active_time_seconds = Column(Integer, default=0)
    total_idle_time_seconds = Column(Integer, default=0)
    total_keystrokes = Column(Integer, default=0)
    total_clicks = Column(Integer, default=0)
    total_scrolls = Column(Integer, default=0)
    synced = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    activity_data = Column(String)
    inactive_periods = Column(String)
    manual_breaks = Column(String)
    leave_periods = Column(String)

    employee = relationship("EmployeeDetails", back_populates="aggregated_activities")


class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, projects_id_seq, server_default=projects_id_seq.next_value(), primary_key=True)
    project_name = Column(String, unique=False, nullable=False)
    employee_id = Column(String, ForeignKey('employee_details.employee_id'))
    server_project_id = Column(Integer, nullable=True, unique=True)
    synced = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    status = Column(String, default="Active")

    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    employee = relationship("EmployeeDetails", back_populates="projects")


class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, tasks_id_seq, server_default=tasks_id_seq.next_value(), primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'))
    server_task_id = Column(Integer, nullable=True, unique=True)
    task_name = Column(String, nullable=False)
    due_date = Column(Date, nullable=True)
    status = Column(String, default="To Do")
    synced = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

    project = relationship("Project", back_populates="tasks")
    task_activities = relationship("TaskActivity", back_populates="task", cascade="all, delete-orphan")


class TaskActivity(Base):
    __tablename__ = 'task_activities'
    id = Column(Integer, task_activities_id_seq, server_default=task_activities_id_seq.next_value(), primary_key=True)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    server_activity_id = Column(Integer, nullable=True, unique=True)
    name = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)  # Will represent log time
    end_time = Column(DateTime, nullable=False)  # Will represent log time

    # --- NEW COLUMN ---
    duration_minutes = Column(Integer, default=0)

    status = Column(String, default="To Do", nullable=False)  # Default is now "To Do"

    # MODIFIED: Added column to store manager's approval status from the server
    manager_approval_status = Column(String, nullable=True, default='pending_review')

    synced = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

    task = relationship("Task", back_populates="task_activities")


class BusinessProcess(Base):
    __tablename__ = 'business_processes'
    id = Column(Integer, business_processes_id_seq, server_default=business_processes_id_seq.next_value(), primary_key=True)
    server_process_id = Column(Integer, nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    frequency = Column(String(50), nullable=False)
    status = Column(String(50), default='Active', nullable=False)
    synced = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    process_tasks = relationship("ProcessTask", back_populates="business_process", cascade="all, delete-orphan")


class ProcessTask(Base):
    __tablename__ = 'process_tasks'
    id = Column(Integer, process_tasks_id_seq, server_default=process_tasks_id_seq.next_value(), primary_key=True)
    server_process_task_id = Column(Integer, nullable=False, unique=True)
    process_id = Column(Integer, ForeignKey('business_processes.id'), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    expected_duration_minutes = Column(Integer, nullable=True)
    priority = Column(String(50), default='Medium', nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    mapped_apps = Column(JSON, nullable=True)
    mapped_websites = Column(JSON, nullable=True)
    mapped_keywords = Column(JSON, nullable=True)
    mapped_activity_category = Column(String(50), nullable=True)
    min_active_time_seconds = Column(Integer, default=0)
    min_keystrokes = Column(Integer, default=0)
    min_clicks = Column(Integer, default=0)
    synced = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    business_process = relationship("BusinessProcess", back_populates="process_tasks")


class EmployeeDetails(Base):
    __tablename__ = 'employee_details'
    employee_id = Column(String, primary_key=True, unique=True, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    workgroup = Column(String, nullable=True)
    department = Column(String, nullable=True)
    synced = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    aggregated_activities = relationship("AggregatedActivity", back_populates="employee")
    leave_periods = relationship("LeavePeriod", back_populates="employee")
    manual_breaks = relationship("ManualBreak", back_populates="employee")
    projects = relationship("Project", back_populates="employee")


class LeavePeriod(Base):
    __tablename__ = 'leave_periods'
    id = Column(Integer, leave_periods_id_seq, server_default=leave_periods_id_seq.next_value(), primary_key=True)
    employee_id = Column(String, ForeignKey('employee_details.employee_id'))
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    synced = Column(Boolean, default=False)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

    employee = relationship("EmployeeDetails", back_populates="leave_periods")


class ManualBreak(Base):
    __tablename__ = 'manual_breaks'
    id = Column(Integer, manual_breaks_id_seq, server_default=manual_breaks_id_seq.next_value(), primary_key=True)
    employee_id = Column(String, ForeignKey('employee_details.employee_id'))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer)
    synced = Column(Boolean, default=False)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

    employee = relationship("EmployeeDetails", back_populates="manual_breaks")


class InactivePeriod(Base):
    __tablename__ = 'inactive_periods'
    id = Column(Integer, inactive_periods_id_seq, server_default=inactive_periods_id_seq.next_value(), primary_key=True)
    employee_id = Column(String, ForeignKey('employee_details.employee_id'))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    duration = Column(Integer, default=0)
    synced = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    employee = relationship("EmployeeDetails")


class EmployeeAIInsight(Base):
    __tablename__ = 'employee_ai_insights'
    id = Column(Integer, employee_ai_insights_id_seq, server_default=employee_ai_insights_id_seq.next_value(), primary_key=True)
    employee_id = Column(String, ForeignKey('employee_details.employee_id'))
    insight_date = Column(Date, nullable=False, unique=True)
    overall_insight = Column(String, nullable=True)
    efficiency_score = Column(Float, nullable=True)
    focus_score = Column(Float, nullable=True)
    idle_time_percentage = Column(Float, nullable=True)
    synced = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    employee = relationship("EmployeeDetails")


class AppConfig(Base):
    __tablename__ = 'app_configs'
    id = Column(Integer, app_config_id_seq, server_default=app_config_id_seq.next_value(), primary_key=True)
    settings = Column(JSON, nullable=False)
    pushed_to_central = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
