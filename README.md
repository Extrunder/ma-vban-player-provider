# VBAN Player — Music Assistant community provider

A native player provider that sends Music Assistant audio to a VBAN receiver over UDP.
It uses the normal music sources, queue, decoder and DSP, with no additional Python dependencies.

**Status:** community release 0.2.0; catalog admission is pending.
Source and releases: [Extrunder/ma-vban-player-provider](https://github.com/Extrunder/ma-vban-player-provider).
Music Assistant 2.10.13 has no community installer. Installation through the Marketplace
requires a server channel that supports the catalog and a VBAN release admitted to it.
A ZIP alone cannot be installed through the MA API.

## Features

- Signed little-endian PCM, 16/24-bit, mono/stereo, 44.1/48/96 kHz in the setup form.
- Play, pause/resume, stop, software volume and mute.
- Continuous queue flow, MA transitions/crossfades and output-plan filters/DSP.
- Multiple receivers, independently configured, with stable player IDs.
- Frame-aligned packets, monotonic pacing, bounded buffers and cancellation cleanup.
- English texts and Russian translations.

## Install from the community catalog

Once published, admitted and offered for your MA channel:

1. Sign in to MA as an administrator and enable the community catalog in the Marketplace.
2. Install **VBAN Player**, then add/configure its player provider.
3. Enter the receiver's IPv4 address, UDP port, exact stream name and audio format.
4. Enable the matching incoming stream on the receiver and select the player in MA.

The server manages community-provider storage separately from its installed Python package.
No custom MA image is needed. Updating/recreating the container retains providers when the
persistent MA data is retained. A clean reinstall deleting those data requires reinstalling
or restoring a backup. Compatibility is checked by the catalog for each server channel.

[Инструкция на русском](docs/INSTALL_RU.md).

## Receiver settings

| Setting | Default | Meaning |
|---|---|---|
| Receiver IPv4 address | Required | Device receiving audio |
| UDP port | `6980` | Incoming VBAN port |
| Stream name | `MusicAssistant` | 1–16 printable ASCII characters, case-sensitive |
| Sample rate | `48000` | 44100, 48000 or 96000 Hz |
| Channels | `2` | Mono or stereo |
| PCM bit depth | `16` | 16 or 24 bits |
| Frames per packet | `128` | 1–256; clamped to 239 for 24-bit stereo |

Use **Reconfigure** to change receiver settings. The player ID stays the same. On Voicemeeter,
enable VBAN and the incoming stream, match its name/port, allow the MA host's source IP and
choose the destination strip/output. UDP must be routable from MA to the receiver.

Volume/mute modify samples, not hardware volume. 100% means no attenuation. Mute sends zero
PCM; pause/stop stop packets. A paused live source may resume behind the live edge.
UDP has no delivery acknowledgement: `available` means configured, not confirmed online.
Errors end playback and appear in the log and `last_error`. Automatic VBAN discovery,
device power control and synchronised receiver clocks are not implemented.

## Develop and test

The canonical provider is [`vban/`](vban/); there is no duplicate inside the MA package.
Quick tests run on Windows, Linux or macOS with Python 3.14:

```sh
uv sync --locked --group dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run python scripts/package_community.py
```

Exercise actual community loading, native Player registration, FFmpeg, software volume and
byte-accurate loopback UDP without changing an existing MA instance:

```sh
docker build -f Dockerfile.community-test -t vban-community-check .
docker run --rm --network none vban-community-check
```

The test keeps source outside the installed MA package, asserts the `community` tier and
uses temporary data. Discovery is restricted to IPv4 loopback; optional device providers
are suppressed. Pin the image with `--build-arg SERVER_IMAGE=...` when needed.
CI separately invokes the official catalog's reusable workflow for `folder: vban`, `channel: nightly`.

Local validation: **56 tests pass**, the official catalog checker reports `vban: passed`,
and real community loading/audio/unload passes in MA `2.11.0.dev2026112103`.
[Exact images, checks and limits](docs/VALIDATION.md).

Before admission, the official **Music Assistant DEV SERVER** App can load a public
repository through **Provider repository**, using a separate test MA installation.

## Publish

Configure the real GitHub repository and maintainer; no placeholder identity is published:

```sh
python scripts/configure_repository.py Extrunder/ma-vban-player-provider --maintainer Extrunder
python scripts/package_community.py --check-publication --version 0.2.0
```

Push, pass CI, publish `v0.2.0` using **Publish release**, and submit to the catalog.
Publication and admission are distinct; catalog maintainers decide admission.
[Full procedure](docs/SUBMISSION.md).

The original provider was tested with MA 2.10.13/models 1.1.205. The old manual installer
and image/App packaging remain legacy development options, not the community mechanism.

## Licence and references

Apache-2.0. See [LICENSE](LICENSE).
Official logo sources and credits: [Artwork](docs/ARTWORK.md).

- [Building a provider](https://developers.music-assistant.io/building-a-provider/)
- [Community catalog](https://github.com/music-assistant/community-catalog)
- [VBAN specification](https://vb-audio.com/Voicemeeter/VBANProtocol_Specifications.pdf)

