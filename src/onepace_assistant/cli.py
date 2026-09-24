"""CLI interface for One Pace Assistant."""

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .downloader import (
    DownloadError,
    download_playlist_sync,
    download_playlist_zip_sync,
    fetch_playlist_files_sync,
    format_size,
    validate_api_key_sync,
)
from .nfo import generate_arc_nfos, generate_tvshow_nfo
from .poster_utils import copy_poster_to_arc_dir, find_poster_for_arc
from .scraper import ScraperError, fetch_metadata_sync
from .syncer import (
    SyncError,
    SyncOptions,
    build_rsync_command,
    check_remote_rsync,
    check_rsync_installed,
    run_rsync,
)

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="onepace")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress non-essential output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, quiet: bool) -> None:
    """One Pace Assistant - Download and organize One Pace files."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet


@cli.command()
@click.option("-a", "--all", "include_all", is_flag=True, help="Include specials and side stories")
@click.option(
    "-f",
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "plain"]),
    default="table",
    help="Output format",
)
@click.pass_context
def list(ctx: click.Context, include_all: bool, output_format: str) -> None:
    """List available arcs."""
    try:
        arcs = fetch_metadata_sync()
    except ScraperError as e:
        console.print(f"[red]Error fetching metadata: {e}[/red]")
        raise SystemExit(1)

    # Filter specials if not including all
    if not include_all:
        arcs = [a for a in arcs if not a.special]

    if output_format == "json":
        import json

        arc_data = [
            {
                "slug": a.slug,
                "title": a.title,
                "special": a.special,
                "chapters": a.chapters,
                "episodes": a.episodes,
                "resolutions": sorted(a.available_resolutions()),
            }
            for a in arcs
        ]
        click.echo(json.dumps(arc_data, indent=2))

    elif output_format == "plain":
        for arc in arcs:
            click.echo(f"{arc.slug}\t{arc.title}")

    else:  # table
        table = Table(title="One Pace Arcs")
        table.add_column("Slug", style="cyan")
        table.add_column("Title", style="bold")
        table.add_column("Chapters")
        table.add_column("Resolutions")

        for arc in arcs:
            resolutions = ", ".join(f"{r}p" for r in sorted(arc.available_resolutions()))
            table.add_row(
                arc.slug,
                arc.title,
                arc.chapters or "-",
                resolutions or "-",
            )

        console.print(table)


@cli.command()
@click.argument("arc_slug")
@click.pass_context
def info(ctx: click.Context, arc_slug: str) -> None:
    """Show detailed information about an arc."""
    try:
        arcs = fetch_metadata_sync()
    except ScraperError as e:
        console.print(f"[red]Error fetching metadata: {e}[/red]")
        raise SystemExit(1)

    # Find the arc
    arc = next((a for a in arcs if a.slug == arc_slug), None)
    if not arc:
        console.print(f"[red]Arc '{arc_slug}' not found[/red]")
        console.print("[dim]Use 'onepace list' to see available arcs[/dim]")
        raise SystemExit(1)

    # Display arc info
    console.print(f"\n[bold cyan]{arc.title}[/bold cyan]")
    console.print(f"[dim]Slug: {arc.slug}[/dim]\n")

    if arc.description:
        console.print(f"[italic]{arc.description}[/italic]\n")

    if arc.chapters:
        console.print(f"📖 Manga Chapters: {arc.chapters}")
    if arc.episodes:
        console.print(f"📺 Anime Episodes: {arc.episodes}")

    # Resolutions
    resolutions = sorted(arc.available_resolutions(), reverse=True)
    console.print(f"🎬 Resolutions: {', '.join(f'{r}p' for r in resolutions)}")

    # Language options
    console.print("\n[bold]Available Variants:[/bold]")
    for lang in arc.available_languages():
        variant = f" ({lang['variant']})" if lang.get("variant") else ""
        sub = lang.get("sub") or "none"
        dub = lang.get("dub") or "unknown"
        console.print(f"  • Sub: {sub}, Dub: {dub}{variant}")


@cli.command()
@click.argument("arc_slug")
@click.option(
    "-o",
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=Path("./downloads"),
    help="Output directory",
)
@click.option(
    "-r",
    "--resolution",
    type=click.Choice(["480", "720", "1080"]),
    default="1080",
    help="Video resolution",
)
@click.option("-s", "--sub", default=None, help="Subtitle language (en, none, or omit for auto)")
@click.option("-d", "--dub", default="ja", help="Audio language (ja, en)")
@click.option(
    "--variant",
    default=None,
    help="Arc variant (e.g., 'extended' for extended dub versions)",
)
@click.option("-n", "--dry-run", is_flag=True, help="Show what would be downloaded")
@click.option("--no-nfo", is_flag=True, help="Skip NFO file generation")
@click.option("--resume/--no-resume", default=True, help="Resume interrupted downloads")
@click.option(
    "-m",
    "--method",
    type=click.Choice(["individual", "zip", "auto"]),
    default="individual",
    help="Download method: individual (per-file, default), zip (bulk), auto (try zip first)",
)
@click.option(
    "--posters-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Optional: Directory containing poster images to copy after download",
)
@click.option(
    "--pixeldrain-api-key",
    default=None,
    envvar="PIXELDRAIN_API_KEY",
    help="Pixeldrain API key for authenticated requests",
)
@click.pass_context
def download(
    ctx: click.Context,
    arc_slug: str,
    output_dir: Path,
    resolution: str,
    sub: str,
    dub: str,
    variant: str | None,
    dry_run: bool,
    no_nfo: bool,
    resume: bool,
    method: str,
    posters_dir: Path | None,
    pixeldrain_api_key: str | None,
) -> None:
    """Download an arc."""
    quiet = ctx.obj.get("quiet", False)

    # Validate API key before doing anything else
    if pixeldrain_api_key:
        try:
            validate_api_key_sync(pixeldrain_api_key)
        except DownloadError as e:
            console.print(f"[red]{e}[/red]")
            raise SystemExit(1)

    # Fetch metadata
    if not quiet:
        console.print("[cyan]Fetching arc metadata...[/cyan]")

    try:
        arcs = fetch_metadata_sync()
    except ScraperError as e:
        console.print(f"[red]Error fetching metadata: {e}[/red]")
        raise SystemExit(1)

    # Find the arc
    arc = next((a for a in arcs if a.slug == arc_slug), None)
    if not arc:
        console.print(f"[red]Arc '{arc_slug}' not found[/red]")
        console.print("[dim]Use 'onepace list' to see available arcs[/dim]")
        raise SystemExit(1)

    # Handle subtitle preference with smart defaults
    playlist = None
    actual_sub = None  # Track what was actually selected
    
    if sub is None:
        # Auto-detect based on dub language
        if dub == "en":
            # Try English dub without subs first, fall back to with subs
            playlist = arc.get_playlist(resolution=int(resolution), sub=None, dub=dub, variant=variant)
            if playlist:
                actual_sub = "none"
            else:
                playlist = arc.get_playlist(resolution=int(resolution), sub="en", dub=dub, variant=variant)
                if playlist:
                    actual_sub = "en"
        else:
            # For non-English dubs, default to English subs
            playlist = arc.get_playlist(resolution=int(resolution), sub="en", dub=dub, variant=variant)
            if playlist:
                actual_sub = "en"
    else:
        # User explicitly specified subtitle preference
        sub_pref = None if sub.lower() == "none" else sub
        playlist = arc.get_playlist(resolution=int(resolution), sub=sub_pref, dub=dub, variant=variant)
        actual_sub = sub

    if not playlist:
        console.print("[red]No playlist found matching preferences[/red]")
        console.print(f"[dim]Try 'onepace info {arc_slug}' to see available options[/dim]")
        raise SystemExit(1)

    if not quiet:
        console.print(f"[green]Found: {arc.title}[/green]")
        console.print(f"[dim]Resolution: {playlist.resolution}p, Sub: {actual_sub}, Dub: {dub}[/dim]")

    # Dry run
    if dry_run:
        console.print("\n[yellow]DRY RUN - No files will be downloaded[/yellow]\n")

        file_list = fetch_playlist_files_sync(playlist, api_key=pixeldrain_api_key)
        total_size = sum(f.size for f in file_list.files)

        table = Table(title="Files to Download")
        table.add_column("Filename")
        table.add_column("Size", justify="right")

        for f in file_list.files:
            table.add_row(f.name, format_size(f.size))

        console.print(table)
        console.print(f"\n[bold]Total: {len(file_list.files)} files, {format_size(total_size)}[/bold]")
        return

    # Create output directory
    arc_output_dir = output_dir / arc.slug
    arc_output_dir.mkdir(parents=True, exist_ok=True)

    if not quiet:
        console.print(f"[dim]Output: {arc_output_dir}[/dim]\n")

    # Download files with selected method
    try:
        if method == "individual":
            # Show hint about zip option
            if not quiet:
                console.print("[dim]💡 Tip: Use --method zip to download all as a single archive. This may help delay rate limits.[/dim]\n")
            # Force individual file downloads
            downloaded_files = download_playlist_sync(playlist, arc_output_dir, resume=resume, api_key=pixeldrain_api_key)
        elif method == "zip":
            # Force zip download
            downloaded_files = download_playlist_zip_sync(playlist, arc_output_dir, resume=resume, api_key=pixeldrain_api_key)
        else:  # auto
            # Try zip first, fallback to individual on error
            try:
                downloaded_files = download_playlist_zip_sync(playlist, arc_output_dir, resume=resume, api_key=pixeldrain_api_key)
            except (DownloadError, Exception) as e:
                if not quiet:
                    console.print(
                        f"[yellow]Zip download failed ({e}), "
                        "falling back to individual downloads[/yellow]"
                    )
                downloaded_files = download_playlist_sync(playlist, arc_output_dir, resume=resume, api_key=pixeldrain_api_key)
    except Exception as e:
        console.print(f"[red]Download failed: {e}[/red]")
        raise SystemExit(1)

    # Generate NFO files
    if not no_nfo and downloaded_files:
        if not quiet:
            console.print("\n[cyan]Generating NFO files...[/cyan]")

        # Generate tvshow.nfo in parent directory
        generate_tvshow_nfo(output_dir)

        # Generate episode NFOs
        video_files = [f for f in downloaded_files if f.suffix.lower() in (".mkv", ".mp4", ".avi")]
        generate_arc_nfos(arc, video_files, arc_output_dir, arcs=arcs)

        if not quiet:
            console.print(f"[green]Generated {len(video_files) + 1} NFO files[/green]")

    # Copy poster if posters-dir provided
    if posters_dir and downloaded_files:
        poster_source = find_poster_for_arc(arc.slug, posters_dir)
        if poster_source:
            try:
                poster_dest = copy_poster_to_arc_dir(poster_source, arc_output_dir)
                if not quiet:
                    console.print(f"[green]Copied poster: {poster_dest.name}[/green]")
            except (OSError, PermissionError) as e:
                console.print(f"[yellow]Warning: Could not copy poster: {e}[/yellow]")
        else:
            if not quiet:
                console.print(
                    f"[yellow]No matching poster found for '{arc.slug}' "
                    f"in {posters_dir}[/yellow]"
                )

    console.print("\n[bold green]✓ Download complete![/bold green]")
    console.print(f"[dim]Files saved to: {arc_output_dir}[/dim]")


@cli.command("generate-nfo")
@click.option(
    "-i",
    "--input",
    "input_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help="Directory containing video files organized by arc subdirectories",
)
@click.option(
    "-p",
    "--posters",
    "posters_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Optional: Directory containing poster images to copy",
)
@click.pass_context
def generate_nfo_cmd(ctx: click.Context, input_dir: Path, posters_dir: Path | None) -> None:
    """Generate NFO files for existing video files.

    Video files must be organized in subdirectories by arc.
    The command will fetch metadata and generate appropriate NFO files.

    Example directory structure:
        ./downloads/romance-dawn/Romance Dawn 01.mkv
        ./downloads/romance-dawn/Romance Dawn 02.mkv
        ./downloads/water-seven/Water Seven 01.mkv
    """
    quiet = ctx.obj.get("quiet", False)
    video_extensions = (".mkv", ".mp4", ".avi")

    # Scan for arc subdirectories
    arc_dirs = [d for d in input_dir.iterdir() if d.is_dir()]

    if not arc_dirs:
        console.print("[red]No subdirectories found in input directory.[/red]")
        console.print("[dim]Expected structure: input_dir/arc-slug/video-files.mkv[/dim]")
        raise SystemExit(1)

    # Fetch metadata
    if not quiet:
        console.print("[cyan]Fetching arc metadata...[/cyan]")

    try:
        arcs = fetch_metadata_sync()
    except ScraperError as e:
        console.print(f"[red]Error fetching metadata: {e}[/red]")
        raise SystemExit(1)

    # Build slug lookup (case-insensitive, flexible separators)
    arc_lookup = {arc.slug.lower(): arc for arc in arcs}

    # Process results tracking
    results = {"nfo_generated": 0, "posters_copied": 0, "skipped": 0, "errors": []}

    # Generate tvshow.nfo in parent directory
    generate_tvshow_nfo(input_dir)
    results["nfo_generated"] += 1
    if not quiet:
        console.print("[green]Generated tvshow.nfo[/green]")

    # Process each arc directory
    for arc_dir in arc_dirs:
        # Normalize directory name to slug format
        dir_slug = arc_dir.name.lower().replace(" ", "-").replace("_", "-")

        # Find matching arc
        arc = arc_lookup.get(dir_slug)
        if not arc:
            if not quiet:
                console.print(f"[yellow]Skipping '{arc_dir.name}': No matching arc found[/yellow]")
            results["skipped"] += 1
            continue

        # Find video files
        video_files = [
            f for f in arc_dir.iterdir()
            if f.is_file() and f.suffix.lower() in video_extensions
        ]

        if not video_files:
            if not quiet:
                console.print(f"[yellow]Skipping '{arc_dir.name}': No video files found[/yellow]")
            results["skipped"] += 1
            continue

        # Generate episode NFOs
        nfo_paths = generate_arc_nfos(arc, video_files, arc_dir, arcs=arcs)
        results["nfo_generated"] += len(nfo_paths)
        if not quiet:
            console.print(
                f"[green]Generated {len(nfo_paths)} episode NFOs for '{arc.title}'[/green]"
            )

        # Copy poster if provided
        if posters_dir:
            poster_source = find_poster_for_arc(arc.slug, posters_dir)
            if poster_source:
                try:
                    copy_poster_to_arc_dir(poster_source, arc_dir)
                    results["posters_copied"] += 1
                    if not quiet:
                        console.print(f"[green]Copied poster for '{arc.title}'[/green]")
                except (OSError, PermissionError) as e:
                    results["errors"].append(f"{arc.slug}: {e}")
            else:
                if not quiet:
                    console.print(f"[dim]No poster found for '{arc.slug}'[/dim]")

    # Summary
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  NFO files generated: {results['nfo_generated']}")
    if posters_dir:
        console.print(f"  Posters copied: {results['posters_copied']}")
    if results["skipped"]:
        console.print(f"  Directories skipped: {results['skipped']}")
    if results["errors"]:
        console.print(f"  [red]Errors: {len(results['errors'])}[/red]")
        for error in results["errors"]:
            console.print(f"    [red]• {error}[/red]")


@cli.command("add-posters")
@click.option(
    "-i",
    "--input",
    "input_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help="Directory containing arc subdirectories",
)
@click.option(
    "-p",
    "--posters",
    "posters_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help="Directory containing poster images",
)
@click.option(
    "--require-nfo",
    is_flag=True,
    default=False,
    help="Only copy posters to directories that contain NFO files",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing poster.jpg files",
)
@click.pass_context
def add_posters_cmd(
    ctx: click.Context,
    input_dir: Path,
    posters_dir: Path,
    require_nfo: bool,
    force: bool,
) -> None:
    """Copy poster images to arc directories.

    Searches for poster images matching arc slugs and copies them
    as 'poster.jpg' to the respective arc directories.
    """
    quiet = ctx.obj.get("quiet", False)

    # Scan for arc subdirectories
    arc_dirs = [d for d in input_dir.iterdir() if d.is_dir()]

    if not arc_dirs:
        console.print("[red]No subdirectories found in input directory.[/red]")
        raise SystemExit(1)

    # Process results tracking
    results = {"copied": 0, "skipped": 0, "no_match": 0, "errors": []}

    for arc_dir in arc_dirs:
        # Check for existing poster
        existing_poster = arc_dir / "poster.jpg"
        if existing_poster.exists() and not force:
            if not quiet:
                console.print(
                    f"[dim]Skipping '{arc_dir.name}': "
                    "poster.jpg already exists (use --force to overwrite)[/dim]"
                )
            results["skipped"] += 1
            continue

        # Check for NFO files if required
        if require_nfo:
            nfo_files = list(arc_dir.glob("*.nfo"))
            if not nfo_files:
                if not quiet:
                    console.print(
                        f"[dim]Skipping '{arc_dir.name}': "
                        "No NFO files found (--require-nfo is set)[/dim]"
                    )
                results["skipped"] += 1
                continue

        # Normalize directory name to slug format
        dir_slug = arc_dir.name.lower().replace(" ", "-").replace("_", "-")

        # Find matching poster
        poster_source = find_poster_for_arc(dir_slug, posters_dir)
        if not poster_source:
            if not quiet:
                console.print(f"[yellow]No matching poster found for '{arc_dir.name}'[/yellow]")
            results["no_match"] += 1
            continue

        # Copy poster
        try:
            copy_poster_to_arc_dir(poster_source, arc_dir)
            results["copied"] += 1
            if not quiet:
                console.print(f"[green]Copied poster to '{arc_dir.name}'[/green]")
        except (OSError, PermissionError) as e:
            results["errors"].append(f"{arc_dir.name}: {e}")

    # Summary
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Posters copied: {results['copied']}")
    if results["skipped"]:
        console.print(f"  Directories skipped: {results['skipped']}")
    if results["no_match"]:
        console.print(f"  No matching poster: {results['no_match']}")
    if results["errors"]:
        console.print(f"  [red]Errors: {len(results['errors'])}[/red]")
        for error in results["errors"]:
            console.print(f"    [red]• {error}[/red]")


@cli.command()
@click.option(
    "-s",
    "--source",
    "source_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("./downloads"),
    help="Local directory to sync from",
)
@click.option(
    "-t",
    "--target",
    required=True,
    help="Remote target (e.g., user@host:/path/to/media)",
)
@click.option(
    "--ssh-key",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to SSH private key",
)
@click.option(
    "--port",
    type=int,
    default=None,
    help="SSH port",
)
@click.option(
    "-n",
    "--dry-run",
    is_flag=True,
    help="Show what would be transferred without actually syncing",
)
@click.option(
    "--delete",
    is_flag=True,
    help="Delete remote files not present locally",
)
@click.option(
    "--exclude",
    multiple=True,
    help="Exclude pattern (can be specified multiple times)",
)
@click.option(
    "--bwlimit",
    type=str,
    default=None,
    help="Bandwidth limit (e.g., '5000' for 5000 KBps, '10m' for 10 MBps)",
)
@click.pass_context
def rsync(
    ctx: click.Context,
    source_dir: Path,
    target: str,
    ssh_key: Path | None,
    port: int | None,
    dry_run: bool,
    delete: bool,
    exclude: tuple[str, ...],
    bwlimit: str | None,
) -> None:
    """Sync downloaded files to a remote host via rsync over SSH."""
    quiet = ctx.obj.get("quiet", False)
    verbose = ctx.obj.get("verbose", False)

    # Pre-flight: check local rsync
    try:
        check_rsync_installed()
    except SyncError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)

    # Pre-flight: check remote rsync
    try:
        check_remote_rsync(target, ssh_key=ssh_key, port=port)
    except SyncError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)

    # Validate source has content
    if not any(source_dir.iterdir()):
        console.print(f"[red]Source directory is empty: {source_dir}[/red]")
        raise SystemExit(1)

    options = SyncOptions(
        source=source_dir,
        target=target,
        ssh_key=ssh_key,
        port=port,
        dry_run=dry_run,
        delete=delete,
        exclude=exclude,
        bwlimit=bwlimit,
        verbose=verbose,
    )

    if not quiet:
        console.print(f"[cyan]Syncing {source_dir} -> {target}[/cyan]")
        if dry_run:
            console.print("[yellow]DRY RUN - no files will be transferred[/yellow]")
        if delete:
            console.print(
                "[yellow]--delete is set: remote files not present locally will be removed[/yellow]"
            )
        if verbose:
            cmd = build_rsync_command(options)
            console.print(f"[dim]Command: {' '.join(cmd)}[/dim]")
        console.print()

    try:
        run_rsync(options)
    except SyncError as e:
        console.print(f"\n[red]Sync failed: {e}[/red]")
        raise SystemExit(1)

    if not quiet:
        console.print("\n[bold green]Sync complete![/bold green]")


def main() -> None:
    """Entry point for the CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
