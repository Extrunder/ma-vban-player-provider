"""Native Music Assistant player backed by a paced VBAN sender."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import aclosing, suppress
from typing import TYPE_CHECKING

from music_assistant.helpers.ffmpeg import get_ffmpeg_stream
from music_assistant_models.enums import ContentType, IdentifierType, PlaybackState, PlayerFeature
from music_assistant_models.media_items import AudioFormat
from music_assistant_models.player import DeviceInfo, PlayerMedia

from .protocol import VBANConfig
from .sender import VBANSender

try:
    from music_assistant.models.player_protocol import PlayerProtocol as PlayerBase
except ModuleNotFoundError as err:
    if err.name != "music_assistant.models.player_protocol":
        raise
    from music_assistant.models.player import Player as PlayerBase

    LEGACY_PLAYER_API = True
else:
    LEGACY_PLAYER_API = False

if TYPE_CHECKING:
    from .provider import VBANProvider


class VBANPlayer(PlayerBase):
    """Output-only receiver; reported availability means configured, not acknowledged."""

    def __init__(self, provider: VBANProvider, player_id: str, config: VBANConfig) -> None:
        super().__init__(provider, player_id)
        self._attr_name = f"VBAN {config.stream_name}"
        self._attr_supported_features = {
            PlayerFeature.PLAY_MEDIA,
            PlayerFeature.PAUSE,
            PlayerFeature.VOLUME_SET,
            PlayerFeature.VOLUME_MUTE,
        }
        self._attr_device_info = DeviceInfo(
            model="VBAN receiver", manufacturer="VB-Audio compatible"
        )
        self._attr_device_info.add_identifier(IdentifierType.IP_ADDRESS, config.host)
        self._attr_supported_sample_rates = [(config.sample_rate, config.bit_depth)]
        self._attr_volume_level = 100
        self._attr_volume_muted = False
        self._sender = VBANSender(config)
        self._stream_task: asyncio.Task[None] | None = None
        self._command_lock = asyncio.Lock()
        self._format = AudioFormat(
            content_type=ContentType.PCM_S16LE if config.bit_depth == 16 else ContentType.PCM_S24LE,
            sample_rate=config.sample_rate,
            bit_depth=config.bit_depth,
            channels=config.channels,
        )
        self._extra_attributes["receiver_status"] = "unconfirmed (UDP has no acknowledgement)"

    @property
    def output_player_id(self) -> str:
        """Resolve the user-visible player when the modern protocol API is in use."""
        if LEGACY_PLAYER_API:
            return self.player_id
        return self.player.player_id if self.player is not None else self.protocol_id

    @property
    def requires_flow_mode(self) -> bool:
        """Keep tracks, crossfades and queue transitions in one PCM stream."""
        return True

    async def play_media(self, media: PlayerMedia) -> None:
        async with self._command_lock:
            await self._stop_stream()
            self._attr_current_media = media
            self._attr_active_source = media.source_id
            self._attr_elapsed_time = 0
            self._attr_elapsed_time_last_updated = time.time()
            self._extra_attributes.pop("last_error", None)
            self._sender.resume()
            self._attr_playback_state = PlaybackState.PLAYING
            self.update_state()
            self._stream_task = asyncio.create_task(
                self._stream(media), name=f"vban_stream_{self.output_player_id}"
            )

    async def _stream(self, media: PlayerMedia) -> None:
        try:
            await self._sender.run(self._audio_source(media), self._on_progress)
        except asyncio.CancelledError:
            raise
        except Exception as err:
            self._extra_attributes["last_error"] = str(err)
            self.logger.exception("VBAN playback failed for %s", self.output_player_id)
        finally:
            self._attr_playback_state = PlaybackState.IDLE
            self._attr_elapsed_time = self._sender.sent_frames / self._format.sample_rate
            self._attr_elapsed_time_last_updated = time.time()
            if LEGACY_PLAYER_API or self.player is not None:
                self.update_state()

    async def _audio_source(self, media: PlayerMedia) -> AsyncGenerator[bytes]:
        source = self.mass.streams.get_stream(media, self._format, self.output_player_id)
        async with aclosing(source):
            # Match direct-PCM providers: get_stream selects/decodes media; the
            # output plan applies the player's DSP and channel filters once.
            plan = self.mass.streams.audio.get_player_output_plan(
                self.output_player_id, self._format, self._format, handoff_format=self._format
            )
            if plan.filter_params:
                filtered = get_ffmpeg_stream(
                    audio_input=source,
                    input_format=self._format,
                    output_format=self._format,
                    filter_params=plan.filter_params,
                    chunk_size=self._sender.config.packet_bytes,
                )
                async with aclosing(filtered):
                    async for chunk in filtered:
                        yield chunk
            else:
                async for chunk in source:
                    yield chunk

    def _on_progress(self, elapsed: float) -> None:
        self._attr_elapsed_time = elapsed
        self._attr_elapsed_time_last_updated = time.time()
        self.update_state()

    async def _stop_stream(self) -> None:
        task, self._stream_task = self._stream_task, None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def stop(self) -> None:
        async with self._command_lock:
            await self._stop_stream()
            self._attr_playback_state = PlaybackState.IDLE
            self._attr_current_media = None
            self._attr_active_source = None
            self._attr_elapsed_time = 0
            self._attr_elapsed_time_last_updated = time.time()
            self.update_state()

    async def pause(self) -> None:
        async with self._command_lock:
            if self._stream_task is not None and not self._stream_task.done():
                self._sender.pause()
                self._attr_elapsed_time = self._sender.sent_frames / self._format.sample_rate
                self._attr_elapsed_time_last_updated = time.time()
                self._attr_playback_state = PlaybackState.PAUSED
                self.update_state()

    async def play(self) -> None:
        async with self._command_lock:
            if self._stream_task is not None and not self._stream_task.done():
                self._sender.resume()
                self._attr_playback_state = PlaybackState.PLAYING
                self._attr_elapsed_time_last_updated = time.time()
                self.update_state()

    async def volume_set(self, volume_level: int) -> None:
        self._attr_volume_level = max(0, min(100, volume_level))
        self._update_gain()

    async def volume_mute(self, muted: bool) -> None:
        self._attr_volume_muted = muted
        self._update_gain()

    def _update_gain(self) -> None:
        self._sender.gain = 0 if self._attr_volume_muted else self._attr_volume_level / 100
        self.update_state()

    async def on_unload(self) -> None:
        await self.stop()
        if LEGACY_PLAYER_API:
            await super().on_unload()

    async def on_detach(self) -> None:
        """Release the stream when a modern protocol is disabled or unloaded."""
        await self._stop_stream()
        if not LEGACY_PLAYER_API:
            await super().on_detach()
