"""SQLAlchemy models for AudioWatch database.

Uses DuckDB as the backend for efficient analytical queries on listing data.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Sequence,
    String,
    Text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

if TYPE_CHECKING:
    pass


class ListingType(str, Enum):
    """Type of listing on Head-Fi classifieds."""

    FOR_SALE = "for_sale"
    FOR_SALE_TRADE = "for_sale_trade"
    WANT_TO_BUY = "want_to_buy"


class ListingCondition(str, Enum):
    """Condition of the item being sold."""

    NEW = "new"
    LIKE_NEW = "like_new"
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    FOR_PARTS = "for_parts"


class ListingStatus(str, Enum):
    """Current status of a listing."""

    ACTIVE = "active"
    SOLD = "sold"
    EXPIRED = "expired"
    DELETED = "deleted"


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Listing(Base):
    """A classified listing from Head-Fi.

    Stores all metadata about a listing including price history tracking.
    """

    __tablename__ = "listings"

    # Primary key - using Head-Fi's listing ID
    id: Mapped[str] = mapped_column(String(50), primary_key=True)

    # Basic listing info
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Categorization
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    subcategory: Mapped[str | None] = mapped_column(String(100), nullable=True)
    listing_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Pricing
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    is_negotiable: Mapped[bool] = mapped_column(Boolean, default=False)
    accepts_offers: Mapped[bool] = mapped_column(Boolean, default=False)

    # Item details
    condition: Mapped[str | None] = mapped_column(String(50), nullable=True)
    shipping_regions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Seller info
    seller_username: Mapped[str] = mapped_column(String(100), nullable=False)
    seller_reputation: Mapped[int | None] = mapped_column(nullable=True)

    # Timestamps
    listed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Status tracking
    status: Mapped[str] = mapped_column(String(20), default=ListingStatus.ACTIVE.value)

    # Relationships
    price_history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["NotificationLog"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_listings_category", "category"),
        Index("ix_listings_status", "status"),
        Index("ix_listings_listed_at", "listed_at"),
        Index("ix_listings_price", "price"),
        Index("ix_listings_seller", "seller_username"),
        Index("ix_listings_title_search", "title"),
    )

    def __repr__(self) -> str:
        return f"<Listing(id={self.id!r}, title={self.title!r}, price={self.price})>"


class PriceHistory(Base):
    """Historical price data for a listing.

    Tracks price changes over time for trend analysis.
    """

    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("price_history_id_seq"), primary_key=True
    )
    listing_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("listings.id"), nullable=False
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationship
    listing: Mapped["Listing"] = relationship(back_populates="price_history")

    __table_args__ = (
        Index("ix_price_history_listing", "listing_id"),
        Index("ix_price_history_recorded", "recorded_at"),
    )

    def __repr__(self) -> str:
        return f"<PriceHistory(listing_id={self.listing_id!r}, price={self.price})>"


class WatchRuleDB(Base):
    """Persisted watch rule for matching listings.

    Stores user-defined rules for filtering and notification.
    """

    __tablename__ = "watch_rules"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("watch_rules_id_seq"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    notify_via: Mapped[str] = mapped_column(String(100), nullable=False)  # Comma-separated
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationships
    notifications: Mapped[list["NotificationLog"]] = relationship(
        back_populates="rule", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<WatchRule(id={self.id}, name={self.name!r})>"


class NotificationLog(Base):
    """Log of sent notifications.

    Tracks which notifications were sent for which listings and rules.
    """

    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("notification_log_id_seq"), primary_key=True
    )
    listing_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("listings.id"), nullable=False
    )
    rule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("watch_rules.id"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)  # email, discord
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    listing: Mapped["Listing"] = relationship(back_populates="notifications")
    rule: Mapped["WatchRuleDB"] = relationship(back_populates="notifications")

    __table_args__ = (
        Index("ix_notification_log_listing", "listing_id"),
        Index("ix_notification_log_rule", "rule_id"),
        Index("ix_notification_log_sent", "sent_at"),
    )

    def __repr__(self) -> str:
        return f"<NotificationLog(listing={self.listing_id!r}, rule={self.rule_id})>"


class ScrapeLog(Base):
    """Log of scraping runs.

    Tracks when scrapes occurred and their results.
    """

    __tablename__ = "scrape_log"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("scrape_log_id_seq"), primary_key=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running, success, failed
    listings_found: Mapped[int] = mapped_column(default=0)
    listings_new: Mapped[int] = mapped_column(default=0)
    listings_updated: Mapped[int] = mapped_column(default=0)
    pages_scraped: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_scrape_log_started", "started_at"),)

    def __repr__(self) -> str:
        return f"<ScrapeLog(id={self.id}, status={self.status!r})>"
