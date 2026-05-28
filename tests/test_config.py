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
      return_to_after_correct: idle
      return_to_after_incorrect: idle
      return_to_after_buzz_timeout: idle
      return_to_after_round_start: idle
      correct_hold_seconds: 2.0
      incorrect_hold_seconds: 2.0
      buzz_timeout_hold_seconds: 3.0
      round_start_hold_seconds: 2.0
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


def test_invalid_return_to_raises():
    raw = load(MINIMAL_YAML)
    raw["state_machine"]["return_to_after_correct"] = "game_over"
    with pytest.raises(ValueError, match="return_to_after_correct"):
        parse_config(raw)


def test_scene_lighting_states_deep_merge():
    base = load(MINIMAL_YAML)
    scene = {"lighting": {"states": {"locked": "/palette/CustomLocked/start"}}}
    merged_raw = apply_scene_override(base, scene)
    cfg = parse_config(merged_raw)
    assert cfg.lighting.states["locked"] == "/palette/CustomLocked/start"
    assert cfg.lighting.states["idle"] == "/palette/Idle/activate"
