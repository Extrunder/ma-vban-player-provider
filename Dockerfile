ARG MA_VERSION=2.10.13
FROM ghcr.io/music-assistant/server:${MA_VERSION}
COPY music_assistant/providers/vban /tmp/vban-provider
RUN /app/venv/bin/python -c "import pathlib, shutil, music_assistant; dst = pathlib.Path(music_assistant.__file__).parent / 'providers' / 'vban'; shutil.copytree('/tmp/vban-provider', dst, dirs_exist_ok=True)"

