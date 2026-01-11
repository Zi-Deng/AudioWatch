"""Notifier module for AudioWatch.

Provides notification functionality via email and Discord.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from audiowatch.config import GlobalFilters, RuleFilters, Settings, WatchRule
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
        self.global_filters = settings.global_filters

        # Initialize notifiers
        self.notifiers: dict[str, BaseNotifier] = {
            "email": EmailNotifier(settings.notifications.email),
            "discord": DiscordNotifier(settings.notifications.discord),
        }

        # Pre-compile rule evaluators for enabled rules
        # Stores: rule_id -> (WatchRuleDB, RuleEvaluator, categories, rule_filters)
        self._rule_evaluators: dict[int, tuple[WatchRuleDB, RuleEvaluator, list[str] | None, RuleFilters | None]] = {}

        # Store config watch rules for accessing per-rule settings
        self._config_rules: dict[int, WatchRule] = {}

    def passes_global_filters(self, listing: Listing) -> bool:
        """Check if a listing passes the global filters.

        Args:
            listing: The listing to check.

        Returns:
            True if the listing passes all global filters.
        """
        filters = self.global_filters

        # Check listing types filter (whitelist)
        if filters.listing_types and listing.listing_type:
            type_match = False
            for allowed_type in filters.listing_types:
                if listing.listing_type.lower() == allowed_type.lower():
                    type_match = True
                    break
            if not type_match:
                logger.debug(
                    "Listing filtered by listing_types",
                    listing_id=listing.id,
                    listing_type=listing.listing_type,
                    allowed=filters.listing_types,
                )
                return False

        # Check excluded listing types (blacklist)
        if filters.exclude_listing_types and listing.listing_type:
            for excluded in filters.exclude_listing_types:
                if listing.listing_type.lower() == excluded.lower():
                    logger.debug(
                        "Listing filtered by excluded listing_type",
                        listing_id=listing.id,
                        listing_type=listing.listing_type,
                    )
                    return False

        # Check shipping regions
        # If ships_to filter is set, check if listing ships to any of the required regions
        # Note: If listing.shipping_regions is None, we allow it through (benefit of doubt)
        if filters.ships_to and listing.shipping_regions:
            # Check if any of the required regions are in the listing's shipping regions
            listing_regions = listing.shipping_regions.lower()
            region_match = False
            for region in filters.ships_to:
                if region.lower() in listing_regions:
                    region_match = True
                    break
            if not region_match:
                logger.debug(
                    "Listing filtered by ships_to",
                    listing_id=listing.id,
                    shipping_regions=listing.shipping_regions,
                    required=filters.ships_to,
                )
                return False

        # Check excluded statuses
        if filters.exclude_status and listing.status:
            for excluded in filters.exclude_status:
                if listing.status.lower() == excluded.lower():
                    logger.debug(
                        "Listing filtered by excluded status",
                        listing_id=listing.id,
                        status=listing.status,
                    )
                    return False

        # Check minimum seller reputation
        if filters.min_seller_reputation is not None:
            if listing.seller_reputation is None or listing.seller_reputation < filters.min_seller_reputation:
                logger.debug(
                    "Listing filtered by seller reputation",
                    listing_id=listing.id,
                    reputation=listing.seller_reputation,
                    min_required=filters.min_seller_reputation,
                )
                return False

        return True

    def passes_rule_filters(
        self,
        listing: Listing,
        categories: list[str] | None,
        rule_filters: RuleFilters | None,
        rule_name: str,
    ) -> bool:
        """Check if a listing passes rule-specific filters.

        Rule filters override global filters when specified.

        Args:
            listing: The listing to check.
            categories: Rule-specific categories (None = use all).
            rule_filters: Rule-specific filters (None = use global only).
            rule_name: Name of the rule (for logging).

        Returns:
            True if the listing passes all applicable filters.
        """
        # Check category filter
        if categories and listing.category:
            category_match = False
            listing_cat = listing.category.lower()
            for cat in categories:
                if cat.lower() in listing_cat or listing_cat in cat.lower():
                    category_match = True
                    break
            if not category_match:
                logger.debug(
                    "Listing filtered by rule categories",
                    listing_id=listing.id,
                    category=listing.category,
                    rule=rule_name,
                    allowed=categories,
                )
                return False

        # If no rule-specific filters, use global filters
        if rule_filters is None:
            return self.passes_global_filters(listing)

        # Merge rule filters with global (rule overrides global)
        global_f = self.global_filters

        # Listing types: use rule's if specified, else global
        listing_types = rule_filters.listing_types if rule_filters.listing_types is not None else global_f.listing_types
        if listing_types and listing.listing_type:
            type_match = False
            for allowed_type in listing_types:
                if listing.listing_type.lower() == allowed_type.lower():
                    type_match = True
                    break
            if not type_match:
                logger.debug(
                    "Listing filtered by rule listing_types",
                    listing_id=listing.id,
                    listing_type=listing.listing_type,
                    rule=rule_name,
                )
                return False

        # Ships to: use rule's if specified, else global
        ships_to = rule_filters.ships_to if rule_filters.ships_to is not None else global_f.ships_to
        if ships_to and listing.shipping_regions:
            listing_regions = listing.shipping_regions.lower()
            region_match = False
            for region in ships_to:
                if region.lower() in listing_regions:
                    region_match = True
                    break
            if not region_match:
                logger.debug(
                    "Listing filtered by rule ships_to",
                    listing_id=listing.id,
                    shipping_regions=listing.shipping_regions,
                    rule=rule_name,
                )
                return False

        # Exclude status: use rule's if specified, else global
        exclude_status = rule_filters.exclude_status if rule_filters.exclude_status is not None else global_f.exclude_status
        if exclude_status and listing.status:
            for excluded in exclude_status:
                if listing.status.lower() == excluded.lower():
                    logger.debug(
                        "Listing filtered by rule exclude_status",
                        listing_id=listing.id,
                        status=listing.status,
                        rule=rule_name,
                    )
                    return False

        # Min seller reputation: use rule's if specified, else global
        min_rep = rule_filters.min_seller_reputation if rule_filters.min_seller_reputation is not None else global_f.min_seller_reputation
        if min_rep is not None:
            if listing.seller_reputation is None or listing.seller_reputation < min_rep:
                logger.debug(
                    "Listing filtered by rule min_seller_reputation",
                    listing_id=listing.id,
                    reputation=listing.seller_reputation,
                    rule=rule_name,
                )
                return False

        return True

    def load_rules(self, rules: list[WatchRuleDB], config_rules: list[WatchRule] | None = None) -> None:
        """Load and compile watch rules.

        Args:
            rules: List of watch rules to load (WatchRuleDB from database or converted).
            config_rules: Optional list of WatchRule configs (for per-rule settings).
        """
        self._rule_evaluators.clear()
        self._config_rules.clear()

        # Build mapping from rule ID to config rule (for per-rule settings)
        config_rule_map: dict[int, WatchRule] = {}
        if config_rules:
            for i, cr in enumerate(config_rules):
                # Config rules use negative IDs starting from -1
                rule_id = -(i + 1)
                config_rule_map[rule_id] = cr

        for rule in rules:
            if not rule.enabled:
                continue

            try:
                evaluator = RuleEvaluator.from_string(rule.expression)

                # Get per-rule settings from config if available
                categories = None
                rule_filters = None

                if rule.id in config_rule_map:
                    config_rule = config_rule_map[rule.id]
                    categories = config_rule.categories
                    rule_filters = config_rule.filters
                    self._config_rules[rule.id] = config_rule

                self._rule_evaluators[rule.id] = (rule, evaluator, categories, rule_filters)
                logger.debug(
                    "Loaded rule",
                    rule_id=rule.id,
                    rule_name=rule.name,
                    categories=categories,
                    has_filters=rule_filters is not None,
                )
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

        for rule_id, (rule, evaluator, categories, rule_filters) in self._rule_evaluators.items():
            # Apply per-rule filters (which merge with global filters)
            if not self.passes_rule_filters(listing, categories, rule_filters, rule.name):
                continue
            # Check if already notified for this listing/rule combo
            # (only applies to database rules with positive IDs)
            if rule_id > 0 and self.notification_repo.has_been_notified(listing.id, rule_id):
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

                # Log the notification attempt (only for database rules, not config rules)
                # Config rules have negative IDs and can't be logged due to foreign key
                if rule_id > 0:
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
