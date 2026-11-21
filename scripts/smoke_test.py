"""Integration check inside the MA image, with temporary data and loopback UDP only.

Run with --network none and without mounting any Music Assistant data directory.
The actual MA controllers, provider loader, Player base and FFmpeg are exercised.
"""

from __future__ import annotations

import asyncio
import logging
import math
import socket
import struct
import tempfile
import wave
from pathlib import Path
from unittest.mock import patch

from music_assistant.mass import MusicAssistant
from music_assistant_models.enums import EventType, PlaybackState
from music_assistant_models.player import PlayerMedia
from zeroconf import IPVersion

from music_assistant.providers.vban.player import VBANPlayer


async def receive(sock: socket.socket, count: int) -> list[bytes]:
    loop = asyncio.get_running_loop()
    packets = []
    for _ in range(count):
        packet, _ = await loop.sock_recvfrom(sock, 2048)
        packets.append(packet)
    return packets


async def check_player(mass: MusicAssistant, wav_path: Path, bits: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.setblocking(False)
        config = await mass.config._create_provider_instance(
            "vban",
            {},
            setup_data={
                "host": "127.0.0.1",
                "port": sock.getsockname()[1],
                "bit_depth": bits,
                "stream_name": f"Smoke{bits}",
            },
        )
        player_id = f"vban_{config.instance_id}"
        ready = asyncio.Event()
        unsubscribe = mass.subscribe(
            lambda _: ready.set(), event_filter=EventType.PLAYER_ADDED, id_filter=player_id
        )
        try:
            if mass.players.get_player(player_id) is None:
                await asyncio.wait_for(ready.wait(), 10)
            player = mass.players.get_player(player_id)
        finally:
            unsubscribe()
        assert isinstance(player, VBANPlayer), "Provider did not register its native Player"
        await player.initialized.wait()
        assert player.requires_flow_mode
        await player.volume_set(50)
        packet_count = math.ceil(4800 / 128)
        reader = asyncio.create_task(receive(sock, packet_count))
        try:
            await player.play_media(PlayerMedia(uri=str(wav_path), title="Loopback smoke test"))
            await asyncio.wait_for(player._stream_task, 20)
            packets = await asyncio.wait_for(reader, 5)
            assert "last_error" not in player.extra_attributes, player.extra_attributes
            assert player.playback_state == PlaybackState.IDLE
            assert len(packets) == packet_count
            assert all(p[:4] == b"VBAN" and p[7] == (1 if bits == 16 else 2) for p in packets)
            payload = b"".join(p[28:] for p in packets)
            assert len(payload) == 4800 * 2 * (bits // 8)
            width = bits // 8
            samples = [
                int.from_bytes(payload[i : i + width], "little", signed=True)
                for i in range(0, len(payload), width)
            ]
            expected = 500 * (1 if bits == 16 else 256)
            assert max(samples) == expected and min(samples) == -expected
            await player.volume_mute(True)
            assert player._sender.gain == 0
            await player.volume_mute(False)
            assert player._sender.gain == 0.5
            await player.stop()
            assert player.current_media is None
            await mass.unload_provider(config.instance_id)
            assert mass.players.get_player(player_id) is None
            print(
                f"PASS: real MA provider loading, Player, FFmpeg, {bits}-bit PCM, "
                "volume, UDP, unload"
            )
        finally:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)


async def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    for handler in logging.getLogger().handlers:
        handler.setLevel(logging.WARNING)
    with tempfile.TemporaryDirectory(prefix="ma-vban-smoke-") as directory:
        root = Path(directory)
        wav_path = root / "source.wav"
        with wave.open(str(wav_path), "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(48000)
            wav.writeframes(struct.pack("<hh", 1000, -1000) * 4800)
        cache = root / "cache"
        cache.mkdir()
        mass = MusicAssistant(str(root), str(cache), safe_mode=True)
        try:
            # A --network none sandbox has no multicast-capable default adapter.
            # Limit discovery to IPv4 loopback; audio still uses the real stack.
            with patch(
                "music_assistant.controllers.discovery.controller.get_zeroconf_args",
                return_value={"ip_version": IPVersion.V4Only, "interfaces": ["127.0.0.1"]},
            ):
                await asyncio.wait_for(mass.start(), 60)
            manifest = mass.get_provider_manifest("vban")
            assert manifest.has_setup_flow, "Native setup flow was not detected"
            await check_player(mass, wav_path, 16)
            await check_player(mass, wav_path, 24)
        finally:
            await mass.stop()


if __name__ == "__main__":
    asyncio.run(main())
