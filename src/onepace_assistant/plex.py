"""Plex API client for metadata updates.

This module provides functionality to update Plex metadata for One Pace
episodes, offering an alternative to NFO files for users who don't want
to install third-party Plex plugins.

Note: Plex cannot create custom shows, so this works by updating the
existing "One Piece" show metadata with One Pace information.
"""

from pathlib import Path

from plexapi.exceptions import NotFound, Unauthorized
from plexapi.server import PlexServer
from plexapi.video import Episode, Season, Show

from .models import Arc
from .poster_utils import SUPPORTED_EXTENSIONS, find_poster_for_arc


class PlexConnectionError(Exception):
    """Error connecting to Plex server."""


class PlexShowNotFoundError(Exception):
    """Show not found in Plex library."""


class PlexClient:
    """Client for interacting with Plex server.

    Attributes:
        server: PlexServer instance
    """

    def __init__(self, host: str, token: str):
        """Initialize Plex client.

        Args:
            host: Plex server URL (e.g., http://localhost:32400)
            token: Plex authentication token

        Raises:
            PlexConnectionError: If unable to connect to server
        """
        try:
            self.server = PlexServer(host, token)
        except Unauthorized as e:
            raise PlexConnectionError(f"Invalid Plex token: {e}") from e
        except Exception as e:
            raise PlexConnectionError(f"Failed to connect to Plex server: {e}") from e

    def get_show(self, library: str, show_name: str) -> Show | None:
        """Find a show in the specified library.

        Args:
            library: Library section name (e.g., "TV", "Anime")
            show_name: Show title to search for

        Returns:
            Show object if found, None otherwise

        Raises:
            PlexConnectionError: If library not found
        """
        try:
            section = self.server.library.section(library)
        except NotFound as e:
            raise PlexConnectionError(f"Library '{library}' not found: {e}") from e

        shows = section.searchShows(title=show_name)
        return shows[0] if shows else None

    def update_show_metadata(
        self,
        show: Show,
        title: str | None = None,
        summary: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, str]:
        """Update show-level metadata.

        Args:
            show: Plex Show object to update
            title: New title (optional)
            summary: New plot/summary (optional)
            dry_run: If True, return changes without applying

        Returns:
            Dict of changes made (field: new_value)
        """
        changes = {}

        if title and show.title != title:
            changes["title"] = title
            if not dry_run:
                show.edit(**{"title.value": title, "title.locked": 1})

        if summary and show.summary != summary:
            changes["summary"] = summary
            if not dry_run:
                show.edit(**{"summary.value": summary, "summary.locked": 1})

        return changes

    def update_season_metadata(
        self,
        season: Season,
        title: str,
        summary: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, str]:
        """Update season metadata.

        Args:
            season: Plex Season object to update
            title: New season title
            summary: New plot/summary (optional)
            dry_run: If True, return changes without applying

        Returns:
            Dict of changes made
        """
        changes = {}

        if season.title != title:
            changes["title"] = title
            if not dry_run:
                season.edit(**{"title.value": title, "title.locked": 1})

        if summary and season.summary != summary:
            changes["summary"] = summary
            if not dry_run:
                season.edit(**{"summary.value": summary, "summary.locked": 1})

        return changes

    def update_episode_metadata(
        self,
        episode: Episode,
        title: str,
        summary: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, str]:
        """Update episode metadata.

        Args:
            episode: Plex Episode object to update
            title: New episode title
            summary: New plot/summary (optional)
            dry_run: If True, return changes without applying

        Returns:
            Dict of changes made
        """
        changes = {}

        if episode.title != title:
            changes["title"] = title
            if not dry_run:
                episode.edit(**{"title.value": title, "title.locked": 1})

        if summary and episode.summary != summary:
            changes["summary"] = summary
            if not dry_run:
                episode.edit(**{"summary.value": summary, "summary.locked": 1})

        return changes

    def upload_poster(
        self,
        item: Show | Season,
        poster_path: Path,
        dry_run: bool = False,
    ) -> bool:
        """Upload poster image to a show or season.

        Args:
            item: Plex Show or Season object
            poster_path: Path to poster image file
            dry_run: If True, validate only without uploading

        Returns:
            True if poster was uploaded/would be uploaded
        """
        if not poster_path.exists():
            return False

        if poster_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return False

        if not dry_run:
            item.uploadPoster(filepath=str(poster_path))

        return True

    def rescan_library(self, library: str) -> None:
        """Trigger library rescan.

        Args:
            library: Library section name to rescan

        Raises:
            PlexConnectionError: If library not found
        """
        try:
            section = self.server.library.section(library)
            section.update()
        except NotFound as e:
            raise PlexConnectionError(f"Library '{library}' not found: {e}") from e


def build_season_title(arc: Arc, season_number: int) -> str:
    """Build formatted season title from arc.

    Args:
        arc: One Pace arc
        season_number: Season number (1-indexed)

    Returns:
        Formatted title like "01 - Romance Dawn"
    """
    return f"{season_number:02d} - {arc.title}"


def build_episode_title(arc: Arc, episode_number: int) -> str:
    """Build formatted episode title from arc.

    Args:
        arc: One Pace arc
        episode_number: Episode number within season (1-indexed)

    Returns:
        Formatted title like "Romance Dawn 01"
    """
    return f"{arc.title} {episode_number:02d}"


def update_plex_metadata(
    client: PlexClient,
    arcs: list[Arc],
    library: str,
    show_name: str,
    rename_show: bool = False,
    poster_dir: Path | None = None,
    dry_run: bool = False,
) -> dict:
    """Update Plex metadata for all One Pace arcs.

    Args:
        client: PlexClient instance
        arcs: List of One Pace arcs (in order)
        library: Plex library name
        show_name: Current show name in Plex
        rename_show: If True, rename show to "One Pace"
        poster_dir: Optional directory containing poster images
        dry_run: If True, preview changes without applying

    Returns:
        Summary of changes made

    Raises:
        PlexShowNotFoundError: If show not found in library
    """
    show = client.get_show(library, show_name)
    if not show:
        raise PlexShowNotFoundError(
            f"Show '{show_name}' not found in library '{library}'"
        )

    results = {
        "show_changes": {},
        "seasons_updated": 0,
        "episodes_updated": 0,
        "posters_uploaded": 0,
        "errors": [],
    }

    # Update show metadata
    show_summary = (
        "One Pace is a fan project that re-edits the One Piece anime to more closely "
        "follow the pacing of the original manga by Eiichiro Oda."
    )

    if rename_show:
        results["show_changes"] = client.update_show_metadata(
            show,
            title="One Pace",
            summary=show_summary,
            dry_run=dry_run,
        )
    else:
        results["show_changes"] = client.update_show_metadata(
            show,
            summary=show_summary,
            dry_run=dry_run,
        )

    # Upload show poster if available
    if poster_dir:
        # Look for show poster (e.g., "one-pace.jpg" or "show.jpg")
        show_poster = find_poster_for_arc("one-pace", poster_dir)
        if show_poster and client.upload_poster(show, show_poster, dry_run=dry_run):
            results["posters_uploaded"] += 1

    # Build arc slug to arc mapping for matching seasons
    arc_by_index = {i: arc for i, arc in enumerate(arcs, start=1)}

    # Process each season
    for season in show.seasons():
        season_num = season.seasonNumber

        # Skip season 0 (specials)
        if season_num == 0:
            continue

        arc = arc_by_index.get(season_num)
        if not arc:
            results["errors"].append(f"No arc found for season {season_num}")
            continue

        # Update season metadata
        season_title = build_season_title(arc, season_num)
        season_changes = client.update_season_metadata(
            season,
            title=season_title,
            summary=arc.description,
            dry_run=dry_run,
        )
        if season_changes:
            results["seasons_updated"] += 1

        # Upload season poster if available
        if poster_dir:
            season_poster = find_poster_for_arc(arc.slug, poster_dir)
            if season_poster and client.upload_poster(
                season, season_poster, dry_run=dry_run
            ):
                results["posters_uploaded"] += 1

        # Process episodes in this season
        for episode in season.episodes():
            episode_num = episode.episodeNumber
            episode_title = build_episode_title(arc, episode_num)

            episode_changes = client.update_episode_metadata(
                episode,
                title=episode_title,
                summary=arc.description,
                dry_run=dry_run,
            )
            if episode_changes:
                results["episodes_updated"] += 1

    return results
