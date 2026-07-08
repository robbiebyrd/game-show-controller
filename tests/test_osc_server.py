import asyncio
import pytest
from unittest.mock import MagicMock
from gameshow.bus import EventBus
from gameshow.config import AppConfig, ServiceConfig, BuzzerConfig, PlayerConfig, StateMachineConfig, LightingConfig, AudioConfig, OBSConfig
from gameshow.events import ControlCommand, SceneChanged, StateChanged, ScoreChanged, AwardChanged
from gameshow.osc_server import OSCServer


def make_config():
    return AppConfig(
        service=ServiceConfig(touchosc_host="127.0.0.1", touchosc_port=9001),
        buzzers=BuzzerConfig(players=[]),
        state_machine=StateMachineConfig(initial="idle"),
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


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["correct", "incorrect", "idle"])
async def test_feedback_player_cleared_on_result_states(state):
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    mock_client = MagicMock()
    server._feedback_client = mock_client

    await server._on_state_changed(StateChanged(new_state=state))

    calls = [call for call in mock_client.send_message.call_args_list
             if call.args[0] == "/feedback/player"]
    assert calls, f"Expected /feedback/player message for state {state}"
    assert calls[0].args[1] == ["None"]


@pytest.mark.asyncio
async def test_feedback_score_changed():
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    mock_client = MagicMock()
    server._feedback_client = mock_client

    await server._on_score_changed(ScoreChanged(player_id=1, score=300, delta=100))

    calls = [c for c in mock_client.send_message.call_args_list
             if c.args[0] == "/feedback/score/1"]
    assert calls and calls[0].args[1] == [300]


@pytest.mark.asyncio
async def test_feedback_award_changed():
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    mock_client = MagicMock()
    server._feedback_client = mock_client

    await server._on_award_changed(AwardChanged(value=200))

    calls = [c for c in mock_client.send_message.call_args_list
             if c.args[0] == "/feedback/award"]
    assert calls and calls[0].args[1] == [200]


@pytest.mark.asyncio
async def test_feedback_player_not_cleared_on_locked_state():
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    mock_client = MagicMock()
    server._feedback_client = mock_client

    await server._on_state_changed(StateChanged(new_state="locked"))

    calls = [call for call in mock_client.send_message.call_args_list
             if call.args[0] == "/feedback/player"]
    assert not calls
