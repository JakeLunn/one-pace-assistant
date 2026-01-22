"""Tests for the plex module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from onepace_assistant.models import Arc
from onepace_assistant.plex import (
    PlexClient,
    PlexConnectionError,
    PlexShowNotFoundError,
    build_episode_title,
    build_season_title,
    update_plex_metadata,
)


class TestPlexClient:
    """Tests for PlexClient class."""

    def test_init_connection_error_invalid_token(self):
        """Test that invalid token raises PlexConnectionError."""
        with patch("onepace_assistant.plex.PlexServer") as mock_server:
            from plexapi.exceptions import Unauthorized

            mock_server.side_effect = Unauthorized("Invalid token")

            with pytest.raises(PlexConnectionError) as exc_info:
                PlexClient("http://localhost:32400", "bad_token")

            assert "Invalid Plex token" in str(exc_info.value)

    def test_init_connection_error_generic(self):
        """Test that connection failures raise PlexConnectionError."""
        with patch("onepace_assistant.plex.PlexServer") as mock_server:
            mock_server.side_effect = ConnectionError("Cannot connect")

            with pytest.raises(PlexConnectionError) as exc_info:
                PlexClient("http://localhost:32400", "token")

            assert "Failed to connect" in str(exc_info.value)

    def test_init_success(self):
        """Test successful client initialization."""
        with patch("onepace_assistant.plex.PlexServer") as mock_server:
            mock_server.return_value = MagicMock()
            client = PlexClient("http://localhost:32400", "valid_token")
            assert client.server is not None

    def test_get_show_found(self):
        """Test getting a show that exists."""
        with patch("onepace_assistant.plex.PlexServer") as mock_server:
            mock_plex = MagicMock()
            mock_show = MagicMock()
            mock_show.title = "One Piece"
            mock_plex.library.section.return_value.searchShows.return_value = [mock_show]
            mock_server.return_value = mock_plex

            client = PlexClient("http://localhost:32400", "token")
            result = client.get_show("TV", "One Piece")

            assert result == mock_show

    def test_get_show_not_found(self):
        """Test getting a show that doesn't exist."""
        with patch("onepace_assistant.plex.PlexServer") as mock_server:
            mock_plex = MagicMock()
            mock_plex.library.section.return_value.searchShows.return_value = []
            mock_server.return_value = mock_plex

            client = PlexClient("http://localhost:32400", "token")
            result = client.get_show("TV", "Nonexistent Show")

            assert result is None

    def test_get_show_library_not_found(self):
        """Test getting a show from non-existent library."""
        with patch("onepace_assistant.plex.PlexServer") as mock_server:
            from plexapi.exceptions import NotFound

            mock_plex = MagicMock()
            mock_plex.library.section.side_effect = NotFound("Library not found")
            mock_server.return_value = mock_plex

            client = PlexClient("http://localhost:32400", "token")

            with pytest.raises(PlexConnectionError) as exc_info:
                client.get_show("NonexistentLibrary", "Show")

            assert "not found" in str(exc_info.value)


class TestUpdateShowMetadata:
    """Tests for update_show_metadata method."""

    def test_update_title_when_different(self):
        """Test that title is updated when different."""
        with patch("onepace_assistant.plex.PlexServer") as mock_server:
            mock_plex = MagicMock()
            mock_server.return_value = mock_plex

            mock_show = MagicMock()
            mock_show.title = "One Piece"
            mock_show.summary = ""

            client = PlexClient("http://localhost:32400", "token")
            changes = client.update_show_metadata(mock_show, title="One Pace")

            assert "title" in changes
            assert changes["title"] == "One Pace"
            mock_show.edit.assert_called()

    def test_no_update_when_same_title(self):
        """Test that no update happens when title is the same."""
        with patch("onepace_assistant.plex.PlexServer") as mock_server:
            mock_plex = MagicMock()
            mock_server.return_value = mock_plex

            mock_show = MagicMock()
            mock_show.title = "One Pace"
            mock_show.summary = "Existing summary"

            client = PlexClient("http://localhost:32400", "token")
            changes = client.update_show_metadata(mock_show, title="One Pace")

            assert "title" not in changes

    def test_dry_run_returns_changes_without_applying(self):
        """Test that dry_run returns changes without calling edit."""
        with patch("onepace_assistant.plex.PlexServer") as mock_server:
            mock_plex = MagicMock()
            mock_server.return_value = mock_plex

            mock_show = MagicMock()
            mock_show.title = "One Piece"
            mock_show.summary = ""

            client = PlexClient("http://localhost:32400", "token")
            changes = client.update_show_metadata(
                mock_show, title="One Pace", dry_run=True
            )

            assert "title" in changes
            mock_show.edit.assert_not_called()


class TestUpdateSeasonMetadata:
    """Tests for update_season_metadata method."""

    def test_update_season_title(self):
        """Test updating season title."""
        with patch("onepace_assistant.plex.PlexServer") as mock_server:
            mock_plex = MagicMock()
            mock_server.return_value = mock_plex

            mock_season = MagicMock()
            mock_season.title = "Season 1"
            mock_season.summary = ""

            client = PlexClient("http://localhost:32400", "token")
            changes = client.update_season_metadata(
                mock_season, title="01 - Romance Dawn", summary="The story begins..."
            )

            assert "title" in changes
            assert "summary" in changes
            mock_season.edit.assert_called()


class TestUpdateEpisodeMetadata:
    """Tests for update_episode_metadata method."""

    def test_update_episode_title(self):
        """Test updating episode title."""
        with patch("onepace_assistant.plex.PlexServer") as mock_server:
            mock_plex = MagicMock()
            mock_server.return_value = mock_plex

            mock_episode = MagicMock()
            mock_episode.title = "Episode 1"
            mock_episode.summary = ""

            client = PlexClient("http://localhost:32400", "token")
            changes = client.update_episode_metadata(
                mock_episode, title="Romance Dawn 01", summary="Luffy sets sail..."
            )

            assert "title" in changes
            mock_episode.edit.assert_called()


class TestBuildTitles:
    """Tests for title building functions."""

    @pytest.fixture
    def sample_arc(self) -> Arc:
        """Create a sample arc for testing."""
        return Arc(
            slug="romance-dawn",
            title="Romance Dawn",
            description="The start of Luffy's adventure",
            special=False,
            chapters="1-7",
            episodes="1-3",
        )

    def test_build_season_title(self, sample_arc: Arc):
        """Test building season title."""
        result = build_season_title(sample_arc, 1)
        assert result == "01 - Romance Dawn"

    def test_build_season_title_double_digit(self, sample_arc: Arc):
        """Test building season title with double digit number."""
        result = build_season_title(sample_arc, 15)
        assert result == "15 - Romance Dawn"

    def test_build_episode_title(self, sample_arc: Arc):
        """Test building episode title."""
        result = build_episode_title(sample_arc, 1)
        assert result == "Romance Dawn 01"

    def test_build_episode_title_double_digit(self, sample_arc: Arc):
        """Test building episode title with double digit number."""
        result = build_episode_title(sample_arc, 12)
        assert result == "Romance Dawn 12"


class TestUpdatePlexMetadata:
    """Tests for the update_plex_metadata function."""

    @pytest.fixture
    def sample_arcs(self) -> list[Arc]:
        """Create sample arcs for testing."""
        return [
            Arc(
                slug="romance-dawn",
                title="Romance Dawn",
                description="The start of Luffy's adventure",
                special=False,
            ),
            Arc(
                slug="orange-town",
                title="Orange Town",
                description="Buggy the Clown appears",
                special=False,
            ),
        ]

    def test_show_not_found_raises_error(self, sample_arcs: list[Arc]):
        """Test that PlexShowNotFoundError is raised when show not found."""
        with patch("onepace_assistant.plex.PlexServer"):
            mock_client = MagicMock(spec=PlexClient)
            mock_client.get_show.return_value = None

            with pytest.raises(PlexShowNotFoundError):
                update_plex_metadata(
                    client=mock_client,
                    arcs=sample_arcs,
                    library="TV",
                    show_name="One Piece",
                )

    def test_updates_show_metadata(self, sample_arcs: list[Arc]):
        """Test that show metadata is updated."""
        mock_client = MagicMock(spec=PlexClient)
        mock_show = MagicMock()
        mock_show.seasons.return_value = []
        mock_client.get_show.return_value = mock_show
        mock_client.update_show_metadata.return_value = {"summary": "updated"}

        results = update_plex_metadata(
            client=mock_client,
            arcs=sample_arcs,
            library="TV",
            show_name="One Piece",
            rename_show=False,
        )

        mock_client.update_show_metadata.assert_called_once()
        assert "show_changes" in results

    def test_updates_seasons_and_episodes(self, sample_arcs: list[Arc]):
        """Test that seasons and episodes are updated."""
        mock_client = MagicMock(spec=PlexClient)

        # Create mock show with seasons and episodes
        mock_show = MagicMock()
        mock_season = MagicMock()
        mock_season.seasonNumber = 1
        mock_episode = MagicMock()
        mock_episode.episodeNumber = 1
        mock_season.episodes.return_value = [mock_episode]
        mock_show.seasons.return_value = [mock_season]

        mock_client.get_show.return_value = mock_show
        mock_client.update_show_metadata.return_value = {}
        mock_client.update_season_metadata.return_value = {"title": "updated"}
        mock_client.update_episode_metadata.return_value = {"title": "updated"}

        results = update_plex_metadata(
            client=mock_client,
            arcs=sample_arcs,
            library="TV",
            show_name="One Piece",
        )

        assert results["seasons_updated"] == 1
        assert results["episodes_updated"] == 1
