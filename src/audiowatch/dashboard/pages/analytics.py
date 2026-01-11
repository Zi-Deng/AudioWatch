"""Analytics page for AudioWatch dashboard."""

from __future__ import annotations

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from audiowatch.dashboard.db import (
    get_categories,
    get_listing_stats,
    get_listings,
    get_listings_over_time,
    get_price_trends_by_category,
)


def render():
    """Render the analytics page."""
    st.title("Price Trends & Analytics")
    st.markdown("Analyze listing trends and price data from Head-Fi classifieds.")

    # Load data
    listing_stats = get_listing_stats()
    listings_over_time = get_listings_over_time()
    price_trends = get_price_trends_by_category()

    # Top metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Listings", f"{listing_stats['total']:,}")
    with col2:
        st.metric("Active Listings", f"{listing_stats['active']:,}")
    with col3:
        st.metric("Average Price", f"${listing_stats['avg_price']:,.0f}")
    with col4:
        st.metric("Categories", len(listing_stats['categories']))

    st.divider()

    # Listings over time chart
    st.subheader("Listings Over Time (Last 30 Days)")

    if not listings_over_time.empty:
        fig = px.area(
            listings_over_time,
            x="Date",
            y="Listings",
            title="New Listings Per Day",
        )
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Number of Listings",
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Not enough data to show listings over time.")

    st.divider()

    # Price trends by category
    st.subheader("Average Price by Category")

    if not price_trends.empty:
        # Pivot for line chart
        categories = price_trends["Category"].unique()

        fig = go.Figure()
        for category in categories:
            cat_data = price_trends[price_trends["Category"] == category]
            fig.add_trace(go.Scatter(
                x=cat_data["Date"],
                y=cat_data["Average Price"],
                mode="lines+markers",
                name=category,
            ))

        fig.update_layout(
            title="Average Price Trends by Category (Last 30 Days)",
            xaxis_title="Date",
            yaxis_title="Average Price ($)",
            legend_title="Category",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Not enough data to show price trends.")

    st.divider()

    # Category breakdown
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Listings by Category")

        if listing_stats["categories"]:
            # Pie chart
            fig = px.pie(
                values=list(listing_stats["categories"].values()),
                names=list(listing_stats["categories"].keys()),
                title="Distribution by Category",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No category data available.")

    with col_right:
        st.subheader("Price Distribution")

        # Get listings for histogram
        listings_df = get_listings(limit=1000)

        if not listings_df.empty and listings_df["Price"].notna().any():
            fig = px.histogram(
                listings_df[listings_df["Price"].notna()],
                x="Price",
                nbins=50,
                title="Price Distribution (All Listings)",
            )
            fig.update_layout(
                xaxis_title="Price ($)",
                yaxis_title="Count",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No price data available.")

    st.divider()

    # Category-specific analysis
    st.subheader("Category Deep Dive")

    categories = get_categories()
    if categories:
        selected_category = st.selectbox(
            "Select a category to analyze",
            options=categories,
        )

        if selected_category:
            _render_category_analysis(selected_category)


def _render_category_analysis(category: str):
    """Render detailed analysis for a specific category."""
    # Get listings for this category
    listings_df = get_listings(category=category, limit=500)

    if listings_df.empty:
        st.info(f"No listings found in {category}.")
        return

    # Category stats
    col1, col2, col3, col4 = st.columns(4)

    prices = listings_df["Price"].dropna()

    with col1:
        st.metric("Listings", len(listings_df))
    with col2:
        st.metric("Avg Price", f"${prices.mean():,.0f}" if len(prices) > 0 else "N/A")
    with col3:
        st.metric("Min Price", f"${prices.min():,.0f}" if len(prices) > 0 else "N/A")
    with col4:
        st.metric("Max Price", f"${prices.max():,.0f}" if len(prices) > 0 else "N/A")

    # Price histogram for category
    if len(prices) > 0:
        fig = px.histogram(
            listings_df[listings_df["Price"].notna()],
            x="Price",
            nbins=30,
            title=f"Price Distribution: {category}",
        )
        fig.update_layout(
            xaxis_title="Price ($)",
            yaxis_title="Count",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Top sellers in category
    st.markdown("**Top Sellers in Category:**")
    seller_counts = listings_df["Seller"].value_counts().head(10)
    if not seller_counts.empty:
        fig = px.bar(
            x=seller_counts.index,
            y=seller_counts.values,
            title="Most Active Sellers",
        )
        fig.update_layout(
            xaxis_title="Seller",
            yaxis_title="Listings",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Recent listings table
    st.markdown("**Recent Listings:**")
    recent = listings_df.head(10)[["Title", "Price", "Condition", "Seller", "Listed"]]
    st.dataframe(recent, use_container_width=True, hide_index=True)
