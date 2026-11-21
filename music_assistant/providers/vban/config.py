"""Configuration entries shown by Music Assistant."""

from music_assistant_models.config_entries import ConfigEntry, ConfigValueOption
from music_assistant_models.enums import ConfigEntryType


def config_entries() -> tuple[ConfigEntry, ...]:
    """Create fresh entries on each render (MA may mutate them)."""
    return (
        ConfigEntry(
            key="host",
            type=ConfigEntryType.STRING,
            label="VBAN receiver IPv4 address",
            required=True,
            description="IPv4 address of the device receiving audio.",
        ),
        ConfigEntry(
            key="port",
            type=ConfigEntryType.INTEGER,
            label="VBAN UDP port",
            default_value=6980,
            range=(1, 65535),
        ),
        ConfigEntry(
            key="stream_name",
            type=ConfigEntryType.STRING,
            label="VBAN stream name",
            default_value="MusicAssistant",
            description="1–16 printable ASCII characters; must match the receiver exactly.",
        ),
        ConfigEntry(
            key="sample_rate",
            type=ConfigEntryType.INTEGER,
            label="Sample rate",
            default_value=48000,
            options=[
                ConfigValueOption(value=rate, title=str(rate)) for rate in (44100, 48000, 96000)
            ],
        ),
        ConfigEntry(
            key="channels",
            type=ConfigEntryType.INTEGER,
            label="Channels",
            default_value=2,
            options=[
                ConfigValueOption(value=1, title="Mono"),
                ConfigValueOption(value=2, title="Stereo"),
            ],
        ),
        ConfigEntry(
            key="bit_depth",
            type=ConfigEntryType.INTEGER,
            label="PCM bit depth",
            default_value=16,
            options=[
                ConfigValueOption(value=16, title="16 bit"),
                ConfigValueOption(value=24, title="24 bit"),
            ],
        ),
        ConfigEntry(
            key="packet_frames",
            type=ConfigEntryType.INTEGER,
            label="Audio frames per packet",
            default_value=128,
            range=(1, 256),
            advanced=True,
            description="Clamped to the VBAN datagram limit (239 for 24-bit stereo).",
        ),
    )
