"""Bounded native PCM attenuation and the player's software volume curve."""

from __future__ import annotations

import math

# NumPy is a core Music Assistant dependency, not an extra provider requirement.
import numpy as np

VOLUME_RANGE_DB = 60.0


def volume_to_gain(volume: int) -> float:
    """Map 1..100 to -59.4..0 dB in equal dB steps; zero is digital silence."""
    volume = max(0, min(100, volume))
    if volume == 0:
        return 0.0
    return 10 ** ((volume - 100) * VOLUME_RANGE_DB / 100 / 20)


def apply_gain(pcm: bytes, bit_depth: int, gain: float) -> bytes:
    """Attenuate one PCM packet using native array operations, never a sample loop.

    The sender bounds input to at most 256 frames / 512 samples. Unity is a
    zero-copy bypass and mute only allocates zero bytes. Intermediate gain uses
    float64 and truncates toward zero to preserve signed 16/24-bit PCM exactly.
    """
    if bit_depth not in (16, 24) or len(pcm) % (bit_depth // 8):
        raise ValueError("Unaligned or unsupported PCM samples")
    if not math.isfinite(gain):
        raise ValueError("PCM gain must be finite")
    if gain >= 1.0 or not pcm:
        return pcm
    if gain <= 0.0:
        return bytes(len(pcm))
    if bit_depth == 16:
        samples = np.frombuffer(pcm, dtype="<i2")
        return (samples * gain).astype("<i2").tobytes()

    # Unpack little-endian s24 into s32, then sign-extend the high PCM bit.
    packed = np.frombuffer(pcm, dtype=np.uint8).reshape(-1, 3)
    padded = np.zeros((len(packed), 4), dtype=np.uint8)
    padded[:, :3] = packed
    samples = padded.view("<i4").reshape(-1)
    samples <<= 8
    samples >>= 8
    scaled = (samples * gain).astype("<i4")
    return scaled.view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
