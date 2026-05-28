import asyncio
import pytest
from gameshow.bus import EventBus
from gameshow.config import AppConfig, ServiceConfig, BuzzerConfig, PlayerConfig, StateMachineConfig, LightingConfig, AudioConfig, OBSConfig
from gameshow.events import ControlCommand, SceneChanged
from gameshow.osc_server import OSCServer


def make_config():
    return AppConfig(
        service=ServiceConfig(touchosc_host="127.0.0.1", touchosc_port=9001),
        buzzers=BuzzerConfig(players=[]),
        state_machine=StateMachineConfig(),
        lighting=LightingConfig(),
        audio=AudioConfig(),
        obs=OBSConfig(),
        scenes=[],
    )


@pytest.mark.asyncio
async def test_buzzer_clear_publishes_control_command():
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    received = []
    async def capture(e): received.append(e)
    bus.subscribe(ControlCommand, capture)

    await server._dispatch("/buzzer/clear", [])
    assert any(e.command == "clear" for e in received)


@pytest.mark.asyncio
async def test_timed_lockout_passes_duration():
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    received = []
    async def capture(e): received.append(e)
    bus.subscribe(ControlCommand, capture)

    await server._dispatch("/buzzer/timed_lockout", [7.5])
    assert received[0].command == "timed_lockout"
    assert received[0].args == (7.5,)


@pytest.mark.asyncio
async def test_show_goto_int_publishes_scene_goto_command():
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    received = []
    async def capture(e): received.append(e)
    bus.subscribe(ControlCommand, capture)

    await server._dispatch("/show/goto", [2])
    assert received[0].command == "scene_goto_index"
    assert received[0].args == (2,)


@pytest.mark.asyncio
async def test_show_goto_string_publishes_scene_goto_name():
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    received = []
    async def capture(e): received.append(e)
    bus.subscribe(ControlCommand, capture)

    await server._dispatch("/show/goto", ["Round 1"])
    assert received[0].command == "scene_goto_name"
    assert received[0].args == ("Round 1",)
