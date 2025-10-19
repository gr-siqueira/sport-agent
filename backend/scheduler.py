"""Scheduling system for automated daily sport digest generation.

This module handles scheduling daily digest generation at user-specified times
using APScheduler. Each user can configure their preferred delivery time and timezone.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from typing import Optional
from datetime import datetime
import logging

# Initialize scheduler
scheduler = BackgroundScheduler()
logger = logging.getLogger(__name__)


def schedule_daily_digest(user_id: str, delivery_time: str, timezone: str):
    """Schedule daily digest for a user at specified time.
    
    Args:
        user_id: Unique user identifier
        delivery_time: Time in HH:MM format (e.g., "07:00")
        timezone: IANA timezone string (e.g., "America/Los_Angeles")
    """
    try:
        hour, minute = delivery_time.split(":")
        tz = pytz.timezone(timezone)
        
        trigger = CronTrigger(
            hour=int(hour),
            minute=int(minute),
            timezone=tz
        )
        
        scheduler.add_job(
            generate_and_send_digest,
            trigger=trigger,
            id=f"digest_{user_id}",
            replace_existing=True,
            args=[user_id],
            name=f"Daily digest for {user_id}"
        )
        
        logger.info(f"Scheduled daily digest for user {user_id} at {delivery_time} {timezone}")
    except Exception as e:
        logger.error(f"Error scheduling digest for user {user_id}: {e}")


def unschedule_digest(user_id: str) -> bool:
    """Remove scheduled digest for a user.
    
    Args:
        user_id: Unique user identifier
        
    Returns:
        True if successfully unscheduled, False otherwise
    """
    try:
        job_id = f"digest_{user_id}"
        scheduler.remove_job(job_id)
        logger.info(f"Unscheduled digest for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error unscheduling digest for user {user_id}: {e}")
        return False


def generate_and_send_digest(user_id: str):
    """Generate digest and save to history.
    
    This function is called by the scheduler at the user's configured time.
    For MVP, it generates the digest and saves it to JSON storage.
    Future versions will send via email/SMS.
    
    Args:
        user_id: Unique user identifier
    """
    from storage import load_preferences, save_digest_history
    from main import build_graph
    
    try:
        logger.info(f"Generating scheduled digest for user {user_id}")
        
        # Load user preferences
        prefs = load_preferences(user_id)
        if not prefs:
            logger.error(f"No preferences found for user {user_id}")
            return
        
        # Generate digest using LangGraph workflow
        graph = build_graph()
        state = {
            "messages": [],
            "user_preferences": prefs,
            "tool_calls": [],
        }
        
        out = graph.invoke(state)
        digest = out.get("final_digest", "")
        
        # Save to history
        timestamp = datetime.now().isoformat()
        save_digest_history(user_id, digest, timestamp)
        
        logger.info(f"Successfully generated and saved digest for user {user_id}")
        
        # TODO: Future - send via email/SMS
        # send_email(prefs.get("email"), digest)
        # send_sms(prefs.get("phone"), digest[:160])
        
    except Exception as e:
        logger.error(f"Error generating digest for user {user_id}: {e}")


def start_scheduler():
    """Initialize scheduler and load all user schedules.
    
    This is called during FastAPI startup to restore all scheduled jobs
    from user preferences.
    """
    from storage import list_all_users, load_preferences
    
    try:
        scheduler.start()
        logger.info("Scheduler started")
        
        # Load all users and schedule their digests
        user_ids = list_all_users()
        for user_id in user_ids:
            prefs = load_preferences(user_id)
            if prefs:
                delivery_time = prefs.get("delivery_time", "07:00")
                timezone = prefs.get("timezone", "America/Los_Angeles")
                schedule_daily_digest(user_id, delivery_time, timezone)
        
        logger.info(f"Restored {len(user_ids)} scheduled digests")
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")


def stop_scheduler():
    """Gracefully shutdown scheduler.
    
    This is called during FastAPI shutdown to ensure all jobs complete.
    """
    try:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")


def get_scheduled_jobs():
    """Get list of all scheduled jobs.
    
    Returns:
        List of job information dictionaries
    """
    jobs = scheduler.get_jobs()
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None
        }
        for job in jobs
    ]

