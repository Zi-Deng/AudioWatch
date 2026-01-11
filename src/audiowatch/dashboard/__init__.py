"""Dashboard package for AudioWatch.

Provides a Streamlit-based web interface for:
- Browsing and searching listings
- Managing watch rules
- Viewing price trends and analytics
- Notification history
"""

from audiowatch.dashboard.app import main

__all__ = ["main"]
