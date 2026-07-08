import pytest
import textwrap
import yaml
from gameshow.config import (
    parse_config, deep_merge, apply_scene_override,
    AppConfig,
)

MINIMAL_YAML = textwrap.dedent("""\
    service:
      osc_server_host: "0.0.0.0"
      osc_server_port: 21601
      dmx_osc_host: "localhost"
      dmx_osc_port: 21600
      obs_host: "localhost"
      obs_port: 4455
      obs_password: ""
      touchosc_host: "192.168.1.5"
      touchosc_port: 9000
    buzzers:
      buzz_timeout_seconds: 10.0
      players:
        - id: 1
          name: "P1"
          key: "1"
          enabled: true
        - id: 2
          name: "P2"
          key: "2"
          enabled: true
    state_machine:
      initial: idle
      global:
        clear: { to: idle, do: [clear_bans, clear_player] }
      states:
        idle:
          transitions: { buzz: locked }
        locked:
          behaviors: [countdown]
          transitions:
            countdown_expire: buzz_timeout
            correct: correct
            incorrect: { to: incorrect, do: [ban_current] }
        correct: { hold: 2.0, then: idle }
        incorrect: { hold: 2.0, then: idle }
        buzz_timeout:
          hold: 0.5
          then: { to: idle, do: [ban_current, clear_player], when_all_banned: idle }
    lighting:
      states:
        idle: "/palette/Idle/activate"
        locked: "/palette/Locked/activate"
    audio:
      default_background_volume: 0.7
      default_effect_volume: 1.0
      states: {}
    obs:
      states:
        idle: "Idle"
    show:
      scenes: []
""")


def load(yaml_str: str) -> dict:
    return yaml.safe_load(yaml_str)


def test_parse_config_returns_app_config():
    cfg = parse_config(load(MINIMAL_YAML))
    assert isinstance(cfg, AppConfig)
    assert cfg.service.osc_server_port == 21601
    assert len(cfg.buzzers.players) == 2
    assert cfg.buzzers.players[0].name == "P1"


def test_deep_merge_scalars_replace():
    base = {"a": 1, "b": {"x": 10, "y": 20}}
    override = {"b": {"x": 99}}
    result = deep_merge(base, override)
    assert result["b"]["x"] == 99
    assert result["b"]["y"] == 20
    assert result["a"] == 1


def test_deep_merge_players_by_id():
    base = {"players": [{"id": 1, "enabled": True}, {"id": 2, "enabled": True}]}
    override = {"players": [{"id": 2, "enabled": False}]}
    result = deep_merge(base, override)
    players = {p["id"]: p for p in result["players"]}
    assert players[1]["enabled"] is True
    assert players[2]["enabled"] is False


def test_all_enabled_false_disables_all_players():
    base = load(MINIMAL_YAML)
    scene = {"buzzers": {"all_enabled": False}}
    merged_raw = apply_scene_override(base, scene)
    cfg = parse_config(merged_raw)
    assert all(not p.enabled for p in cfg.buzzers.players)


def test_all_enabled_then_per_player_override():
    base = load(MINIMAL_YAML)
    scene = {"buzzers": {"all_enabled": False, "players": [{"id": 1, "enabled": True}]}}
    merged_raw = apply_scene_override(base, scene)
    cfg = parse_config(merged_raw)
    players = {p.id: p for p in cfg.buzzers.players}
    assert players[1].enabled is True
    assert players[2].enabled is False


def test_state_machine_parses_initial_and_states():
    sm = parse_config(load(MINIMAL_YAML)).state_machine
    assert sm.initial == "idle"
    assert set(sm.states) >= {"idle", "locked", "correct", "incorrect", "buzz_timeout"}


def test_string_transition_parses_to_transition_config():
    tr = parse_config(load(MINIMAL_YAML)).state_machine.states["idle"].transitions["buzz"]
    assert tr.to == "locked"
    assert tr.do == []
    assert tr.when_all_banned is None


def test_mapping_transition_parses_do_and_guard():
    tr = parse_config(load(MINIMAL_YAML)).state_machine.states["buzz_timeout"].then
    assert tr.to == "idle"
    assert tr.do == ["ban_current", "clear_player"]
    assert tr.when_all_banned == "idle"


def test_behaviors_and_hold_parsed():
    sm = parse_config(load(MINIMAL_YAML)).state_machine
    assert sm.states["locked"].behaviors == ["countdown"]
    assert sm.states["correct"].hold == 2.0
    assert sm.states["correct"].then.to == "idle"


def test_global_transitions_parsed():
    clear = parse_config(load(MINIMAL_YAML)).state_machine.global_["clear"]
    assert clear.to == "idle"
    assert clear.do == ["clear_bans", "clear_player"]


def test_missing_state_machine_raises():
    raw = load(MINIMAL_YAML)
    del raw["state_machine"]
    with pytest.raises(ValueError, match="state_machine"):
        parse_config(raw)


def test_missing_states_raises():
    raw = load(MINIMAL_YAML)
    del raw["state_machine"]["states"]
    with pytest.raises(ValueError, match="states"):
        parse_config(raw)


def test_missing_initial_raises():
    raw = load(MINIMAL_YAML)
    del raw["state_machine"]["initial"]
    with pytest.raises(ValueError, match="initial"):
        parse_config(raw)


def test_initial_not_in_states_raises():
    raw = load(MINIMAL_YAML)
    raw["state_machine"]["initial"] = "ghost"
    with pytest.raises(ValueError, match="ghost"):
        parse_config(raw)


def test_unknown_transition_target_raises():
    raw = load(MINIMAL_YAML)
    raw["state_machine"]["states"]["idle"]["transitions"]["buzz"] = "nowhere"
    with pytest.raises(ValueError, match="nowhere"):
        parse_config(raw)


def test_unknown_guard_target_raises():
    raw = load(MINIMAL_YAML)
    raw["state_machine"]["states"]["buzz_timeout"]["then"]["when_all_banned"] = "nowhere"
    with pytest.raises(ValueError, match="nowhere"):
        parse_config(raw)


def test_unknown_behavior_raises():
    raw = load(MINIMAL_YAML)
    raw["state_machine"]["states"]["locked"]["behaviors"] = ["teleport"]
    with pytest.raises(ValueError, match="teleport"):
        parse_config(raw)


def test_unknown_do_behavior_raises():
    raw = load(MINIMAL_YAML)
    raw["state_machine"]["states"]["locked"]["transitions"]["incorrect"]["do"] = ["explode"]
    with pytest.raises(ValueError, match="explode"):
        parse_config(raw)


def _with_library(raw: dict) -> dict:
    """Move the inline state_machine into a 'standard' library entry + reference it."""
    raw = dict(raw)
    raw["state_machines"] = {"standard": raw["state_machine"]}
    raw["state_machine"] = "standard"
    return raw


def test_inline_state_machine_still_parses():
    # The pre-library form (inline dict) must keep working.
    cfg = parse_config(load(MINIMAL_YAML))
    assert cfg.state_machine.initial == "idle"
    assert "locked" in cfg.state_machine.states


def test_state_machine_string_reference_resolves():
    cfg = parse_config(_with_library(load(MINIMAL_YAML)))
    assert cfg.state_machine.initial == "idle"
    assert "buzz_timeout" in cfg.state_machine.states


def test_state_machine_extends_merges_overrides():
    raw = _with_library(load(MINIMAL_YAML))
    raw["state_machine"] = {"extends": "standard",
                            "states": {"correct": {"hold": 9.0, "then": "idle"}}}
    cfg = parse_config(raw)
    assert cfg.state_machine.states["correct"].hold == 9.0   # override applied
    assert "buzz_timeout" in cfg.state_machine.states        # base states preserved


def test_unknown_machine_reference_raises():
    raw = _with_library(load(MINIMAL_YAML))
    raw["state_machine"] = "nope"
    with pytest.raises(ValueError, match="nope"):
        parse_config(raw)


def test_extends_unknown_base_raises():
    raw = _with_library(load(MINIMAL_YAML))
    raw["state_machine"] = {"extends": "ghost", "states": {}}
    with pytest.raises(ValueError, match="ghost"):
        parse_config(raw)


def test_malformed_library_entry_raises():
    raw = _with_library(load(MINIMAL_YAML))
    raw["state_machines"]["broken"] = {"states": {"idle": {}}}  # missing 'initial'
    with pytest.raises(ValueError, match="broken"):
        parse_config(raw)


def test_scene_lighting_states_deep_merge():
    base = load(MINIMAL_YAML)
    scene = {"lighting": {"states": {"locked": "/palette/CustomLocked/start"}}}
    merged_raw = apply_scene_override(base, scene)
    cfg = parse_config(merged_raw)
    assert cfg.lighting.states["locked"] == "/palette/CustomLocked/start"
    assert cfg.lighting.states["idle"] == "/palette/Idle/activate"


def test_no_control_surface_section_is_none():
    cfg = parse_config(load(MINIMAL_YAML))
    assert cfg.control_surface is None


CONTROL_SURFACE_YAML = MINIMAL_YAML + textwrap.dedent("""\
    control_surface:
      enabled: true
      brightness: 50
      font_path: "assets/Roboto.ttf"
      root:
        buttons:
          button_0:
            type: state
            label: "Clear"
            state: clear
          button_1:
            type: buzz
            label: "P1"
            player_id: 1
          button_5:
            type: page
            label: "Audio"
            page:
              buttons:
                button_0:
                  type: sound
                  label: "Applause"
                  path: "music/applause.mp3"
                button_1:
                  type: stop_sounds
                  label: "Stop"
""")


def test_control_surface_parsed_with_nested_page():
    cfg = parse_config(load(CONTROL_SURFACE_YAML))
    cs = cfg.control_surface
    assert cs is not None
    assert cs.enabled is True
    assert cs.brightness == 50
    assert cs.font_path == "assets/Roboto.ttf"

    # Buttons are a name -> spec mapping; the key (slot) is derived from a
    # ``button_<N>`` name. Iteration preserves declaration order.
    buttons = cs.root.buttons
    assert len(buttons) == 3
    assert buttons[0].name == "button_0"
    assert buttons[0].type == "state"
    assert buttons[0].state == "clear"
    assert buttons[0].key == 0          # derived from name
    assert buttons[1].name == "button_1"
    assert buttons[1].key == 1          # derived from name

    folder = buttons[2]
    assert folder.type == "page"
    assert folder.key == 5              # derived from "button_5"
    assert folder.page is not None
    assert [b.type for b in folder.page.buttons] == ["sound", "stop_sounds"]
    assert [b.key for b in folder.page.buttons] == [0, 1]
    assert folder.page.buttons[0].path == "music/applause.mp3"


def test_control_surface_label_options_default():
    raw = load(MINIMAL_YAML)
    raw["control_surface"] = {}
    cs = parse_config(raw).control_surface
    assert cs.label_align == "bottom"
    assert cs.label_wrap is False
    assert cs.label_marquee is True
    assert cs.font_size == 16
    assert cs.font_path is None
    assert cs.text_color == "white"
    assert cs.color == "black"
    assert cs.fa_size is None
    assert cs.fa_color is None


def test_control_surface_label_options_global():
    raw = load(MINIMAL_YAML)
    raw["control_surface"] = {"label_align": "center", "label_wrap": True,
                              "label_marquee": False, "font_size": 20,
                              "font_path": "assets/Roboto.ttf",
                              "text_color": "#FFCC00", "color": "#101010",
                              "fa_size": 36, "fa_color": "#00AAFF",
                              "root": {"buttons": {}}}
    cs = parse_config(raw).control_surface
    assert cs.label_align == "center"
    assert cs.label_wrap is True
    assert cs.label_marquee is False
    assert cs.font_size == 20
    assert cs.font_path == "assets/Roboto.ttf"
    assert cs.text_color == "#FFCC00"
    assert cs.color == "#101010"
    assert cs.fa_size == 36
    assert cs.fa_color == "#00AAFF"


def test_button_label_and_font_overrides():
    raw = load(MINIMAL_YAML)
    raw["control_surface"] = {"root": {"buttons": {
        "button_0": {"type": "state", "state": "clear", "label_align": "top",
                     "label_wrap": True, "label_marquee": False,
                     "font_path": "assets/Bold.ttf", "font_size": 24,
                     "text_color": "#00FF00"},
    }}}
    button = parse_config(raw).control_surface.root.buttons[0]
    assert button.label_align == "top"
    assert button.label_wrap is True
    assert button.label_marquee is False
    assert button.font_path == "assets/Bold.ttf"
    assert button.font_size == 24
    assert button.text_color == "#00FF00"


def test_button_pressed_overrides_parsed():
    raw = load(MINIMAL_YAML)
    raw["control_surface"] = {"root": {"buttons": {
        "button_0": {"type": "buzz", "player_id": 1, "label": "P1",
                     "color": "#111111",
                     "pressed": {"color": "#00FF00", "label": "IN",
                                 "text_color": "#000000", "fa_icon": "bell"}},
    }}}
    button = parse_config(raw).control_surface.root.buttons[0]
    assert button.color == "#111111"          # unchanged base value
    assert button.pressed is not None
    assert button.pressed.color == "#00FF00"
    assert button.pressed.label == "IN"
    assert button.pressed.text_color == "#000000"
    assert button.pressed.fa_icon == "bell"
    # Unset pressed fields stay None so they don't clobber base values.
    assert button.pressed.font_size is None


def test_button_without_pressed_section_is_none():
    raw = load(MINIMAL_YAML)
    raw["control_surface"] = {"root": {"buttons": {
        "button_0": {"type": "state", "state": "clear"},
    }}}
    assert parse_config(raw).control_surface.root.buttons[0].pressed is None


def test_font_awesome_config_parsed():
    raw = load(MINIMAL_YAML)
    raw["control_surface"] = {
        "fa_path": "icons/fa/pro", "fa_type": "duotone", "fa_weight": "light",
        "root": {"buttons": {
            "button_0": {"type": "state", "state": "clear", "fa_icon": "circle-user",
                         "fa_type": "sharp", "fa_weight": "thin",
                         "fa_size": 40, "fa_color": "#00FF00"},
        }},
    }
    cs = parse_config(raw).control_surface
    assert cs.fa_path == "icons/fa/pro"
    assert cs.fa_type == "duotone"
    assert cs.fa_weight == "light"
    button = cs.root.buttons[0]
    assert button.fa_icon == "circle-user"
    assert button.fa_type == "sharp"
    assert button.fa_weight == "thin"
    assert button.fa_size == 40
    assert button.fa_color == "#00FF00"


def test_font_awesome_defaults():
    raw = load(MINIMAL_YAML)
    raw["control_surface"] = {}
    cs = parse_config(raw).control_surface
    assert cs.fa_path is None
    assert cs.fa_type == "pro"
    assert cs.fa_weight == "solid"


def test_button_key_derived_from_name():
    raw = load(MINIMAL_YAML)
    raw["control_surface"] = {"root": {"buttons": {
        "button_7": {"type": "buzz", "player_id": 1},
    }}}
    cfg = parse_config(raw)
    assert cfg.control_surface.root.buttons[0].key == 7


def test_descriptive_name_yields_no_key():
    raw = load(MINIMAL_YAML)
    raw["control_surface"] = {"root": {"buttons": {
        "applause": {"type": "sound", "path": "a.mp3"},
    }}}
    cfg = parse_config(raw)
    # Non-"button_N" names carry no derived key → auto-placed at render time.
    assert cfg.control_surface.root.buttons[0].key is None


def test_explicit_key_overrides_name():
    raw = load(MINIMAL_YAML)
    raw["control_surface"] = {"root": {"buttons": {
        "button_3": {"type": "buzz", "player_id": 1, "key": 8},
    }}}
    cfg = parse_config(raw)
    assert cfg.control_surface.root.buttons[0].key == 8


def test_control_surface_defaults_when_minimal():
    raw = load(MINIMAL_YAML)
    raw["control_surface"] = {}
    cfg = parse_config(raw)
    assert cfg.control_surface is not None
    assert cfg.control_surface.enabled is True
    assert cfg.control_surface.brightness == 60
    assert cfg.control_surface.root.buttons == []
