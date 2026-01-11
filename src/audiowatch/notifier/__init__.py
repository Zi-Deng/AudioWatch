"""Notifier module for AudioWatch.

Provides notification functionality via email and Discord.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from audiowatch.config import Settings
from audiowatch.database.models import Listing, WatchRuleDB
from audiowatch.database.repository import NotificationLogRepository
from audiowatch.logging import get_logger
from audiowatch.matcher import RuleEvaluator
from audiowatch.notifier.base import (
    BaseNotifier,
    NotificationContent,
    create_notification_content,
)
from audiowatch.notifier.discord import DiscordNotifier
from audiowatch.notifier.email import EmailNotifier

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = get_logger(__name__)

__all__ = [
    "BaseNotifier",
    "NotificationContent",
    "EmailNotifier",
    "DiscordNotifier",
    "NotificationOrchestrator",
    "create_notification_content",
]


class NotificationOrchestrator:
    """Orchestrates matching and notifications for listings."""

    def __init__(self, settings: Settings, session: "Session"):
        """Initialize the orchestrator.

        Args:
            settings: Application settings.
            session: Database session.
        """
        self.settings = settings
        self.session = session
        self.notification_repo = NotificationLogRepository(session)

        # Initialize notifiers
        self.notifiers: dict[str, BaseNotifier] = {
            "email": EmailNotifier(settings.notifications.email),
            "discord": DiscordNotifier(settings.notifications.discord),
        }

        # Pre-compile rule evaluators for enabled rules
        self._rule_evaluators: dict[int, tuple[WatchRuleDB, RuleEvaluator]] = {}

    def load_rules(self, rules: list[WatchRuleDB]) -> None:
        """Load and compile watch rules.

        Args:
            rules: List of watch rules to load.
        """
        self._rule_evaluators.clear()

        for rule in rules:
            if not rule.enabled:
                continue

            try:
                evaluator = RuleEvaluator.from_string(rule.expression)
                self._rule_evaluators[rule.id] = (rule, evaluator)
                logger.debug("Loaded rule", rule_id=rule.id, rule_name=rule.name)
            except Exception as e:
                logger.error(
                    "Failed to parse rule expression",
                    rule_id=rule.id,
                    rule_name=rule.name,
                    expression=rule.expression,
                    error=str(e),
                )

        logger.info("Loaded watch rules", count=len(self._rule_evaluators))

    async def process_listing(self, listing: Listing) -> int:
        """Process a listing against all watch rules.

        Args:
            listing: The listing to process.

        Returns:
            Number of notifications sent.
        """
        notifications_sent = 0

        for rule_id, (rule, evaluator) in self._rule_evaluators.items():
            # Check if already notified for this listing/rule combo
            if self.notification_repo.has_been_notified(listing.id, rule_id):
                continue

            # Check if listing matches the rule
            if not evaluator.matches(listing):
                continue

            logger.info(
                "Listing matches rule",
                listing_id=listing.id,
                listing_title=listing.title[:50],
                rule_name=rule.name,
            )

            # Send notifications via configured channels
            channels = rule.notify_via.split(",") if rule.notify_via else []

            for channel in channels:
                channel = channel.strip().lower()
                notifier = self.notifiers.get(channel)

                if notifier is None:
                    logger.warning("Unknown notification channel", channel=channel)
                    continue

                if not notifier.is_enabled():
                    logger.debug(
                        "Notifier not enabled",
                        channel=channel,
                        rule_name=rule.name,
                    )
                    continue

                # Create notification content
                content = create_notification_content(listing, rule)

                # Send notification
                success = await notifier.send(content)

                # Log the notification attempt
                self.notification_repo.log_notification(
                    listing_id=listing.id,
                    rule_id=rule_id,
                    channel=channel,
                    success=success,
                )

                if success:
                    notifications_sent += 1

        return notifications_sent

    async def process_listings(self, listings: list[Listing]) -> int:
        """Process multiple listings.

        Args:
            listings: List of listings to process.

        Returns:
            Total number of notifications sent.
        """
        total_notifications = 0

        for listing in listings:
            notifications = await self.process_listing(listing)
            total_notifications += notifications

        return total_notifications
