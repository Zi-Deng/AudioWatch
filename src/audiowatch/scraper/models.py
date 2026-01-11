"""Pydantic models for scraped listing data.

These models represent the data extracted from Head-Fi classifieds pages
before being persisted to the database.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ListingType(str, Enum):
    """Type of classified listing."""

    FOR_SALE = "For Sale"
    FOR_SALE_TRADE = "For Sale/Trade"
    WANT_TO_BUY = "Want To Buy"
    TRADE_ONLY = "Trade Only"


class Condition(str, Enum):
    """Item condition."""

    NEW = "New"
    LIKE_NEW = "Excellent/Like new"
    EXCELLENT = "Excellent"
    GOOD = "Good"
    FAIR = "Fair"
    POOR = "Poor"
    FOR_PARTS = "For parts"


class Negotiability(str, Enum):
    """Price negotiability."""

    FIRM = "Firm"
    OBO = "Or best offer"
    NEGOTIABLE = "Negotiable"


class ListingStatus(str, Enum):
    """Current status of a listing."""

    ACTIVE = "active"
    SOLD = "sold"
    CLOSED = "closed"
    EXPIRED = "expired"


class ScrapedListing(BaseModel):
    """A listing scraped from Head-Fi classifieds.

    This is the raw data extracted from the HTML before normalization
    and database storage.
    """

    # Required fields
    listing_id: str = Field(..., description="Unique listing ID from Head-Fi")
    title: str = Field(..., description="Listing title")
    url: str = Field(..., description="Full URL to the listing")

    # Pricing
    price: Decimal | None = Field(default=None, description="Listed price")
    currency: str = Field(default="USD", description="Price currency")
    listing_type: str = Field(default="For Sale", description="Type of listing")

    # Status
    status: str = Field(default="active", description="Listing status (active, sold, closed)")

    # Item details
    condition: str | None = Field(default=None, description="Item condition")
    negotiability: str | None = Field(default=None, description="Price negotiability")
    ships_to: str | None = Field(default=None, description="Shipping regions")

    # Seller info
    seller_username: str = Field(..., description="Seller's username")
    seller_reputation: int | None = Field(default=None, description="Seller's trade reputation")

    # Media
    image_url: str | None = Field(default=None, description="Thumbnail image URL")

    # Timestamps
    listed_at: datetime | None = Field(default=None, description="When the listing was created")
    last_edited_at: datetime | None = Field(default=None, description="Last edit timestamp")

    # Category (if available)
    category: str | None = Field(default=None, description="Listing category")

    @field_validator("price", mode="before")
    @classmethod
    def parse_price(cls, v):
        """Parse price from string if needed."""
        if v is None:
            return None
        if isinstance(v, str):
            # Remove commas and whitespace
            v = v.replace(",", "").strip()
            try:
                return Decimal(v)
            except Exception:
                return None
        return v

    @field_validator("seller_reputation", mode="before")
    @classmethod
    def parse_reputation(cls, v):
        """Parse reputation from string if needed."""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return None
        return v


class ScrapeResult(BaseModel):
    """Result of a scraping operation."""

    success: bool = Field(..., description="Whether the scrape was successful")
    listings: list[ScrapedListing] = Field(default_factory=list, description="Scraped listings")
    total_found: int = Field(default=0, description="Total listings found")
    pages_scraped: int = Field(default=0, description="Number of pages scraped")
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = Field(default=None)


class CategoryInfo(BaseModel):
    """Information about a Head-Fi classifieds category."""

    name: str = Field(..., description="Category name")
    slug: str = Field(..., description="URL slug")
    category_id: int = Field(..., description="Category ID")
    url: str = Field(..., description="Full category URL")
    parent_id: int | None = Field(default=None, description="Parent category ID (None if top-level)")
    is_leaf: bool = Field(default=True, description="True if this is a leaf category (no children)")
    listing_count: int | None = Field(default=None, description="Number of listings")


# Head-Fi category hierarchy:
#
# Headphones For Sale / Trade (1) [PARENT]
#   ├── Full-Size (2) [LEAF]
#   └── In-Ear Monitors (3) [LEAF]
#
# Amplification For Sale / Trade (4) [PARENT]
#   ├── Desktop (5) [LEAF]
#   └── Portable (6) [LEAF]
#
# Source Components For Sale / Trade (7) [PARENT]
#   ├── DACs (8) [LEAF]
#   ├── DAC/Amps (9) [LEAF]
#   ├── DAPs (10) [LEAF]
#   └── CD Players (11) [LEAF]
#
# Cables, Speakers, Accessories For Sale / Trade (12) [LEAF - no children]
# Media For Sale / Trade (13) [LEAF - no children]

HEADFI_CATEGORIES = [
    # === Headphones ===
    CategoryInfo(
        name="Headphones For Sale / Trade",
        slug="headphones-for-sale-trade",
        category_id=1,
        url="/classifieds/categories/headphones-for-sale-trade.1",
        parent_id=None,
        is_leaf=False,  # Parent category - don't scrape directly
    ),
    CategoryInfo(
        name="Full-Size Headphones",
        slug="full-size",
        category_id=2,
        url="/classifieds/categories/full-size.2",
        parent_id=1,
        is_leaf=True,
    ),
    CategoryInfo(
        name="In-Ear Monitors",
        slug="in-ear-monitors",
        category_id=3,
        url="/classifieds/categories/in-ear-monitors.3",
        parent_id=1,
        is_leaf=True,
    ),
    # === Amplification ===
    CategoryInfo(
        name="Amplification For Sale / Trade",
        slug="amplification-for-sale-trade",
        category_id=4,
        url="/classifieds/categories/amplification-for-sale-trade.4",
        parent_id=None,
        is_leaf=False,  # Parent category - don't scrape directly
    ),
    CategoryInfo(
        name="Desktop Amps",
        slug="desktop",
        category_id=5,
        url="/classifieds/categories/desktop.5",
        parent_id=4,
        is_leaf=True,
    ),
    CategoryInfo(
        name="Portable Amps",
        slug="portable",
        category_id=6,
        url="/classifieds/categories/portable.6",
        parent_id=4,
        is_leaf=True,
    ),
    # === Source Components ===
    CategoryInfo(
        name="Source Components For Sale / Trade",
        slug="source-components-for-sale-trade",
        category_id=7,
        url="/classifieds/categories/source-components-for-sale-trade.7",
        parent_id=None,
        is_leaf=False,  # Parent category - don't scrape directly
    ),
    CategoryInfo(
        name="DACs",
        slug="dacs",
        category_id=8,
        url="/classifieds/categories/dacs.8",
        parent_id=7,
        is_leaf=True,
    ),
    CategoryInfo(
        name="DAC/Amps",
        slug="dac-amps",
        category_id=9,
        url="/classifieds/categories/dac-amps.9",
        parent_id=7,
        is_leaf=True,
    ),
    CategoryInfo(
        name="DAPs",
        slug="daps",
        category_id=10,
        url="/classifieds/categories/daps.10",
        parent_id=7,
        is_leaf=True,
    ),
    CategoryInfo(
        name="CD Players",
        slug="cd-players",
        category_id=11,
        url="/classifieds/categories/cd-players.11",
        parent_id=7,
        is_leaf=True,
    ),
    # === Standalone Categories (no children) ===
    CategoryInfo(
        name="Cables & Accessories",
        slug="cables-speakers-accessories-for-sale-trade",
        category_id=12,
        url="/classifieds/categories/cables-speakers-accessories-for-sale-trade.12",
        parent_id=None,
        is_leaf=True,
    ),
    CategoryInfo(
        name="Media",
        slug="media-for-sale-trade",
        category_id=13,
        url="/classifieds/categories/media-for-sale-trade.13",
        parent_id=None,
        is_leaf=True,
    ),
]


def get_leaf_categories() -> list[CategoryInfo]:
    """Get only leaf categories (no children) to avoid duplicate listings."""
    return [cat for cat in HEADFI_CATEGORIES if cat.is_leaf]


def get_parent_categories() -> list[CategoryInfo]:
    """Get parent categories (have children)."""
    return [cat for cat in HEADFI_CATEGORIES if not cat.is_leaf]


def get_category_by_slug(slug: str) -> CategoryInfo | None:
    """Get category info by slug."""
    for cat in HEADFI_CATEGORIES:
        if cat.slug == slug:
            return cat
    return None


def get_category_by_id(category_id: int) -> CategoryInfo | None:
    """Get category info by ID."""
    for cat in HEADFI_CATEGORIES:
        if cat.category_id == category_id:
            return cat
    return None


def get_children_of(parent_id: int) -> list[CategoryInfo]:
    """Get child categories of a parent."""
    return [cat for cat in HEADFI_CATEGORIES if cat.parent_id == parent_id]
