# aggregation.py (Final Corrected Version)

import json
import logging
from datetime import datetime, date

import pytz
from sqlalchemy import func

from client_models import RawActivity, AggregatedActivity, EmployeeDetails
from config import CONFIG
from database import get_db_session, db_lock

logger = logging.getLogger(__name__)

ACTIVITY_SAMPLE_DURATION_SECONDS = 5


def aggregate_daily_data():
    """
    Aggregates raw activity data into a daily summary based on the new
    periodic sampling model.
    """
    today = date.today()
    employee_id = CONFIG.get("employee_id")
    if not employee_id:
        logger.warning("Aggregation skipped: Employee ID is not configured.")
        return

    logger.info(f"Starting aggregation for {today}, employee_id={employee_id}")

    try:
        with db_lock, get_db_session() as session:
            unprocessed_activities = session.query(RawActivity).filter(
                RawActivity.employee_id == employee_id,
                func.date(RawActivity.timestamp) == today,
                RawActivity.processed == False
            ).all()

            if not unprocessed_activities:
                logger.info("No new raw activities to aggregate.")
                return

            logger.debug(f"Found {len(unprocessed_activities)} unprocessed raw activity records.")

            agg_activity = session.query(AggregatedActivity).filter_by(
                employee_id=employee_id, date=today
            ).first()

            if not agg_activity:
                employee_details = session.query(EmployeeDetails).filter_by(employee_id=employee_id).first()
                workgroup = employee_details.workgroup if employee_details and employee_details.workgroup else 'Default'
                logger.info(f"Creating new aggregated activity record for {today} with workgroup: {workgroup}")
                agg_activity = AggregatedActivity(
                    employee_id=employee_id, date=today, workgroup=workgroup,
                    created_at=datetime.now(pytz.utc),
                    activity_data=json.dumps([]), inactive_periods=json.dumps([]),
                    total_keystrokes=0, total_clicks=0, total_scrolls=0
                )
                session.add(agg_activity)
                session.flush()

            # Fix: Ensure aggregated_list is loaded correctly as a list of dictionaries
            aggregated_list = []
            if agg_activity.activity_data:
                try:
                    aggregated_list = json.loads(agg_activity.activity_data)
                except json.JSONDecodeError:
                    logger.error("Failed to decode existing activity_data, resetting to empty list.")

            inactive_periods_list = []
            if agg_activity.inactive_periods:
                try:
                    inactive_periods_list = json.loads(agg_activity.inactive_periods)
                except json.JSONDecodeError:
                    logger.error("Failed to decode existing inactive_periods, resetting to empty list.")

            # This map stores aggregated counts for each unique app/website to merge new events
            # Structure: { ("app_name", "window_title"): {"duration": X, "keystrokes": Y, ...} }
            activity_map = {}
            for event in aggregated_list:
                key = (event.get("app_name"), event.get("window_title"))
                activity_map[key] = {
                    "duration": event.get("duration", 0),
                    "keystrokes": event.get("keystrokes", 0),
                    "clicks": event.get("clicks", 0),
                    "scrolls": event.get("scrolls", 0),
                    "category": event.get("category", "Neutral"),
                    "timestamp": event.get("timestamp")
                }

            # --- Counters for the total metrics on the AggregatedActivity object ---
            newly_processed_idle_seconds = 0
            newly_processed_keystrokes = 0
            newly_processed_clicks = 0
            newly_processed_scrolls = 0
            newly_processed_active_time = 0

            for raw in unprocessed_activities:
                interaction_data = {}
                if raw.value:
                    try:
                        interaction_data = json.loads(raw.value)
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(f"Could not decode JSON for raw activity value: {raw.value}")
                        interaction_data = {}

                if raw.activity_type == 'active':
                    duration = interaction_data.get("active_duration", ACTIVITY_SAMPLE_DURATION_SECONDS)
                    app_name = raw.application_name
                    window_title = raw.window_title

                    # Get input counts from the raw activity record
                    k_count = interaction_data.get("keystrokes", 0)
                    c_count = interaction_data.get("clicks", 0)
                    s_count = interaction_data.get("scrolls", 0)

                    newly_processed_active_time += duration
                    newly_processed_keystrokes += k_count
                    newly_processed_clicks += c_count
                    newly_processed_scrolls += s_count

                    # Determine category using enhanced logic
                    try:
                        from categorization import categorize_activity
                        category = categorize_activity(app_name, window_title)
                    except Exception as e:
                        logger.debug(f"Enhanced categorization failed, falling back. Error: {e}")
                        category = CONFIG.get("app_config", {}).get(app_name.lower(), {}).get("category", "Neutral")

                    activity_event = {
                        "app_name": app_name,
                        "window_title": window_title,
                        "duration": duration,
                        "timestamp": raw.timestamp.isoformat(),
                        "category": category,
                        "keystrokes": k_count,
                        "clicks": c_count,
                        "scrolls": s_count,
                    }
                    aggregated_list.append(activity_event)
                    logger.debug(
                        f"Added active event: App={app_name}, Title={window_title}, Category={category}, K={k_count}, C={c_count}, S={s_count}")

                elif raw.activity_type == 'inactive' and raw.end_time:
                    duration = (raw.end_time - raw.timestamp).total_seconds()
                    if duration > 0:
                        inactive_periods_list.append({
                            "start_time": raw.timestamp.isoformat(),
                            "end_time": raw.end_time.isoformat(),
                            "duration": duration,
                        })
                        newly_processed_idle_seconds += duration
                        logger.debug(
                            f"Added inactive period: Start={raw.timestamp}, End={raw.end_time}, Duration={duration}")

            # Update the AggregatedActivity object with the new totals
            agg_activity.activity_data = json.dumps(aggregated_list)
            agg_activity.inactive_periods = json.dumps(inactive_periods_list)
            agg_activity.total_idle_time_seconds = (
                                                           agg_activity.total_idle_time_seconds or 0) + newly_processed_idle_seconds
            agg_activity.total_active_time_seconds = (
                                                             agg_activity.total_active_time_seconds or 0) + newly_processed_active_time
            agg_activity.total_keystrokes = (agg_activity.total_keystrokes or 0) + newly_processed_keystrokes
            agg_activity.total_clicks = (agg_activity.total_clicks or 0) + newly_processed_clicks
            agg_activity.total_scrolls = (agg_activity.total_scrolls or 0) + newly_processed_scrolls

            agg_activity.synced = False
            agg_activity.updated_at = datetime.now(pytz.utc)

            session.merge(agg_activity)
            session.flush()

            processed_ids = [r.id for r in unprocessed_activities]
            if processed_ids:
                session.query(RawActivity).filter(
                    RawActivity.id.in_(processed_ids)
                ).update({"processed": True}, synchronize_session=False)
                logger.debug(f"Marked {len(processed_ids)} raw activities as processed.")

            session.commit()
            logger.info(
                f"Aggregation complete. Processed {len(unprocessed_activities)} raw records. Total active: {agg_activity.total_active_time_seconds}, Total idle: {agg_activity.total_idle_time_seconds}.")

    except Exception as e:
        logger.error(f"Fatal error in aggregate_daily_data: {e}", exc_info=True)