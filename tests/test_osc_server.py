import asyncio
import pytest
from unittest.mock import MagicMock
from gameshow.bus import EventBus
from gameshow.config import AppConfig, ServiceConfig, BuzzerConfig, PlayerConfig, StateMachineConfig, LightingConfig, AudioConfig, OBSConfig, ShowConfig
from gameshow.events import (
    ControlCommand, SceneChanged, StateChanged, ScoreChanged, AwardChanged, CounterChanged,
    ConfigReloaded, BuzzerPressed, CountdownTick,
)
from gameshow.osc_server import OSCServer


def make_config(show=None):
    return AppConfig(
        service=ServiceConfig(touchosc_host="127.0.0.1", touchosc_port=9001),
        buzzers=BuzzerConfig(players=[]),
        state_machine=StateMachineConfig(initial="idle"),
        lighting=LightingConfig(),
        audio=AudioConfig(),
        obs=OBSConfig(),
        scenes=[],
        show=show or ShowConfig(),
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
async def test_feedback_counter_changed():
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    mock_client = MagicMock()
    server._feedback_client = mock_client

    await server._on_counter_changed(CounterChanged(name="strikes", value=2))

    calls = [c for c in mock_client.send_message.call_args_list
             if c.args[0] == "/feedback/counter/strikes"]
    assert calls and calls[0].args[1] == [2]


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


@pytest.mark.asyncio
async def test_config_reload_with_path_publishes_command():
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    received = []
    async def capture(e): received.append(e)
    bus.subscribe(ControlCommand, capture)

    await server._dispatch("/config/reload", ["jeopardy.yml"])
    assert received[0].command == "config_reload"
    assert received[0].args == ("jeopardy.yml",)


@pytest.mark.asyncio
async def test_config_reload_without_path_publishes_bare_command():
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    received = []
    async def capture(e): received.append(e)
    bus.subscribe(ControlCommand, capture)

    await server._dispatch("/config/reload", [])
    assert received[0].command == "config_reload"
    assert received[0].args == ()


@pytest.mark.asyncio
async def test_config_reloaded_emits_show_feedback():
    bus = EventBus()
    show = ShowConfig(name="Jeopardy Night", description="Trivia showdown")
    server = OSCServer(bus, lambda: make_config(show=show))
    mock_client = MagicMock()
    server._feedback_client = mock_client

    await bus.publish(ConfigReloaded(path="shows/jeopardy.yml"))

    sent = {c.args[0]: c.args[1] for c in mock_client.send_message.call_args_list}
    assert sent["/feedback/show/name"] == ["Jeopardy Night"]
    assert sent["/feedback/show/description"] == ["Trivia showdown"]


@pytest.mark.asyncio
async def test_config_list_emits_show_feedback(tmp_path, monkeypatch):
    (tmp_path / "trivia.yml").write_text("show:\n  name: Trivia\n")
    (tmp_path / "faceoff.yml").write_text("show:\n  name: Face Off\n")
    monkeypatch.setattr("gameshow.shows.SHOWS_DIR", str(tmp_path))
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    mock_client = MagicMock()
    server._feedback_client = mock_client

    await server._dispatch("/config/list", [])

    calls = mock_client.send_message.call_args_list
    counts = [c for c in calls if c.args[0] == "/feedback/shows/count"]
    items = [c.args[1] for c in calls if c.args[0] == "/feedback/shows/item"]
    assert counts and counts[0].args[1] == [2]
    # sorted by filename: faceoff.yml (0), trivia.yml (1)
    assert items[0] == [0, "faceoff.yml", "Face Off"]
    assert items[1] == [1, "trivia.yml", "Trivia"]


@pytest.mark.asyncio
async def test_config_load_by_index_publishes_reload(tmp_path, monkeypatch):
    (tmp_path / "trivia.yml").write_text("show:\n  name: Trivia\n")
    (tmp_path / "faceoff.yml").write_text("show:\n  name: Face Off\n")
    monkeypatch.setattr("gameshow.shows.SHOWS_DIR", str(tmp_path))
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    received = []
    async def capture(e): received.append(e)
    bus.subscribe(ControlCommand, capture)

    await server._dispatch("/config/load", [1])  # trivia.yml
    assert received[0].command == "config_reload"
    assert received[0].args == ("trivia.yml",)


@pytest.mark.asyncio
async def test_config_load_out_of_range_is_ignored(tmp_path, monkeypatch):
    (tmp_path / "trivia.yml").write_text("show:\n  name: Trivia\n")
    monkeypatch.setattr("gameshow.shows.SHOWS_DIR", str(tmp_path))
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    received = []
    async def capture(e): received.append(e)
    bus.subscribe(ControlCommand, capture)

    await server._dispatch("/config/load", [99])
    assert received == []


# ── Full-parity inbound routes (via osc_map.command_for) ────────────────────

@pytest.mark.asyncio
async def test_generic_trigger_publishes_arbitrary_state_command():
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    received = []
    async def capture(e): received.append(e)
    bus.subscribe(ControlCommand, capture)

    await server._dispatch("/trigger", ["three_strikes"])
    assert received[0] == ControlCommand(command="three_strikes")


@pytest.mark.asyncio
async def test_buzz_press_publishes_buzzer_pressed():
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    received = []
    async def capture(e): received.append(e)
    bus.subscribe(BuzzerPressed, capture)

    await server._dispatch("/buzzer/press", [2])
    assert received[0] == BuzzerPressed(player_id=2)


@pytest.mark.asyncio
@pytest.mark.parametrize("address,args,expected", [
    ("/lighting/cue", ["/live/x/activate"],
     ControlCommand(command="dmx_cue", args=("/live/x/activate",))),
    ("/obs/scene", ["Intro"],
     ControlCommand(command="obs_scene_set", args=("Intro",))),
    ("/award/set", [50], ControlCommand(command="set_award", args=(50.0,))),
    ("/countdown/pause", [], ControlCommand(command="countdown_pause")),
    ("/countdown/toggle", [], ControlCommand(command="countdown_toggle")),
])
async def test_parity_routes_publish_expected_command(address, args, expected):
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    received = []
    async def capture(e): received.append(e)
    bus.subscribe(ControlCommand, capture)

    await server._dispatch(address, args)
    assert received[0] == expected


@pytest.mark.asyncio
async def test_countdown_tick_emits_feedback_countdown():
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    mock_client = MagicMock()
    server._feedback_client = mock_client

    await server._on_tick(CountdownTick(remaining=4.2, total=10.0))

    calls = [c for c in mock_client.send_message.call_args_list
             if c.args[0] == "/feedback/countdown"]
    assert calls and calls[0].args[1] == ["5"]  # ceil(4.2)


@pytest.mark.asyncio
async def test_countdown_feedback_dedupes_same_second():
    bus = EventBus()
    server = OSCServer(bus, lambda: make_config())
    mock_client = MagicMock()
    server._feedback_client = mock_client

    await server._on_tick(CountdownTick(remaining=4.9, total=10.0))
    await server._on_tick(CountdownTick(remaining=4.2, total=10.0))  # still ceil 5

    calls = [c for c in mock_client.send_message.call_args_list
             if c.args[0] == "/feedback/countdown"]
    assert len(calls) == 1
