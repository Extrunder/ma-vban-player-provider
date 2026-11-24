"""Measure PCM attenuation CPU time per second of audio, without network or decoding.

Run from the repository root: python -m scripts.benchmark_gain --compare-scalar
This is a local measurement, not a timing assertion for CI or a Raspberry Pi result.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import math
import platform
import statistics
import time

from vban.audio import apply_gain


def scalar_reference(pcm: bytes, bits: int, gain: float) -> bytes:
    """The previous implementation, only for benchmark comparison."""
    width = bits // 8
    result = bytearray(len(pcm))
    for offset in range(0, len(pcm), width):
        sample = int.from_bytes(pcm[offset : offset + width], "little", signed=True)
        result[offset : offset + width] = int(sample * gain).to_bytes(width, "little", signed=True)
    return bytes(result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-seconds", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--compare-scalar", action="store_true")
    args = parser.parse_args()
    if args.audio_seconds < 1 or args.repeats < 1:
        parser.error("audio-seconds and repeats must be positive")
    print(
        f"{platform.system()}/{platform.machine()}, Python {platform.python_version()}, "
        f"NumPy {importlib.metadata.version('numpy')}"
    )
    print("128 frames/packet, stereo, gain 0.5; median CPU ms per second of audio per player")
    for bits, rate in ((16, 48000), (24, 96000)):
        width = bits // 8
        pcm = (-(2 ** (bits - 2))).to_bytes(width, "little", signed=True) * 256
        packets = math.ceil(rate * args.audio_seconds / 128)
        results = {}
        functions = {"native": apply_gain}
        if args.compare_scalar:
            functions["scalar"] = scalar_reference
        for label, function in functions.items():
            function(pcm, bits, 0.5)
            measurements = []
            for _ in range(args.repeats):
                started = time.process_time()
                for _ in range(packets):
                    function(pcm, bits, 0.5)
                measurements.append((time.process_time() - started) * 1000 / args.audio_seconds)
            results[label] = statistics.median(measurements)
        text = ", ".join(f"{label}={value:.3f}" for label, value in results.items())
        if "scalar" in results and results["native"]:
            text += f", speedup={results['scalar'] / results['native']:.1f}x"
        print(f"{bits}-bit/{rate} Hz: {text}")


if __name__ == "__main__":
    main()
