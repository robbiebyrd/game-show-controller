import pytest
from gameshow.config import ButtonConfig
from gameshow.events import ControlCommand, BuzzerPressed
from gameshow import osc_map
from gameshow.osc_map import OscSend, button_to_osc, command_for


# ── button_to_osc: each Stream Deck button type → OSC send(s) ───────────────

def test_reset_buzzer_sends_clear():
    assert button_to_osc(ButtonConfig(type="reset_buzzer")) == [
        OscSend(osc_map.ADDR_CLEAR)
    ]


def test_buzz_sends_player_id_as_int():
    assert button_to_osc(ButtonConfig(type="buzz", player_id=2)) == [
        OscSend(osc_map.ADDR_BUZZ, 2, osc_map.INT)
    ]


def test_state_sends_generic_trigger():
    assert button_to_osc(ButtonConfig(type="state", state="three_strikes")) == [
        OscSend(osc_map.ADDR_TRIGGER, "three_strikes", osc_map.STRING)
    ]


def test_state_timed_lockout_sends_duration():
    assert button_to_osc(
        ButtonConfig(type="state", state="timed_lockout", duration=7.5)
    ) == [OscSend(osc_map.ADDR_TIMED_LOCKOUT, 7.5, osc_map.FLOAT)]


def test_scene_advance_and_previous():
    assert button_to_osc(ButtonConfig(type="scene_advance")) == [
        OscSend(osc_map.ADDR_SCENE_ADVANCE)
    ]
    assert button_to_osc(ButtonConfig(type="scene_previous")) == [
        OscSend(osc_map.ADDR_SCENE_PREVIOUS)
    ]


def test_scene_goto_name_is_string_index_is_int():
    assert button_to_osc(ButtonConfig(type="scene_goto", target="Round 1")) == [
        OscSend(osc_map.ADDR_SCENE_GOTO, "Round 1", osc_map.STRING)
    ]
    assert button_to_osc(ButtonConfig(type="scene_goto", target=3)) == [
        OscSend(osc_map.ADDR_SCENE_GOTO, 3, osc_map.INT)
    ]


def test_sound_sends_effect_play_with_path():
    assert button_to_osc(ButtonConfig(type="sound", path="music/x.mp3")) == [
        OscSend(osc_map.ADDR_EFFECT_PLAY, "music/x.mp3", osc_map.STRING)
    ]


def test_stop_sounds_sends_both_stop_addresses():
    assert button_to_osc(ButtonConfig(type="stop_sounds")) == [
        OscSend(osc_map.ADDR_EFFECT_STOP),
        OscSend(osc_map.ADDR_BG_STOP),
    ]


def test_lighting_sends_cue_address():
    assert button_to_osc(ButtonConfig(type="lighting", osc="/live/x/activate")) == [
        OscSend(osc_map.ADDR_LIGHTING, "/live/x/activate", osc_map.STRING)
    ]


def test_obs_scene_sends_scene_name():
    assert button_to_osc(ButtonConfig(type="obs_scene", scene="Intro")) == [
        OscSend(osc_map.ADDR_OBS_SCENE, "Intro", osc_map.STRING)
    ]


def test_obs_request_sends_request_type():
    assert button_to_osc(
        ButtonConfig(type="obs_request", request_type="GetVersion")
    ) == [OscSend(osc_map.ADDR_OBS_REQUEST, "GetVersion", osc_map.STRING)]


def test_set_award_sends_float_value():
    assert button_to_osc(ButtonConfig(type="set_award", value=200)) == [
        OscSend(osc_map.ADDR_AWARD_SET, 200.0, osc_map.FLOAT)
    ]


def test_config_reload_sends_file():
    assert button_to_osc(
        ButtonConfig(type="config_reload", config="trivia.yml")
    ) == [OscSend(osc_map.ADDR_CONFIG_RELOAD, "trivia.yml", osc_map.STRING)]


@pytest.mark.parametrize("action", ["pause", "resume", "reset", "cancel", "toggle"])
def test_countdown_control_actions_send_dedicated_address(action):
    assert button_to_osc(ButtonConfig(type="countdown", action=action)) == [
        OscSend(f"/countdown/{action}")
    ]


@pytest.mark.parametrize("button", [
    ButtonConfig(type="countdown", action="display"),
    ButtonConfig(type="state_display"),
    ButtonConfig(type="scene_current"),
    ButtonConfig(type="score_display"),
    ButtonConfig(type="counter_display", counter="strikes"),
    ButtonConfig(type="page"),
    ButtonConfig(type="return"),
])
def test_display_and_navigation_buttons_send_nothing(button):
    assert button_to_osc(button) == []


# ── command_for: inbound OSC (address, args) → bus event ────────────────────

def test_command_for_buzz_returns_buzzer_pressed():
    assert command_for(osc_map.ADDR_BUZZ, [2]) == BuzzerPressed(player_id=2)


def test_command_for_trigger_returns_control_command():
    assert command_for(osc_map.ADDR_TRIGGER, ["three_strikes"]) == \
        ControlCommand(command="three_strikes")


def test_command_for_clear():
    assert command_for(osc_map.ADDR_CLEAR, []) == ControlCommand(command="clear")


def test_command_for_timed_lockout():
    assert command_for(osc_map.ADDR_TIMED_LOCKOUT, [5.0]) == \
        ControlCommand(command="timed_lockout", args=(5.0,))


def test_command_for_scene_goto_int_vs_str():
    assert command_for(osc_map.ADDR_SCENE_GOTO, [2]) == \
        ControlCommand(command="scene_goto_index", args=(2,))
    assert command_for(osc_map.ADDR_SCENE_GOTO, ["Round 1"]) == \
        ControlCommand(command="scene_goto_name", args=("Round 1",))


def test_command_for_effect_play_and_stops():
    assert command_for(osc_map.ADDR_EFFECT_PLAY, ["music/x.mp3"]) == \
        ControlCommand(command="audio_effect_play", args=("music/x.mp3",))
    assert command_for(osc_map.ADDR_EFFECT_STOP, []) == \
        ControlCommand(command="audio_fx_stop")
    assert command_for(osc_map.ADDR_BG_STOP, []) == \
        ControlCommand(command="audio_bg_stop")


def test_command_for_lighting_obs_award():
    assert command_for(osc_map.ADDR_LIGHTING, ["/live/x"]) == \
        ControlCommand(command="dmx_cue", args=("/live/x",))
    assert command_for(osc_map.ADDR_OBS_SCENE, ["Intro"]) == \
        ControlCommand(command="obs_scene_set", args=("Intro",))
    assert command_for(osc_map.ADDR_AWARD_SET, [200]) == \
        ControlCommand(command="set_award", args=(200.0,))


def test_command_for_obs_request_with_and_without_data():
    assert command_for(osc_map.ADDR_OBS_REQUEST, ["GetVersion"]) == \
        ControlCommand(command="obs_request", args=("GetVersion",))
    assert command_for(osc_map.ADDR_OBS_REQUEST, ["SetX", '{"a": 1}']) == \
        ControlCommand(command="obs_request", args=("SetX", {"a": 1}))


def test_command_for_obs_request_malformed_json_falls_back_to_type_only():
    assert command_for(osc_map.ADDR_OBS_REQUEST, ["SetX", "not json"]) == \
        ControlCommand(command="obs_request", args=("SetX",))


@pytest.mark.parametrize("action", ["pause", "resume", "reset", "cancel", "toggle"])
def test_command_for_countdown(action):
    assert command_for(f"/countdown/{action}", []) == \
        ControlCommand(command=f"countdown_{action}")


def test_command_for_config_reload_with_and_without_arg():
    assert command_for(osc_map.ADDR_CONFIG_RELOAD, ["trivia.yml"]) == \
        ControlCommand(command="config_reload", args=("trivia.yml",))
    assert command_for(osc_map.ADDR_CONFIG_RELOAD, []) == \
        ControlCommand(command="config_reload")


def test_command_for_unknown_address_returns_none():
    assert command_for("/nope", []) is None


def test_inbound_addresses_lists_every_command_for_route():
    # The server iterates INBOUND_ADDRESSES to register its dispatcher, so any
    # address command_for handles must be advertised there.
    for addr in osc_map.INBOUND_ADDRESSES:
        assert command_for(addr, [1]) is not None, addr
