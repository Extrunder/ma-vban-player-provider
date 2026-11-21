"""Native setup/reconfigure form for Music Assistant 2.10.13."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .config import config_entries
from .protocol import VBANConfig

if TYPE_CHECKING:
    from music_assistant.models.setup_flow import SetupSession


async def run_setup(session: SetupSession) -> None:
    """Collect and validate the receiver settings before saving a provider."""
    entries = list(config_entries())
    for entry in entries:
        entry.value = session.context.setup_data.get(entry.key, entry.default_value)
    errors: dict[str, str] = {}
    while True:
        values = await session.form(entries, errors=errors, last_step=True)
        try:
            VBANConfig(**values)
        except TypeError, ValueError:
            errors = {"base": "invalid_configuration"}
            for entry in entries:
                entry.value = values.get(entry.key, entry.value)
            continue
        await session.finish(values)
        return
