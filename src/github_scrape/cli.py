import asyncio
import signal
from dataclasses import dataclass
from typing import Any, Optional

import typer
from rich.console import Console
from rich.table import Table

from github_scrape import __version__, config
from github_scrape.tui import GitHubScrapeTUI
from github_scrape.utils import parse_github_url

app = typer.Typer(name="github-scrape", help="Browse and download GitHub repo files (Github Scrape Project).")
config_app = typer.Typer(name="config", help="Manage configuration.")
app.add_typer(config_app)

console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"github-scrape version: [bold cyan]{__version__}[/bold cyan]")
        raise typer.Exit()


@dataclass
class AppState:
    token: str | None = None
    cwd: bool = False
    no_folder: bool = False
    shutdown_requested: bool = False


@config_app.command("set")
def config_set(key: str, value: str) -> None:
    if key == "token":
        config.set_token(value)
        console.print("[green]Token saved.[/green]")
    elif key == "path":
        try:
            config.set_download_path(value)
            console.print(f"[green]Download path saved: {value}[/green]")
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1) from None
    else:
        console.print(f"[red]Invalid key: {key}. Use 'token' or 'path'.[/red]")
        raise typer.Exit(1)


@config_app.command("list")
def config_list() -> None:
    display = config.config_as_display_dict()
    table = Table(title="Configuration")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("token", display["token"])
    table.add_row("path", display["path"])
    console.print(table)


@config_app.command("unset")
def config_unset(key: str) -> None:
    if key == "token":
        if config.unset_key("github", "token"):
            console.print("[green]Token removed.[/green]")
        else:
            console.print("[yellow]Token was not set.[/yellow]")
    elif key == "path":
        if config.unset_key("download", "default_path"):
            console.print("[green]Download path removed.[/green]")
        else:
            console.print("[yellow]Download path was not set.[/yellow]")
    else:
        console.print(f"[red]Invalid key: {key}. Use 'token' or 'path'.[/red]")
        raise typer.Exit(1)


def _print_welcome() -> None:
    """Print welcome message with ASCII art."""
    console.print()
    console.print("[bold #58a6ff] ██████╗ ██╗████████╗██╗  ██╗██╗   ██╗██████╗  ███████╗ ██████╗██████╗  █████╗ ██████╗ ███████╗[/bold #58a6ff]")  # noqa: E501
    console.print("[bold #58a6ff]██╔════╝ ██║╚══██╔══╝██║  ██║██║   ██║██╔══██╗ ██╔════╝██╔════╝██╔═ ██╗██╔══██╗██╔══██╗██╔════╝[/bold #58a6ff]")  # noqa: E501
    console.print("[bold #58a6ff]██║  ███╗██║   ██║   ███████║██║   ██║██████╔╝ ███████╗██║     ██████╔╝███████║██████╔╝█████╗  [/bold #58a6ff]")  # noqa: E501
    console.print("[bold #58a6ff]██║   ██║██║   ██║   ██╔══██║██║   ██║██╔══██╗ ╚════██║██║     ██╔══██╗██╔══██║██╔═══╝ ██╔══╝  [/bold #58a6ff]")  # noqa: E501
    console.print("[bold #58a6ff]╚██████╔╝██║   ██║   ██║  ██║╚██████╔╝██████╔╝ ███████║╚██████╗██║  ██║██║  ██║██║     ███████╗[/bold #58a6ff]")  # noqa: E501
    console.print("[bold #58a6ff] ╚═════╝ ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝  ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚══════╝[/bold #58a6ff]")  # noqa: E501
    console.print()
    console.print("[bold #79c0ff]       Github Scrape Project[/bold #79c0ff] [dim]—[/dim] Download files from GitHub without cloning")
    console.print()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    url: str | None = None,
    token: str | None = typer.Option(None, "--token", "-t", help="GitHub token"),
    cwd: bool = typer.Option(False, "--cwd", help="Download to current directory"),
    no_folder: bool = typer.Option(False, "--no-folder", help="Don't create repo subfolder"),
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True, help="Show version and exit"
    ),
) -> None:
    if ctx.invoked_subcommand is not None:
        return

    state = AppState(token=token, cwd=cwd, no_folder=no_folder)
    ctx.obj = state

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    shutdown_event = asyncio.Event()

    def signal_handler(signum: int, frame: Any) -> None:
        state.shutdown_requested = True
        shutdown_event.set()
        console.print("\n[yellow]Shutdown requested. Cleaning up...[/yellow]")

    signal.signal(signal.SIGINT, signal_handler)

    try:
        if url is None:
            tui_app = GitHubScrapeTUI(
                token=state.token,
                cwd=state.cwd,
                no_folder=state.no_folder,
            )
        else:
            try:
                owner, repo, branch, subpath = parse_github_url(url)
                tui_app = GitHubScrapeTUI(
                    url=url,
                    token=state.token,
                    cwd=state.cwd,
                    no_folder=state.no_folder,
                )
            except ValueError as e:
                console.print(f"[red]Error: {e}[/red]")
                raise typer.Exit(1) from None

        loop.run_until_complete(tui_app.run_async())

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
    finally:
        if not shutdown_event.is_set():
            pass
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        console.print("[dim]Goodbye![/dim]")
