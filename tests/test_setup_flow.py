"""Exercise setup and reconfiguration with real MA config entries."""

from types import SimpleNamespace

from vban.setup_flow import run_setup


class Session:
    def __init__(self, submissions, existing=None):
        self.context = SimpleNamespace(setup_data=existing or {})
        self.submissions = iter(submissions)
        self.forms = []
        self.saved = None

    async def form(self, entries, **kwargs):
        self.forms.append(({entry.key: entry.value for entry in entries}, kwargs))
        return next(self.submissions)

    async def finish(self, values):
        self.saved = values


async def test_setup_retries_invalid_values():
    bad = {"host": "192.168.1.25", "stream_name": "name is far too long"}
    good = {"host": "192.168.1.25", "stream_name": "Stream1"}
    session = Session([bad, good])
    await run_setup(session)
    assert session.saved == good
    assert session.forms[1][1]["errors"] == {"base": "invalid_configuration"}
    assert session.forms[1][0]["host"] == good["host"]


async def test_reconfiguration_prefills_existing_values():
    existing = {"host": "192.168.1.25", "stream_name": "Stream1", "sample_rate": 44100}
    changed = {**existing, "host": "192.168.1.26"}
    session = Session([changed], existing)
    await run_setup(session)
    assert session.forms[0][0]["host"] == existing["host"]
    assert session.forms[0][0]["sample_rate"] == 44100
    assert session.saved == changed
