"""Main entry point for the email cleaner agent."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import load_config
from .agents import JunkDetectorAgent


console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="email-cleaner")
def cli():
    """Email Cleaner - An agent to identify and clean junk emails.

    This tool connects to your email account via IMAP and analyzes
    emails to identify spam, phishing, and promotional junk.
    """
    pass


@cli.command()
@click.option(
    "--env-file",
    type=click.Path(exists=True, path_type=Path),
    help="Path to .env file with credentials",
)
@click.option(
    "--folder",
    default="INBOX",
    help="Email folder to scan (default: INBOX)",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Maximum number of emails to scan",
)
@click.option(
    "--search",
    default="ALL",
    help="IMAP search criteria (e.g., 'UNSEEN', 'SINCE 01-Jan-2024')",
)
def scan(env_file: Path | None, folder: str, limit: int | None, search: str):
    """Scan emails and identify junk without taking action.

    This command analyzes your emails and reports which ones are
    identified as junk, along with confidence scores and reasons.
    """
    try:
        config = load_config(env_file)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        console.print("Make sure to create a .env file with your email credentials.")
        console.print("See .env.example for the required format.")
        sys.exit(1)

    if not config.email.email_address or not config.email.email_password:
        console.print("[red]Error: EMAIL_ADDRESS and EMAIL_PASSWORD are required.[/red]")
        sys.exit(1)

    agent = JunkDetectorAgent(config)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning emails...", total=None)

        def log_progress(message: str):
            progress.update(task, description=message)

        agent.set_progress_callback(log_progress)
        report = agent.scan_emails(folder=folder, limit=limit, search_criteria=search)

    # Display results
    console.print()
    console.print(Panel(report.summary(), title="Scan Results", border_style="green"))

    # Show junk email details
    junk_details = agent.get_junk_details(report)
    if junk_details:
        console.print()
        console.print("[bold]Junk Emails Found:[/bold]")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("From", style="cyan", max_width=30)
        table.add_column("Subject", max_width=40)
        table.add_column("Confidence", justify="center")
        table.add_column("Action", style="yellow")
        table.add_column("Indicators", max_width=30)

        for detail in junk_details:
            confidence_color = (
                "red" if detail["confidence"] >= 0.9
                else "yellow" if detail["confidence"] >= 0.7
                else "green"
            )
            table.add_row(
                detail["sender"][:30],
                detail["subject"][:40],
                f"[{confidence_color}]{detail['confidence']:.0%}[/{confidence_color}]",
                detail["recommended_action"],
                ", ".join(detail["indicators"][:3]),
            )

        console.print(table)
        console.print()
        console.print(
            "[dim]Run 'email-cleaner clean' to remove junk emails "
            "(use --dry-run first to preview)[/dim]"
        )


@cli.command()
@click.option(
    "--env-file",
    type=click.Path(exists=True, path_type=Path),
    help="Path to .env file with credentials",
)
@click.option(
    "--folder",
    default="INBOX",
    help="Email folder to clean (default: INBOX)",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Maximum number of emails to process",
)
@click.option(
    "--search",
    default="ALL",
    help="IMAP search criteria",
)
@click.option(
    "--dry-run/--no-dry-run",
    default=True,
    help="Preview changes without actually deleting (default: dry-run)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Skip confirmation prompt",
)
def clean(
    env_file: Path | None,
    folder: str,
    limit: int | None,
    search: str,
    dry_run: bool,
    force: bool,
):
    """Scan and clean junk emails.

    This command scans emails, identifies junk, and takes action:
    - High confidence (≥90%): Move to trash
    - Medium confidence (≥70%): Move to spam folder
    - Lower confidence: Mark for review

    Use --dry-run (default) to preview what would happen.
    Use --no-dry-run to actually perform the cleanup.
    """
    try:
        config = load_config(env_file)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        sys.exit(1)

    if not config.email.email_address or not config.email.email_password:
        console.print("[red]Error: EMAIL_ADDRESS and EMAIL_PASSWORD are required.[/red]")
        sys.exit(1)

    agent = JunkDetectorAgent(config)

    # First scan
    console.print("[bold]Scanning emails...[/bold]")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning...", total=None)

        def log_progress(message: str):
            progress.update(task, description=message)

        agent.set_progress_callback(log_progress)
        report = agent.scan_emails(folder=folder, limit=limit, search_criteria=search)

    if report.junk_emails_found == 0:
        console.print("[green]No junk emails found. Your inbox is clean![/green]")
        return

    # Show what will be cleaned
    junk_details = agent.get_junk_details(report)
    console.print()
    console.print(f"[bold]Found {report.junk_emails_found} junk emails:[/bold]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("From", style="cyan", max_width=30)
    table.add_column("Subject", max_width=40)
    table.add_column("Confidence", justify="center")
    table.add_column("Action", style="yellow")

    for detail in junk_details:
        confidence_color = (
            "red" if detail["confidence"] >= 0.9
            else "yellow" if detail["confidence"] >= 0.7
            else "green"
        )
        table.add_row(
            detail["sender"][:30],
            detail["subject"][:40],
            f"[{confidence_color}]{detail['confidence']:.0%}[/{confidence_color}]",
            detail["recommended_action"],
        )

    console.print(table)
    console.print()

    if dry_run:
        console.print(
            "[yellow][DRY RUN] No emails will be modified. "
            "Use --no-dry-run to perform actual cleanup.[/yellow]"
        )
        return

    # Confirmation
    if not force:
        if not click.confirm(
            f"Proceed with cleaning {report.junk_emails_found} emails?"
        ):
            console.print("[yellow]Cancelled.[/yellow]")
            return

    # Perform cleanup
    console.print()
    console.print("[bold]Cleaning junk emails...[/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Cleaning...", total=None)

        def log_progress(message: str):
            progress.update(task, description=message)

        agent.set_progress_callback(log_progress)
        report = agent.clean_junk(report, dry_run=False)

    console.print()
    console.print(Panel(report.summary(), title="Cleanup Results", border_style="green"))


@cli.command()
@click.option(
    "--env-file",
    type=click.Path(exists=True, path_type=Path),
    help="Path to .env file with credentials",
)
def folders(env_file: Path | None):
    """List available email folders."""
    try:
        config = load_config(env_file)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        sys.exit(1)

    if not config.email.email_address or not config.email.email_password:
        console.print("[red]Error: EMAIL_ADDRESS and EMAIL_PASSWORD are required.[/red]")
        sys.exit(1)

    from .services import IMAPEmailClient

    console.print(f"Connecting to {config.email.imap_server}...")

    try:
        with IMAPEmailClient(config.email) as client:
            folder_list = client.list_folders()
            console.print()
            console.print("[bold]Available folders:[/bold]")
            for folder_name in folder_list:
                console.print(f"  • {folder_name}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
def init():
    """Create a sample .env file with configuration template."""
    env_path = Path(".env")
    example_path = Path(".env.example")

    if env_path.exists():
        if not click.confirm(".env file already exists. Overwrite?"):
            console.print("[yellow]Cancelled.[/yellow]")
            return

    content = """# Email Server Configuration
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
EMAIL_ADDRESS=your-email@gmail.com
EMAIL_PASSWORD=your-app-password

# For Gmail, use an App Password:
# https://support.google.com/accounts/answer/185833

# Agent Configuration
DRY_RUN=true
MAX_EMAILS_TO_PROCESS=100
JUNK_CONFIDENCE_THRESHOLD=0.7
"""

    env_path.write_text(content)
    console.print(f"[green]Created {env_path}[/green]")
    console.print()
    console.print("Next steps:")
    console.print("1. Edit .env with your email credentials")
    console.print("2. For Gmail, create an App Password at:")
    console.print("   https://support.google.com/accounts/answer/185833")
    console.print("3. Run 'email-cleaner scan' to analyze your emails")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
