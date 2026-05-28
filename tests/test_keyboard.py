import pytest
from gameshow.bus import EventBus
from gameshow.config import AppConfig, BuzzerConfig, PlayerConfig, ServiceConfig, StateMachineConfig, LightingConfig, AudioConfig, OBSConfig
from gameshow.events import BuzzerPressed
from gameshow.keyboard import KeyboardListener


def make_config(players):
    return AppConfig(
        service=ServiceConfig(), buzzers=BuzzerConfig(players=players),
        state_machine=StateMachineConfig(), lighting=LightingConfig(),
        audio=AudioConfig(), obs=OBSConfig(), scenes=[],
    )


@pytest.mark.asyncio
async def test_known_key_publishes_buzzer_pressed():
    bus = EventBus()
    players = [PlayerConfig(id=1, name="P1", key="1", enabled=True)]
    config = make_config(players)
    listener = KeyboardListener(bus, lambda: config)

    received = []
    async def capture(e): received.append(e)
    bus.subscribe(BuzzerPressed, capture)

    await listener._on_key("1")
    assert len(received) == 1
    assert received[0].player_id == 1


@pytest.mark.asyncio
async def test_unknown_key_is_ignored():
    bus = EventBus()
    players = [PlayerConfig(id=1, name="P1", key="1", enabled=True)]
    config = make_config(players)
    listener = KeyboardListener(bus, lambda: config)

    received = []
    async def capture(e): received.append(e)
    bus.subscribe(BuzzerPressed, capture)

    await listener._on_key("z")
    assert len(received) == 0


@pytest.mark.asyncio
async def test_disabled_player_key_is_ignored():
    bus = EventBus()
    players = [PlayerConfig(id=1, name="P1", key="1", enabled=False)]
    config = make_config(players)
    listener = KeyboardListener(bus, lambda: config)

    received = []
    async def capture(e): received.append(e)
    bus.subscribe(BuzzerPressed, capture)

    await listener._on_key("1")
    assert len(received) == 0
