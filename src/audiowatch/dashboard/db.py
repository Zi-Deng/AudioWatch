"""Database helpers for the dashboard.

Provides cached database connections and query functions for Streamlit.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from audiowatch.database.models import (
    Base,
    Listing,
    NotificationLog,
    PriceHistory,
    ScrapeLog,
    WatchRuleDB,
)


def get_db_path() -> Path:
    """Get database path from config or default."""
    # Try to load from config
    config_path = Path("config.yaml")
    if config_path.exists():
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        db_path = config.get("database", {}).get("path", "./data/audiowatch.db")
        return Path(db_path)
    return Path("./data/audiowatch.db")


@st.cache_resource
def get_engine():
    """Get cached SQLAlchemy engine."""
    db_path = get_db_path()
    if not db_path.exists():
        st.error(f"Database not found at {db_path}. Run `audiowatch init` first.")
        st.stop()
    return create_engine(f"duckdb:///{db_path}")


def get_session() -> Session:
    """Get a new database session."""
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


# ============================================================================
# Listing Queries
# ============================================================================

def get_listings(
    search: str | None = None,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> pd.DataFrame:
    """Get listings with optional filters."""
    with get_session() as session:
        stmt = select(Listing)

        if search:
            stmt = stmt.where(Listing.title.ilike(f"%{search}%"))
        if category and category != "All":
            stmt = stmt.where(Listing.category == category)
        if min_price is not None:
            stmt = stmt.where(Listing.price >= Decimal(str(min_price)))
        if max_price is not None:
            stmt = stmt.where(Listing.price <= Decimal(str(max_price)))
        if status and status != "All":
            stmt = stmt.where(Listing.status == status.lower())

        stmt = stmt.order_by(Listing.listed_at.desc()).limit(limit).offset(offset)
        results = session.scalars(stmt).all()

        return pd.DataFrame([
            {
                "ID": l.id,
                "Title": l.title,
                "Price": float(l.price) if l.price else None,
                "Currency": l.currency,
                "Category": l.category,
                "Condition": l.condition,
                "Status": l.status,
                "Seller": l.seller_username,
                "Reputation": l.seller_reputation,
                "Listed": l.listed_at,
                "URL": l.url,
            }
            for l in results
        ])


def get_listing_by_id(listing_id: str) -> dict[str, Any] | None:
    """Get a single listing by ID."""
    with get_session() as session:
        listing = session.get(Listing, listing_id)
        if not listing:
            return None
        return {
            "id": listing.id,
            "title": listing.title,
            "price": float(listing.price) if listing.price else None,
            "currency": listing.currency,
            "category": listing.category,
            "condition": listing.condition,
            "status": listing.status,
            "listing_type": listing.listing_type,
            "seller_username": listing.seller_username,
            "seller_reputation": listing.seller_reputation,
            "shipping_regions": listing.shipping_regions,
            "listed_at": listing.listed_at,
            "last_edited_at": listing.last_edited_at,
            "url": listing.url,
            "image_url": listing.image_url,
        }


def get_categories() -> list[str]:
    """Get unique categories."""
    with get_session() as session:
        stmt = select(Listing.category).distinct().order_by(Listing.category)
        return list(session.scalars(stmt))


def get_listing_stats() -> dict[str, Any]:
    """Get listing statistics."""
    with get_session() as session:
        total = session.scalar(select(func.count(Listing.id)))
        active = session.scalar(
            select(func.count(Listing.id)).where(Listing.status == "active")
        )
        sold = session.scalar(
            select(func.count(Listing.id)).where(Listing.status == "sold")
        )
        avg_price = session.scalar(
            select(func.avg(Listing.price)).where(Listing.price.isnot(None))
        )

        # Category breakdown
        category_counts = session.execute(
            select(Listing.category, func.count(Listing.id))
            .group_by(Listing.category)
            .order_by(func.count(Listing.id).desc())
        ).all()

        return {
            "total": total or 0,
            "active": active or 0,
            "sold": sold or 0,
            "avg_price": float(avg_price) if avg_price else 0,
            "categories": {cat: count for cat, count in category_counts},
        }


# ============================================================================
# Watch Rule Queries
# ============================================================================

def get_watch_rules() -> pd.DataFrame:
    """Get all watch rules."""
    with get_session() as session:
        stmt = select(WatchRuleDB).order_by(WatchRuleDB.created_at.desc())
        rules = session.scalars(stmt).all()

        return pd.DataFrame([
            {
                "ID": r.id,
                "Name": r.name,
                "Expression": r.expression,
                "Notify Via": r.notify_via,
                "Enabled": r.enabled,
                "Created": r.created_at,
                "Updated": r.updated_at,
            }
            for r in rules
        ])


def create_watch_rule(
    name: str,
    expression: str,
    notify_via: list[str],
    enabled: bool = True,
) -> int:
    """Create a new watch rule. Returns the new rule ID."""
    with get_session() as session:
        now = datetime.now()
        rule = WatchRuleDB(
            name=name,
            expression=expression,
            notify_via=",".join(notify_via),
            enabled=enabled,
            created_at=now,
            updated_at=now,
        )
        session.add(rule)
        session.commit()
        return rule.id


def update_watch_rule(
    rule_id: int,
    name: str | None = None,
    expression: str | None = None,
    notify_via: list[str] | None = None,
    enabled: bool | None = None,
) -> bool:
    """Update a watch rule. Returns True if successful."""
    with get_session() as session:
        rule = session.get(WatchRuleDB, rule_id)
        if not rule:
            return False

        if name is not None:
            rule.name = name
        if expression is not None:
            rule.expression = expression
        if notify_via is not None:
            rule.notify_via = ",".join(notify_via)
        if enabled is not None:
            rule.enabled = enabled
        rule.updated_at = datetime.now()

        session.commit()
        return True


def delete_watch_rule(rule_id: int) -> bool:
    """Delete a watch rule. Returns True if successful."""
    with get_session() as session:
        rule = session.get(WatchRuleDB, rule_id)
        if not rule:
            return False
        session.delete(rule)
        session.commit()
        return True


# ============================================================================
# Notification Queries
# ============================================================================

def get_notifications(limit: int = 100) -> pd.DataFrame:
    """Get recent notifications."""
    with get_session() as session:
        stmt = (
            select(NotificationLog, Listing.title, WatchRuleDB.name)
            .join(Listing, NotificationLog.listing_id == Listing.id)
            .outerjoin(WatchRuleDB, NotificationLog.rule_id == WatchRuleDB.id)
            .order_by(NotificationLog.sent_at.desc())
            .limit(limit)
        )
        results = session.execute(stmt).all()

        return pd.DataFrame([
            {
                "ID": n.id,
                "Listing": title,
                "Listing ID": n.listing_id,
                "Rule": rule_name or f"Config Rule #{abs(n.rule_id)}",
                "Channel": n.channel,
                "Sent At": n.sent_at,
                "Success": n.success,
                "Error": n.error_message,
            }
            for n, title, rule_name in results
        ])


def get_notification_stats() -> dict[str, Any]:
    """Get notification statistics."""
    with get_session() as session:
        total = session.scalar(select(func.count(NotificationLog.id)))
        successful = session.scalar(
            select(func.count(NotificationLog.id)).where(NotificationLog.success == True)
        )
        failed = session.scalar(
            select(func.count(NotificationLog.id)).where(NotificationLog.success == False)
        )

        # By channel
        by_channel = session.execute(
            select(NotificationLog.channel, func.count(NotificationLog.id))
            .group_by(NotificationLog.channel)
        ).all()

        # Recent (last 24h)
        yesterday = datetime.now() - timedelta(hours=24)
        recent = session.scalar(
            select(func.count(NotificationLog.id))
            .where(NotificationLog.sent_at >= yesterday)
        )

        return {
            "total": total or 0,
            "successful": successful or 0,
            "failed": failed or 0,
            "recent_24h": recent or 0,
            "by_channel": {ch: count for ch, count in by_channel},
        }


# ============================================================================
# Price History / Analytics
# ============================================================================

def get_price_history(listing_id: str) -> pd.DataFrame:
    """Get price history for a listing."""
    with get_session() as session:
        stmt = (
            select(PriceHistory)
            .where(PriceHistory.listing_id == listing_id)
            .order_by(PriceHistory.recorded_at)
        )
        history = session.scalars(stmt).all()

        return pd.DataFrame([
            {
                "Date": h.recorded_at,
                "Price": float(h.price),
                "Currency": h.currency,
            }
            for h in history
        ])


def get_price_trends_by_category() -> pd.DataFrame:
    """Get average price trends by category."""
    with get_session() as session:
        # Get recent listings with prices
        stmt = (
            select(
                Listing.category,
                func.date(Listing.listed_at).label("date"),
                func.avg(Listing.price).label("avg_price"),
                func.count(Listing.id).label("count"),
            )
            .where(Listing.price.isnot(None))
            .where(Listing.listed_at >= datetime.now() - timedelta(days=30))
            .group_by(Listing.category, func.date(Listing.listed_at))
            .order_by(func.date(Listing.listed_at))
        )
        results = session.execute(stmt).all()

        return pd.DataFrame([
            {
                "Category": r.category,
                "Date": r.date,
                "Average Price": float(r.avg_price) if r.avg_price else 0,
                "Listing Count": r.count,
            }
            for r in results
        ])


def get_listings_over_time() -> pd.DataFrame:
    """Get listing counts over time."""
    with get_session() as session:
        stmt = (
            select(
                func.date(Listing.listed_at).label("date"),
                func.count(Listing.id).label("count"),
            )
            .where(Listing.listed_at >= datetime.now() - timedelta(days=30))
            .group_by(func.date(Listing.listed_at))
            .order_by(func.date(Listing.listed_at))
        )
        results = session.execute(stmt).all()

        return pd.DataFrame([
            {"Date": r.date, "Listings": r.count}
            for r in results
        ])


# ============================================================================
# Scrape Log Queries
# ============================================================================

def get_scrape_logs(limit: int = 20) -> pd.DataFrame:
    """Get recent scrape logs."""
    with get_session() as session:
        stmt = (
            select(ScrapeLog)
            .order_by(ScrapeLog.started_at.desc())
            .limit(limit)
        )
        logs = session.scalars(stmt).all()

        return pd.DataFrame([
            {
                "ID": l.id,
                "Started": l.started_at,
                "Completed": l.completed_at,
                "Status": l.status,
                "Pages": l.pages_scraped,
                "Found": l.listings_found,
                "New": l.listings_new,
                "Updated": l.listings_updated,
                "Error": l.error_message,
            }
            for l in logs
        ])


def get_last_scrape() -> dict[str, Any] | None:
    """Get the most recent scrape log."""
    with get_session() as session:
        stmt = select(ScrapeLog).order_by(ScrapeLog.started_at.desc()).limit(1)
        log = session.scalar(stmt)
        if not log:
            return None
        return {
            "started_at": log.started_at,
            "completed_at": log.completed_at,
            "status": log.status,
            "pages_scraped": log.pages_scraped,
            "listings_found": log.listings_found,
            "listings_new": log.listings_new,
            "listings_updated": log.listings_updated,
        }
