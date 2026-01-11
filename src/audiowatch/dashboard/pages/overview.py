"""Overview page for AudioWatch dashboard."""

from __future__ import annotations

import streamlit as st

from audiowatch.dashboard.db import (
    get_last_scrape,
    get_listing_stats,
    get_notification_stats,
    get_scrape_logs,
)


def render():
    """Render the overview page."""
    st.title("AudioWatch Dashboard")
    st.markdown("Monitor Head-Fi.org classifieds for your dream audio gear.")

    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)

    listing_stats = get_listing_stats()
    notification_stats = get_notification_stats()

    with col1:
        st.metric(
            label="Total Listings",
            value=f"{listing_stats['total']:,}",
        )

    with col2:
        st.metric(
            label="Active Listings",
            value=f"{listing_stats['active']:,}",
        )

    with col3:
        st.metric(
            label="Notifications Sent",
            value=f"{notification_stats['total']:,}",
            delta=f"+{notification_stats['recent_24h']} (24h)",
        )

    with col4:
        st.metric(
            label="Avg Price",
            value=f"${listing_stats['avg_price']:,.0f}",
        )

    st.divider()

    # Two columns: Last Scrape and Categories
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Last Scrape")
        last_scrape = get_last_scrape()

        if last_scrape:
            status_color = "green" if last_scrape["status"] == "success" else "red"
            st.markdown(f"**Status:** :{status_color}[{last_scrape['status'].upper()}]")
            st.markdown(f"**Started:** {last_scrape['started_at'].strftime('%Y-%m-%d %H:%M:%S')}")
            if last_scrape["completed_at"]:
                duration = (last_scrape["completed_at"] - last_scrape["started_at"]).seconds
                st.markdown(f"**Duration:** {duration}s")
            st.markdown(f"**Pages Scraped:** {last_scrape['pages_scraped']}")
            st.markdown(f"**Listings Found:** {last_scrape['listings_found']}")
            st.markdown(f"**New:** {last_scrape['listings_new']} | **Updated:** {last_scrape['listings_updated']}")
        else:
            st.info("No scrapes recorded yet. Run `audiowatch run --once` to start.")

    with col_right:
        st.subheader("Listings by Category")
        if listing_stats["categories"]:
            for category, count in listing_stats["categories"].items():
                pct = (count / listing_stats["total"] * 100) if listing_stats["total"] > 0 else 0
                st.markdown(f"**{category}:** {count:,} ({pct:.1f}%)")
        else:
            st.info("No listings yet.")

    st.divider()

    # Recent scrape history
    st.subheader("Recent Scrape History")
    scrape_logs = get_scrape_logs(limit=10)

    if not scrape_logs.empty:
        # Format the dataframe
        display_df = scrape_logs.copy()
        display_df["Started"] = display_df["Started"].dt.strftime("%Y-%m-%d %H:%M")
        display_df["Duration"] = scrape_logs.apply(
            lambda r: f"{(r['Completed'] - r['Started']).seconds}s" if r['Completed'] else "-",
            axis=1
        )
        display_df = display_df[["Started", "Status", "Pages", "Found", "New", "Updated", "Duration"]]

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No scrape history yet.")

    # Notification channels
    st.divider()
    st.subheader("Notification Channels")

    if notification_stats["by_channel"]:
        cols = st.columns(len(notification_stats["by_channel"]))
        for i, (channel, count) in enumerate(notification_stats["by_channel"].items()):
            with cols[i]:
                st.metric(
                    label=channel.capitalize(),
                    value=count,
                )
    else:
        st.info("No notifications sent yet.")
