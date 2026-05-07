import asyncio
import logging
import signal
from dataclasses import dataclass
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from github_scrape import config
from github_scrape.logging_cfg import setup_logging
from github_scrape.tui import GitHubScrapeTUI
from github_scrape.utils import parse_github_url

app = typer.Typer(name="github-scrape", help="Browse and download GitHub repo files.")
config_app = typer.Typer(name="config", help="Manage configuration.")
app.add_typer(config_app)

console = Console()


@dataclass
class AppState:
    token: str | None = None
    cwd: bool = False
    no_folder: bool = False
    verbose: bool = False
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


@app.command("rate-limit")
def rate_limit(
    token: str | None = typer.Option(None, "--token", "-t", help="GitHub token"),
) -> None:
    from github_scrape.api import GitHubClient

    async def _check() -> None:
        tok = token or config.get_token()
        async with GitHubClient(token=tok) as client:
            limits = await client.get_rate_limit()
            rl = client.rate_limit_info
            table = Table(title="GitHub API Rate Limit")
            table.add_column("Resource", style="cyan")
            table.add_column("Limit", style="green")
            table.add_column("Remaining", style="yellow" if rl.remaining < 100 else "green")
            table.add_column("Reset At", style="blue")
            table.add_row("core", str(limits["limit"]), str(limits["remaining"]), rl.reset_datetime)
            console.print(table)
            if rl.remaining < 10:
                console.print(f"[yellow]Warning: Only {rl.remaining} requests remaining![/yellow]")

    asyncio.run(_check())


@app.command("cache")
def cache_management(
    action: str = typer.Argument("status", help="Action: status, clear"),
) -> None:
    if action == "status":
        console.print("[dim]Cache is in-memory per session. No persistent cache to inspect.[/dim]")
        console.print("Tree responses are cached for 5 minutes within a single session.")
    elif action == "clear":
        console.print("[green]In-memory cache is cleared on restart.[/green]")
    else:
        console.print(f"[red]Unknown action: {action}. Use 'status' or 'clear'.[/red]")
        raise typer.Exit(1)


@app.command("version")
def show_version() -> None:
    from github_scrape import __version__

    console.print(f"github-scrape v{__version__}")


def _print_welcome() -> None:
    console.print()
    console.print("[bold #58a6ff] ██████╗ ██╗████████╗██╗ ██╗██╗ ██╗██████╗ ███████╗ ██████╗██████╗ █████╗ ██████╗ ███████╗[/bold #58a6ff]")  # noqa: E501
    console.print("[bold #58a6ff]██╔════╝ ██║╚══██╔══╝██║ ██║██║ ██║██╔══██╗ ██╔════╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██╔════╝[/bold #58a6ff]")  # noqa: E501
    console.print("[bold #58a6ff]██║ ███╗██║ ██║ ███████║██║ ██║██████╔╝ ███████╗██║ ██████╔╝███████║██████╔╝█████╗[/bold #58a6ff]")  # noqa: E501
    console.print("[bold #58a6ff]██║ ██║██║ ██║ ██╔══██║██║ ██║██╔══██╗ ╚════██║██║ ██╔══██╗██╔══██║██╔═══╝ ██╔══╝[/bold #58a6ff]")  # noqa: E501
    console.print("[bold #58a6ff]╚██████╔╝██║ ██║ ██║ ██║╚██████╔╝██████╔╝ ███████║╚██████╗██║ ██║██║ ██║██║ ███████╗[/bold #58a6ff]")  # noqa: E501
    console.print("[bold #58a6ff] ╚═════╝ ╚═╝ ╚═╝ ╚═╝ ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝ ╚═════╝╚═╝ ╚═╝╚═╝ ╚═╝╚═╝ ╚══════╝[/bold #58a6ff]")  # noqa: E501
    console.print()
    console.print("[bold #79c0ff]           github-scrape[/bold #79c0ff] [dim]—[/dim] Download files from GitHub without cloning")
    console.print()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    url: str | None = None,
    token: str | None = typer.Option(None, "--token", "-t", help="GitHub token"),
    cwd: bool = typer.Option(False, "--cwd", help="Download to current directory"),
    no_folder: bool = typer.Option(False, "--no-folder", help="Don't create repo subfolder"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug logging"),
) -> None:
    if ctx.invoked_subcommand is not None:
        return

    log_level = logging.WARNING
    if debug:
        log_level = logging.DEBUG
    elif verbose:
        log_level = logging.INFO
    setup_logging(log_level)

    state = AppState(token=token, cwd=cwd, no_folder=no_folder, verbose=verbose)
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
        _print_welcome()

        if url is None:
            console.print("[italic]Launching interactive browser... Press Ctrl+C to quit anytime[/italic]\n")
            tui_app = GitHubScrapeTUI(
                token=state.token,
                cwd=state.cwd,
                no_folder=state.no_folder,
            )
        else:
            try:
                owner, repo, branch, subpath = parse_github_url(url)
                console.print(f"[green]Opening {owner}/{repo}@{branch or 'default'}...[/green]\n")
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
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        console.print("[dim]Goodbye![/dim]")
