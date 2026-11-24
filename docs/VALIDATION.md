# Validation

## 0.2.1 volume performance review fix

Checked on 2026-11-24:

- 79 unit tests pass with NumPy 2.3.5; Ruff lint and format pass.
- The official catalog checker reports `vban: passed` with no network access.
- Native community loading, FFmpeg, exact signed 16/24-bit UDP PCM, live volume changes,
  mute/change-volume/unmute, unity restoration and active unload pass in
  MA `2.11.0.dev2026112103`. The legacy MA `2.10.13` path passes the same audio checks.
- Volume changes keep the same stream task. Existing output-plan DSP remains in its
  FFmpeg stage; the player's final attenuation is applied once, at packet send time.

The Python sample loop was replaced with native NumPy array operations. The sender
still bounds each call to one VBAN packet, at most 256 frames / 512 samples. Unity
returns the original bytes and mute produces zero bytes without unpacking samples.
Float64 multiplication and truncation toward zero match the scalar reference, including
negative s24 values and full-scale endpoints. The wire-format module remains dependency-free.

NumPy is already a core dependency of both tested MA images (2.3.5). It is pinned only
in the local test environment; the provider needs no additional package installation.
The volume scale now has equal 0.6 dB steps: 1% is -59.4 dB, 50% is -30 dB, 100%
is unchanged and 0% is digital silence. This intentionally changes levels below 100%.

Reproduce the processing-only comparison from the repository root:

```sh
uv run python -m scripts.benchmark_gain --compare-scalar
```

Measured in the Linux/x86_64 MA container, Python 3.14.10, NumPy 2.3.5. The median of
five runs, each processing ten seconds of stereo audio at gain 0.5, 128 frames per packet:

| Format | Previous Python loop | Native NumPy | Speedup |
|---|---:|---:|---:|
| 16-bit / 48 kHz | 60.563 ms CPU/s audio | 1.232 ms CPU/s audio | 49.2x |
| 24-bit / 96 kHz | 122.269 ms CPU/s audio | 10.298 ms CPU/s audio | 11.9x |

These are processing costs per player on this host, not end-to-end playback CPU or
Raspberry Pi measurements. Absolute results vary by CPU and runtime; the script is a
measurement tool, not a CI timing threshold. No thread dispatch, IPC, extra audio buffer
or FFmpeg restart is introduced for volume changes.

## Original 0.2.0 checks

Checked on 2026-11-21. These results are local checks, not catalog admission or a public release.

| Check | Result |
|---|---|
| Unit/UDP/setup/release-metadata tests | 56 passed |
| Ruff lint and format | Passed |
| GitHub workflows: actionlint 1.7.12 | Passed |
| Official catalog `python -m registry ... check-folder .../vban` | `vban: passed` |
| Native community loading, MA `2.11.0.dev2026112103` | Passed, tier `community` |
| FFmpeg → 16-bit stereo PCM → loopback UDP, volume, active unload | Passed |
| FFmpeg → 24-bit stereo PCM → loopback UDP, volume, active unload | Passed |
| Legacy native loading/audio/unload, MA `2.10.13` | Passed (manual install only) |

Exact images used:

- Nightly: `ghcr.io/music-assistant/server@sha256:c502d4902efd1ed38fe864f40cc4528fca5830bfed68d8cba50cea6f6620f0a0`.
- Legacy 2.10.13: `ghcr.io/music-assistant/server@sha256:7510aaa7ee5fc85b34fd0de17992bd14473895b23ce3eb9b310092743f4dbb84`.
- Official catalog checker source: `music-assistant/community-catalog` commit
  `43fdb7eb0ae4d45a29303aa83ec76b8e4fbdcb56`.

The audio integration checks used temporary server data and `--network none`. Discovery
was limited to IPv4 loopback. Sendspin's own missing-multicast message in this sandbox
is expected and does not participate in the VBAN audio path.

Not established by these checks:

- Admission to the public registry, public repository metadata or a GitHub Actions run.
- Compatibility with every beta/stable or future Music Assistant release.
- Audio delivery from a Raspberry Pi to a physical VBAN device.

The provider has no additional Python/binary requirements; the official catalog checker
validates requirements using the server's mechanism. The runtime integration ran on linux/amd64;
no execution on Raspberry Pi/arm64 hardware has been claimed.

