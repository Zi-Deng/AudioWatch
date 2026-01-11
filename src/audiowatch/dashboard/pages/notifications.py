"""Notification history page for AudioWatch dashboard."""

from __future__ import annotations

import streamlit as st
import plotly.express as px

from audiowatch.dashboard.db import (
    get_listing_by_id,
    get_notification_stats,
    get_notifications,
)


def render():
    """Render the notification history page."""
    st.title("Notification History")
    st.markdown("View all notifications sent by AudioWatch.")

    # Stats row
    stats = get_notification_stats()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Sent", stats["total"])
    with col2:
        st.metric("Successful", stats["successful"])
    with col3:
        st.metric("Failed", stats["failed"])
    with col4:
        st.metric("Last 24h", stats["recent_24h"])

    st.divider()

    # Channel breakdown
    if stats["by_channel"]:
        st.subheader("By Channel")
        col_left, col_right = st.columns([1, 2])

        with col_left:
            for channel, count in stats["by_channel"].items():
                pct = (count / stats["total"] * 100) if stats["total"] > 0 else 0
                st.metric(
                    channel.capitalize(),
                    count,
                    delta=f"{pct:.1f}%",
                )

        with col_right:
            if len(stats["by_channel"]) > 0:
                fig = px.pie(
                    values=list(stats["by_channel"].values()),
                    names=[c.capitalize() for c in stats["by_channel"].keys()],
                    title="Notifications by Channel",
                )
                st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Notification history table
    st.subheader("Recent Notifications")

    notifications_df = get_notifications(limit=100)

    if notifications_df.empty:
        st.info("No notifications have been sent yet. Configure watch rules and run a scrape to start receiving notifications.")
        return

    # Filter options
    col1, col2 = st.columns(2)

    with col1:
        channel_filter = st.multiselect(
            "Filter by channel",
            options=notifications_df["Channel"].unique().tolist(),
            default=notifications_df["Channel"].unique().tolist(),
        )

    with col2:
        status_filter = st.radio(
            "Status",
            options=["All", "Successful", "Failed"],
            horizontal=True,
        )

    # Apply filters
    filtered_df = notifications_df.copy()

    if channel_filter:
        filtered_df = filtered_df[filtered_df["Channel"].isin(channel_filter)]

    if status_filter == "Successful":
        filtered_df = filtered_df[filtered_df["Success"] == True]
    elif status_filter == "Failed":
        filtered_df = filtered_df[filtered_df["Success"] == False]

    st.markdown(f"**{len(filtered_df)}** notifications")

    # Display table
    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID": st.column_config.NumberColumn("ID", width="small"),
            "Listing": st.column_config.TextColumn("Listing", width="large"),
            "Listing ID": st.column_config.TextColumn("Listing ID", width="small"),
            "Rule": st.column_config.TextColumn("Rule", width="medium"),
            "Channel": st.column_config.TextColumn("Channel", width="small"),
            "Sent At": st.column_config.DatetimeColumn("Sent At", format="YYYY-MM-DD HH:mm"),
            "Success": st.column_config.CheckboxColumn("Success", width="small"),
            "Error": st.column_config.TextColumn("Error", width="medium"),
        },
    )

    # Notification detail
    st.divider()
    st.subheader("Notification Detail")

    if not filtered_df.empty:
        selected_idx = st.selectbox(
            "Select a notification to view details",
            options=filtered_df.index.tolist(),
            format_func=lambda x: f"#{filtered_df.loc[x, 'ID']} - {filtered_df.loc[x, 'Listing'][:40]}...",
        )

        if selected_idx is not None:
            notification = filtered_df.loc[selected_idx]
            _render_notification_detail(notification)


def _render_notification_detail(notification):
    """Render detailed view of a notification."""
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown(f"### {notification['Listing']}")

        # Status
        if notification["Success"]:
            st.success("Successfully sent")
        else:
            st.error(f"Failed: {notification['Error']}")

        st.markdown(f"**Rule:** {notification['Rule']}")
        st.markdown(f"**Channel:** {notification['Channel'].capitalize()}")
        st.markdown(f"**Sent at:** {notification['Sent At'].strftime('%Y-%m-%d %H:%M:%S')}")

    with col_right:
        # Try to get listing details
        listing = get_listing_by_id(notification["Listing ID"])

        if listing:
            st.markdown("**Listing Details:**")
            if listing["price"]:
                st.markdown(f"Price: ${listing['price']:,.2f}")
            st.markdown(f"Category: {listing['category']}")
            st.markdown(f"Seller: {listing['seller_username']}")

            if listing["url"]:
                st.link_button("View Listing", listing["url"])
        else:
            st.info("Listing details not available")
