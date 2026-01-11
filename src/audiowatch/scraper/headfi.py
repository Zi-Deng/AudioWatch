"""Head-Fi classifieds scraper using Playwright and BeautifulSoup.

This module handles fetching and parsing listings from Head-Fi.org classifieds.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import AsyncIterator

from bs4 import BeautifulSoup
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright_stealth import Stealth

from audiowatch.logging import get_logger
from audiowatch.scraper.models import (
    HEADFI_CATEGORIES,
    CategoryInfo,
    ScrapedListing,
    ScrapeResult,
    get_leaf_categories,
)

logger = get_logger(__name__)

BASE_URL = "https://www.head-fi.org"
CLASSIFIEDS_URL = f"{BASE_URL}/classifieds/"


class HeadFiScraper:
    """Scraper for Head-Fi.org classifieds."""

    def __init__(
        self,
        headless: bool = True,
        rate_limit_delay: float = 2.0,
        timeout: int = 30000,
    ):
        """Initialize the scraper.

        Args:
            headless: Run browser in headless mode.
            rate_limit_delay: Delay between page requests in seconds.
            timeout: Page load timeout in milliseconds.
        """
        self.headless = headless
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._playwright = None

    async def __aenter__(self) -> "HeadFiScraper":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()

    async def start(self) -> None:
        """Start the browser."""
        logger.info("Starting HeadFi scraper", headless=self.headless)
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )

        # Apply stealth mode
        stealth = Stealth()
        await stealth.apply_stealth_async(self._context)

        logger.debug("Browser started successfully")

    async def stop(self) -> None:
        """Stop the browser."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("HeadFi scraper stopped")

    async def _new_page(self) -> Page:
        """Create a new page."""
        if not self._context:
            raise RuntimeError("Scraper not started. Call start() first.")
        return await self._context.new_page()

    async def _fetch_page(self, url: str) -> str:
        """Fetch a page and return its HTML content.

        Args:
            url: URL to fetch.

        Returns:
            HTML content of the page.
        """
        page = await self._new_page()
        try:
            logger.debug("Fetching page", url=url)
            await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
            # Wait for dynamic content
            await page.wait_for_timeout(2000)
            html = await page.content()
            logger.debug("Page fetched", url=url, size=len(html))
            return html
        finally:
            await page.close()

    def _parse_listing(self, element: BeautifulSoup, category: str | None = None) -> ScrapedListing | None:
        """Parse a single listing element.

        Args:
            element: BeautifulSoup element for the listing.
            category: Optional category name.

        Returns:
            ScrapedListing or None if parsing failed.
        """
        try:
            # Extract URL and ID
            url = element.get("href", "")
            if not url:
                return None

            # Extract listing ID from URL (format: /classifieds/title.ID/)
            match = re.search(r"\.(\d+)/?$", url)
            if not match:
                logger.warning("Could not extract listing ID", url=url)
                return None

            listing_id = match.group(1)
            full_url = f"{BASE_URL}{url}" if url.startswith("/") else url

            # Title
            title_el = element.find(class_="hfcListingTitle")
            title = title_el.get_text(strip=True) if title_el else "Unknown"

            # Detect sold/closed status from element classes or content
            status = "active"
            element_classes = element.get("class", [])
            if isinstance(element_classes, list):
                element_classes_str = " ".join(element_classes).lower()
            else:
                element_classes_str = str(element_classes).lower()

            # Check for common sold/closed class patterns
            if any(indicator in element_classes_str for indicator in ["sold", "closed", "expired", "inactive"]):
                if "sold" in element_classes_str:
                    status = "sold"
                elif "closed" in element_classes_str:
                    status = "closed"
                elif "expired" in element_classes_str:
                    status = "expired"

            # Price and type
            price = None
            currency = "USD"
            listing_type = "For Sale"

            price_el = element.find(class_="hfcPrice")
            if price_el:
                label = price_el.find("span", class_="label")
                if label:
                    label_text = label.get_text(strip=True)
                    listing_type = label_text

                    # Check label for sold/closed indicators
                    label_lower = label_text.lower()
                    if "sold" in label_lower:
                        status = "sold"
                    elif "closed" in label_lower:
                        status = "closed"

                price_text = price_el.get_text(strip=True)

                # Check price text for SOLD indicator (common pattern)
                if "sold" in price_text.lower():
                    status = "sold"

                # Extract price: look for number followed by currency
                price_match = re.search(r"([\d,]+\.?\d*)\s*(USD|EUR|GBP|CAD|AUD)?", price_text)
                if price_match:
                    price_str = price_match.group(1).replace(",", "")
                    try:
                        price = Decimal(price_str)
                    except Exception:
                        pass
                    if price_match.group(2):
                        currency = price_match.group(2)

            # Also check title for [SOLD] or similar patterns
            title_lower = title.lower()
            if "[sold]" in title_lower or "(sold)" in title_lower or title_lower.startswith("sold:"):
                status = "sold"
            elif "[closed]" in title_lower or "(closed)" in title_lower:
                status = "closed"

            # Image
            img = element.find("img", class_="hfcCoverImage--clear")
            image_url = img.get("src") if img else None

            # Seller info
            seller_username = "Unknown"
            seller_reputation = None

            creator_el = element.find(class_="hfcCreatorInfo")
            if creator_el:
                text = creator_el.get_text(strip=True)
                # Parse "Listed by:username (reputation)"
                seller_match = re.search(r"Listed by:(\w+)\s*\((\d+)\)", text)
                if seller_match:
                    seller_username = seller_match.group(1)
                    seller_reputation = int(seller_match.group(2))
                else:
                    # Try without reputation
                    seller_match = re.search(r"Listed by:(\w+)", text)
                    if seller_match:
                        seller_username = seller_match.group(1)

            # Custom fields
            condition = None
            negotiability = None
            ships_to = None

            custom_el = element.find(class_="hfcCustomFields")
            if custom_el:
                pairs = custom_el.find_all("dl", class_="pairs")
                for pair in pairs:
                    dt = pair.find("dt")
                    dd = pair.find("dd")
                    if dt and dd:
                        key = dt.get_text(strip=True).lower()
                        val = dd.get_text(strip=True)
                        if "condition" in key:
                            condition = val
                        elif "negotiab" in key:
                            negotiability = val
                        elif "ship" in key:
                            ships_to = val

            # Date
            listed_at = None
            date_el = element.find(class_="hfcListingDate")
            if date_el:
                time_el = date_el.find("time")
                if time_el and time_el.get("datetime"):
                    try:
                        listed_at = datetime.fromisoformat(
                            time_el.get("datetime").replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

            # Last edited
            last_edited_at = None
            edit_el = element.find(class_="hfcLastEditDate")
            if edit_el:
                time_el = edit_el.find("time")
                if time_el and time_el.get("datetime"):
                    try:
                        last_edited_at = datetime.fromisoformat(
                            time_el.get("datetime").replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

            return ScrapedListing(
                listing_id=listing_id,
                title=title,
                url=full_url,
                price=price,
                currency=currency,
                listing_type=listing_type,
                status=status,
                condition=condition,
                negotiability=negotiability,
                ships_to=ships_to,
                seller_username=seller_username,
                seller_reputation=seller_reputation,
                image_url=image_url,
                listed_at=listed_at,
                last_edited_at=last_edited_at,
                category=category,
            )

        except Exception as e:
            logger.warning("Failed to parse listing", error=str(e))
            return None

    def _parse_listings_page(self, html: str, category: str | None = None) -> list[ScrapedListing]:
        """Parse all listings from an HTML page.

        Args:
            html: HTML content of the page.
            category: Optional category name.

        Returns:
            List of parsed listings.
        """
        soup = BeautifulSoup(html, "lxml")
        listing_elements = soup.find_all("a", class_="hfcUserListing")

        listings = []
        for element in listing_elements:
            listing = self._parse_listing(element, category)
            if listing:
                listings.append(listing)

        logger.debug("Parsed listings from page", count=len(listings))
        return listings

    def _get_next_page_url(self, html: str, current_url: str) -> str | None:
        """Get the URL for the next page.

        Args:
            html: HTML content of the current page.
            current_url: URL of the current page.

        Returns:
            URL of the next page or None if no more pages.
        """
        soup = BeautifulSoup(html, "lxml")
        page_nav = soup.find("nav", class_="pageNavWrapper")

        if page_nav:
            next_btn = page_nav.find("a", class_="pageNav-jump--next")
            if next_btn:
                href = next_btn.get("href")
                if href:
                    if href.startswith("/"):
                        return f"{BASE_URL}{href}"
                    return href

        return None

    def _get_total_pages(self, html: str) -> int | None:
        """Get total number of pages from pagination.

        Args:
            html: HTML content of the page.

        Returns:
            Total number of pages or None if not found.
        """
        soup = BeautifulSoup(html, "lxml")
        page_nav = soup.find("nav", class_="pageNavWrapper")

        if page_nav:
            # Look for last page number
            pages = page_nav.find_all("a", class_="pageNav-page")
            if pages:
                try:
                    return int(pages[-1].get_text(strip=True))
                except ValueError:
                    pass

        return None

    async def scrape_page(self, url: str, category: str | None = None) -> list[ScrapedListing]:
        """Scrape a single page of listings.

        Args:
            url: URL to scrape.
            category: Optional category name.

        Returns:
            List of scraped listings.
        """
        html = await self._fetch_page(url)
        return self._parse_listings_page(html, category)

    async def scrape_category(
        self,
        category: CategoryInfo,
        max_pages: int | None = None,
        max_age_days: int | None = None,
    ) -> AsyncIterator[ScrapedListing]:
        """Scrape all listings from a category.

        Args:
            category: Category to scrape.
            max_pages: Maximum number of pages to scrape (None for all).
            max_age_days: Stop when listings are older than this.

        Yields:
            ScrapedListing objects.
        """
        url = f"{BASE_URL}{category.url}"
        page_num = 1
        cutoff_date = None

        if max_age_days:
            cutoff_date = datetime.now() - timedelta(days=max_age_days)

        logger.info(
            "Starting category scrape",
            category=category.name,
            max_pages=max_pages,
            max_age_days=max_age_days,
        )

        while url:
            logger.info("Scraping page", page=page_num, url=url)

            try:
                html = await self._fetch_page(url)
                listings = self._parse_listings_page(html, category.name)

                for listing in listings:
                    # Check age cutoff
                    if cutoff_date and listing.listed_at and listing.listed_at < cutoff_date:
                        logger.info(
                            "Reached age cutoff",
                            listing_date=listing.listed_at,
                            cutoff=cutoff_date,
                        )
                        return

                    yield listing

                # Check max pages
                if max_pages and page_num >= max_pages:
                    logger.info("Reached max pages", max_pages=max_pages)
                    break

                # Get next page
                url = self._get_next_page_url(html, url)
                if url:
                    page_num += 1
                    # Rate limiting
                    await asyncio.sleep(self.rate_limit_delay)

            except Exception as e:
                logger.error("Error scraping page", page=page_num, error=str(e))
                break

        logger.info("Category scrape complete", category=category.name, pages=page_num)

    async def scrape_all_categories(
        self,
        max_pages_per_category: int | None = None,
        max_age_days: int | None = 30,
        categories: list[str] | None = None,
        leaf_only: bool = True,
    ) -> AsyncIterator[ScrapedListing]:
        """Scrape listings from all (or specified) categories.

        Args:
            max_pages_per_category: Max pages per category.
            max_age_days: Stop when listings are older than this.
            categories: List of category slugs to scrape (None for all leaf categories).
            leaf_only: If True, only scrape leaf categories to avoid duplicates.

        Yields:
            ScrapedListing objects.
        """
        # Default to leaf categories to avoid duplicates
        if leaf_only:
            cats_to_scrape = get_leaf_categories()
        else:
            cats_to_scrape = HEADFI_CATEGORIES

        # Filter by specific categories if provided
        if categories:
            cats_to_scrape = [
                cat for cat in cats_to_scrape
                if cat.slug in categories
            ]

        logger.info(
            "Scraping categories",
            count=len(cats_to_scrape),
            categories=[c.name for c in cats_to_scrape],
        )

        for category in cats_to_scrape:
            async for listing in self.scrape_category(
                category,
                max_pages=max_pages_per_category,
                max_age_days=max_age_days,
            ):
                yield listing

            # Rate limit between categories
            await asyncio.sleep(self.rate_limit_delay)

    async def scrape_all_leaf_categories(
        self,
        max_pages_per_category: int | None = 10,
        max_age_days: int | None = 30,
    ) -> ScrapeResult:
        """Scrape all leaf categories and return a ScrapeResult.

        This is the recommended method for comprehensive scraping as it:
        - Only scrapes leaf categories (avoids duplicate listings)
        - Captures proper category data for each listing
        - Returns a structured result like scrape_recent()

        Args:
            max_pages_per_category: Max pages per category.
            max_age_days: Stop when listings are older than this.

        Returns:
            ScrapeResult with all scraped listings.
        """
        result = ScrapeResult(
            success=False,
            started_at=datetime.now(),
        )

        leaf_cats = get_leaf_categories()
        total_pages = 0

        logger.info(
            "Starting leaf category scrape",
            categories=len(leaf_cats),
            max_pages_per_category=max_pages_per_category,
            max_age_days=max_age_days,
        )

        try:
            for category in leaf_cats:
                logger.info("Scraping category", category=category.name)
                pages_in_category = 0

                async for listing in self.scrape_category(
                    category,
                    max_pages=max_pages_per_category,
                    max_age_days=max_age_days,
                ):
                    result.listings.append(listing)
                    # Track pages (rough estimate based on listings)
                    if len(result.listings) % 20 == 0:
                        pages_in_category = len(result.listings) // 20

                total_pages += max(1, pages_in_category)

                # Rate limit between categories
                await asyncio.sleep(self.rate_limit_delay)

            result.success = True
            result.total_found = len(result.listings)
            result.pages_scraped = total_pages

        except Exception as e:
            logger.error("Scrape failed", error=str(e))
            result.errors.append(str(e))

        result.completed_at = datetime.now()
        logger.info(
            "Leaf category scrape complete",
            success=result.success,
            listings=result.total_found,
            categories=len(leaf_cats),
        )

        return result

    async def scrape_recent(
        self,
        max_pages: int = 10,
        max_age_days: int = 30,
    ) -> ScrapeResult:
        """Scrape recent listings from the main classifieds page.

        Args:
            max_pages: Maximum number of pages to scrape.
            max_age_days: Stop when listings are older than this.

        Returns:
            ScrapeResult with all scraped listings.
        """
        result = ScrapeResult(
            success=False,
            started_at=datetime.now(),
        )

        url = CLASSIFIEDS_URL
        page_num = 1
        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        logger.info(
            "Starting recent listings scrape",
            max_pages=max_pages,
            max_age_days=max_age_days,
        )

        try:
            while url and page_num <= max_pages:
                logger.info("Scraping page", page=page_num, url=url)

                html = await self._fetch_page(url)
                listings = self._parse_listings_page(html)

                reached_cutoff = False
                for listing in listings:
                    if listing.listed_at and listing.listed_at < cutoff_date:
                        reached_cutoff = True
                        break
                    result.listings.append(listing)

                result.pages_scraped = page_num

                if reached_cutoff:
                    logger.info("Reached age cutoff")
                    break

                # Get next page
                url = self._get_next_page_url(html, url)
                if url:
                    page_num += 1
                    await asyncio.sleep(self.rate_limit_delay)

            result.success = True
            result.total_found = len(result.listings)

        except Exception as e:
            logger.error("Scrape failed", error=str(e))
            result.errors.append(str(e))

        result.completed_at = datetime.now()
        logger.info(
            "Scrape complete",
            success=result.success,
            listings=result.total_found,
            pages=result.pages_scraped,
        )

        return result
