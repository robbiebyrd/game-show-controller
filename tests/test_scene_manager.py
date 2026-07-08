import asyncio
import pytest
import yaml
from gameshow.bus import EventBus
from gameshow.config import parse_config, apply_scene_override
from gameshow.events import SceneChanged
from gameshow.scene_manager import SceneManager

RAW_YAML = """
service:
  osc_server_host: "0.0.0.0"
  osc_server_port: 21601
  dmx_osc_host: localhost
  dmx_osc_port: 21600
  obs_host: localhost
  obs_port: 4455
  obs_password: ""
  touchosc_host: ""
  touchosc_port: 9000
buzzers:
  buzz_timeout_seconds: 10.0
  players:
    - {id: 1, name: P1, key: "1", enabled: true}
    - {id: 2, name: P2, key: "2", enabled: true}
state_machine:
  initial: idle
  global:
    clear: { to: idle, do: [clear_bans, clear_player] }
    game_over: { to: game_over, do: [clear_bans, clear_player] }
    round_start: round_start
    timed_lockout: timed_lockout
  states:
    idle:
      transitions: { buzz: locked }
    locked:
      behaviors: [countdown]
      transitions:
        countdown_expire: buzz_timeout
        correct: correct
        incorrect: { to: incorrect, do: [ban_current] }
        allow_next: { to: allow_next, do: [ban_current, clear_player], when_all_banned: idle }
    correct: { hold: 2.0, then: idle }
    incorrect: { hold: 2.0, then: idle, transitions: { buzz: locked } }
    allow_next: { transitions: { buzz: locked } }
    buzz_timeout: { hold: 3.0, then: { to: allow_next, do: [ban_current, clear_player], when_all_banned: idle } }
    timed_lockout: { hold_from_arg: 5.0, then: idle }
    round_start: { hold: 2.0, then: idle }
    game_over: {}
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
  scenes:
    - name: "Intro"
      buzzers:
        all_enabled: false
    - name: "Round 1"
      state_machine:
        states:
          incorrect:
            then: allow_next
    - name: "Round 2"
"""


def make_manager():
    raw = yaml.safe_load(RAW_YAML)
    base_config = parse_config(raw)
    bus = EventBus()
    return SceneManager(bus, raw, base_config), bus


@pytest.mark.asyncio
async def test_advance_moves_to_next_scene():
    sm, bus = make_manager()
    published = []
    async def capture(e): published.append(e)
    bus.subscribe(SceneChanged, capture)

    await sm.advance()
    assert sm.current_index == 1
    assert sm.current_scene_name == "Intro"
    assert any(e.name == "Intro" and e.index == 1 for e in published)


@pytest.mark.asyncio
async def test_advance_at_last_scene_stays():
    sm, bus = make_manager()
    await sm.goto_index(3)
    await sm.advance()
    assert sm.current_index == 3


@pytest.mark.asyncio
async def test_previous_moves_back():
    sm, bus = make_manager()
    await sm.goto_index(3)
    await sm.previous()
    assert sm.current_index == 2


@pytest.mark.asyncio
async def test_previous_at_start_stays():
    sm, bus = make_manager()
    await sm.previous()
    assert sm.current_index == 0


@pytest.mark.asyncio
async def test_goto_by_name():
    sm, bus = make_manager()
    await sm.goto_name("Round 1")
    assert sm.current_index == 2
    assert sm.current_scene_name == "Round 1"


@pytest.mark.asyncio
async def test_goto_unknown_name_is_ignored():
    sm, bus = make_manager()
    await sm.goto_name("Nonexistent")
    assert sm.current_index == 0  # unchanged


@pytest.mark.asyncio
async def test_goto_out_of_range_index_is_ignored():
    sm, bus = make_manager()
    await sm.goto_index(99)
    assert sm.current_index == 0


@pytest.mark.asyncio
async def test_scene_applies_override_to_config():
    sm, bus = make_manager()
    await sm.goto_name("Intro")
    cfg = sm.current_config
    assert all(not p.enabled for p in cfg.buzzers.players)


@pytest.mark.asyncio
async def test_scene_override_merges_state_machine():
    sm, bus = make_manager()
    await sm.goto_name("Round 1")
    cfg = sm.current_config
    assert cfg.state_machine.states["incorrect"].then.to == "allow_next"
    assert cfg.state_machine.states["correct"].then.to == "idle"  # global default preserved
