# Validation of 0.2.0

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

