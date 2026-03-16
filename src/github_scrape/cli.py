import signal
import sys
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from github_scrape import config
from github_scrape.tui import BrowseScreen, GitHubScrapeTUI
from github_scrape.utils import parse_github_url

app = typer.Typer(name="github-scrape", help="Browse and download GitHub repo files.")
config_app = typer.Typer(name="config", help="Manage configuration.")
app.add_typer(config_app)

console = Console()

_session_token: str | None = None
_session_cwd: bool = False
_session_no_folder: bool = False


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


def _signal_handler(signum: int, frame: Any) -> None:
    console.print("\n[yellow]Interrupted. Cleaning up...[/yellow]")
    sys.exit(130)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    url: str | None = None,
    token: str | None = typer.Option(None, "--token", "-t", help="GitHub token"),
    cwd: bool = typer.Option(False, "--cwd", help="Download to current directory"),
    no_folder: bool = typer.Option(False, "--no-folder", help="Don't create repo subfolder"),
) -> None:
    global _session_token, _session_cwd, _session_no_folder

    if ctx.invoked_subcommand is not None:
        return

    signal.signal(signal.SIGINT, _signal_handler)

    _session_token = token
    _session_cwd = cwd
    _session_no_folder = no_folder

    if token:
        import os

        os.environ["GITHUB_SCRAPE_TOKEN"] = token

    if url is None:
        tui_app = GitHubScrapeTUI()
        tui_app.run()
    else:
        try:
            owner, repo, branch, subpath = parse_github_url(url)
            tui_app = GitHubScrapeTUI()
            tui_app.push_screen(
                BrowseScreen(owner=owner, repo=repo, branch=branch, subpath=subpath)
            )
            tui_app.run()
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1) from None
