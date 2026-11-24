"""VBAN audio wire format, independent of Music Assistant and third-party libraries.

Reference: https://vb-audio.com/Voicemeeter/VBANProtocol_Specifications.pdf
"""

from __future__ import annotations

import ipaddress
import struct
from dataclasses import dataclass

SAMPLE_RATES = (
    6000,
    12000,
    24000,
    48000,
    96000,
    192000,
    384000,
    8000,
    16000,
    32000,
    64000,
    128000,
    256000,
    512000,
    11025,
    22050,
    44100,
    88200,
    176400,
    352800,
    705600,
)
HEADER = struct.Struct("<4sBBBB16sI")
MAX_PACKET_SIZE = 1464


@dataclass(frozen=True, slots=True)
class VBANConfig:
    """A single manually configured, IPv4 unicast VBAN audio stream."""

    host: str
    port: int = 6980
    stream_name: str = "MusicAssistant"
    sample_rate: int = 48000
    channels: int = 2
    bit_depth: int = 16
    packet_frames: int = 128

    def __post_init__(self) -> None:
        address = ipaddress.IPv4Address(self.host)
        if address.is_multicast or address.is_unspecified or str(address) == "255.255.255.255":
            raise ValueError("VBAN receiver must have a unicast IPv4 address")
        if not 1 <= self.port <= 65535:
            raise ValueError("UDP port must be between 1 and 65535")
        try:
            name = self.stream_name.encode("ascii")
        except UnicodeEncodeError as err:
            raise ValueError("VBAN stream name must use ASCII characters") from err
        if not 1 <= len(name) <= 16 or any(byte < 32 or byte > 126 for byte in name):
            raise ValueError("VBAN stream name must contain 1 to 16 printable ASCII characters")
        if self.sample_rate not in SAMPLE_RATES:
            raise ValueError("Unsupported VBAN sample rate")
        if self.channels not in (1, 2):
            raise ValueError("Only mono and stereo streams are supported")
        if self.bit_depth not in (16, 24):
            raise ValueError("Only signed 16-bit and 24-bit PCM are supported")
        if not 1 <= self.packet_frames <= 256:
            raise ValueError("Packet size must be between 1 and 256 audio frames")

    @property
    def frame_bytes(self) -> int:
        """Bytes in one interleaved sample frame."""
        return self.channels * (self.bit_depth // 8)

    @property
    def frames_per_packet(self) -> int:
        """Stay within the VBAN packet limit, including for 24-bit stereo."""
        return min(self.packet_frames, (MAX_PACKET_SIZE - HEADER.size) // self.frame_bytes)

    @property
    def packet_bytes(self) -> int:
        """Maximum PCM payload size."""
        return self.frames_per_packet * self.frame_bytes


def encode_packet(config: VBANConfig, pcm: bytes, counter: int) -> bytes:
    """Encode aligned little-endian PCM; the VBAN counts are zero-based."""
    frames, remainder = divmod(len(pcm), config.frame_bytes)
    if remainder or not 1 <= frames <= config.frames_per_packet:
        raise ValueError("PCM payload must contain complete frames within the packet limit")
    return (
        HEADER.pack(
            b"VBAN",
            SAMPLE_RATES.index(config.sample_rate),  # protocol AUDIO = 0, codec PCM = 0
            frames - 1,
            config.channels - 1,
            1 if config.bit_depth == 16 else 2,
            config.stream_name.encode("ascii").ljust(16, b"\0"),
            counter & 0xFFFFFFFF,
        )
        + pcm
    )
