---
status: approved
created: 2026-05-28
validated_at: "2026-05-28T01:21:50.176Z"
updated: "2026-05-28T01:21:50.317Z"
approved_at: "2026-05-28T01:21:50.316Z"
---
# Game Show Control System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python background service that intercepts USB HID buzzer inputs, drives a game state machine, and controls DMX lighting, OBS Studio graphics, and audio playback via an event-driven asyncio architecture.

**Architecture:** A single asyncio process with a central typed event bus. Components publish and subscribe to events without calling each other directly. A ConfigProvider holds the current deep-merged config (global defaults + active scene overrides) and is consulted by all components.

**Tech Stack:** Python 3.11+, pynput, python-osc, pygame, simpleobsws, pyyaml, pytest, pytest-asyncio

---

## File Map

| File | Responsibility |
|---|---|
| `requirements.txt` | pinned dependencies |
| `config.yaml` | example show configuration |
| `gameshow/__init__.py` | empty package marker |
| `gameshow/events.py` | all typed event dataclasses + `GameState` enum |
| `gameshow/bus.py` | async pub/sub event bus |
| `gameshow/config.py` | YAML loader, dataclasses, deep-merge, ConfigProvider |
| `gameshow/state_machine.py` | game state, lockout rules, timers |
| `gameshow/scene_manager.py` | show rundown, scene navigation, SceneChanged events |
| `gameshow/keyboard.py` | pynput global hook → BuzzerPressed events |
| `gameshow/osc_server.py` | inbound OSC server (TouchOSC commands) |
| `gameshow/dmx_client.py` | outbound OSC → DMX lighting server |
| `gameshow/audio.py` | pygame.mixer two-channel playback |
| `gameshow/obs_client.py` | simpleobsws OBS WebSocket v5 client |
| `main.py` | entry point, wires all components |
| `tests/test_events.py` | event dataclass creation |
| `tests/test_bus.py` | pub/sub correctness |
| `tests/test_config.py` | YAML loading, deep-merge, validation |
| `tests/test_state_machine.py` | all state transitions and timer behaviour |
| `tests/test_scene_manager.py` | scene navigation, error handling |
| `tests/test_keyboard.py` | key→player mapping (not the pynput hook) |
| `tests/test_osc_server.py` | OSC address → event translation |
| `tests/test_dmx_client.py` | StateChanged → OSC cue |
| `tests/test_audio.py` | StateChanged → pygame.mixer calls |
| `tests/test_obs_client.py` | StateChanged → OBS scene switch |

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `config.yaml`
- Create: `gameshow/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `requirements.txt`**

```
pyyaml>=6.0
pynput>=1.7
python-osc>=1.8
pygame>=2.5
simpleobsws>=1.5
pytest>=8.0
pytest-asyncio>=0.23
```

- [ ] **Step 2: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 3: Create package files**

`gameshow/__init__.py` — empty file.
`tests/__init__.py` — empty file.

- [ ] **Step 4: Create `tests/conftest.py`**

```python
import pytest

pytest_plugins = ("pytest_asyncio",)
```

- [ ] **Step 5: Create `config.yaml`**

```yaml
service:
  osc_server_host: "0.0.0.0"
  osc_server_port: 21601
  dmx_osc_host: "localhost"
  dmx_osc_port: 21600
  obs_host: "localhost"
  obs_port: 4455
  obs_password: ""
  touchosc_host: "192.168.1.100"
  touchosc_port: 9000

buzzers:
  buzz_timeout_seconds: 10.0
  players:
    - id: 1
      name: "Player 1"
      key: "1"
      enabled: true
    - id: 2
      name: "Player 2"
      key: "2"
      enabled: true
    - id: 3
      name: "Player 3"
      key: "3"
      enabled: false
    - id: 4
      name: "Player 4"
      key: "4"
      enabled: false

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
    idle:          "/palette/Idle/activate"
    player_1_buzz: "/palette/Buzz_P1/start"
    player_2_buzz: "/palette/Buzz_P2/start"
    player_3_buzz: "/palette/Buzz_P3/start"
    player_4_buzz: "/palette/Buzz_P4/start"
    locked:        "/palette/Locked/activate"
    correct:       "/palette/Correct/start"
    incorrect:     "/palette/Incorrect/start"
    allow_next:    "/palette/AllowNext/activate"
    buzz_timeout:  "/palette/BuzzTimeout/start"
    timed_lockout: "/palette/TimedLockout/activate"
    round_start:   "/palette/RoundStart/activate"
    game_over:     "/palette/GameOver/activate"

audio:
  default_background_volume: 0.7
  default_effect_volume: 1.0
  states:
    player_1_buzz:
      effect: "sounds/buzz_p1.mp3"
    player_2_buzz:
      effect: "sounds/buzz_p2.mp3"
    correct:
      effect: "sounds/correct.mp3"
    incorrect:
      effect: "sounds/incorrect.mp3"
    buzz_timeout:
      effect: "sounds/bong.mp3"
    round_start:
      background: "music/round_theme.mp3"
    game_over:
      background: "music/game_over.mp3"

obs:
  states:
    idle:          "Idle"
    locked:        "Buzz_Locked"
    correct:       "Correct"
    incorrect:     "Incorrect"
    allow_next:    "Allow_Next"
    buzz_timeout:  "Buzz_Timeout"
    timed_lockout: "Timed_Lockout"
    round_start:   "Round_Start"
    game_over:     "Game_Over"

show:
  scenes:
    - name: "Intro"
      on_enter:
        audio_background: "music/intro_theme.mp3"
        obs_scene: "Intro_Screen"
        lighting: "/palette/Intro/activate"
      buzzers:
        all_enabled: false
    - name: "Face Off"
      on_enter:
        obs_scene: "FaceOff_Ready"
        lighting: "/palette/FaceOff/activate"
      buzzers:
        buzz_timeout_seconds: null
      lighting:
        states:
          locked: "/palette/FaceOff_Buzz/start"
      obs:
        states:
          locked: "FaceOff_Buzz"
          correct: "FaceOff_Correct"
    - name: "Round 1"
      on_enter:
        audio_background: "music/round1_theme.mp3"
        obs_scene: "Round1_Board"
      state_machine:
        return_to_after_incorrect: allow_next
      buzzers:
        buzz_timeout_seconds: 8.0
```

- [ ] **Step 6: Create placeholder directories**

```bash
mkdir -p sounds music
```

- [ ] **Step 7: Commit**

```bash
git add requirements.txt config.yaml gameshow/ tests/
git commit -m "feat: project scaffold with dependencies and example config"
```

---

## Task 2: Event Types

**Files:**
- Create: `gameshow/events.py`
- Create: `tests/test_events.py`

- [ ] **Step 1: Write the failing test**

`tests/test_events.py`:
```python
from gameshow.events import GameState, BuzzerPressed, PlayerBuzzed, StateChanged, SceneChanged, ControlCommand

def test_game_state_enum_has_all_states():
    states = {s.name for s in GameState}
    assert states == {
        "IDLE", "LOCKED", "ALLOW_NEXT", "CORRECT", "INCORRECT",
        "BUZZ_TIMEOUT", "TIMED_LOCKOUT", "ROUND_START", "GAME_OVER"
    }

def test_buzzer_pressed_is_frozen():
    e = BuzzerPressed(player_id=1)
    try:
        e.player_id = 2  # type: ignore
        assert False, "should be frozen"
    except Exception:
        pass

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
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_events.py -v
```

Expected: `ModuleNotFoundError: No module named 'gameshow.events'`

- [ ] **Step 3: Implement `gameshow/events.py`**

```python
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class GameState(Enum):
    IDLE = auto()
    LOCKED = auto()
    ALLOW_NEXT = auto()
    CORRECT = auto()
    INCORRECT = auto()
    BUZZ_TIMEOUT = auto()
    TIMED_LOCKOUT = auto()
    ROUND_START = auto()
    GAME_OVER = auto()


@dataclass(frozen=True)
class BuzzerPressed:
    player_id: int


@dataclass(frozen=True)
class PlayerBuzzed:
    player_id: int
    player_name: str


@dataclass(frozen=True)
class StateChanged:
    new_state: GameState
    player_id: Optional[int] = None
    duration: Optional[float] = None  # set for TIMED_LOCKOUT; carries duration seconds


@dataclass(frozen=True)
class SceneChanged:
    index: int  # 1-based
    name: str


@dataclass(frozen=True)
class ControlCommand:
    command: str
    args: tuple = field(default_factory=tuple)
```

- [ ] **Step 4: Run tests to verify passing**

```bash
pytest tests/test_events.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add gameshow/events.py tests/test_events.py
git commit -m "feat: event type definitions"
```

---

## Task 3: Event Bus

**Files:**
- Create: `gameshow/bus.py`
- Create: `tests/test_bus.py`

- [ ] **Step 1: Write the failing test**

`tests/test_bus.py`:
```python
import asyncio
import pytest
from gameshow.bus import EventBus
from gameshow.events import BuzzerPressed, StateChanged, GameState


@pytest.mark.asyncio
async def test_subscriber_called_on_matching_event():
    bus = EventBus()
    received = []

    async def handler(event: BuzzerPressed):
        received.append(event)

    bus.subscribe(BuzzerPressed, handler)
    await bus.publish(BuzzerPressed(player_id=1))

    assert len(received) == 1
    assert received[0].player_id == 1


@pytest.mark.asyncio
async def test_subscriber_not_called_for_other_event_type():
    bus = EventBus()
    received = []

    async def handler(event: BuzzerPressed):
        received.append(event)

    bus.subscribe(BuzzerPressed, handler)
    await bus.publish(StateChanged(new_state=GameState.IDLE))

    assert len(received) == 0


@pytest.mark.asyncio
async def test_multiple_subscribers_all_called():
    bus = EventBus()
    calls = []

    async def h1(e): calls.append(1)
    async def h2(e): calls.append(2)

    bus.subscribe(BuzzerPressed, h1)
    bus.subscribe(BuzzerPressed, h2)
    await bus.publish(BuzzerPressed(player_id=1))

    assert sorted(calls) == [1, 2]
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_bus.py -v
```

Expected: `ModuleNotFoundError: No module named 'gameshow.bus'`

- [ ] **Step 3: Implement `gameshow/bus.py`**

```python
from typing import Any, Callable, Awaitable


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[type, list[Callable[[Any], Awaitable[None]]]] = {}

    def subscribe(self, event_type: type, handler: Callable[[Any], Awaitable[None]]) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    async def publish(self, event: Any) -> None:
        for handler in self._subscribers.get(type(event), []):
            await handler(event)
```

- [ ] **Step 4: Run tests to verify passing**

```bash
pytest tests/test_bus.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add gameshow/bus.py tests/test_bus.py
git commit -m "feat: asyncio event bus"
```

---

## Task 4: Configuration System

**Files:**
- Create: `gameshow/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_config.py`:
```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'gameshow.config'`

- [ ] **Step 3: Implement `gameshow/config.py`**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import yaml


VALID_RETURN_TARGETS = {"idle", "allow_next"}


@dataclass
class ServiceConfig:
    osc_server_host: str = "0.0.0.0"
    osc_server_port: int = 21601
    dmx_osc_host: str = "localhost"
    dmx_osc_port: int = 21600
    obs_host: str = "localhost"
    obs_port: int = 4455
    obs_password: str = ""
    touchosc_host: str = ""
    touchosc_port: int = 9000


@dataclass
class PlayerConfig:
    id: int
    name: str
    key: str
    enabled: bool = True


@dataclass
class BuzzerConfig:
    players: list[PlayerConfig]
    buzz_timeout_seconds: Optional[float] = 10.0


@dataclass
class StateMachineConfig:
    return_to_after_correct: str = "idle"
    return_to_after_incorrect: str = "idle"
    return_to_after_buzz_timeout: str = "idle"
    return_to_after_round_start: str = "idle"
    correct_hold_seconds: float = 2.0
    incorrect_hold_seconds: float = 2.0
    buzz_timeout_hold_seconds: float = 3.0
    round_start_hold_seconds: float = 2.0


@dataclass
class LightingConfig:
    states: dict[str, str] = field(default_factory=dict)


@dataclass
class AudioStateEntry:
    effect: Optional[str] = None
    background: Optional[str] = None


@dataclass
class AudioConfig:
    default_background_volume: float = 0.7
    default_effect_volume: float = 1.0
    states: dict[str, AudioStateEntry] = field(default_factory=dict)


@dataclass
class OBSConfig:
    states: dict[str, str] = field(default_factory=dict)


@dataclass
class OnEnterConfig:
    audio_background: Optional[str] = None
    obs_scene: Optional[str] = None
    lighting: Optional[str] = None


@dataclass
class SceneConfig:
    name: str
    on_enter: OnEnterConfig = field(default_factory=OnEnterConfig)
    _raw_override: dict = field(default_factory=dict, repr=False)


@dataclass
class AppConfig:
    service: ServiceConfig
    buzzers: BuzzerConfig
    state_machine: StateMachineConfig
    lighting: LightingConfig
    audio: AudioConfig
    obs: OBSConfig
    scenes: list[SceneConfig] = field(default_factory=list)


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key == "players" and isinstance(value, list):
            base_players = {p["id"]: dict(p) for p in result.get("players", [])}
            for player_override in value:
                pid = player_override["id"]
                if pid in base_players:
                    base_players[pid].update(player_override)
                else:
                    base_players[pid] = dict(player_override)
            result["players"] = list(base_players.values())
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def apply_scene_override(base_raw: dict, scene_raw: dict) -> dict:
    override = {k: v for k, v in scene_raw.items() if k not in ("name", "on_enter")}
    if "buzzers" in override:
        buzzers = dict(override["buzzers"])
        if "all_enabled" in buzzers:
            all_enabled = buzzers.pop("all_enabled")
            base_players = base_raw.get("buzzers", {}).get("players", [])
            shorthand = [{"id": p["id"], "enabled": all_enabled} for p in base_players]
            existing_ids = {p["id"] for p in buzzers.get("players", [])}
            extra = [p for p in shorthand if p["id"] not in existing_ids]
            buzzers["players"] = extra + buzzers.get("players", [])
        override["buzzers"] = buzzers
    return deep_merge(base_raw, override)


def _validate_return_targets(sm: StateMachineConfig) -> None:
    for attr in ("return_to_after_correct", "return_to_after_incorrect",
                 "return_to_after_buzz_timeout", "return_to_after_round_start"):
        value = getattr(sm, attr)
        if value not in VALID_RETURN_TARGETS:
            raise ValueError(
                f"{attr}='{value}' is not valid; must be one of {sorted(VALID_RETURN_TARGETS)}"
            )


def parse_config(raw: dict) -> AppConfig:
    svc_raw = raw.get("service", {})
    service = ServiceConfig(**{k: v for k, v in svc_raw.items()
                               if k in ServiceConfig.__dataclass_fields__})

    bz_raw = raw.get("buzzers", {})
    players = [PlayerConfig(**{k: v for k, v in p.items()
                               if k in PlayerConfig.__dataclass_fields__})
               for p in bz_raw.get("players", [])]
    buzzers = BuzzerConfig(
        players=players,
        buzz_timeout_seconds=bz_raw.get("buzz_timeout_seconds", 10.0),
    )

    sm_raw = raw.get("state_machine", {})
    state_machine = StateMachineConfig(**{k: v for k, v in sm_raw.items()
                                         if k in StateMachineConfig.__dataclass_fields__})
    _validate_return_targets(state_machine)

    lighting = LightingConfig(states=raw.get("lighting", {}).get("states", {}))

    audio_raw = raw.get("audio", {})
    audio_states = {
        k: AudioStateEntry(effect=v.get("effect"), background=v.get("background"))
        for k, v in audio_raw.get("states", {}).items()
    }
    audio = AudioConfig(
        default_background_volume=audio_raw.get("default_background_volume", 0.7),
        default_effect_volume=audio_raw.get("default_effect_volume", 1.0),
        states=audio_states,
    )

    obs = OBSConfig(states=raw.get("obs", {}).get("states", {}))

    scenes = []
    for s in raw.get("show", {}).get("scenes", []):
        on_enter_raw = s.get("on_enter", {})
        on_enter = OnEnterConfig(
            audio_background=on_enter_raw.get("audio_background"),
            obs_scene=on_enter_raw.get("obs_scene"),
            lighting=on_enter_raw.get("lighting"),
        )
        raw_override = {k: v for k, v in s.items() if k != "name"}
        scenes.append(SceneConfig(name=s["name"], on_enter=on_enter,
                                  _raw_override=raw_override))

    return AppConfig(
        service=service, buzzers=buzzers, state_machine=state_machine,
        lighting=lighting, audio=audio, obs=obs, scenes=scenes,
    )


def load_config(path: str) -> tuple[dict, AppConfig]:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return raw, parse_config(raw)
```

- [ ] **Step 4: Run tests to verify passing**

```bash
pytest tests/test_config.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add gameshow/config.py tests/test_config.py
git commit -m "feat: YAML config loading with deep-merge and validation"
```

---

## Task 5: State Machine

**Files:**
- Create: `gameshow/state_machine.py`
- Create: `tests/test_state_machine.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_state_machine.py`:
```python
import asyncio
import pytest
from unittest.mock import AsyncMock
from gameshow.bus import EventBus
from gameshow.events import (
    BuzzerPressed, PlayerBuzzed, StateChanged, ControlCommand, GameState
)
from gameshow.state_machine import StateMachine
from gameshow.config import (
    AppConfig, ServiceConfig, BuzzerConfig, PlayerConfig,
    StateMachineConfig, LightingConfig, AudioConfig, OBSConfig
)


def make_config(
    buzz_timeout_seconds=None,
    correct_hold=0.05,
    incorrect_hold=0.05,
    buzz_timeout_hold=0.05,
    round_start_hold=0.05,
    return_correct="idle",
    return_incorrect="idle",
    return_buzz_timeout="idle",
    return_round_start="idle",
    players=None,
):
    if players is None:
        players = [
            PlayerConfig(id=1, name="P1", key="1", enabled=True),
            PlayerConfig(id=2, name="P2", key="2", enabled=True),
        ]
    return AppConfig(
        service=ServiceConfig(),
        buzzers=BuzzerConfig(players=players, buzz_timeout_seconds=buzz_timeout_seconds),
        state_machine=StateMachineConfig(
            correct_hold_seconds=correct_hold,
            incorrect_hold_seconds=incorrect_hold,
            buzz_timeout_hold_seconds=buzz_timeout_hold,
            round_start_hold_seconds=round_start_hold,
            return_to_after_correct=return_correct,
            return_to_after_incorrect=return_incorrect,
            return_to_after_buzz_timeout=return_buzz_timeout,
            return_to_after_round_start=return_round_start,
        ),
        lighting=LightingConfig(),
        audio=AudioConfig(),
        obs=OBSConfig(),
        scenes=[],
    )


@pytest.mark.asyncio
async def test_idle_buzz_emits_player_buzzed_and_state_changed_locked():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    events = []
    bus.subscribe(PlayerBuzzed, lambda e: events.append(e) or asyncio.sleep(0))
    bus.subscribe(StateChanged, lambda e: events.append(e) or asyncio.sleep(0))

    published = []
    async def capture(e): published.append(e)
    bus.subscribe(PlayerBuzzed, capture)
    bus.subscribe(StateChanged, capture)

    await bus.publish(BuzzerPressed(player_id=1))

    assert any(isinstance(e, PlayerBuzzed) and e.player_id == 1 for e in published)
    assert any(isinstance(e, StateChanged) and e.new_state == GameState.LOCKED for e in published)
    assert sm.state == GameState.LOCKED

    await sm.stop()


@pytest.mark.asyncio
async def test_second_buzz_in_locked_is_ignored():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    published = []
    async def capture(e): published.append(e)
    bus.subscribe(StateChanged, capture)

    await bus.publish(BuzzerPressed(player_id=1))
    published.clear()
    await bus.publish(BuzzerPressed(player_id=2))

    assert len(published) == 0
    assert sm.state == GameState.LOCKED

    await sm.stop()


@pytest.mark.asyncio
async def test_correct_from_locked_transitions_and_auto_returns():
    bus = EventBus()
    config = make_config(correct_hold=0.05, return_correct="idle")
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="correct"))
    assert sm.state == GameState.CORRECT

    await asyncio.sleep(0.15)
    assert sm.state == GameState.IDLE

    await sm.stop()


@pytest.mark.asyncio
async def test_incorrect_from_locked_auto_returns():
    bus = EventBus()
    config = make_config(incorrect_hold=0.05)
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="incorrect"))
    await asyncio.sleep(0.15)
    assert sm.state == GameState.IDLE

    await sm.stop()


@pytest.mark.asyncio
async def test_allow_next_from_locked_bans_player_and_allows_others():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="allow_next"))
    assert sm.state == GameState.ALLOW_NEXT

    await bus.publish(BuzzerPressed(player_id=1))
    assert sm.state == GameState.ALLOW_NEXT  # still banned

    await bus.publish(BuzzerPressed(player_id=2))
    assert sm.state == GameState.LOCKED
    assert sm.locked_player_id == 2

    await sm.stop()


@pytest.mark.asyncio
async def test_allow_next_exhaustion_returns_to_idle():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="allow_next"))
    await bus.publish(BuzzerPressed(player_id=2))
    await bus.publish(ControlCommand(command="allow_next"))

    assert sm.state == GameState.IDLE

    await sm.stop()


@pytest.mark.asyncio
async def test_allow_next_outside_locked_is_ignored():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    assert sm.state == GameState.IDLE
    await bus.publish(ControlCommand(command="allow_next"))
    assert sm.state == GameState.IDLE

    await sm.stop()


@pytest.mark.asyncio
async def test_clear_from_any_state_goes_to_idle():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    assert sm.state == GameState.LOCKED
    await bus.publish(ControlCommand(command="clear"))
    assert sm.state == GameState.IDLE

    await sm.stop()


@pytest.mark.asyncio
async def test_buzz_timeout_fires_after_delay():
    bus = EventBus()
    config = make_config(buzz_timeout_seconds=0.05, buzz_timeout_hold=0.05)
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await asyncio.sleep(0.2)
    assert sm.state == GameState.IDLE  # timeout fired and auto-returned

    await sm.stop()


@pytest.mark.asyncio
async def test_host_input_cancels_buzz_timeout():
    bus = EventBus()
    config = make_config(buzz_timeout_seconds=0.2)
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await asyncio.sleep(0.05)
    await bus.publish(ControlCommand(command="correct"))
    assert sm.state == GameState.CORRECT  # not BUZZ_TIMEOUT

    await sm.stop()


@pytest.mark.asyncio
async def test_any_transition_cancels_transient_timer():
    bus = EventBus()
    config = make_config(correct_hold=1.0)  # long hold
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="correct"))
    assert sm.state == GameState.CORRECT

    await bus.publish(ControlCommand(command="clear"))
    assert sm.state == GameState.IDLE

    await asyncio.sleep(0.1)
    assert sm.state == GameState.IDLE  # no ghost timer

    await sm.stop()


@pytest.mark.asyncio
async def test_timed_lockout_auto_returns_to_idle():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(ControlCommand(command="timed_lockout", args=(0.05,)))
    assert sm.state == GameState.TIMED_LOCKOUT
    await asyncio.sleep(0.15)
    assert sm.state == GameState.IDLE

    await sm.stop()


@pytest.mark.asyncio
async def test_game_over_only_exits_via_clear():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(ControlCommand(command="game_over"))
    assert sm.state == GameState.GAME_OVER

    await bus.publish(BuzzerPressed(player_id=1))
    assert sm.state == GameState.GAME_OVER  # buzz does nothing

    await bus.publish(ControlCommand(command="clear"))
    assert sm.state == GameState.IDLE

    await sm.stop()
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_state_machine.py -v
```

Expected: `ModuleNotFoundError: No module named 'gameshow.state_machine'`

- [ ] **Step 3: Implement `gameshow/state_machine.py`**

```python
from __future__ import annotations
import asyncio
from typing import Optional, Callable
from gameshow.bus import EventBus
from gameshow.config import AppConfig, StateMachineConfig
from gameshow.events import (
    BuzzerPressed, PlayerBuzzed, StateChanged, ControlCommand, GameState
)

_TRANSIENT_HOLD_MAP = {
    GameState.CORRECT: lambda sm: sm._config().state_machine.correct_hold_seconds,
    GameState.INCORRECT: lambda sm: sm._config().state_machine.incorrect_hold_seconds,
    GameState.BUZZ_TIMEOUT: lambda sm: sm._config().state_machine.buzz_timeout_hold_seconds,
    GameState.ROUND_START: lambda sm: sm._config().state_machine.round_start_hold_seconds,
}

_RETURN_TO_MAP = {
    GameState.CORRECT: lambda sm: sm._config().state_machine.return_to_after_correct,
    GameState.INCORRECT: lambda sm: sm._config().state_machine.return_to_after_incorrect,
    GameState.BUZZ_TIMEOUT: lambda sm: sm._config().state_machine.return_to_after_buzz_timeout,
    GameState.ROUND_START: lambda sm: sm._config().state_machine.return_to_after_round_start,
}

_STATE_NAME_TO_ENUM = {s.name.lower(): s for s in GameState}


class StateMachine:
    def __init__(self, bus: EventBus, config: Callable[[], AppConfig]) -> None:
        self._bus = bus
        self._config = config
        self.state = GameState.IDLE
        self.locked_player_id: Optional[int] = None
        self._banned: set[int] = set()
        self._timer: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._bus.subscribe(BuzzerPressed, self._on_buzzer_pressed)
        self._bus.subscribe(ControlCommand, self._on_control_command)

    async def stop(self) -> None:
        self._cancel_timer()

    def _cancel_timer(self) -> None:
        if self._timer and not self._timer.done():
            self._timer.cancel()
        self._timer = None

    def _enabled_player_ids(self) -> set[int]:
        return {p.id for p in self._config().buzzers.players if p.enabled}

    def _player_name(self, player_id: int) -> str:
        for p in self._config().buzzers.players:
            if p.id == player_id:
                return p.name
        return str(player_id)

    async def _enter_state(self, new_state: GameState, player_id: Optional[int] = None) -> None:
        self._cancel_timer()
        self.state = new_state

        await self._bus.publish(StateChanged(new_state=new_state, player_id=player_id))

        if new_state in _TRANSIENT_HOLD_MAP:
            hold = _TRANSIENT_HOLD_MAP[new_state](self)
            return_to = _RETURN_TO_MAP[new_state](self)
            self._timer = asyncio.create_task(self._auto_return(hold, return_to))
        elif new_state == GameState.TIMED_LOCKOUT:
            pass  # timer set by caller

    async def _auto_return(self, delay: float, return_to: str) -> None:
        await asyncio.sleep(delay)
        target = _STATE_NAME_TO_ENUM.get(return_to, GameState.IDLE)
        await self._enter_state(target)

    async def _on_buzzer_pressed(self, event: BuzzerPressed) -> None:
        pid = event.player_id
        enabled = self._enabled_player_ids()
        if pid not in enabled:
            return

        if self.state == GameState.IDLE:
            await self._lock_player(pid)
        elif self.state == GameState.ALLOW_NEXT and pid not in self._banned:
            await self._lock_player(pid)

    async def _lock_player(self, player_id: int) -> None:
        self.locked_player_id = player_id
        await self._bus.publish(PlayerBuzzed(
            player_id=player_id, player_name=self._player_name(player_id)
        ))

        cfg = self._config()
        if cfg.buzzers.buzz_timeout_seconds is not None:
            timeout = cfg.buzzers.buzz_timeout_seconds
            self._cancel_timer()
            self.state = GameState.LOCKED
            await self._bus.publish(StateChanged(new_state=GameState.LOCKED, player_id=player_id))
            self._timer = asyncio.create_task(self._buzz_timeout(timeout))
        else:
            self.state = GameState.LOCKED
            await self._bus.publish(StateChanged(new_state=GameState.LOCKED, player_id=player_id))

    async def _buzz_timeout(self, delay: float) -> None:
        await asyncio.sleep(delay)
        await self._enter_state(GameState.BUZZ_TIMEOUT, self.locked_player_id)

    async def _on_control_command(self, event: ControlCommand) -> None:
        cmd = event.command

        if cmd == "clear":
            self._banned.clear()
            self.locked_player_id = None
            await self._enter_state(GameState.IDLE)
            return

        if cmd == "game_over":
            self._banned.clear()
            self.locked_player_id = None
            await self._enter_state(GameState.GAME_OVER)
            return

        if cmd == "round_start":
            await self._enter_state(GameState.ROUND_START)
            return

        if cmd == "timed_lockout":
            duration = float(event.args[0]) if event.args else 5.0
            self._cancel_timer()
            self.state = GameState.TIMED_LOCKOUT
            await self._bus.publish(StateChanged(new_state=GameState.TIMED_LOCKOUT, duration=duration))
            self._timer = asyncio.create_task(self._auto_return(duration, "idle"))
            return

        if self.state != GameState.LOCKED:
            return  # correct, incorrect, allow_next ignored outside LOCKED

        if cmd == "correct":
            await self._enter_state(GameState.CORRECT, self.locked_player_id)
        elif cmd == "incorrect":
            await self._enter_state(GameState.INCORRECT, self.locked_player_id)
        elif cmd == "allow_next":
            self._banned.add(self.locked_player_id)
            enabled = self._enabled_player_ids()
            if self._banned >= enabled:
                self._banned.clear()
                self.locked_player_id = None
                await self._enter_state(GameState.IDLE)
            else:
                self.locked_player_id = None
                await self._enter_state(GameState.ALLOW_NEXT)
```

- [ ] **Step 4: Run tests to verify passing**

```bash
pytest tests/test_state_machine.py -v
```

Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add gameshow/state_machine.py tests/test_state_machine.py
git commit -m "feat: game state machine with timers and lockout rules"
```

---

## Task 6: Scene Manager

**Files:**
- Create: `gameshow/scene_manager.py`
- Create: `tests/test_scene_manager.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_scene_manager.py`:
```python
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
  scenes:
    - name: "Intro"
      buzzers:
        all_enabled: false
    - name: "Round 1"
      state_machine:
        return_to_after_incorrect: allow_next
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
    assert cfg.state_machine.return_to_after_incorrect == "allow_next"
    assert cfg.state_machine.return_to_after_correct == "idle"  # global default preserved
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_scene_manager.py -v
```

- [ ] **Step 3: Implement `gameshow/scene_manager.py`**

```python
from __future__ import annotations
import logging
from typing import Optional
from gameshow.bus import EventBus
from gameshow.config import AppConfig, SceneConfig, parse_config, apply_scene_override
from gameshow.events import SceneChanged

log = logging.getLogger(__name__)


class SceneManager:
    def __init__(self, bus: EventBus, base_raw: dict, base_config: AppConfig) -> None:
        self._bus = bus
        self._base_raw = base_raw
        self._base_config = base_config
        self.current_index: int = 0  # 0 = no scene selected
        self._scenes: list[SceneConfig] = base_config.scenes
        self.current_config: AppConfig = base_config

    @property
    def current_scene_name(self) -> Optional[str]:
        if self.current_index == 0:
            return None
        return self._scenes[self.current_index - 1].name

    async def advance(self) -> None:
        if self.current_index >= len(self._scenes):
            log.warning("Already at last scene; advance ignored")
            return
        await self.goto_index(self.current_index + 1)

    async def previous(self) -> None:
        if self.current_index <= 1:
            log.warning("Already at first scene; previous ignored")
            return
        await self.goto_index(self.current_index - 1)

    async def goto_index(self, index: int) -> None:
        if index < 1 or index > len(self._scenes):
            log.warning("Scene index %d out of range (1–%d); ignored", index, len(self._scenes))
            return
        self.current_index = index
        scene = self._scenes[index - 1]
        self._apply(scene)
        await self._bus.publish(SceneChanged(index=index, name=scene.name))

    async def goto_name(self, name: str) -> None:
        for i, scene in enumerate(self._scenes, start=1):
            if scene.name == name:
                await self.goto_index(i)
                return
        log.warning("Scene name %r not found; ignored", name)

    def _apply(self, scene: SceneConfig) -> None:
        merged_raw = apply_scene_override(self._base_raw, scene._raw_override)
        self.current_config = parse_config(merged_raw)
```

- [ ] **Step 4: Run tests to verify passing**

```bash
pytest tests/test_scene_manager.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add gameshow/scene_manager.py tests/test_scene_manager.py
git commit -m "feat: scene manager with show rundown and deep-merge config"
```

---

## Task 7: Keyboard Listener

**Files:**
- Create: `gameshow/keyboard.py`
- Create: `tests/test_keyboard.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_keyboard.py`:
```python
import asyncio
import pytest
from unittest.mock import MagicMock, patch
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
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_keyboard.py -v
```

- [ ] **Step 3: Implement `gameshow/keyboard.py`**

```python
from __future__ import annotations
import asyncio
from typing import Callable, Optional
from pynput import keyboard
from gameshow.bus import EventBus
from gameshow.config import AppConfig
from gameshow.events import BuzzerPressed


class KeyboardListener:
    def __init__(self, bus: EventBus, config: Callable[[], AppConfig]) -> None:
        self._bus = bus
        self._config = config
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._listener: Optional[keyboard.Listener] = None
        self._key_map: dict[str, int] = {}

    def _build_key_map(self) -> dict[str, int]:
        return {
            p.key: p.id
            for p in self._config().buzzers.players
            if p.enabled
        }

    async def _on_key(self, key_char: str) -> None:
        key_map = self._build_key_map()
        player_id = key_map.get(key_char)
        if player_id is not None:
            await self._bus.publish(BuzzerPressed(player_id=player_id))

    def _handle_key(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        try:
            char = key.char
        except AttributeError:
            return
        if char and self._loop:
            asyncio.run_coroutine_threadsafe(self._on_key(char), self._loop)

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._listener = keyboard.Listener(on_press=self._handle_key)
        self._listener.start()

    async def stop(self) -> None:
        if self._listener:
            self._listener.stop()
```

- [ ] **Step 4: Run tests to verify passing**

```bash
pytest tests/test_keyboard.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add gameshow/keyboard.py tests/test_keyboard.py
git commit -m "feat: pynput global keyboard listener with key-to-player mapping"
```

---

## Task 8: Inbound OSC Server

**Files:**
- Create: `gameshow/osc_server.py`
- Create: `tests/test_osc_server.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_osc_server.py`:
```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_osc_server.py -v
```

- [ ] **Step 3: Implement `gameshow/osc_server.py`**

```python
from __future__ import annotations
import asyncio
from typing import Any, Callable
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
from gameshow.bus import EventBus
from gameshow.config import AppConfig
from gameshow.events import ControlCommand, SceneChanged, StateChanged, PlayerBuzzed, GameState

_SIMPLE_COMMANDS = {
    "/buzzer/clear": "clear",
    "/buzzer/allow_next": "allow_next",
    "/buzzer/correct": "correct",
    "/buzzer/incorrect": "incorrect",
    "/buzzer/round_start": "round_start",
    "/buzzer/game_over": "game_over",
    "/show/advance": "scene_advance",
    "/show/previous": "scene_previous",
    "/show/current": "scene_current",
    "/audio/background/stop": "audio_bg_stop",
    "/audio/effect/stop": "audio_fx_stop",
}


class OSCServer:
    def __init__(self, bus: EventBus, config: Callable[[], AppConfig]) -> None:
        self._bus = bus
        self._config = config
        self._server = None
        self._feedback_client: SimpleUDPClient | None = None
        self._setup_feedback()
        self._setup_feedback_subscriptions()

    def _setup_feedback(self) -> None:
        svc = self._config().service
        if svc.touchosc_host:
            self._feedback_client = SimpleUDPClient(svc.touchosc_host, svc.touchosc_port)

    def _feedback(self, address: str, *args: Any) -> None:
        if self._feedback_client:
            self._feedback_client.send_message(address, list(args))

    def _setup_feedback_subscriptions(self) -> None:
        self._bus.subscribe(StateChanged, self._on_state_changed)
        self._bus.subscribe(PlayerBuzzed, self._on_player_buzzed)
        self._bus.subscribe(SceneChanged, self._on_scene_changed)

    async def _on_state_changed(self, event: StateChanged) -> None:
        self._feedback("/feedback/state", event.new_state.name.lower())
        if event.new_state == GameState.TIMED_LOCKOUT and event.duration is not None:
            self._feedback("/feedback/timed_lockout/duration", event.duration)

    async def _on_player_buzzed(self, event: PlayerBuzzed) -> None:
        self._feedback("/feedback/player", event.player_id, event.player_name)

    async def _on_scene_changed(self, event: SceneChanged) -> None:
        self._feedback("/feedback/scene", event.index, event.name)

    async def _dispatch(self, address: str, args: list[Any]) -> None:
        if address in _SIMPLE_COMMANDS:
            await self._bus.publish(ControlCommand(command=_SIMPLE_COMMANDS[address]))
            return

        if address == "/buzzer/timed_lockout":
            duration = float(args[0]) if args else 5.0
            await self._bus.publish(ControlCommand(command="timed_lockout", args=(duration,)))
            return

        if address == "/show/goto":
            arg = args[0] if args else None
            if isinstance(arg, int):
                await self._bus.publish(ControlCommand(command="scene_goto_index", args=(arg,)))
            elif isinstance(arg, str):
                await self._bus.publish(ControlCommand(command="scene_goto_name", args=(arg,)))
            return

        if address in ("/audio/background/play", "/audio/effect/play",
                       "/audio/background/volume", "/audio/effect/volume"):
            arg = args[0] if args else None
            cmd = address.lstrip("/").replace("/", "_")
            await self._bus.publish(ControlCommand(command=cmd, args=(arg,) if arg is not None else ()))
            return

    def _make_handler(self, address: str) -> Callable:
        def handler(addr: str, *args: Any) -> None:
            self._loop.create_task(self._dispatch(address, list(args)))
        return handler

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        cfg = self._config().service
        dispatcher = Dispatcher()
        for address in list(_SIMPLE_COMMANDS.keys()) + [
            "/buzzer/timed_lockout", "/show/goto",
            "/audio/background/play", "/audio/background/stop",
            "/audio/background/volume", "/audio/effect/play",
            "/audio/effect/stop", "/audio/effect/volume",
        ]:
            dispatcher.map(address, self._make_handler(address))

        server = AsyncIOOSCUDPServer(
            (cfg.osc_server_host, cfg.osc_server_port), dispatcher, self._loop
        )
        self._transport, self._protocol = await server.create_serve_endpoint()

    async def stop(self) -> None:
        if self._transport:
            self._transport.close()
```

- [ ] **Step 4: Run tests to verify passing**

```bash
pytest tests/test_osc_server.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add gameshow/osc_server.py tests/test_osc_server.py
git commit -m "feat: inbound OSC server with TouchOSC feedback"
```

---

## Task 9: DMX Client

**Files:**
- Create: `gameshow/dmx_client.py`
- Create: `tests/test_dmx_client.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_dmx_client.py`:
```python
import pytest
from unittest.mock import MagicMock, patch
from gameshow.bus import EventBus
from gameshow.config import AppConfig, ServiceConfig, BuzzerConfig, PlayerConfig, StateMachineConfig, LightingConfig, AudioConfig, OBSConfig
from gameshow.events import StateChanged, PlayerBuzzed, GameState
from gameshow.dmx_client import DMXClient


def make_config(lighting_states=None):
    return AppConfig(
        service=ServiceConfig(dmx_osc_host="localhost", dmx_osc_port=21600),
        buzzers=BuzzerConfig(players=[PlayerConfig(id=1, name="P1", key="1")]),
        state_machine=StateMachineConfig(),
        lighting=LightingConfig(states=lighting_states or {
            "idle": "/palette/Idle/activate",
            "locked": "/palette/Locked/activate",
            "player_1_buzz": "/palette/Buzz_P1/start",
        }),
        audio=AudioConfig(),
        obs=OBSConfig(),
        scenes=[],
    )


@pytest.mark.asyncio
async def test_state_changed_sends_configured_osc():
    bus = EventBus()
    config = make_config()
    with patch("gameshow.dmx_client.SimpleUDPClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        client = DMXClient(bus, lambda: config)
        await bus.publish(StateChanged(new_state=GameState.LOCKED))
        mock_client.send_message.assert_called_once_with("/palette/Locked/activate", [])


@pytest.mark.asyncio
async def test_player_buzzed_sends_player_specific_cue():
    bus = EventBus()
    config = make_config()
    with patch("gameshow.dmx_client.SimpleUDPClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        client = DMXClient(bus, lambda: config)
        await bus.publish(PlayerBuzzed(player_id=1, player_name="P1"))
        mock_client.send_message.assert_called_once_with("/palette/Buzz_P1/start", [])


@pytest.mark.asyncio
async def test_state_with_no_configured_cue_sends_nothing():
    bus = EventBus()
    config = make_config(lighting_states={"idle": "/palette/Idle/activate"})
    with patch("gameshow.dmx_client.SimpleUDPClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        client = DMXClient(bus, lambda: config)
        await bus.publish(StateChanged(new_state=GameState.CORRECT))
        mock_client.send_message.assert_not_called()
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_dmx_client.py -v
```

- [ ] **Step 3: Implement `gameshow/dmx_client.py`**

```python
from __future__ import annotations
from typing import Callable
from pythonosc.udp_client import SimpleUDPClient
from gameshow.bus import EventBus
from gameshow.config import AppConfig
from gameshow.events import StateChanged, PlayerBuzzed, ControlCommand


class DMXClient:
    def __init__(self, bus: EventBus, config: Callable[[], AppConfig]) -> None:
        self._config = config
        svc = config().service
        self._client = SimpleUDPClient(svc.dmx_osc_host, svc.dmx_osc_port)
        bus.subscribe(StateChanged, self._on_state_changed)
        bus.subscribe(PlayerBuzzed, self._on_player_buzzed)
        bus.subscribe(ControlCommand, self._on_control_command)

    def _send(self, address: str) -> None:
        self._client.send_message(address, [])

    async def _on_state_changed(self, event: StateChanged) -> None:
        states = self._config().lighting.states
        cue = states.get(event.new_state.name.lower())
        if cue:
            self._send(cue)

    async def _on_player_buzzed(self, event: PlayerBuzzed) -> None:
        states = self._config().lighting.states
        key = f"player_{event.player_id}_buzz"
        cue = states.get(key)
        if cue:
            self._send(cue)

    async def _on_control_command(self, event: ControlCommand) -> None:
        if event.command == "dmx_cue" and event.args:
            self._send(str(event.args[0]))
```

- [ ] **Step 4: Run tests to verify passing**

```bash
pytest tests/test_dmx_client.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add gameshow/dmx_client.py tests/test_dmx_client.py
git commit -m "feat: DMX OSC client driven by lighting config"
```

---

## Task 10: Audio Engine

**Files:**
- Create: `gameshow/audio.py`
- Create: `tests/test_audio.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_audio.py`:
```python
import pytest
from unittest.mock import MagicMock, patch, call
from gameshow.bus import EventBus
from gameshow.config import AppConfig, ServiceConfig, BuzzerConfig, StateMachineConfig, LightingConfig, AudioConfig, AudioStateEntry, OBSConfig
from gameshow.events import StateChanged, PlayerBuzzed, GameState, ControlCommand
from gameshow.audio import AudioEngine


def make_config(audio_states=None):
    return AppConfig(
        service=ServiceConfig(),
        buzzers=BuzzerConfig(players=[]),
        state_machine=StateMachineConfig(),
        lighting=LightingConfig(),
        audio=AudioConfig(
            default_background_volume=0.7,
            default_effect_volume=1.0,
            states=audio_states or {
                "player_1_buzz": AudioStateEntry(effect="sounds/buzz.mp3"),
                "correct": AudioStateEntry(effect="sounds/correct.mp3"),
                "round_start": AudioStateEntry(background="music/theme.mp3"),
            }
        ),
        obs=OBSConfig(),
        scenes=[],
    )


@pytest.mark.asyncio
async def test_player_buzzed_plays_effect():
    bus = EventBus()
    config = make_config()
    with patch("gameshow.audio.pygame") as mock_pygame:
        mock_ch = MagicMock()
        mock_pygame.mixer.Channel.return_value = mock_ch
        mock_pygame.mixer.Sound.return_value = MagicMock()
        engine = AudioEngine(bus, lambda: config)
        await bus.publish(PlayerBuzzed(player_id=1, player_name="P1"))
        mock_pygame.mixer.Sound.assert_called_with("sounds/buzz.mp3")
        mock_ch.play.assert_called_once()


@pytest.mark.asyncio
async def test_state_changed_correct_plays_effect():
    bus = EventBus()
    config = make_config()
    with patch("gameshow.audio.pygame") as mock_pygame:
        mock_ch = MagicMock()
        mock_pygame.mixer.Channel.return_value = mock_ch
        mock_pygame.mixer.Sound.return_value = MagicMock()
        engine = AudioEngine(bus, lambda: config)
        await bus.publish(StateChanged(new_state=GameState.CORRECT))
        mock_pygame.mixer.Sound.assert_called_with("sounds/correct.mp3")


@pytest.mark.asyncio
async def test_background_stops_before_new_track():
    bus = EventBus()
    config = make_config()
    with patch("gameshow.audio.pygame") as mock_pygame:
        mock_bg_ch = MagicMock()
        mock_fx_ch = MagicMock()
        mock_pygame.mixer.Channel.side_effect = [mock_bg_ch, mock_fx_ch]
        mock_pygame.mixer.Sound.return_value = MagicMock()
        engine = AudioEngine(bus, lambda: config)
        await bus.publish(StateChanged(new_state=GameState.ROUND_START))
        mock_bg_ch.stop.assert_called_once()
        mock_bg_ch.play.assert_called_once()


@pytest.mark.asyncio
async def test_audio_bg_stop_command_stops_background():
    bus = EventBus()
    config = make_config()
    with patch("gameshow.audio.pygame") as mock_pygame:
        mock_bg_ch = MagicMock()
        mock_fx_ch = MagicMock()
        mock_pygame.mixer.Channel.side_effect = [mock_bg_ch, mock_fx_ch]
        engine = AudioEngine(bus, lambda: config)
        await bus.publish(ControlCommand(command="audio_bg_stop"))
        mock_bg_ch.stop.assert_called_once()
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_audio.py -v
```

- [ ] **Step 3: Implement `gameshow/audio.py`**

```python
from __future__ import annotations
from typing import Callable
import pygame
from gameshow.bus import EventBus
from gameshow.config import AppConfig
from pythonosc.udp_client import SimpleUDPClient
from gameshow.events import StateChanged, PlayerBuzzed, ControlCommand

_BG_CHANNEL = 0
_FX_CHANNEL = 1


class AudioEngine:
    def __init__(self, bus: EventBus, config: Callable[[], AppConfig]) -> None:
        self._config = config
        pygame.mixer.init()
        self._bg = pygame.mixer.Channel(_BG_CHANNEL)
        self._fx = pygame.mixer.Channel(_FX_CHANNEL)
        svc = config().service
        self._feedback_client = SimpleUDPClient(svc.touchosc_host, svc.touchosc_port) if svc.touchosc_host else None
        bus.subscribe(StateChanged, self._on_state_changed)
        bus.subscribe(PlayerBuzzed, self._on_player_buzzed)
        bus.subscribe(ControlCommand, self._on_control_command)

    def _feedback(self, address: str, *args) -> None:
        if self._feedback_client:
            self._feedback_client.send_message(address, list(args))

    def _play_effect(self, path: str) -> None:
        sound = pygame.mixer.Sound(path)
        cfg = self._config().audio
        self._fx.set_volume(cfg.default_effect_volume)
        self._fx.play(sound)
        self._feedback("/feedback/audio/effect/state", "playing")
        self._feedback("/feedback/audio/effect/track", path)

    def _play_background(self, path: str) -> None:
        sound = pygame.mixer.Sound(path)
        cfg = self._config().audio
        self._bg.stop()
        self._bg.set_volume(cfg.default_background_volume)
        self._bg.play(sound, loops=-1)
        self._feedback("/feedback/audio/background/state", "playing")
        self._feedback("/feedback/audio/background/track", path)

    def _handle_audio_state(self, state_key: str) -> None:
        entry = self._config().audio.states.get(state_key)
        if not entry:
            return
        if entry.effect:
            self._play_effect(entry.effect)
        if entry.background:
            self._play_background(entry.background)

    async def _on_state_changed(self, event: StateChanged) -> None:
        self._handle_audio_state(event.new_state.name.lower())

    async def _on_player_buzzed(self, event: PlayerBuzzed) -> None:
        self._handle_audio_state(f"player_{event.player_id}_buzz")

    async def _on_control_command(self, event: ControlCommand) -> None:
        if event.command == "audio_bg_stop":
            self._bg.stop()
            self._feedback("/feedback/audio/background/state", "stopped")
        elif event.command == "audio_fx_stop":
            self._fx.stop()
            self._feedback("/feedback/audio/effect/state", "stopped")
        elif event.command == "audio_background_play" and event.args:
            self._play_background(str(event.args[0]))
        elif event.command == "audio_effect_play" and event.args:
            self._play_effect(str(event.args[0]))
        elif event.command == "audio_background_volume" and event.args:
            self._bg.set_volume(float(event.args[0]))
        elif event.command == "audio_effect_volume" and event.args:
            self._fx.set_volume(float(event.args[0]))
```

- [ ] **Step 4: Run tests to verify passing**

```bash
pytest tests/test_audio.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add gameshow/audio.py tests/test_audio.py
git commit -m "feat: pygame.mixer two-channel audio engine"
```

---

## Task 11: OBS Client

**Files:**
- Create: `gameshow/obs_client.py`
- Create: `tests/test_obs_client.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_obs_client.py`:
```python
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from gameshow.bus import EventBus
from gameshow.config import AppConfig, ServiceConfig, BuzzerConfig, StateMachineConfig, LightingConfig, AudioConfig, OBSConfig
from gameshow.events import StateChanged, GameState
from gameshow.obs_client import OBSClient


def make_config(obs_states=None):
    return AppConfig(
        service=ServiceConfig(obs_host="localhost", obs_port=4455, obs_password=""),
        buzzers=BuzzerConfig(players=[]),
        state_machine=StateMachineConfig(),
        lighting=LightingConfig(),
        audio=AudioConfig(),
        obs=OBSConfig(states=obs_states or {
            "idle": "Idle",
            "locked": "Buzz_Locked",
            "correct": "Correct",
        }),
        scenes=[],
    )


@pytest.mark.asyncio
async def test_state_changed_calls_obs_switch():
    bus = EventBus()
    config = make_config()
    mock_ws = AsyncMock()
    mock_ws.call = AsyncMock(return_value=MagicMock())

    with patch("gameshow.obs_client.simpleobsws.WebSocketClient", return_value=mock_ws):
        client = OBSClient(bus, lambda: config)
        client._ws = mock_ws
        client._connected = True
        await bus.publish(StateChanged(new_state=GameState.LOCKED))
        mock_ws.call.assert_called_once()
        args = mock_ws.call.call_args
        assert "Buzz_Locked" in str(args)


@pytest.mark.asyncio
async def test_state_with_no_obs_mapping_sends_nothing():
    bus = EventBus()
    config = make_config(obs_states={"idle": "Idle"})
    mock_ws = AsyncMock()

    with patch("gameshow.obs_client.simpleobsws.WebSocketClient", return_value=mock_ws):
        client = OBSClient(bus, lambda: config)
        client._ws = mock_ws
        client._connected = True
        await bus.publish(StateChanged(new_state=GameState.CORRECT))
        mock_ws.call.assert_not_called()


@pytest.mark.asyncio
async def test_obs_not_connected_does_not_raise():
    bus = EventBus()
    config = make_config()
    with patch("gameshow.obs_client.simpleobsws.WebSocketClient"):
        client = OBSClient(bus, lambda: config)
        client._connected = False
        await bus.publish(StateChanged(new_state=GameState.LOCKED))
        # no exception
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_obs_client.py -v
```

- [ ] **Step 3: Implement `gameshow/obs_client.py`**

```python
from __future__ import annotations
import asyncio
import logging
from typing import Callable, Optional
import simpleobsws
from pythonosc.udp_client import SimpleUDPClient
from gameshow.bus import EventBus
from gameshow.config import AppConfig
from gameshow.events import StateChanged, ControlCommand

log = logging.getLogger(__name__)


class OBSClient:
    def __init__(self, bus: EventBus, config: Callable[[], AppConfig]) -> None:
        self._config = config
        self._connected = False
        svc = config().service
        self._ws = simpleobsws.WebSocketClient(
            url=f"ws://{svc.obs_host}:{svc.obs_port}",
            password=svc.obs_password,
        )
        self._feedback_client = SimpleUDPClient(svc.touchosc_host, svc.touchosc_port) if svc.touchosc_host else None
        bus.subscribe(StateChanged, self._on_state_changed)
        bus.subscribe(ControlCommand, self._on_control_command)

    async def _on_state_changed(self, event: StateChanged) -> None:
        if not self._connected:
            return
        scene_name = self._config().obs.states.get(event.new_state.name.lower())
        if not scene_name:
            return
        try:
            req = simpleobsws.Request("SetCurrentProgramScene", {"sceneName": scene_name})
            await self._ws.call(req)
        except Exception as exc:
            log.warning("OBS scene switch failed: %s", exc)

    async def start(self) -> None:
        asyncio.create_task(self._connect_loop())

    async def _connect_loop(self) -> None:
        delay = 1.0
        while True:
            try:
                await self._ws.connect()
                await self._ws.wait_until_identified()
                self._connected = True
                log.info("OBS connected")
                self._ws.register_event_callback(self._on_obs_event)
                return
            except Exception as exc:
                self._connected = False
                log.info("OBS connection failed (%s); retrying in %.0fs", exc, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)

    async def _on_obs_event(self, event: simpleobsws.Event) -> None:
        if event.eventType == "CurrentProgramSceneChanged":
            scene_name = event.eventData.get("sceneName", "")
            log.debug("OBS scene changed: %s", scene_name)
            if self._feedback_client:
                self._feedback_client.send_message("/feedback/obs/scene", [scene_name])

    async def _on_control_command(self, event: ControlCommand) -> None:
        if event.command == "obs_scene_set" and event.args and self._connected:
            scene_name = str(event.args[0])
            try:
                req = simpleobsws.Request("SetCurrentProgramScene", {"sceneName": scene_name})
                await self._ws.call(req)
            except Exception as exc:
                log.warning("OBS scene set failed: %s", exc)

    async def stop(self) -> None:
        if self._connected:
            await self._ws.disconnect()
```

- [ ] **Step 4: Run tests to verify passing**

```bash
pytest tests/test_obs_client.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add gameshow/obs_client.py tests/test_obs_client.py
git commit -m "feat: OBS WebSocket client with auto-reconnect"
```

---

## Task 12: Main Entry Point

**Files:**
- Create: `main.py`

- [ ] **Step 1: Implement `main.py`**

```python
import asyncio
import logging
import signal
import sys
from gameshow.config import load_config
from gameshow.bus import EventBus
from gameshow.state_machine import StateMachine
from gameshow.scene_manager import SceneManager
from gameshow.keyboard import KeyboardListener
from gameshow.osc_server import OSCServer
from gameshow.dmx_client import DMXClient
from gameshow.audio import AudioEngine
from gameshow.obs_client import OBSClient
from gameshow.events import ControlCommand, SceneChanged

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

CONFIG_PATH = "config.yaml"


async def main() -> None:
    base_raw, base_config = load_config(CONFIG_PATH)
    bus = EventBus()

    scene_manager = SceneManager(bus, base_raw, base_config)
    config_fn = lambda: scene_manager.current_config

    state_machine = StateMachine(bus, config_fn)
    keyboard = KeyboardListener(bus, config_fn)
    osc_server = OSCServer(bus, config_fn)
    DMXClient(bus, config_fn)
    AudioEngine(bus, config_fn)
    obs_client = OBSClient(bus, config_fn)

    # Wire on_enter actions when a scene activates.
    # DMXClient handles "dmx_cue"; OBSClient handles "obs_scene_set".
    async def on_scene_changed(event: SceneChanged) -> None:
        scene = next((s for s in base_config.scenes if s.name == event.name), None)
        if not scene or not scene.on_enter:
            return
        oe = scene.on_enter
        if oe.audio_background:
            await bus.publish(ControlCommand(command="audio_background_play", args=(oe.audio_background,)))
        if oe.obs_scene:
            await bus.publish(ControlCommand(command="obs_scene_set", args=(oe.obs_scene,)))
        if oe.lighting:
            await bus.publish(ControlCommand(command="dmx_cue", args=(oe.lighting,)))

    bus.subscribe(SceneChanged, on_scene_changed)

    # Wire scene commands from OSC to SceneManager
    async def on_control(event: ControlCommand) -> None:
        if event.command == "scene_advance":
            await scene_manager.advance()
        elif event.command == "scene_previous":
            await scene_manager.previous()
        elif event.command == "scene_goto_index" and event.args:
            await scene_manager.goto_index(int(event.args[0]))
        elif event.command == "scene_goto_name" and event.args:
            await scene_manager.goto_name(str(event.args[0]))
        elif event.command == "scene_current":
            await bus.publish(SceneChanged(
                index=scene_manager.current_index,
                name=scene_manager.current_scene_name or "",
            ))

    bus.subscribe(ControlCommand, on_control)

    await state_machine.start()
    await keyboard.start()
    await osc_server.start()
    await obs_client.start()

    log.info("Game show control service running. Press Ctrl+C to stop.")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()

    log.info("Shutting down...")
    await keyboard.stop()
    await state_machine.stop()
    await obs_client.stop()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Smoke test — verify service starts without error**

```bash
python main.py &
sleep 2
kill %1
```

Expected: Service prints "Game show control service running." and exits cleanly. No exceptions.

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: main entry point wiring all components"
```

---

## Full Test Run

```bash
pytest tests/ -v --tb=short
```

Expected: All tests in all 10 test files pass.
