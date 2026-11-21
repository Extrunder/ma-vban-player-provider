"""Music Assistant player-provider lifecycle."""

from __future__ import annotations

from music_assistant.models.player_provider import PlayerProvider
from music_assistant_models.config_entries import ConfigEntry
from music_assistant_models.errors import SetupFailedError

from .player import VBANPlayer
from .protocol import VBANConfig


class VBANProvider(PlayerProvider):
    """Each provider instance owns one receiver with a stable player ID."""

    async def get_config_entries(self) -> tuple[ConfigEntry, ...]:
        # Connection/audio settings live in setup_data and are edited through
        # the native Reconfigure flow, without conflicting option overrides.
        return ()

    async def handle_async_init(self) -> None:
        try:
            self.vban_config = VBANConfig(
                host=str(self.get_setup_value("host", "")),
                port=int(self.get_setup_value("port", 6980)),
                stream_name=str(self.get_setup_value("stream_name", "MusicAssistant")),
                sample_rate=int(self.get_setup_value("sample_rate", 48000)),
                channels=int(self.get_setup_value("channels", 2)),
                bit_depth=int(self.get_setup_value("bit_depth", 16)),
                packet_frames=int(self.get_setup_value("packet_frames", 128)),
            )
        except (TypeError, ValueError) as err:
            raise SetupFailedError(f"Invalid VBAN configuration: {err}") from err

    async def discover_players(self) -> None:
        player_id = f"vban_{self.instance_id}"
        if not self.mass.players.get_player(player_id):
            await self.mass.players.register(VBANPlayer(self, player_id, self.vban_config))
