"""Listings browser page for AudioWatch dashboard."""

from __future__ import annotations

import streamlit as st

from audiowatch.dashboard.db import (
    get_categories,
    get_listing_by_id,
    get_listings,
    get_price_history,
)


def render():
    """Render the listings browser page."""
    st.title("Listings Browser")
    st.markdown("Search and browse Head-Fi classified listings.")

    # Filters in sidebar-style columns
    with st.expander("Filters", expanded=True):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            search = st.text_input(
                "Search titles",
                placeholder="e.g., HD800, Focal, etc.",
                key="listing_search",
            )

        with col2:
            categories = ["All"] + get_categories()
            category = st.selectbox(
                "Category",
                options=categories,
                key="listing_category",
            )

        with col3:
            price_range = st.slider(
                "Price Range ($)",
                min_value=0,
                max_value=10000,
                value=(0, 10000),
                step=100,
                key="listing_price",
            )

        with col4:
            status = st.selectbox(
                "Status",
                options=["All", "Active", "Sold", "Expired"],
                key="listing_status",
            )

    # Get filtered listings
    min_price = price_range[0] if price_range[0] > 0 else None
    max_price = price_range[1] if price_range[1] < 10000 else None

    listings_df = get_listings(
        search=search if search else None,
        category=category if category != "All" else None,
        min_price=min_price,
        max_price=max_price,
        status=status if status != "All" else None,
        limit=200,
    )

    # Results summary
    st.markdown(f"**{len(listings_df)}** listings found")

    if listings_df.empty:
        st.info("No listings match your filters. Try adjusting your search criteria.")
        return

    # Display listings in a data editor (read-only)
    st.dataframe(
        listings_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID": st.column_config.TextColumn("ID", width="small"),
            "Title": st.column_config.TextColumn("Title", width="large"),
            "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
            "Currency": st.column_config.TextColumn("Currency", width="small"),
            "Category": st.column_config.TextColumn("Category", width="medium"),
            "Condition": st.column_config.TextColumn("Condition", width="medium"),
            "Status": st.column_config.TextColumn("Status", width="small"),
            "Seller": st.column_config.TextColumn("Seller", width="medium"),
            "Reputation": st.column_config.NumberColumn("Rep", width="small"),
            "Listed": st.column_config.DatetimeColumn("Listed", format="YYYY-MM-DD"),
            "URL": st.column_config.LinkColumn("Link", display_text="View"),
        },
    )

    # Listing detail view
    st.divider()
    st.subheader("Listing Details")

    if not listings_df.empty:
        listing_ids = listings_df["ID"].tolist()
        selected_id = st.selectbox(
            "Select a listing to view details",
            options=listing_ids,
            format_func=lambda x: f"{x} - {listings_df[listings_df['ID'] == x]['Title'].values[0][:50]}...",
            key="selected_listing",
        )

        if selected_id:
            listing = get_listing_by_id(selected_id)
            if listing:
                _render_listing_detail(listing)


def _render_listing_detail(listing: dict):
    """Render detailed view of a single listing."""
    col_main, col_side = st.columns([2, 1])

    with col_main:
        st.markdown(f"### {listing['title']}")

        # Status badge
        status_colors = {
            "active": "green",
            "sold": "red",
            "expired": "orange",
        }
        status = listing["status"]
        color = status_colors.get(status, "gray")
        st.markdown(f"**Status:** :{color}[{status.upper()}]")

        # Price
        if listing["price"]:
            st.markdown(f"**Price:** ${listing['price']:,.2f} {listing['currency']}")
        else:
            st.markdown("**Price:** Not specified")

        # Details grid
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Category:** {listing['category']}")
            st.markdown(f"**Condition:** {listing['condition'] or 'Not specified'}")
            st.markdown(f"**Type:** {listing['listing_type']}")
        with col2:
            st.markdown(f"**Seller:** {listing['seller_username']}")
            st.markdown(f"**Reputation:** {listing['seller_reputation'] or 'N/A'}")
            st.markdown(f"**Ships to:** {listing['shipping_regions'] or 'Not specified'}")

        # Timestamps
        st.markdown(f"**Listed:** {listing['listed_at'].strftime('%Y-%m-%d %H:%M')}")
        if listing["last_edited_at"]:
            st.markdown(f"**Last edited:** {listing['last_edited_at'].strftime('%Y-%m-%d %H:%M')}")

        # Link to listing
        st.link_button("View on Head-Fi", listing["url"], type="primary")

    with col_side:
        # Image
        if listing["image_url"]:
            st.image(listing["image_url"], use_container_width=True)
        else:
            st.info("No image available")

    # Price history
    st.subheader("Price History")
    price_history = get_price_history(listing["id"])

    if not price_history.empty:
        st.line_chart(
            price_history.set_index("Date")["Price"],
            use_container_width=True,
        )
    else:
        st.info("No price history available for this listing.")
