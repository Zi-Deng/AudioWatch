"""Database repository for AudioWatch.

Provides data access functions for listings, watch rules, and notifications.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from audiowatch.database.models import (
    Listing,
    ListingStatus,
    NotificationLog,
    PriceHistory,
    ScrapeLog,
    WatchRuleDB,
)
from audiowatch.logging import get_logger
from audiowatch.scraper.models import ScrapedListing

logger = get_logger(__name__)


class ListingRepository:
    """Repository for listing operations."""

    def __init__(self, session: Session):
        """Initialize with a database session."""
        self.session = session

    def get_by_id(self, listing_id: str) -> Listing | None:
        """Get a listing by its ID."""
        return self.session.get(Listing, listing_id)

    def get_active_listings(self, limit: int = 100, offset: int = 0) -> list[Listing]:
        """Get active listings with pagination."""
        stmt = (
            select(Listing)
            .where(Listing.status == ListingStatus.ACTIVE.value)
            .order_by(Listing.listed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt))

    def search(
        self,
        query: str | None = None,
        category: str | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        condition: str | None = None,
        limit: int = 100,
    ) -> list[Listing]:
        """Search listings with filters."""
        stmt = select(Listing).where(Listing.status == ListingStatus.ACTIVE.value)

        if query:
            stmt = stmt.where(Listing.title.ilike(f"%{query}%"))
        if category:
            stmt = stmt.where(Listing.category == category)
        if min_price is not None:
            stmt = stmt.where(Listing.price >= min_price)
        if max_price is not None:
            stmt = stmt.where(Listing.price <= max_price)
        if condition:
            stmt = stmt.where(Listing.condition == condition)

        stmt = stmt.order_by(Listing.listed_at.desc()).limit(limit)
        return list(self.session.scalars(stmt))

    def upsert_from_scraped(self, scraped: ScrapedListing) -> tuple[Listing, bool]:
        """Insert or update a listing from scraped data.

        Args:
            scraped: ScrapedListing from the scraper.

        Returns:
            Tuple of (Listing, is_new) where is_new is True if inserted.
        """
        now = datetime.now()
        existing = self.get_by_id(scraped.listing_id)

        if existing:
            # Update existing listing
            price_changed = existing.price != scraped.price

            existing.title = scraped.title
            existing.url = scraped.url
            existing.price = scraped.price
            existing.currency = scraped.currency
            existing.listing_type = scraped.listing_type
            existing.condition = scraped.condition
            existing.shipping_regions = scraped.ships_to
            existing.seller_username = scraped.seller_username
            existing.seller_reputation = scraped.seller_reputation
            existing.image_url = scraped.image_url
            existing.last_edited_at = scraped.last_edited_at
            existing.last_seen_at = now
            # Use scraped status if detected, otherwise keep as active
            existing.status = scraped.status if scraped.status else ListingStatus.ACTIVE.value

            if scraped.category:
                existing.category = scraped.category

            # Track price change
            if price_changed and scraped.price is not None:
                self._add_price_history(existing.id, scraped.price, scraped.currency)

            logger.debug("Updated listing", listing_id=scraped.listing_id)
            return existing, False

        else:
            # Create new listing
            listing = Listing(
                id=scraped.listing_id,
                title=scraped.title,
                url=scraped.url,
                image_url=scraped.image_url,
                category=scraped.category or "Unknown",
                listing_type=scraped.listing_type,
                price=scraped.price,
                currency=scraped.currency,
                is_negotiable=scraped.negotiability == "Or best offer" if scraped.negotiability else False,
                accepts_offers=scraped.negotiability in ("Or best offer", "Negotiable") if scraped.negotiability else False,
                condition=scraped.condition,
                shipping_regions=scraped.ships_to,
                seller_username=scraped.seller_username,
                seller_reputation=scraped.seller_reputation,
                listed_at=scraped.listed_at or now,
                last_edited_at=scraped.last_edited_at,
                first_seen_at=now,
                last_seen_at=now,
                # Use scraped status if detected, otherwise default to active
                status=scraped.status if scraped.status else ListingStatus.ACTIVE.value,
            )
            self.session.add(listing)

            # Add initial price history
            if scraped.price is not None:
                self._add_price_history(scraped.listing_id, scraped.price, scraped.currency)

            logger.debug("Created listing", listing_id=scraped.listing_id)
            return listing, True

    def _add_price_history(self, listing_id: str, price: Decimal, currency: str) -> None:
        """Add a price history entry."""
        history = PriceHistory(
            listing_id=listing_id,
            price=price,
            currency=currency,
            recorded_at=datetime.now(),
        )
        self.session.add(history)

    def mark_stale_as_expired(self, hours: int = 48) -> int:
        """Mark listings not seen recently as expired.

        Args:
            hours: Hours since last seen to consider expired.

        Returns:
            Number of listings marked as expired.
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        stmt = (
            update(Listing)
            .where(Listing.status == ListingStatus.ACTIVE.value)
            .where(Listing.last_seen_at < cutoff)
            .values(status=ListingStatus.EXPIRED.value)
        )
        result = self.session.execute(stmt)
        return result.rowcount

    def count_by_status(self) -> dict[str, int]:
        """Get counts of listings by status."""
        from sqlalchemy import func

        stmt = (
            select(Listing.status, func.count(Listing.id))
            .group_by(Listing.status)
        )
        results = self.session.execute(stmt).all()
        return {status: count for status, count in results}


class WatchRuleRepository:
    """Repository for watch rule operations."""

    def __init__(self, session: Session):
        """Initialize with a database session."""
        self.session = session

    def get_all(self) -> list[WatchRuleDB]:
        """Get all watch rules."""
        stmt = select(WatchRuleDB).order_by(WatchRuleDB.created_at)
        return list(self.session.scalars(stmt))

    def get_enabled(self) -> list[WatchRuleDB]:
        """Get all enabled watch rules."""
        stmt = (
            select(WatchRuleDB)
            .where(WatchRuleDB.enabled == True)
            .order_by(WatchRuleDB.created_at)
        )
        return list(self.session.scalars(stmt))

    def get_by_id(self, rule_id: int) -> WatchRuleDB | None:
        """Get a watch rule by ID."""
        return self.session.get(WatchRuleDB, rule_id)

    def create(
        self,
        name: str,
        expression: str,
        notify_via: list[str],
        enabled: bool = True,
    ) -> WatchRuleDB:
        """Create a new watch rule."""
        now = datetime.now()
        rule = WatchRuleDB(
            name=name,
            expression=expression,
            notify_via=",".join(notify_via),
            enabled=enabled,
            created_at=now,
            updated_at=now,
        )
        self.session.add(rule)
        return rule

    def update(
        self,
        rule_id: int,
        name: str | None = None,
        expression: str | None = None,
        notify_via: list[str] | None = None,
        enabled: bool | None = None,
    ) -> WatchRuleDB | None:
        """Update an existing watch rule."""
        rule = self.get_by_id(rule_id)
        if not rule:
            return None

        if name is not None:
            rule.name = name
        if expression is not None:
            rule.expression = expression
        if notify_via is not None:
            rule.notify_via = ",".join(notify_via)
        if enabled is not None:
            rule.enabled = enabled
        rule.updated_at = datetime.now()

        return rule

    def delete(self, rule_id: int) -> bool:
        """Delete a watch rule."""
        rule = self.get_by_id(rule_id)
        if rule:
            self.session.delete(rule)
            return True
        return False


class ScrapeLogRepository:
    """Repository for scrape log operations."""

    def __init__(self, session: Session):
        """Initialize with a database session."""
        self.session = session

    def create(self) -> ScrapeLog:
        """Create a new scrape log entry."""
        log = ScrapeLog(
            started_at=datetime.now(),
            status="running",
        )
        self.session.add(log)
        self.session.flush()  # Get the ID
        return log

    def complete(
        self,
        log: ScrapeLog,
        status: str = "success",
        listings_found: int = 0,
        listings_new: int = 0,
        listings_updated: int = 0,
        pages_scraped: int = 0,
        error_message: str | None = None,
    ) -> None:
        """Mark a scrape as complete."""
        log.completed_at = datetime.now()
        log.status = status
        log.listings_found = listings_found
        log.listings_new = listings_new
        log.listings_updated = listings_updated
        log.pages_scraped = pages_scraped
        log.error_message = error_message

    def get_last(self) -> ScrapeLog | None:
        """Get the most recent scrape log."""
        stmt = select(ScrapeLog).order_by(ScrapeLog.started_at.desc()).limit(1)
        return self.session.scalar(stmt)


class NotificationLogRepository:
    """Repository for notification log operations."""

    def __init__(self, session: Session):
        """Initialize with a database session."""
        self.session = session

    def has_been_notified(self, listing_id: str, rule_id: int) -> bool:
        """Check if a notification was already sent for this listing/rule combo."""
        stmt = (
            select(NotificationLog)
            .where(NotificationLog.listing_id == listing_id)
            .where(NotificationLog.rule_id == rule_id)
            .where(NotificationLog.success == True)
            .limit(1)
        )
        return self.session.scalar(stmt) is not None

    def log_notification(
        self,
        listing_id: str,
        rule_id: int,
        channel: str,
        success: bool = True,
        error_message: str | None = None,
    ) -> NotificationLog:
        """Log a notification."""
        log = NotificationLog(
            listing_id=listing_id,
            rule_id=rule_id,
            channel=channel,
            sent_at=datetime.now(),
            success=success,
            error_message=error_message,
        )
        self.session.add(log)
        return log


# Import timedelta at module level
from datetime import timedelta
