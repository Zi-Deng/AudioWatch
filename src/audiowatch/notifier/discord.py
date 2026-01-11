"""Discord webhook notifier."""

from __future__ import annotations

from discord_webhook import DiscordEmbed, DiscordWebhook

from audiowatch.config import DiscordConfig
from audiowatch.logging import get_logger
from audiowatch.notifier.base import BaseNotifier, NotificationContent

logger = get_logger(__name__)


class DiscordNotifier(BaseNotifier):
    """Discord webhook notifier."""

    def __init__(self, config: DiscordConfig):
        """Initialize the Discord notifier.

        Args:
            config: Discord configuration.
        """
        self.config = config

    @property
    def channel_name(self) -> str:
        """Return the channel name."""
        return "discord"

    def is_enabled(self) -> bool:
        """Check if Discord notifications are enabled."""
        return self.config.enabled and bool(self.config.webhook_url)

    async def send(self, content: NotificationContent) -> bool:
        """Send a Discord notification.

        Args:
            content: The notification content.

        Returns:
            True if the notification was sent successfully.
        """
        if not self.is_enabled():
            logger.warning("Discord notifier not enabled or configured")
            return False

        try:
            webhook = DiscordWebhook(
                url=self.config.webhook_url,
                username="AudioWatch",
            )

            # Create embed
            embed = DiscordEmbed(
                title=content.listing_title,
                description=content.message,
                color="03b2f8",  # Nice blue color
                url=content.listing_url,
            )

            # Add thumbnail if available
            if content.listing_image_url:
                embed.set_thumbnail(url=content.listing_image_url)

            # Add fields
            embed.add_embed_field(
                name="Price",
                value=content.listing_price,
                inline=True,
            )

            if content.listing_condition:
                embed.add_embed_field(
                    name="Condition",
                    value=content.listing_condition,
                    inline=True,
                )

            embed.add_embed_field(
                name="Seller",
                value=content.listing_seller,
                inline=True,
            )

            embed.add_embed_field(
                name="Watch Rule",
                value=content.rule_name,
                inline=False,
            )

            # Set footer
            embed.set_footer(text="AudioWatch - Head-Fi Classifieds Monitor")
            embed.set_timestamp(content.matched_at.isoformat())

            webhook.add_embed(embed)

            # Send the webhook
            response = webhook.execute()

            if response.status_code in (200, 204):
                logger.info(
                    "Discord notification sent",
                    rule=content.rule_name,
                )
                return True
            else:
                logger.error(
                    "Discord webhook returned error",
                    status_code=response.status_code,
                    response=response.text,
                )
                return False

        except Exception as e:
            logger.error(
                "Failed to send Discord notification",
                error=str(e),
                rule=content.rule_name,
            )
            return False
