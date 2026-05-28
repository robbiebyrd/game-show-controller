import pytest

from gameshow.events import GameState, BuzzerPressed, PlayerBuzzed, StateChanged, SceneChanged, ControlCommand

def test_game_state_enum_has_all_states():
    states = {s.name for s in GameState}
    assert states == {
        "IDLE", "LOCKED", "ALLOW_NEXT", "CORRECT", "INCORRECT",
        "BUZZ_TIMEOUT", "TIMED_LOCKOUT", "ROUND_START", "GAME_OVER"
    }

def test_buzzer_pressed_is_frozen():
    e = BuzzerPressed(player_id=1)
    with pytest.raises(AttributeError):
        e.player_id = 2  # type: ignore

def test_state_changed_carries_optional_player():
    e = StateChanged(new_state=GameState.LOCKED, player_id=2)
    assert e.new_state == GameState.LOCKED
    assert e.player_id == 2

    e2 = StateChanged(new_state=GameState.IDLE)
    assert e2.player_id is None

def test_state_changed_carries_optional_duration():
    e = StateChanged(new_state=GameState.TIMED_LOCKOUT, duration=7.5)
    assert e.duration == 7.5
    e2 = StateChanged(new_state=GameState.IDLE)
    assert e2.duration is None

def test_control_command_stores_args():
    e = ControlCommand(command="timed_lockout", args=(5.0,))
    assert e.args == (5.0,)
