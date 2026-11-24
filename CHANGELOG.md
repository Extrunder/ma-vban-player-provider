# Changelog

## 0.2.1

- Replace per-sample Python volume scaling with bounded native NumPy operations, using
  Music Assistant's existing NumPy dependency and retaining dynamic per-packet volume/mute.
- Use a 60 dB volume range: 100% remains unity, 50% is now -30 dB instead of about -6 dB,
  and volume zero/mute produce exact digital silence.
- Add signed PCM/reference tests, live gain changes, native MA volume/mute integration
  checks and a reproducible CPU benchmark against the previous scalar implementation.

## 0.2.0

- Package the native player as an independent Music Assistant community provider in `vban/`.
- Add the Apache-2.0 licence, English/Russian texts, CI and a guarded release workflow.
- Exercise the real community loader without modifying the installed Music Assistant package.
- Support the modern PlayerProtocol interface with the legacy Player fallback.
- Preserve 16/24-bit PCM, mono/stereo, flow playback, pause, software volume and mute.

## 0.1.0

- Initial native player provider, tested against Music Assistant 2.10.13.

