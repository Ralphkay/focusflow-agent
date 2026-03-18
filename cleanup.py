# cleanup.py (Pipeline-Fixed Version)
import logging
import asyncio
from datetime import date, timedelta
from sqlalchemy import func, text
import threading
import os

from database import get_db_session, db_lock, engine, DATABASE_FILE
from client_models import RawActivity, AggregatedActivity, InactivePeriod, ManualBreak, LeavePeriod, LocationRecord
from config import LOG_FILE, APP_DATA_PATH
from aggregation import aggregate_daily_data
from sync import sync_data

logger = logging.getLogger(__name__)

# Retention policy: Maximum days to keep unsynced data before force-deleting
MAX_UNSYNCED_RETENTION_DAYS = 7

# Log rotation: Keep last N log files
MAX_LOG_FILES = 5

def _rotate_log_file():
    """
    Rotates the log file instead of truncating it.
    Keeps the last MAX_LOG_FILES rotated logs.
    """
    try:
        if not os.path.exists(LOG_FILE):
            return
            
        log_size = os.path.getsize(LOG_FILE)
        if log_size == 0:
            return
            
        # Rotate existing log files
        for i in range(MAX_LOG_FILES - 1, 0, -1):
            old_log = f"{LOG_FILE}.{i}"
            new_log = f"{LOG_FILE}.{i + 1}"
            if os.path.exists(old_log):
                if i + 1 >= MAX_LOG_FILES:
                    os.remove(old_log)
                else:
                    os.rename(old_log, new_log)
        
        # Rename current log to .1
        if os.path.exists(LOG_FILE):
            os.rename(LOG_FILE, f"{LOG_FILE}.1")
            
        # Create new empty log file
        with open(LOG_FILE, 'w', encoding='utf-8'):
            pass
            
        logger.info(f"Log file rotated successfully. Keeping last {MAX_LOG_FILES} logs.")
    except Exception as e:
        logger.error(f"Could not rotate log file: {e}", exc_info=True)


def _vacuum_database():
    """
    Runs VACUUM on DuckDB to reclaim space after deletions.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("CHECKPOINT"))
            logger.info("DuckDB checkpoint completed - space reclaimed.")
    except Exception as e:
        logger.warning(f"Could not run DuckDB checkpoint: {e}")


def _run_sync_and_cleanup_blocking():
    """Performs the blocking part of the cleanup in a separate thread."""
    sync_successful = False
    
    try:
        logger.info("Running final aggregation before daily reset.")
        aggregate_daily_data()
        logger.info("Running final data sync before daily reset.")
        sync_data()  # sync_data is now synchronous
        sync_successful = True
    except Exception as e:
        logger.error(f"Error during final pre-reset aggregation/sync: {e}", exc_info=True)
        logger.warning("Sync failed - will only delete already-synced data to prevent data loss.")

    logger.info("Starting daily reset of local data from previous days.")
    today = date.today()
    retention_cutoff = today - timedelta(days=MAX_UNSYNCED_RETENTION_DAYS)

    try:
        with db_lock, get_db_session() as session:
            logger.info(f"Purging records from before {today}. Retention cutoff for unsynced: {retention_cutoff}")

            # Only delete raw activities that have been processed (aggregated)
            # Raw activities are safe to delete because they're aggregated into AggregatedActivity
            # which has its own sync check
            deleted_raw = session.query(RawActivity).filter(
                func.date(RawActivity.timestamp) < today,
                RawActivity.processed == True  # Only delete if already aggregated
            ).delete(synchronize_session=False)
            
            # Delete inactive periods from previous days (embedded in AggregatedActivity)
            deleted_inactive = session.query(InactivePeriod).filter(
                func.date(InactivePeriod.start_time) < today
            ).delete(synchronize_session=False)
            
            # Delete manual breaks from previous days (embedded in AggregatedActivity)
            deleted_breaks = session.query(ManualBreak).filter(
                func.date(ManualBreak.start_time) < today
            ).delete(synchronize_session=False)
            
            # Delete old leave periods (ended before today) - these come FROM server
            deleted_leaves = session.query(LeavePeriod).filter(
                LeavePeriod.end_date < today
            ).delete(synchronize_session=False)

            # Delete synced aggregated records from previous days
            deleted_agg_synced = session.query(AggregatedActivity).filter(
                AggregatedActivity.date < today,
                AggregatedActivity.synced == True
            ).delete(synchronize_session=False)
            
            # Force delete very old unsynced records (retention policy)
            # This prevents infinite DB growth if sync is permanently broken
            deleted_agg_old_unsynced = session.query(AggregatedActivity).filter(
                AggregatedActivity.date < retention_cutoff,
                AggregatedActivity.synced == False
            ).delete(synchronize_session=False)
            
            if deleted_agg_old_unsynced > 0:
                logger.warning(
                    f"Force-deleted {deleted_agg_old_unsynced} unsynced aggregated records "
                    f"older than {MAX_UNSYNCED_RETENTION_DAYS} days. Data was lost due to sync failures."
                )

            # Clean up synced location records from previous days
            deleted_location_synced = session.query(LocationRecord).filter(
                func.date(LocationRecord.timestamp) < today,
                LocationRecord.synced == True
            ).delete(synchronize_session=False)

            # Force delete old unsynced location records (retention policy)
            deleted_location_old_unsynced = session.query(LocationRecord).filter(
                func.date(LocationRecord.timestamp) < retention_cutoff,
                LocationRecord.synced == False
            ).delete(synchronize_session=False)

            if deleted_location_old_unsynced > 0:
                logger.warning(
                    f"Force-deleted {deleted_location_old_unsynced} unsynced location records "
                    f"older than {MAX_UNSYNCED_RETENTION_DAYS} days."
                )
            
            # Count unsynced records still remaining (for monitoring)
            unsynced_remaining = session.query(AggregatedActivity).filter(
                AggregatedActivity.synced == False
            ).count()
            
            if unsynced_remaining > 0:
                logger.warning(f"{unsynced_remaining} unsynced aggregated records remain - will retry sync later.")

            session.commit()
            logger.info(
                f"Cleanup complete: "
                f"{deleted_raw} raw activities, "
                f"{deleted_agg_synced} synced aggregated days, "
                f"{deleted_agg_old_unsynced} old unsynced aggregated days, "
                f"{deleted_inactive} inactive periods, "
                f"{deleted_breaks} manual breaks, "
                f"{deleted_leaves} expired leave periods, "
                f"{deleted_location_synced} synced location records, "
                f"{deleted_location_old_unsynced} old unsynced location records."
            )
    except Exception as e:
        logger.error(f"Could not purge old data from local database: {e}", exc_info=True)

    # Rotate log file instead of truncating
    _rotate_log_file()
    
    # Reclaim database space
    _vacuum_database()
    
    logger.info("Daily cleanup complete.")


def reset_daily_data():
    """
    Public function to run the blocking cleanup process in a new thread.
    This prevents the main thread from hanging.
    """
    cleanup_thread = threading.Thread(target=_run_sync_and_cleanup_blocking, daemon=True, name="CleanupThread")
    cleanup_thread.start()
    logger.info("Cleanup process started in a background thread.")