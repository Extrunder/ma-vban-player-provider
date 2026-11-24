"""Bounded, paced UDP transmission of async PCM sources."""

from __future__ import annotations

import asyncio
import socket
from collections.abc import AsyncGenerator, Callable
from contextlib import aclosing

from .audio import apply_gain
from .protocol import VBANConfig, encode_packet


class VBANSender:
    """One sender per player; callers must serialize run() invocations.

    UDP has no receiver acknowledgement. A successful send only confirms that
    the local OS accepted the packet, never that the receiver is online.
    """

    def __init__(self, config: VBANConfig) -> None:
        self.config = config
        self.counter = 0
        self.sent_frames = 0
        self.gain = 1.0
        self._playing = asyncio.Event()
        self._playing.set()
        self._timing_generation = 0

    def pause(self) -> None:
        """Suspend packets and source consumption at the next packet boundary."""
        self._playing.clear()
        self._timing_generation += 1

    def resume(self) -> None:
        """Resume with a fresh timing anchor, without a catch-up burst."""
        self._timing_generation += 1
        self._playing.set()

    async def run(
        self,
        source: AsyncGenerator[bytes],
        on_progress: Callable[[float], None] | None = None,
    ) -> None:
        """Consume PCM incrementally and send at the configured sample rate.

        Reassemble arbitrary source chunk boundaries and send a short final
        packet rather than padding the end with audible extra silence.
        Cancellation closes the source (and its FFmpeg pipeline) and socket.
        """
        loop = asyncio.get_running_loop()
        self.sent_frames = 0
        deadline = loop.time()
        timing_generation = self._timing_generation
        last_progress = deadline - 1
        pending = bytearray()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)

        async def send(pcm: bytes) -> None:
            nonlocal deadline, timing_generation, last_progress
            await self._playing.wait()
            now = loop.time()
            if timing_generation != self._timing_generation or now - deadline > 0.05:
                deadline = now
                timing_generation = self._timing_generation
            await asyncio.sleep(max(0.0, deadline - now))
            await self._playing.wait()
            if timing_generation != self._timing_generation:
                deadline = loop.time()
                timing_generation = self._timing_generation
            payload = apply_gain(pcm, self.config.bit_depth, self.gain)
            await loop.sock_sendall(sock, encode_packet(self.config, payload, self.counter))
            self.counter = (self.counter + 1) & 0xFFFFFFFF
            frames = len(pcm) // self.config.frame_bytes
            self.sent_frames += frames
            deadline += frames / self.config.sample_rate
            now = loop.time()
            if on_progress and now - last_progress >= 1:
                on_progress(self.sent_frames / self.config.sample_rate)
                last_progress = now

        try:
            # Closing the source also covers connection/setup failures.
            async with aclosing(source):
                await loop.sock_connect(sock, (self.config.host, self.config.port))
                while True:
                    await self._playing.wait()
                    try:
                        chunk = await anext(source)
                    except StopAsyncIteration:
                        break
                    # Process a large upstream chunk without copying it all into pending.
                    view = memoryview(chunk)
                    offset = 0
                    while offset < len(view):
                        take = min(self.config.packet_bytes - len(pending), len(view) - offset)
                        pending.extend(view[offset : offset + take])
                        offset += take
                        if len(pending) < self.config.packet_bytes:
                            continue
                        await send(bytes(pending))
                        pending.clear()
                if len(pending) % self.config.frame_bytes:
                    raise ValueError("PCM source ended in the middle of an audio frame")
                if pending:
                    await send(bytes(pending))
                # Do not mark playback finished until the final packet has played out.
                await asyncio.sleep(max(0.0, deadline - loop.time()))
                if on_progress:
                    on_progress(self.sent_frames / self.config.sample_rate)
        finally:
            sock.close()
