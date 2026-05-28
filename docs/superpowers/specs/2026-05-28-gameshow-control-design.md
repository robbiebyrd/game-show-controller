# Game Show Control System — Design Spec

**Date:** 2026-05-28  
**Status:** Approved

---

## Overview

A Python background service (no UI) that acts as the central nervous system for a live game show. It intercepts USB HID buzzer inputs, maintains a game state machine, and drives three output systems — DMX lighting, OBS Studio graphics, and audio playback — in response to state changes. A TouchOSC touchscreen client connects to the service's OSC server to issue host commands and receive real-time feedback.

**Development platform:** macOS  
**Deployment platform:** Windows  
**Python version:** 3.11+

---

## Architecture

Event-driven single-process architecture. Six components communicate through a central asyncio event bus. No component calls another directly.

```
┌──────────────────────────────────────────────────────────────┐
│                       asyncio Event Loop                      │
│                                                              │
│  [Keyboard Listener]  ──┐                                    │
│                         ▼                                    │
│  [OSC Server]  ─────► [Event Bus] ──► [State Machine]        │
│                                            │                 │
│                         ┌──────────────────┼──────────────┐  │
│                         ▼                  ▼              ▼  │
│                   [DMX Client]      [Audio Engine]  [OBS Client] │
└──────────────────────────────────────────────────────────────┘
                                   ▲
                           [Scene Manager]
                    (provides merged config to all components)
```

### Components

| Component | Responsibility |
|---|---|
| **Keyboard Listener** | `pynput` global hook in a thread; maps configured keys to player IDs; publishes `BuzzerPressed` events |
| **OSC Server** | `python-osc` async server on configurable port (default 21601); translates TouchOSC messages into typed events |
| **Event Bus** | Thin asyncio queue wrapper; typed events, async pub/sub |
| **Scene Manager** | Holds the ordered show rundown; handles advance/previous/goto; deep-merges scene config over global defaults; publishes `SceneChanged` events |
| **State Machine** | Sole owner of game logic; consumes `BuzzerPressed` and control events; enforces lockout rules and timers; publishes `StateChanged` events |
| **DMX Client** | Subscribes to `StateChanged`; fires configured OSC cue paths to lighting server at port 21600 |
| **Audio Engine** | Subscribes to `StateChanged`; drives `pygame.mixer` on two channels (background + effects) |
| **OBS Client** | Subscribes to `StateChanged`; switches OBS scenes via WebSocket v5; subscribes to `CurrentProgramSceneChanged` OBS events for real-time feedback |

---

## State Machine

### States

| State | Description |
|---|---|
| `IDLE` | Waiting for any buzz |
| `LOCKED` | A player has buzzed in; all other buzzers blocked |
| `ALLOW_NEXT` | Last player locked out; remaining players may buzz |
| `CORRECT` | Transient; auto-returns to configured state after hold duration |
| `INCORRECT` | Transient; auto-returns to configured state after hold duration |
| `BUZZ_TIMEOUT` | Transient; fires when LOCKED timer expires without host input |
| `TIMED_LOCKOUT` | All buzzers disabled for a configured duration; auto-returns to IDLE |
| `ROUND_START` | Transient; auto-returns to IDLE after hold duration |
| `GAME_OVER` | Terminal; only exits via explicit `/buzzer/clear` |

### Transitions

```
IDLE ──(first buzz)──► LOCKED
LOCKED ──(correct)──► CORRECT ──(auto)──► [configured return state]
LOCKED ──(incorrect)──► INCORRECT ──(auto)──► [configured return state]
LOCKED ──(allow_next)──► ALLOW_NEXT
LOCKED ──(buzz_timeout_seconds expires)──► BUZZ_TIMEOUT ──(auto)──► [configured return state]
ALLOW_NEXT ──(next buzz)──► LOCKED
ANY ──(clear)──► IDLE
ANY ──(timed_lockout t)──► TIMED_LOCKOUT ──(timer)──► IDLE
ANY ──(round_start)──► ROUND_START ──(auto)──► IDLE
ANY ──(game_over)──► GAME_OVER ──(clear only)──► IDLE
```

### Rules

- Only the **first** press in `IDLE` or `ALLOW_NEXT` triggers a lock; all others are silently dropped
- `BUZZ_TIMEOUT` is optional — disabled when `buzz_timeout_seconds` is null
- The buzz timeout timer is cancelled immediately if the host sends Correct / Incorrect / Allow Next
- Transient states (`CORRECT`, `INCORRECT`, `BUZZ_TIMEOUT`, `ROUND_START`) hold for a configurable duration then auto-return

---

## Show Scenes

A show rundown is an ordered list of scenes. Each scene deep-merges over root-level defaults — any key not specified in a scene falls back to the global config.

### Scene Manager OSC Commands

| Address | Args | Action |
|---|---|---|
| `/show/advance` | — | Next scene |
| `/show/previous` | — | Previous scene |
| `/show/goto` | `int` index | Go to scene by 1-based index |
| `/show/goto` | `string` name | Go to scene by name |
| `/show/current` | — | Broadcast current scene info back |

### on_enter

Each scene may define an `on_enter` block that fires automatically when the scene activates: plays a background track, sets an OBS scene, and/or fires a lighting cue.

---

## OSC Address Space

### Inbound (our server, port 21601)

| Address | Args | Action |
|---|---|---|
| `/buzzer/clear` | — | Clear all locks → IDLE |
| `/buzzer/allow_next` | — | Lock last player, allow others |
| `/buzzer/correct` | — | Trigger CORRECT state |
| `/buzzer/incorrect` | — | Trigger INCORRECT state |
| `/buzzer/round_start` | — | Trigger ROUND_START state |
| `/buzzer/game_over` | — | Trigger GAME_OVER state |
| `/buzzer/timed_lockout` | `float` seconds | Trigger TIMED_LOCKOUT |
| `/show/advance` | — | Next scene |
| `/show/previous` | — | Previous scene |
| `/show/goto` | `int` or `string` | Go to scene by index or name |
| `/show/current` | — | Broadcast current scene |
| `/audio/background/play` | `string` path | Play background track |
| `/audio/background/stop` | — | Stop background track |
| `/audio/background/volume` | `float` 0.0–1.0 | Set background volume |
| `/audio/effect/play` | `string` path | Play sound effect |
| `/audio/effect/stop` | — | Stop sound effect |
| `/audio/effect/volume` | `float` 0.0–1.0 | Set effect volume |

### Outbound Feedback (broadcast back to TouchOSC)

| Address | Args | When |
|---|---|---|
| `/feedback/state` | `string` state | On every state change |
| `/feedback/player` | `int` id, `string` name | When a player buzzes in |
| `/feedback/scene` | `int` index, `string` name | On show scene change |
| `/feedback/audio/background/state` | `string` playing\|stopped | On background track start/stop |
| `/feedback/audio/background/track` | `string` filename | On background track change |
| `/feedback/audio/effect/state` | `string` playing\|stopped | On effect start/stop |
| `/feedback/audio/effect/track` | `string` filename | On effect change |
| `/feedback/obs/scene` | `string` scene_name | On OBS scene change (ours or manual) |

### Outbound — DMX Lighting Server (port 21600)

Fully driven by `lighting.states` config mappings. No hardcoded OSC addresses in code.

---

## Configuration Structure

```yaml
service:
  osc_server_host: "0.0.0.0"
  osc_server_port: 21601
  dmx_osc_host: "localhost"
  dmx_osc_port: 21600
  obs_host: "localhost"
  obs_port: 4455
  obs_password: "your-password-here"

buzzers:
  buzz_timeout_seconds: 10.0   # null to disable globally
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
  correct_hold_seconds: 2.0
  incorrect_hold_seconds: 2.0
  buzz_timeout_hold_seconds: 3.0

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

---

## File Structure

```
gameshow/
├── config.yaml
├── main.py
├── gameshow/
│   ├── __init__.py
│   ├── config.py           # YAML loader, dataclasses, deep-merge logic
│   ├── events.py           # all event type definitions
│   ├── bus.py              # asyncio event bus
│   ├── keyboard.py         # pynput global hook
│   ├── state_machine.py    # game state, lockout rules, timers
│   ├── scene_manager.py    # show rundown, scene navigation, merged config
│   ├── osc_server.py       # inbound OSC (TouchOSC + scene commands)
│   ├── dmx_client.py       # outbound OSC → DMX lighting server
│   ├── audio.py            # pygame.mixer two-channel playback
│   └── obs_client.py       # obsws-python OBS WebSocket v5 client
├── sounds/
├── music/
├── tests/
│   ├── test_config.py
│   ├── test_bus.py
│   ├── test_state_machine.py
│   ├── test_scene_manager.py
│   └── test_osc_server.py
└── requirements.txt
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `pyyaml` | YAML config loading |
| `pynput` | Global keyboard capture (macOS + Windows) |
| `python-osc` | OSC server + DMX client |
| `pygame` | Two-channel audio playback |
| `obsws-python` | OBS WebSocket v5 client |
