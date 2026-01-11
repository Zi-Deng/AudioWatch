"""Email notifier using Gmail SMTP."""

from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from audiowatch.config import EmailConfig
from audiowatch.logging import get_logger
from audiowatch.notifier.base import BaseNotifier, NotificationContent

logger = get_logger(__name__)


class EmailNotifier(BaseNotifier):
    """Email notifier using SMTP."""

    def __init__(self, config: EmailConfig):
        """Initialize the email notifier.

        Args:
            config: Email configuration.
        """
        self.config = config

    @property
    def channel_name(self) -> str:
        """Return the channel name."""
        return "email"

    def is_enabled(self) -> bool:
        """Check if email notifications are enabled."""
        return (
            self.config.enabled
            and bool(self.config.sender_email)
            and bool(self.config.sender_password)
            and bool(self.config.recipient_email)
        )

    async def send(self, content: NotificationContent) -> bool:
        """Send an email notification.

        Args:
            content: The notification content.

        Returns:
            True if the email was sent successfully.
        """
        if not self.is_enabled():
            logger.warning("Email notifier not enabled or configured")
            return False

        try:
            msg = self._create_message(content)

            # Create secure SSL context
            context = ssl.create_default_context()

            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                if self.config.use_tls:
                    server.starttls(context=context)
                server.login(self.config.sender_email, self.config.sender_password)
                server.sendmail(
                    self.config.sender_email,
                    self.config.recipient_email,
                    msg.as_string(),
                )

            logger.info(
                "Email notification sent",
                recipient=self.config.recipient_email,
                rule=content.rule_name,
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to send email notification",
                error=str(e),
                rule=content.rule_name,
            )
            return False

    def _create_message(self, content: NotificationContent) -> MIMEMultipart:
        """Create the email message.

        Args:
            content: The notification content.

        Returns:
            MIMEMultipart message.
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[AudioWatch] {content.title}"
        msg["From"] = self.config.sender_email
        msg["To"] = self.config.recipient_email

        # Plain text version
        text_body = f"""
{content.message}

Listing: {content.listing_title}
Price: {content.listing_price}
Condition: {content.listing_condition or 'N/A'}
Seller: {content.listing_seller}

View listing: {content.listing_url}

---
AudioWatch - Head-Fi Classifieds Monitor
        """.strip()

        # HTML version
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #2c3e50; color: white; padding: 15px; border-radius: 5px 5px 0 0; }}
        .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
        .listing {{ background-color: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
        .listing img {{ max-width: 200px; border-radius: 5px; }}
        .price {{ font-size: 1.4em; color: #27ae60; font-weight: bold; }}
        .button {{ display: inline-block; background-color: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 15px; }}
        .footer {{ text-align: center; padding: 15px; color: #666; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2 style="margin: 0;">{content.title}</h2>
        </div>
        <div class="content">
            <p>{content.message}</p>
            
            <div class="listing">
                {'<img src="' + content.listing_image_url + '" alt="Listing image">' if content.listing_image_url else ''}
                <h3>{content.listing_title}</h3>
                <p class="price">{content.listing_price}</p>
                <p><strong>Condition:</strong> {content.listing_condition or 'N/A'}</p>
                <p><strong>Seller:</strong> {content.listing_seller}</p>
                <a href="{content.listing_url}" class="button">View Listing</a>
            </div>
        </div>
        <div class="footer">
            <p>AudioWatch - Head-Fi Classifieds Monitor</p>
        </div>
    </div>
</body>
</html>
        """.strip()

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        return msg
