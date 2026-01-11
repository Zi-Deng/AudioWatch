"""Command-line interface for AudioWatch.

Provides commands to run the scraper, manage watch rules, and start the dashboard.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from audiowatch import __version__

# Create Typer app
app = typer.Typer(
    name="audiowatch",
    help="Monitor Head-Fi.org classifieds and get notified when items matching your criteria are listed.",
    add_completion=False,
    no_args_is_help=True,
)

# Rich console for pretty output
console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"[bold blue]AudioWatch[/bold blue] version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """AudioWatch - Monitor Head-Fi classifieds for your dream audio gear."""
    pass


@app.command()
def init(
    config_path: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file.",
        ),
    ] = Path("config.yaml"),
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite existing database.",
        ),
    ] = False,
) -> None:
    """Initialize the AudioWatch database."""
    from audiowatch.config import get_settings
    from audiowatch.database import close_database, get_engine, init_database, reset_database
    from audiowatch.logging import get_logger, setup_logging

    # Load settings and set up logging
    settings = get_settings(config_path)
    setup_logging(settings.logging)
    log = get_logger("audiowatch.cli")

    db_path = settings.database.path

    try:
        if db_path.exists() and not force:
            console.print(
                f"[yellow]Database already exists at {db_path}[/yellow]\n"
                "Use --force to reinitialize (this will delete all data)."
            )
            raise typer.Exit(1)

        if force and db_path.exists():
            log.warning("Reinitializing database", path=str(db_path))
            reset_database(db_path)
            console.print(f"[green]Database reinitialized at {db_path}[/green]")
        else:
            log.info("Initializing database", path=str(db_path))
            engine = get_engine(db_path)
            init_database(engine)
            console.print(f"[green]Database initialized at {db_path}[/green]")

    except Exception as e:
        log.exception("Failed to initialize database")
        console.print(f"[red]Error initializing database: {e}[/red]")
        raise typer.Exit(1)
    finally:
        close_database()


@app.command()
def run(
    config_path: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file.",
        ),
    ] = Path("config.yaml"),
    once: Annotated[
        bool,
        typer.Option(
            "--once",
            help="Run scraper once and exit (don't schedule).",
        ),
    ] = False,
    max_pages: Annotated[
        int,
        typer.Option(
            "--max-pages",
            "-p",
            help="Maximum pages to scrape per run.",
        ),
    ] = 10,
    headless: Annotated[
        bool,
        typer.Option(
            "--headless/--no-headless",
            help="Run browser in headless mode.",
        ),
    ] = True,
) -> None:
    """Start the AudioWatch scraper and notification service."""
    from audiowatch.config import get_settings
    from audiowatch.database import get_engine, get_session, init_database
    from audiowatch.logging import get_logger, setup_logging

    # Load settings and set up logging
    settings = get_settings(config_path)
    setup_logging(settings.logging)
    log = get_logger("audiowatch.cli")

    log.info(
        "Starting AudioWatch",
        poll_interval=settings.scraper.poll_interval_minutes,
        categories=settings.scraper.categories,
    )

    # Ensure database is initialized
    engine = get_engine()
    init_database(engine)

    if once:
        console.print("[blue]Running scraper once...[/blue]")
        asyncio.run(_run_scrape_once(settings, max_pages, headless))
    else:
        console.print(
            f"[blue]Starting scheduled scraper (every {settings.scraper.poll_interval_minutes} minutes)...[/blue]"
        )
        console.print("[dim]Press Ctrl+C to stop[/dim]")
        # TODO: Implement scheduled scraping
        console.print("[yellow]Scheduler not yet implemented. Coming in Phase 4![/yellow]")


async def _run_scrape_once(settings, max_pages: int, headless: bool) -> None:
    """Run a single scrape operation."""
    from audiowatch.database import get_session
    from audiowatch.database.repository import ListingRepository, ScrapeLogRepository
    from audiowatch.logging import get_logger
    from audiowatch.scraper import HeadFiScraper

    log = get_logger("audiowatch.cli")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing scraper...", total=None)

        async with HeadFiScraper(
            headless=headless,
            rate_limit_delay=settings.scraper.rate_limit_delay_seconds,
            timeout=settings.scraper.timeout_seconds * 1000,
        ) as scraper:
            progress.update(task, description="Scraping Head-Fi classifieds...")

            result = await scraper.scrape_recent(
                max_pages=max_pages,
                max_age_days=settings.scraper.initial_scrape_days,
            )

            progress.update(task, description="Saving listings to database...")

            # Save to database
            with get_session() as session:
                listing_repo = ListingRepository(session)
                scrape_log_repo = ScrapeLogRepository(session)

                # Create scrape log
                scrape_log = scrape_log_repo.create()

                new_count = 0
                updated_count = 0

                for listing in result.listings:
                    _, is_new = listing_repo.upsert_from_scraped(listing)
                    if is_new:
                        new_count += 1
                    else:
                        updated_count += 1

                # Complete scrape log
                scrape_log_repo.complete(
                    scrape_log,
                    status="success" if result.success else "error",
                    listings_found=result.total_found,
                    listings_new=new_count,
                    listings_updated=updated_count,
                    pages_scraped=result.pages_scraped,
                    error_message="; ".join(result.errors) if result.errors else None,
                )

                session.commit()

            progress.update(task, description="Done!")

    # Display results
    console.print()
    table = Table(title="Scrape Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Status", "[green]Success[/green]" if result.success else "[red]Failed[/red]")
    table.add_row("Pages Scraped", str(result.pages_scraped))
    table.add_row("Total Listings Found", str(result.total_found))
    table.add_row("New Listings", str(new_count))
    table.add_row("Updated Listings", str(updated_count))

    if result.errors:
        table.add_row("Errors", ", ".join(result.errors))

    console.print(table)


@app.command()
def dashboard(
    config_path: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file.",
        ),
    ] = Path("config.yaml"),
) -> None:
    """Start the Streamlit dashboard."""
    import subprocess
    import sys

    from audiowatch.config import get_settings

    settings = get_settings(config_path)

    console.print(
        f"[blue]Starting dashboard at http://{settings.dashboard.host}:{settings.dashboard.port}[/blue]"
    )

    # Get the path to the dashboard app
    dashboard_path = Path(__file__).parent / "dashboard" / "app.py"

    if not dashboard_path.exists():
        console.print("[yellow]Dashboard not yet implemented. Coming in Phase 5![/yellow]")
        raise typer.Exit(1)

    # Run Streamlit
    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(dashboard_path),
            "--server.port",
            str(settings.dashboard.port),
            "--server.address",
            settings.dashboard.host,
        ]
    )


@app.command()
def status(
    config_path: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file.",
        ),
    ] = Path("config.yaml"),
) -> None:
    """Show AudioWatch status and statistics."""
    from audiowatch.config import get_settings
    from audiowatch.database import get_engine, get_session, init_database
    from audiowatch.database.models import Listing, NotificationLog, ScrapeLog, WatchRuleDB
    from audiowatch.logging import setup_logging

    settings = get_settings(config_path)
    setup_logging(settings.logging)

    # Check database
    db_path = settings.database.path
    if not db_path.exists():
        console.print(f"[yellow]Database not found at {db_path}[/yellow]")
        console.print("Run [bold]audiowatch init[/bold] to create the database.")
        raise typer.Exit(1)

    engine = get_engine(db_path)
    init_database(engine)  # Ensure tables exist

    with get_session() as session:
        # Get counts
        listing_count = session.query(Listing).count()
        active_listings = session.query(Listing).filter(Listing.status == "active").count()
        rule_count = session.query(WatchRuleDB).count()
        notification_count = session.query(NotificationLog).count()

        # Get last scrape
        last_scrape = session.query(ScrapeLog).order_by(ScrapeLog.started_at.desc()).first()

    # Display status table
    table = Table(title="AudioWatch Status")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Database Path", str(db_path))
    table.add_row("Total Listings", str(listing_count))
    table.add_row("Active Listings", str(active_listings))
    table.add_row("Watch Rules", str(rule_count))
    table.add_row("Notifications Sent", str(notification_count))

    if last_scrape:
        table.add_row("Last Scrape", last_scrape.started_at.strftime("%Y-%m-%d %H:%M:%S"))
        table.add_row("Last Scrape Status", last_scrape.status)
    else:
        table.add_row("Last Scrape", "Never")

    console.print(table)

    # Show config summary
    config_table = Table(title="Configuration")
    config_table.add_column("Setting", style="cyan")
    config_table.add_column("Value", style="green")

    config_table.add_row("Poll Interval", f"{settings.scraper.poll_interval_minutes} minutes")
    config_table.add_row("Initial Scrape", f"{settings.scraper.initial_scrape_days} days")
    config_table.add_row("Email Notifications", "Enabled" if settings.notifications.email.enabled else "Disabled")
    config_table.add_row("Discord Notifications", "Enabled" if settings.notifications.discord.enabled else "Disabled")
    config_table.add_row("Watch Rules (config)", str(len(settings.watch_rules)))

    console.print(config_table)


@app.command("rules")
def list_rules(
    config_path: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file.",
        ),
    ] = Path("config.yaml"),
) -> None:
    """List configured watch rules."""
    from audiowatch.config import get_settings

    settings = get_settings(config_path)

    if not settings.watch_rules:
        console.print("[yellow]No watch rules configured.[/yellow]")
        console.print("Add rules to your config.yaml file.")
        return

    table = Table(title="Watch Rules")
    table.add_column("Name", style="cyan")
    table.add_column("Expression", style="green")
    table.add_column("Notify Via", style="blue")
    table.add_column("Enabled", style="yellow")

    for rule in settings.watch_rules:
        table.add_row(
            rule.name,
            rule.expression,
            ", ".join(rule.notify_via),
            "Yes" if rule.enabled else "No",
        )

    console.print(table)


@app.command("listings")
def list_listings(
    config_path: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file.",
        ),
    ] = Path("config.yaml"),
    query: Annotated[
        Optional[str],
        typer.Option(
            "--query",
            "-q",
            help="Search query for listing titles.",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum listings to show.",
        ),
    ] = 20,
    category: Annotated[
        Optional[str],
        typer.Option(
            "--category",
            help="Filter by category.",
        ),
    ] = None,
) -> None:
    """List scraped listings from the database."""
    from audiowatch.config import get_settings
    from audiowatch.database import get_engine, get_session, init_database
    from audiowatch.database.repository import ListingRepository
    from audiowatch.logging import setup_logging

    settings = get_settings(config_path)
    setup_logging(settings.logging)

    # Check database
    db_path = settings.database.path
    if not db_path.exists():
        console.print(f"[yellow]Database not found at {db_path}[/yellow]")
        console.print("Run [bold]audiowatch init[/bold] to create the database.")
        raise typer.Exit(1)

    engine = get_engine(db_path)
    init_database(engine)

    with get_session() as session:
        repo = ListingRepository(session)

        if query or category:
            listings = repo.search(query=query, category=category, limit=limit)
        else:
            listings = repo.get_active_listings(limit=limit)

    if not listings:
        console.print("[yellow]No listings found.[/yellow]")
        if query:
            console.print(f"Try a different search query than '{query}'.")
        return

    table = Table(title=f"Listings ({len(listings)} shown)")
    table.add_column("ID", style="dim", max_width=10)
    table.add_column("Title", style="cyan", max_width=40)
    table.add_column("Price", style="green", justify="right")
    table.add_column("Condition", style="yellow")
    table.add_column("Seller", style="blue")
    table.add_column("Listed", style="dim")

    for listing in listings:
        price_str = f"{listing.price} {listing.currency}" if listing.price else "N/A"
        listed_str = listing.listed_at.strftime("%Y-%m-%d") if listing.listed_at else "Unknown"

        table.add_row(
            listing.id[:8] + "...",
            listing.title[:37] + "..." if len(listing.title) > 40 else listing.title,
            price_str,
            listing.condition or "N/A",
            listing.seller_username,
            listed_str,
        )

    console.print(table)


@app.command("categories")
def list_categories() -> None:
    """List available Head-Fi classifieds categories."""
    from audiowatch.scraper.models import HEADFI_CATEGORIES

    table = Table(title="Head-Fi Categories")
    table.add_column("Slug", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("ID", style="dim")

    for cat in HEADFI_CATEGORIES:
        table.add_row(cat.slug, cat.name, str(cat.category_id))

    console.print(table)


if __name__ == "__main__":
    app()
