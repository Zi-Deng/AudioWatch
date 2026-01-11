"""Scheduler module for AudioWatch.

Provides scheduled scraping using APScheduler with:
- Configurable intervals (1 min - 1 hour)
- Job persistence to survive restarts
- Graceful shutdown handling
"""

from __future__ import annotations

import asyncio
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from audiowatch.logging import get_logger

if TYPE_CHECKING:
    from audiowatch.config import Settings

__all__ = ["ScrapeScheduler"]


class ScrapeScheduler:
    """Scheduler for periodic scraping operations.

    Uses APScheduler with SQLAlchemy-based job persistence to survive restarts.
    Supports graceful shutdown on SIGINT/SIGTERM.
    """

    def __init__(
        self,
        settings: Settings,
        scrape_func: Callable[[], None],
        job_store_path: Path | None = None,
    ):
        """Initialize the scheduler.

        Args:
            settings: Application settings
            scrape_func: Synchronous function to call for each scrape
            job_store_path: Path to SQLite file for job persistence.
                           If None, uses in-memory storage.
        """
        self.settings = settings
        self.scrape_func = scrape_func
        self.log = get_logger("audiowatch.scheduler")
        self._shutdown_event = asyncio.Event()
        self._is_running = False

        # Set up job store for persistence
        jobstores = {}
        if job_store_path:
            job_store_path.parent.mkdir(parents=True, exist_ok=True)
            jobstores["default"] = SQLAlchemyJobStore(
                url=f"sqlite:///{job_store_path}"
            )
            self.log.info("Using persistent job store", path=str(job_store_path))

        # Configure executors
        executors = {
            "default": ThreadPoolExecutor(max_workers=1),  # One scrape at a time
        }

        # Job defaults
        job_defaults = {
            "coalesce": True,  # Combine missed runs into one
            "max_instances": 1,  # Only one instance of each job
            "misfire_grace_time": 60 * 5,  # 5 minutes grace period
        }

        # Create scheduler
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone="UTC",
        )

        # Add event listeners
        self.scheduler.add_listener(
            self._on_job_executed,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR,
        )

    def _on_job_executed(self, event: JobExecutionEvent) -> None:
        """Handle job execution events."""
        if event.exception:
            self.log.error(
                "Scrape job failed",
                job_id=event.job_id,
                exception=str(event.exception),
                traceback=event.traceback,
            )
        else:
            self.log.info(
                "Scrape job completed",
                job_id=event.job_id,
                run_time=event.scheduled_run_time.isoformat() if event.scheduled_run_time else None,
            )

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum: int, frame) -> None:
            sig_name = signal.Signals(signum).name
            self.log.info("Received shutdown signal", signal=sig_name)
            self.stop()
            # Set the event for async waiting
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(self._shutdown_event.set)
            except RuntimeError:
                # No running event loop
                pass

        # Handle SIGINT (Ctrl+C) and SIGTERM
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # On Windows, also handle SIGBREAK if available
        if sys.platform == "win32" and hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, signal_handler)

    def add_scrape_job(self) -> None:
        """Add the scrape job to the scheduler."""
        interval_minutes = self.settings.scraper.poll_interval_minutes

        # Remove existing job if any (for restarts with different settings)
        if self.scheduler.get_job("scrape_headfi"):
            self.scheduler.remove_job("scrape_headfi")

        # Add the job
        self.scheduler.add_job(
            self.scrape_func,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="scrape_headfi",
            name="Scrape Head-Fi Classifieds",
            replace_existing=True,
        )

        self.log.info(
            "Scheduled scrape job",
            interval_minutes=interval_minutes,
        )

    def start(self, run_immediately: bool = True) -> None:
        """Start the scheduler.

        Args:
            run_immediately: If True, run the scrape job immediately on start.
        """
        if self._is_running:
            self.log.warning("Scheduler is already running")
            return

        self._setup_signal_handlers()
        self.add_scrape_job()

        self.log.info("Starting scheduler")
        self.scheduler.start()
        self._is_running = True

        if run_immediately:
            self.log.info("Running initial scrape")
            # Run immediately in a separate thread
            self.scheduler.add_job(
                self.scrape_func,
                id="scrape_headfi_immediate",
                name="Initial Scrape",
                replace_existing=True,
            )

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if not self._is_running:
            return

        self.log.info("Stopping scheduler...")
        self.scheduler.shutdown(wait=True)
        self._is_running = False
        self.log.info("Scheduler stopped")

    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self._is_running and self.scheduler.running

    def get_next_run_time(self) -> datetime | None:
        """Get the next scheduled run time for the scrape job."""
        job = self.scheduler.get_job("scrape_headfi")
        if job:
            return job.next_run_time
        return None

    async def wait_for_shutdown(self) -> None:
        """Wait until shutdown signal is received.

        Use this in async contexts to keep the main task running
        until the scheduler is stopped.
        """
        await self._shutdown_event.wait()

    def run_blocking(self, run_immediately: bool = True) -> None:
        """Start the scheduler and block until shutdown.

        This is the main entry point for running the scheduler.

        Args:
            run_immediately: If True, run the scrape job immediately on start.
        """
        self.start(run_immediately=run_immediately)

        self.log.info(
            "Scheduler running",
            interval_minutes=self.settings.scraper.poll_interval_minutes,
            next_run=self.get_next_run_time(),
        )

        try:
            # Keep the main thread alive
            while self._is_running:
                asyncio.get_event_loop().run_until_complete(
                    asyncio.sleep(1)
                )
        except (KeyboardInterrupt, SystemExit):
            self.log.info("Interrupted, shutting down...")
        finally:
            self.stop()


def create_scrape_job(
    settings: Settings,
    headless: bool = True,
) -> Callable[[], None]:
    """Create a synchronous scrape function for the scheduler.

    Uses settings.scraper.scheduled_max_pages for page limit (default: 2).
    This is intentionally lower than initial scrapes since scheduled jobs
    run frequently and only need to check recent listings.

    Args:
        settings: Application settings
        headless: Run browser in headless mode

    Returns:
        A synchronous function that runs the async scrape operation.
    """
    log = get_logger("audiowatch.scheduler")
    max_pages = settings.scraper.scheduled_max_pages

    def sync_scrape() -> None:
        """Synchronous wrapper for the async scrape operation."""
        log.info("Starting scheduled scrape", max_pages_per_category=max_pages)
        try:
            asyncio.run(_run_scheduled_scrape(settings, max_pages, headless))
            log.info("Scheduled scrape completed")
        except Exception as e:
            log.exception("Scheduled scrape failed", error=str(e))
            raise

    return sync_scrape


async def _run_scheduled_scrape(
    settings: Settings,
    max_pages: int,
    headless: bool,
) -> None:
    """Run a single scrape operation (async).

    This is the core scraping logic used by the scheduler.
    """
    from audiowatch.database import get_session
    from audiowatch.database.repository import (
        ListingRepository,
        ScrapeLogRepository,
        WatchRuleRepository,
    )
    from audiowatch.notifier import NotificationOrchestrator
    from audiowatch.scraper import HeadFiScraper

    log = get_logger("audiowatch.scheduler")
    new_count = 0
    updated_count = 0
    new_listings = []

    async with HeadFiScraper(
        headless=headless,
        rate_limit_delay=settings.scraper.rate_limit_delay_seconds,
        timeout=settings.scraper.timeout_seconds * 1000,
    ) as scraper:
        # Scrape all leaf categories
        result = await scraper.scrape_all_leaf_categories(
            max_pages_per_category=max_pages,
            max_age_days=settings.scraper.initial_scrape_days,
        )

        # Save to database
        with get_session() as session:
            listing_repo = ListingRepository(session)
            scrape_log_repo = ScrapeLogRepository(session)

            # Create scrape log
            scrape_log = scrape_log_repo.create()

            for scraped in result.listings:
                listing, is_new = listing_repo.upsert_from_scraped(scraped)
                if is_new:
                    new_count += 1
                    new_listings.append(listing)
                else:
                    updated_count += 1

            # Complete scrape log
            scrape_log_repo.complete(
                scrape_log,
                status="success" if result.success else "error",
                listings_found=result.total_found,
                listings_new=new_count,
                listings_updated=updated_count,
                pages_scraped=result.pages_scraped,
                error_message="; ".join(result.errors) if result.errors else None,
            )

            session.commit()

            # Process new listings for notifications
            if new_listings:
                rule_repo = WatchRuleRepository(session)
                db_rules = rule_repo.get_enabled()

                # Also load rules from config
                config_rules = []
                for rule in settings.watch_rules:
                    if rule.enabled:
                        config_rules.append(_ConfigRuleWrapper(rule))

                all_rules = db_rules + config_rules

                if all_rules:
                    orchestrator = NotificationOrchestrator(settings, session)
                    orchestrator.load_rules(all_rules, settings.watch_rules)
                    notifications_sent = await orchestrator.process_listings(new_listings)
                    session.commit()

                    log.info(
                        "Scrape results",
                        pages_scraped=result.pages_scraped,
                        total_found=result.total_found,
                        new_listings=new_count,
                        updated_listings=updated_count,
                        notifications_sent=notifications_sent,
                    )
            else:
                log.info(
                    "Scrape results",
                    pages_scraped=result.pages_scraped,
                    total_found=result.total_found,
                    new_listings=new_count,
                    updated_listings=updated_count,
                    notifications_sent=0,
                )


class _ConfigRuleWrapper:
    """Wrapper to make config WatchRule compatible with WatchRuleDB interface."""

    _id_counter = -1

    def __init__(self, rule):
        self.id = _ConfigRuleWrapper._id_counter
        _ConfigRuleWrapper._id_counter -= 1
        self.name = rule.name
        self.expression = rule.expression
        self.notify_via = ",".join(rule.notify_via)
        self.enabled = rule.enabled
