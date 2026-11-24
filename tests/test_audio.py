"""PCM correctness against scalar reference arithmetic and volume endpoints."""

import math
import random

import pytest

from vban.audio import apply_gain, volume_to_gain


@pytest.mark.parametrize("bits", [16, 24])
@pytest.mark.parametrize("gain", [0.001, 10**-1.5, 0.5, 0.99])
def test_native_gain_matches_signed_scalar_reference(bits, gain):
    width = bits // 8
    minimum, maximum = -(2 ** (bits - 1)), 2 ** (bits - 1) - 1
    rng = random.Random(42)
    samples = [minimum, minimum + 1, -257, -1, 0, 1, 257, maximum - 1, maximum]
    samples += [rng.randint(minimum, maximum) for _ in range(503)]
    pcm = b"".join(value.to_bytes(width, "little", signed=True) for value in samples)
    expected = b"".join(
        int(value * gain).to_bytes(width, "little", signed=True) for value in samples
    )
    assert apply_gain(pcm, bits, gain) == expected


@pytest.mark.parametrize("bits", [16, 24])
def test_bypass_and_mute_do_not_process_samples(bits, monkeypatch):
    pcm = bytes(range(12))

    def no_array(*args, **kwargs):
        pytest.fail("Unity and mute must not unpack PCM")

    monkeypatch.setattr("vban.audio.np.frombuffer", no_array)
    assert apply_gain(pcm, bits, 1) is pcm
    assert apply_gain(pcm, bits, 0) == bytes(len(pcm))
    assert apply_gain(b"", bits, 0.5) == b""


@pytest.mark.parametrize("bits,pcm", [(16, b"x"), (24, b"xx"), (8, b"x")])
@pytest.mark.parametrize("gain", [0, 0.5, 1])
def test_invalid_pcm_is_rejected_even_on_fast_paths(bits, pcm, gain):
    with pytest.raises(ValueError, match="Unaligned or unsupported"):
        apply_gain(pcm, bits, gain)


@pytest.mark.parametrize("gain", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_gain_is_rejected(gain):
    with pytest.raises(ValueError, match="finite"):
        apply_gain(bytes(4), 16, gain)


def test_volume_has_equal_db_steps_and_exact_silence_and_unity():
    assert volume_to_gain(-5) == volume_to_gain(0) == 0
    assert volume_to_gain(100) == volume_to_gain(105) == 1
    assert 20 * math.log10(volume_to_gain(1)) == pytest.approx(-59.4)
    assert 20 * math.log10(volume_to_gain(50)) == pytest.approx(-30)
    for volume in range(1, 100):
        assert 20 * math.log10(volume_to_gain(volume + 1) / volume_to_gain(volume)) == (
            pytest.approx(0.6)
        )
