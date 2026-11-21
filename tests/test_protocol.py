"""Independent wire-format checks, including VBAN's zero-based counts."""

import struct
from dataclasses import replace

import pytest
from music_assistant_models.config_entries import ConfigEntry
from music_assistant_models.provider import ProviderManifest

from music_assistant.providers.vban.config import config_entries
from music_assistant.providers.vban.protocol import (
    HEADER,
    MAX_PACKET_SIZE,
    VBANConfig,
    apply_gain,
    encode_packet,
)


def test_known_wire_packet():
    config = VBANConfig("127.0.0.1", stream_name="Stream1", packet_frames=2)
    pcm = b"\x01\x00\xff\x7f\x00\x80\xfe\xff"
    expected = b"VBAN\x03\x01\x01\x01Stream1\0\0\0\0\0\0\0\0\0\x78\x56\x34\x12" + pcm
    assert encode_packet(config, pcm, 0x12345678) == expected
    assert HEADER.size == 28


@pytest.mark.parametrize("rate,index", [(44100, 16), (48000, 3), (96000, 4)])
@pytest.mark.parametrize("bits,fmt", [(16, 1), (24, 2)])
@pytest.mark.parametrize("channels", [1, 2])
def test_audio_format_fields(rate, index, bits, fmt, channels):
    config = VBANConfig("127.0.0.1", sample_rate=rate, bit_depth=bits, channels=channels)
    packet = encode_packet(config, bytes(config.frame_bytes), 0)
    assert packet[4:8] == bytes([index, 0, channels - 1, fmt])


def test_packet_limit_and_counter_wrap():
    config = VBANConfig(
        "127.0.0.1", bit_depth=24, packet_frames=256, stream_name="1234567890123456"
    )
    assert config.frames_per_packet == 239
    packet = encode_packet(config, bytes(config.packet_bytes), 0x100000001)
    assert len(packet) <= MAX_PACKET_SIZE
    assert packet[8:24] == b"1234567890123456"
    assert packet[24:28] == b"\x01\0\0\0"


@pytest.mark.parametrize(
    "changes",
    [
        {"host": "hostname.local"},
        {"host": "::1"},
        {"host": "0.0.0.0"},
        {"host": "224.0.0.1"},
        {"host": "255.255.255.255"},
        {"port": 0},
        {"port": 65536},
        {"stream_name": ""},
        {"stream_name": "x" * 17},
        {"stream_name": "Музыка"},
        {"stream_name": "a\0b"},
        {"stream_name": "a\nb"},
        {"bit_depth": 32},
        {"channels": 3},
        {"sample_rate": 12345},
        {"packet_frames": 0},
        {"packet_frames": 257},
    ],
)
def test_reject_bad_config(changes):
    with pytest.raises(ValueError):
        replace(VBANConfig("127.0.0.1"), **changes)


@pytest.mark.parametrize("payload", [b"", b"a", bytes(1028)])
def test_reject_bad_payload(payload):
    with pytest.raises(ValueError):
        encode_packet(VBANConfig("127.0.0.1"), payload, 0)


@pytest.mark.parametrize("bits", [16, 24])
def test_gain_preserves_signed_pcm_and_mutes(bits):
    width = bits // 8
    samples = [-(2 ** (bits - 1)), -100, 0, 100, 2 ** (bits - 1) - 1]
    pcm = b"".join(value.to_bytes(width, "little", signed=True) for value in samples)
    scaled = apply_gain(pcm, bits, 0.5)
    result = [
        int.from_bytes(scaled[i : i + width], "little", signed=True)
        for i in range(0, len(scaled), width)
    ]
    assert result == [int(value * 0.5) for value in samples]
    assert apply_gain(pcm, bits, 0) == bytes(len(pcm))
    assert apply_gain(pcm, bits, 1) == pcm


def test_real_ma_models_validate_manifest_and_config():
    import json
    from pathlib import Path

    path = Path(__file__).parents[1] / "music_assistant/providers/vban/manifest.json"
    manifest = ProviderManifest.from_dict(json.loads(path.read_text()))
    assert manifest.domain == "vban" and manifest.multi_instance
    entries = config_entries()
    assert entries is not config_entries()
    for entry in entries:
        assert ConfigEntry.from_dict(entry.to_dict()).key == entry.key
        for option in entry.options:
            assert isinstance(option.value, int)
            assert isinstance(option.title, str)


def test_pcm_interleaving_unchanged():
    pcm = struct.pack("<hhhh", 1, 2, 3, 4)
    packet = encode_packet(VBANConfig("127.0.0.1"), pcm, 0)
    assert packet[28:] == pcm
