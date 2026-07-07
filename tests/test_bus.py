import logging
import pytest
from gameshow.bus import EventBus
from gameshow.events import BuzzerPressed, StateChanged, GameState, CountdownTick


@pytest.mark.asyncio
async def test_subscriber_called_on_matching_event():
    bus = EventBus()
    received = []

    async def handler(event: BuzzerPressed):
        received.append(event)

    bus.subscribe(BuzzerPressed, handler)
    await bus.publish(BuzzerPressed(player_id=1))

    assert len(received) == 1
    assert received[0].player_id == 1


@pytest.mark.asyncio
async def test_subscriber_not_called_for_other_event_type():
    bus = EventBus()
    received = []

    async def handler(event: BuzzerPressed):
        received.append(event)

    bus.subscribe(BuzzerPressed, handler)
    await bus.publish(StateChanged(new_state=GameState.IDLE))

    assert len(received) == 0


@pytest.mark.asyncio
async def test_multiple_subscribers_all_called():
    bus = EventBus()
    calls = []

    async def h1(e): calls.append(1)
    async def h2(e): calls.append(2)

    bus.subscribe(BuzzerPressed, h1)
    bus.subscribe(BuzzerPressed, h2)
    await bus.publish(BuzzerPressed(player_id=1))

    assert sorted(calls) == [1, 2]


@pytest.mark.asyncio
async def test_publish_logs_every_event_at_info(caplog):
    bus = EventBus()
    with caplog.at_level(logging.INFO, logger="gameshow.bus"):
        await bus.publish(BuzzerPressed(player_id=3))
    assert any("BuzzerPressed" in r.message and r.levelno == logging.INFO
               for r in caplog.records)


@pytest.mark.asyncio
async def test_publish_logs_countdown_tick_at_debug(caplog):
    bus = EventBus()
    # At INFO level the high-frequency tick must NOT appear.
    with caplog.at_level(logging.INFO, logger="gameshow.bus"):
        await bus.publish(CountdownTick(remaining=3.0, total=5.0))
    assert not any("CountdownTick" in r.message for r in caplog.records)
    # At DEBUG level it does.
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="gameshow.bus"):
        await bus.publish(CountdownTick(remaining=3.0, total=5.0))
    assert any("CountdownTick" in r.message for r in caplog.records)
