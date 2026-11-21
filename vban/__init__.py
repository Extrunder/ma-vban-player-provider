"""VBAN player community provider for Music Assistant."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from music_assistant.mass import MusicAssistant
    from music_assistant.models import ProviderInstanceType
    from music_assistant_models.config_entries import ProviderConfig
    from music_assistant_models.provider import ProviderManifest


async def setup(
    mass: MusicAssistant, manifest: ProviderManifest, config: ProviderConfig
) -> ProviderInstanceType:
    """Create an independently configured VBAN receiver/player."""
    from .provider import VBANProvider

    return VBANProvider(mass, manifest, config)
