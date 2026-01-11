"""Command-line interface for AudioWatch.

Provides commands to run the scraper, manage watch rules, and start the dashboard.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
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
            engine = get_engine(db_path)
            reset_database(engine)
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
) -> None:
    """Start the AudioWatch scraper and notification service."""
    from audiowatch.config import get_settings
    from audiowatch.database import get_engine, init_database
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
        # TODO: Implement single scrape run
        console.print("[yellow]Scraper not yet implemented. Coming in Phase 2![/yellow]")
    else:
        console.print(
            f"[blue]Starting scheduled scraper (every {settings.scraper.poll_interval_minutes} minutes)...[/blue]"
        )
        console.print("[dim]Press Ctrl+C to stop[/dim]")
        # TODO: Implement scheduled scraping
        console.print("[yellow]Scheduler not yet implemented. Coming in Phase 4![/yellow]")


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


if __name__ == "__main__":
    app()
