"""Real UDP loopback tests: byte integrity, pacing and stream lifecycle."""

import asyncio
import socket
from contextlib import suppress

import pytest

from vban.protocol import HEADER, VBANConfig
from vban.sender import VBANSender


@pytest.fixture
def receiver():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.setblocking(False)
    yield sock
    sock.close()


async def receive(sock, count):
    packets = []
    loop = asyncio.get_running_loop()
    for _ in range(count):
        packet, _ = await asyncio.wait_for(loop.sock_recvfrom(sock, 2048), 3)
        packets.append((packet, loop.time()))
    return packets


async def chunks(data, sizes=(1, 7, 511, 103)):
    offset = 0
    while offset < len(data):
        for size in sizes:
            yield data[offset : offset + size]
            offset += size
            if offset >= len(data):
                return


@pytest.mark.parametrize("bits", [16, 24])
async def test_loopback_arbitrary_chunks_and_short_final_packet(receiver, bits):
    config = VBANConfig("127.0.0.1", port=receiver.getsockname()[1], bit_depth=bits)
    data = bytes(range(256)) * 3
    # Ensure a complete frame in both formats, with a short final packet.
    data = data[: (len(data) // config.frame_bytes) * config.frame_bytes]
    count = (len(data) + config.packet_bytes - 1) // config.packet_bytes
    reader = asyncio.create_task(receive(receiver, count))
    sender = VBANSender(config)
    progress = []
    await sender.run(chunks(data), progress.append)
    packets = [item[0] for item in await reader]
    assert b"".join(packet[28:] for packet in packets) == data
    assert [HEADER.unpack(packet[:28])[-1] for packet in packets] == list(range(count))
    assert sender.sent_frames * config.frame_bytes == len(data)
    assert progress[-1] == sender.sent_frames / config.sample_rate
    assert packets[-1][5] + 1 == len(packets[-1][28:]) // config.frame_bytes


async def test_realtime_pacing(receiver):
    config = VBANConfig(
        "127.0.0.1", port=receiver.getsockname()[1], sample_rate=6000, channels=1, packet_frames=120
    )
    count = 10  # 20 ms per packet, 200 ms of audio.
    data = bytes(config.packet_bytes * count)
    reader = asyncio.create_task(receive(receiver, count))
    start = asyncio.get_running_loop().time()
    await VBANSender(config).run(chunks(data, (len(data),)))
    elapsed = asyncio.get_running_loop().time() - start
    packets = await reader
    assert elapsed >= 0.19
    assert packets[-1][1] - packets[0][1] >= 0.16


async def test_pause_resume_gain_and_cancellation(receiver):
    config = VBANConfig(
        "127.0.0.1", port=receiver.getsockname()[1], sample_rate=6000, channels=1, packet_frames=120
    )
    sender = VBANSender(config)
    closed = asyncio.Event()

    async def source():
        try:
            while True:
                yield b"\xe8\x03" * 120  # signed sample = 1000
        finally:
            closed.set()

    reader = asyncio.create_task(receive(receiver, 1))
    task = asyncio.create_task(sender.run(source()))
    await reader
    sender.pause()
    frames = sender.sent_frames
    await asyncio.sleep(0.06)
    assert sender.sent_frames == frames
    sender.gain = 0.5
    reader = asyncio.create_task(receive(receiver, 1))
    sender.resume()
    packet = (await reader)[0][0]
    assert packet[28:] == b"\xf4\x01" * 120  # signed sample = 500
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    assert closed.is_set()


async def test_truncated_frame_fails_and_closes_source(receiver):
    config = VBANConfig("127.0.0.1", port=receiver.getsockname()[1])
    closed = False

    async def source():
        nonlocal closed
        try:
            yield b"abc"
        finally:
            closed = True

    with pytest.raises(ValueError, match="middle of an audio frame"):
        await VBANSender(config).run(source())
    assert closed


async def test_counter_continues_across_tracks(receiver):
    config = VBANConfig("127.0.0.1", port=receiver.getsockname()[1])
    sender = VBANSender(config)
    sender.counter = 0xFFFFFFFF
    reader = asyncio.create_task(receive(receiver, 2))
    for _ in range(2):
        await sender.run(chunks(bytes(4)))
    packets = await reader
    assert [HEADER.unpack(p[0][:28])[-1] for p in packets] == [0xFFFFFFFF, 0]


async def test_source_failure_is_propagated_and_closed(receiver):
    config = VBANConfig("127.0.0.1", port=receiver.getsockname()[1])
    closed = False

    async def source():
        nonlocal closed
        try:
            yield bytes(4)
            raise RuntimeError("decoder failed")
        finally:
            closed = True

    with pytest.raises(RuntimeError, match="decoder failed"):
        await VBANSender(config).run(source())
    assert closed


async def test_cancellation_while_waiting_for_source(receiver):
    config = VBANConfig("127.0.0.1", port=receiver.getsockname()[1])
    started = asyncio.Event()
    closed = asyncio.Event()

    async def source():
        try:
            started.set()
            await asyncio.Event().wait()
            yield b""
        finally:
            closed.set()

    task = asyncio.create_task(VBANSender(config).run(source()))
    await asyncio.wait_for(started.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set()
