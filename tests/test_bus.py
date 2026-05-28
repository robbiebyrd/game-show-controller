import asyncio
import pytest
from gameshow.bus import EventBus
from gameshow.events import BuzzerPressed, StateChanged, GameState


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
