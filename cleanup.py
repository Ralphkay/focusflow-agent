# cleanup.py (Full Updated Code)
import logging
import asyncio
from datetime import date
from sqlalchemy import func
import threading

from database import get_db_session, db_lock
from client_models import RawActivity, AggregatedActivity, InactivePeriod, ManualBreak
from config import LOG_FILE
from aggregation import aggregate_daily_data
from sync import sync_data # Ensure sync_data is imported for the final sync

logger = logging.getLogger(__name__)

def _run_sync_and_cleanup_blocking():
    """Performs the blocking part of the cleanup in a separate thread."""
    try:
        logger.info("Running final aggregation before daily reset.")
        aggregate_daily_data()
        logger.info("Running final data sync before daily reset.")
        asyncio.run(sync_data())  # This is the blocking call.
    except Exception as e:
        logger.error(f"Error during final pre-reset aggregation/sync: {e}", exc_info=True)

    logger.info("Starting daily reset of local data from previous days.")
    today = date.today()

    try:
        with db_lock, get_db_session() as session:
            logger.debug(f"Purging records from before {today}.")

            deleted_raw = session.query(RawActivity).filter(func.date(RawActivity.timestamp) < today).delete(synchronize_session=False)
            deleted_inactive = session.query(InactivePeriod).filter(func.date(InactivePeriod.start_time) < today).delete(synchronize_session=False)
            deleted_breaks = session.query(ManualBreak).filter(func.date(ManualBreak.start_time) < today).delete(synchronize_session=False)

            # FIXED: Only delete aggregated records that have been successfully synced.
            deleted_agg = session.query(AggregatedActivity).filter(
                AggregatedActivity.date < today,
                AggregatedActivity.synced == True  # <-- This is the critical change
            ).delete(synchronize_session=False)

            session.commit()
            logger.info(
                f"Successfully purged old data: "
                f"{deleted_raw} raw activities, "
                f"{deleted_agg} synced aggregated days, "
                f"{deleted_inactive} inactive periods, "
                f"{deleted_breaks} manual breaks."
            )
    except Exception as e:
        logger.error(f"Could not purge old data from local database: {e}", exc_info=True)

    try:
        logger.debug(f"Resetting log file: {LOG_FILE}")
        # Truncate the log file by opening in 'w' mode
        with open(LOG_FILE, 'w', encoding='utf-8'):
            pass
        logger.info(f"Successfully reset the log file at {LOG_FILE}.")
    except Exception as e:
        logger.error(f"Could not reset log file at {LOG_FILE}: {e}", exc_info=True)
    logger.info("Daily data and log reset complete.")


def reset_daily_data():
    """
    Public function to run the blocking cleanup process in a new thread.
    This prevents the main thread from hanging.
    """
    cleanup_thread = threading.Thread(target=_run_sync_and_cleanup_blocking, daemon=True, name="CleanupThread")
    cleanup_thread.start()
    logger.info("Cleanup process started in a background thread.")