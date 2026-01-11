"""Streamlit Dashboard for AudioWatch.

Main entry point for the web-based dashboard providing:
- Listing browser with search/filter
- Watch rule management
- Price trend analytics
- Notification history
"""

from __future__ import annotations

import streamlit as st

# Page configuration - must be first Streamlit command
st.set_page_config(
    page_title="AudioWatch",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    """Main dashboard application."""
    from audiowatch.dashboard.pages import analytics, listings, notifications, rules, overview

    # Define pages using Streamlit's navigation API
    pages = {
        "Dashboard": [
            st.Page(overview.render, title="Overview", icon="🏠", default=True),
            st.Page(listings.render, title="Listings", icon="📋"),
        ],
        "Management": [
            st.Page(rules.render, title="Watch Rules", icon="👁️"),
            st.Page(notifications.render, title="Notifications", icon="🔔"),
        ],
        "Analytics": [
            st.Page(analytics.render, title="Price Trends", icon="📈"),
        ],
    }

    # Create navigation
    pg = st.navigation(pages)

    # Run the selected page
    pg.run()


if __name__ == "__main__":
    main()
