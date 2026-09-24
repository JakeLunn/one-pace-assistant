"""Data models for One Pace metadata."""

from pydantic import AliasChoices, BaseModel, Field


class Playlist(BaseModel):
    """A download playlist for a specific resolution."""

    id: str = Field(description="PixelDrain playlist ID")
    resolution: int = Field(description="Video resolution (480, 720, 1080)")


class PlayGroup(BaseModel):
    """A group of playlists with specific language settings."""

    sub: str | None = Field(default=None, description="Subtitle language code")
    dub: str = Field(description="Audio/dub language code")
    variant: str | None = Field(default=None, description="Variant type (e.g., 'extended')")
    variant_title: str | None = Field(
        default=None, alias="variantTitle", description="Display name for variant"
    )
    # onepace.net renamed this key from "playlists" to "items"; accept both.
    playlists: list[Playlist] = Field(
        default_factory=list,
        validation_alias=AliasChoices("playlists", "items"),
    )


class Backdrop(BaseModel):
    """Arc backdrop image metadata."""

    src: str = Field(description="Image source path")
    width: int
    height: int


class Arc(BaseModel):
    """A One Pace arc containing episodes."""

    slug: str = Field(description="URL-friendly identifier")
    title: str = Field(description="Display title")
    description: str | None = Field(default=None)
    special: bool = Field(default=False, description="Whether this is a special/side story")
    chapters: str | None = Field(default=None, description="Manga chapter range")
    episodes: str | None = Field(default=None, description="Anime episode range")
    backdrops: list[Backdrop] = Field(default_factory=list)
    play_groups: list[PlayGroup] = Field(default_factory=list, alias="playGroups")

    def get_playlist(
        self,
        resolution: int = 1080,
        sub: str | None = "en",
        dub: str = "ja",
        variant: str | None = None,
    ) -> Playlist | None:
        """Find a playlist matching the given criteria."""
        for group in self.play_groups:
            # Match language preferences
            sub_match = (sub is None and group.sub is None) or group.sub == sub
            dub_match = group.dub == dub
            variant_match = group.variant == variant

            if sub_match and dub_match and variant_match:
                # Find matching resolution
                for playlist in group.playlists:
                    if playlist.resolution == resolution:
                        return playlist
                # Fallback to highest available resolution
                if group.playlists:
                    return max(group.playlists, key=lambda p: p.resolution)

        return None

    def available_resolutions(self) -> set[int]:
        """Get all available resolutions for this arc."""
        resolutions = set()
        for group in self.play_groups:
            for playlist in group.playlists:
                resolutions.add(playlist.resolution)
        return resolutions

    def available_languages(self) -> list[dict[str, str | None]]:
        """Get all available language combinations."""
        return [
            {"sub": g.sub, "dub": g.dub, "variant": g.variant}
            for g in self.play_groups
        ]


class PixelDrainFile(BaseModel):
    """A file in a PixelDrain list."""

    id: str = Field(description="File ID for download URL")
    name: str = Field(description="Original filename")
    size: int = Field(description="File size in bytes")


class PixelDrainList(BaseModel):
    """Metadata for a PixelDrain file list."""

    id: str
    title: str
    download_href: str | None = Field(default=None, description="Direct URL for zip download")
    files: list[PixelDrainFile] = Field(default_factory=list)
