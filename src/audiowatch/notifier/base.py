"""Base notifier interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from audiowatch.database.models import Listing, WatchRuleDB


@dataclass
class NotificationContent:
    """Content for a notification."""

    title: str
    message: str
    listing_url: str
    listing_title: str
    listing_price: str
    listing_condition: str | None
    listing_seller: str
    listing_image_url: str | None
    rule_name: str
    matched_at: datetime


class BaseNotifier(ABC):
    """Abstract base class for notifiers."""

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Return the name of this notification channel."""
        pass

    @abstractmethod
    async def send(self, content: NotificationContent) -> bool:
        """Send a notification.

        Args:
            content: The notification content to send.

        Returns:
            True if the notification was sent successfully.
        """
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        """Check if this notifier is enabled and configured."""
        pass


def create_notification_content(
    listing: "Listing",
    rule: "WatchRuleDB",
) -> NotificationContent:
    """Create notification content from a listing and rule.

    Args:
        listing: The matched listing.
        rule: The watch rule that matched.

    Returns:
        NotificationContent object.
    """
    price_str = f"{listing.price} {listing.currency}" if listing.price else "N/A"

    return NotificationContent(
        title=f"New match for: {rule.name}",
        message=f"A new listing matches your watch rule '{rule.name}'",
        listing_url=listing.url,
        listing_title=listing.title,
        listing_price=price_str,
        listing_condition=listing.condition,
        listing_seller=listing.seller_username,
        listing_image_url=listing.image_url,
        rule_name=rule.name,
        matched_at=datetime.now(),
    )
