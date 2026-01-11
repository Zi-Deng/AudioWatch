#!/usr/bin/env python3
"""Script to analyze Head-Fi classifieds HTML structure."""

import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Apply stealth to avoid detection
        stealth = Stealth()
        await stealth.apply_stealth_async(context)

        page = await context.new_page()

        print("Fetching Head-Fi classifieds page...")
        await page.goto(
            "https://www.head-fi.org/classifieds/",
            wait_until="domcontentloaded",
            timeout=60000
        )
        # Wait a bit for dynamic content
        await page.wait_for_timeout(3000)

        # Save the HTML for analysis
        html = await page.content()
        with open("headfi_sample.html", "w") as f:
            f.write(html)
        print(f"Saved HTML ({len(html)} bytes) to headfi_sample.html")

        # Analyze the structure
        print("\n=== Listing Structure Analysis ===\n")

        # Find listing containers
        listings = await page.query_selector_all(".structItem--listing")
        print(f"Found {len(listings)} listings with class 'structItem--listing'")

        if not listings:
            listings = await page.query_selector_all("[class*='listing']")
            print(f"Found {len(listings)} elements with 'listing' in class")

        if not listings:
            listings = await page.query_selector_all(".structItem")
            print(f"Found {len(listings)} elements with class 'structItem'")

        if listings:
            # Analyze first listing
            first = listings[0]
            print("\n--- First Listing Analysis ---")

            # Get outer HTML
            outer_html = await first.evaluate("el => el.outerHTML")
            print(f"Outer HTML length: {len(outer_html)}")

            # Save first listing HTML
            with open("first_listing.html", "w") as f:
                f.write(outer_html)
            print("Saved first listing to first_listing.html")

            # Try to extract fields
            print("\n--- Field Extraction Test ---")

            # Title
            title_el = await first.query_selector(".structItem-title a")
            if title_el:
                title = await title_el.inner_text()
                href = await title_el.get_attribute("href")
                print(f"Title: {title}")
                print(f"URL: {href}")

            # Price
            price_el = await first.query_selector("[class*='price'], .listingDataItem--price")
            if price_el:
                price = await price_el.inner_text()
                print(f"Price: {price}")

            # Seller
            seller_el = await first.query_selector(".username, [class*='username']")
            if seller_el:
                seller = await seller_el.inner_text()
                print(f"Seller: {seller}")

            # Category
            cat_el = await first.query_selector("[class*='category'], .structItem-cell--main .structItem-minor a")
            if cat_el:
                cat = await cat_el.inner_text()
                print(f"Category: {cat}")

            # Date
            date_el = await first.query_selector("time")
            if date_el:
                date_str = await date_el.get_attribute("datetime")
                print(f"Date: {date_str}")

        # Check pagination
        print("\n--- Pagination Analysis ---")
        pagination = await page.query_selector(".pageNav, nav.pageNavWrapper")
        if pagination:
            print("Found pagination element")
            last_page = await page.query_selector(".pageNav-page:last-child a, .pageNavSimple-el--last")
            if last_page:
                last_text = await last_page.inner_text()
                print(f"Last page indicator: {last_text}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
