import pytest

from gameshow.events import BuzzerPressed, PlayerBuzzed, StateChanged, SceneChanged, ControlCommand


def test_buzzer_pressed_is_frozen():
    e = BuzzerPressed(player_id=1)
    with pytest.raises(AttributeError):
        e.player_id = 2  # type: ignore


def test_state_changed_carries_string_state_and_optional_player():
    e = StateChanged(new_state="locked", player_id=2)
    assert e.new_state == "locked"
    assert e.player_id == 2

    e2 = StateChanged(new_state="idle")
    assert e2.player_id is None


def test_state_changed_carries_optional_duration():
    e = StateChanged(new_state="timed_lockout", duration=7.5)
    assert e.duration == 7.5
    e2 = StateChanged(new_state="idle")
    assert e2.duration is None


def test_control_command_stores_args():
    e = ControlCommand(command="timed_lockout", args=(5.0,))
    assert e.args == (5.0,)
