"""Integration check inside the MA image, with temporary data and loopback UDP only.

Run with --network none and without mounting any Music Assistant data directory.
The actual MA controllers, provider loader, Player base and FFmpeg are exercised.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import logging
import math
import os
import socket
import struct
import tempfile
import wave
from pathlib import Path
from unittest.mock import AsyncMock, patch

from music_assistant.mass import MusicAssistant
from music_assistant_models.enums import EventType, PlaybackState
from music_assistant_models.player import PlayerMedia
from zeroconf import IPVersion


async def receive(sock: socket.socket, count: int) -> list[bytes]:
    loop = asyncio.get_running_loop()
    packets = []
    for _ in range(count):
        packet, _ = await loop.sock_recvfrom(sock, 2048)
        packets.append(packet)
    return packets


async def check_player(
    mass: MusicAssistant, wav_path: Path, long_wav_path: Path, bits: int
) -> None:
    # The community loader registers its import location during server boot.
    from music_assistant.providers.vban.audio import volume_to_gain
    from music_assistant.providers.vban.player import LEGACY_PLAYER_API, VBANPlayer

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
        unsubscribe = mass.subscribe(lambda _: ready.set(), event_filter=EventType.PLAYER_ADDED)

        def get_output():
            if LEGACY_PLAYER_API:
                protocol = mass.players.get_player(player_id)
                return protocol, protocol
            protocol = mass.players.get_protocol(player_id)
            return protocol, protocol.player if protocol is not None else None

        try:
            player, output = get_output()
            if output is None:
                await asyncio.wait_for(ready.wait(), 10)
                player, output = get_output()
        finally:
            unsubscribe()
        assert isinstance(player, VBANPlayer), "Provider did not register its native Player"
        assert output is not None
        output_id = output.player_id
        if LEGACY_PLAYER_API:
            await output.initialized.wait()
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
            full_scale = 1000 * (1 if bits == 16 else 256)
            expected = int(full_scale * volume_to_gain(50))
            assert max(samples) == expected and min(samples) == -expected
            await player.volume_mute(True)
            assert player._sender.gain == 0
            await player.volume_mute(False)
            assert player._sender.gain == volume_to_gain(50)
            await player.stop()
            assert player.current_media is None
            # Unload while a second FFmpeg/UDP stream is active, not just after EOF.
            reader = asyncio.create_task(receive(sock, 1))
            await player.play_media(
                PlayerMedia(uri=str(long_wav_path), title="Live volume and unload test")
            )
            await asyncio.wait_for(reader, 10)
            assert player._stream_task is not None and not player._stream_task.done()
            stream_task = player._stream_task

            async def expect_level(level: int) -> None:
                async with asyncio.timeout(5):
                    while True:
                        packet, _ = await asyncio.get_running_loop().sock_recvfrom(sock, 2048)
                        samples = [
                            int.from_bytes(packet[i : i + width], "little", signed=True)
                            for i in range(28, len(packet), width)
                        ]
                        if max(samples) == level and min(samples) == -level:
                            return

            # Exercise actual PCM during the same running FFmpeg/UDP stream.
            await player.volume_set(75)
            await expect_level(int(full_scale * volume_to_gain(75)))
            await player.volume_mute(True)
            await expect_level(0)
            await player.volume_set(25)
            await expect_level(0)
            await player.volume_mute(False)
            await expect_level(int(full_scale * volume_to_gain(25)))
            await player.volume_set(100)
            await expect_level(full_scale)
            assert player._stream_task is stream_task
            await mass.unload_provider(config.instance_id)
            if LEGACY_PLAYER_API:
                assert mass.players.get_player(output_id) is None
            else:
                remaining = mass.players.get_protocol(player_id)
                assert remaining is None or remaining.player is None
                assert not output.available
            assert player._stream_task is None
            print(
                f"PASS: real MA provider loading, Player, FFmpeg, {bits}-bit PCM, "
                "volume, UDP, unload"
            )
        finally:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)


async def main() -> None:
    print(f"Music Assistant {importlib.metadata.version('music-assistant')}", flush=True)
    logging.basicConfig(level=logging.WARNING)
    for handler in logging.getLogger().handlers:
        handler.setLevel(logging.WARNING)
    with tempfile.TemporaryDirectory(prefix="ma-vban-smoke-") as directory:
        root = Path(directory)
        wav_path = root / "source.wav"
        long_wav_path = root / "long.wav"
        for path, frames in ((wav_path, 4800), (long_wav_path, 480000)):
            with wave.open(str(path), "wb") as wav:
                wav.setnchannels(2)
                wav.setsampwidth(2)
                wav.setframerate(48000)
                wav.writeframes(struct.pack("<hh", 1000, -1000) * frames)
        cache = root / "cache"
        cache.mkdir()
        provider_root = os.environ.get("VBAN_PROVIDER_ROOT")
        if provider_root:
            mass = MusicAssistant(
                str(root), str(cache), safe_mode=False, dev_providers_path=provider_root
            )
            mass.dev_mode = True
        else:
            mass = MusicAssistant(str(root), str(cache), safe_mode=True)
        try:
            # A --network none sandbox has no multicast-capable default adapter.
            # Limit discovery to IPv4 loopback; audio still uses the real stack.
            with (
                patch(
                    "music_assistant.controllers.discovery.controller.get_zeroconf_args",
                    return_value={"ip_version": IPVersion.V4Only, "interfaces": ["127.0.0.1"]},
                ),
                # Do not auto-discover device providers in the isolated test.
                patch.object(mass, "_load_providers", new=AsyncMock()),
            ):
                await asyncio.wait_for(mass.start(), 60)
            if provider_root:
                for task in list(mass._tracked_tasks.values()):
                    if task.get_name() == "community_catalog_start":
                        await asyncio.wait_for(task, 30)
            manifest = mass.get_provider_manifest("vban")
            assert manifest.has_setup_flow, "Native setup flow was not detected"
            if provider_root:
                assert manifest.tier.value == "community", manifest.tier
                print("PASS: provider discovered by the native community loader")
            await check_player(mass, wav_path, long_wav_path, 16)
            await check_player(mass, wav_path, long_wav_path, 24)
        finally:
            await mass.stop()


if __name__ == "__main__":
    asyncio.run(main())
