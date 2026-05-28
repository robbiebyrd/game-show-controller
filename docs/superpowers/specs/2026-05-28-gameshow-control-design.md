# Game Show Control System — Design Spec

**Date:** 2026-05-28  
**Status:** Approved (rev 4)

---

## Overview

A Python background service (no UI) that acts as the central nervous system for a live game show. It intercepts USB HID buzzer inputs, maintains a game state machine, and drives three output systems — DMX lighting, OBS Studio graphics, and audio playback — in response to state changes. A TouchOSC touchscreen client connects to the service's OSC server to issue host commands and receive real-time feedback.

**Development platform:** macOS  
**Deployment platform:** Windows  
**Python version:** 3.11+

---

## Architecture

Event-driven single-process architecture. Seven components communicate through a central asyncio event bus. No component calls another directly.

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
| `ALLOW_NEXT` | Last player locked out; remaining enabled players may buzz |
| `CORRECT` | Transient; auto-returns to configured state after hold duration |
| `INCORRECT` | Transient; auto-returns to configured state after hold duration |
| `BUZZ_TIMEOUT` | Transient; fires when LOCKED timer expires without host input; auto-returns to configured state |
| `TIMED_LOCKOUT` | All buzzers disabled for a configured duration; auto-returns to IDLE |
| `ROUND_START` | Transient; auto-returns to configured state after hold duration |
| `GAME_OVER` | Terminal; only exits via explicit `/buzzer/clear` |

### Transitions

```
IDLE ──(first buzz from any enabled player)──► LOCKED
LOCKED ──(correct)──► CORRECT ──(auto)──► [return_to_after_correct]
LOCKED ──(incorrect)──► INCORRECT ──(auto)──► [return_to_after_incorrect]
LOCKED ──(allow_next)──► ALLOW_NEXT
LOCKED ──(buzz_timeout_seconds expires)──► BUZZ_TIMEOUT ──(auto)──► [return_to_after_buzz_timeout]
ALLOW_NEXT ──(buzz from non-banned enabled player)──► LOCKED
ALLOW_NEXT ──(no eligible players remain)──► IDLE  [auto, see ALLOW_NEXT exhaustion rule]
ANY ──(clear)──► IDLE
ANY ──(timed_lockout t)──► TIMED_LOCKOUT ──(timer)──► IDLE
ANY ──(round_start)──► ROUND_START ──(auto)──► [return_to_after_round_start]
ANY ──(game_over)──► GAME_OVER ──(clear only)──► IDLE
```

### Rules

- Only the **first** press in `IDLE` or `ALLOW_NEXT` triggers a lock; all others are silently dropped
- `BUZZ_TIMEOUT` is optional — disabled when `buzz_timeout_seconds` is null. When disabled, `buzz_timeout_hold_seconds` and `return_to_after_buzz_timeout` are present in config but ignored
- The buzz timeout timer is cancelled immediately if the host sends Correct / Incorrect / Allow Next
- Transient states (`CORRECT`, `INCORRECT`, `BUZZ_TIMEOUT`, `ROUND_START`) hold for a configurable duration then auto-return
- **ALLOW_NEXT exhaustion:** each `allow_next` command adds the currently locked player to a banned set. The "currently enabled" set is evaluated at the moment `allow_next` is issued. When the banned set contains all players that were enabled at that moment, the state machine automatically transitions to `IDLE` and the banned set is cleared
- **`allow_next` outside LOCKED:** if `/buzzer/allow_next` is received while not in `LOCKED` state, it is silently ignored
- **`correct` and `incorrect`** are only valid from `LOCKED` state; received in any other state, they are silently ignored
- **ANY-transition timer cancellation:** when an `ANY`-transition (`clear`, `timed_lockout`, `round_start`, `game_over`) fires while a transient state's auto-return timer is running, the timer is cancelled before entering the new state. No ghost timer fires after the transition
- **`TIMED_LOCKOUT` always returns to `IDLE`** — no `return_to_after_timed_lockout` config key exists; this is intentional
- **Valid `return_to_after_*` values:** only `idle` and `allow_next` are legal return targets. Transient states (`correct`, `incorrect`, `buzz_timeout`, `round_start`) and terminal states (`game_over`) are not valid return targets and will raise a config validation error at startup

### Player Buzz Events vs. State Change Events

When a player presses their buzzer, the state machine emits **two sequential events**:

1. `PlayerBuzzed(player_id)` — immediate; triggers player-specific lighting and audio cues (the `player_N_buzz` keys in `lighting.states` and `audio.states`)
2. `StateChanged(LOCKED, player_id)` — triggers the generic `locked` cues

This means a player buzzing in fires their colour/sound immediately (`player_1_buzz` → blue flash + buzz sound), and separately activates the locked-state cue. The `locked` key in `lighting.states` and `obs.states` covers the general lockout visual; `player_N_buzz` covers the player-specific announcement. Both fire every time a player buzzes in.

The `/feedback/player` OSC message is emitted by the state machine as part of the `PlayerBuzzed` event — at the same time as step 1 above, before `StateChanged(LOCKED)`.

The **DMX Client** and **Audio Engine** subscribe to both `PlayerBuzzed` (for `player_N_buzz` cues) and `StateChanged` (for all other state cues). The **OBS Client** subscribes to `StateChanged` only — there are no `player_N_buzz` entries in `obs.states` and OBS does not react to `PlayerBuzzed` events.

### Timed Lockout Feedback

When `TIMED_LOCKOUT` activates, the service broadcasts `/feedback/timed_lockout/duration <float>` (the configured duration in seconds) so TouchOSC can display a countdown. The state auto-return fires the normal `/feedback/state idle` message.

---

## Show Scenes

A show rundown is an ordered list of scenes. Each scene deep-merges over root-level defaults — any key not specified in a scene falls back to the global config.

### Deep-Merge Rules

- **Scalar fields** (strings, numbers, booleans, null) replace the global value entirely
- **Mapping fields** (e.g. `lighting.states`, `obs.states`, `audio.states`) are merged key-by-key; a scene only needs to specify the keys it overrides
- **`buzzers.players` list** merges by `id`: a scene entry with `id: 2` overrides only the fields specified for player 2; all other players retain their global values
- **`buzzers.all_enabled`** is a boolean shorthand that sets the `enabled` field on all players simultaneously. It is applied before any per-player overrides in the same scene block
- **`on_enter.lighting`** is a one-shot OSC address fired once when the scene activates. It is not merged into `lighting.states` and does not affect per-state lighting behaviour

### Scene Navigation

| Address | Args | Action | Error behaviour |
|---|---|---|---|
| `/show/advance` | — | Next scene | At last scene: log warning, stay on last scene |
| `/show/previous` | — | Previous scene | At first scene: log warning, stay on first scene |
| `/show/goto` | `int` index | Go to scene by 1-based index | Out of range: log warning, ignore |
| `/show/goto` | `string` name | Go to scene by name | Name not found: log warning, ignore |
| `/show/current` | — | Broadcast current scene info back | — |

### on_enter

Each scene may define an `on_enter` block that fires automatically when the scene activates:

| Key | Type | Effect |
|---|---|---|
| `audio_background` | `string` path | Stops any currently playing background track, then starts the named file |
| `obs_scene` | `string` scene name | Switches OBS to the named scene |
| `lighting` | `string` OSC address | Fires a single OSC message to the DMX server |

`on_enter.audio_background` always restarts playback — it is not idempotent. If the same file is already playing, it restarts from the beginning.

---

## OSC Address Space

### Inbound (our server, port 21601)

| Address | Args | Action |
|---|---|---|
| `/buzzer/clear` | — | Clear all locks and bans → IDLE |
| `/buzzer/allow_next` | — | Lock last player, allow others |
| `/buzzer/correct` | — | Trigger CORRECT state |
| `/buzzer/incorrect` | — | Trigger INCORRECT state |
| `/buzzer/round_start` | — | Trigger ROUND_START state |
| `/buzzer/game_over` | — | Trigger GAME_OVER state |
| `/buzzer/timed_lockout` | `float` seconds | Trigger TIMED_LOCKOUT for given duration |
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
| `/feedback/timed_lockout/duration` | `float` seconds | When TIMED_LOCKOUT activates |
| `/feedback/audio/background/state` | `string` playing\|stopped | On background track start/stop |
| `/feedback/audio/background/track` | `string` filename | On background track change |
| `/feedback/audio/effect/state` | `string` playing\|stopped | On effect start/stop |
| `/feedback/audio/effect/track` | `string` filename | On effect change |
| `/feedback/obs/scene` | `string` scene_name | On OBS scene change (ours or manual) |

### Outbound — DMX Lighting Server (port 21600)

Fully driven by `lighting.states` config mappings. No hardcoded OSC addresses in code.

---

## Error Handling

### OBS Connection

- At startup, the OBS client attempts to connect with exponential backoff (initial 1s, max 30s, unlimited retries)
- If OBS is unreachable, the service starts normally; OBS scene switching is silently skipped until connection is established
- If the connection drops mid-show, the client resumes retry loop automatically; no other subsystem is affected
- Connection status is logged at INFO level on each retry attempt

### Other Subsystems

- If the DMX server is unreachable, OSC send failures are logged at WARNING level and the show continues
- If an audio file is missing or unreadable, the error is logged at ERROR level and playback for that event is skipped

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
  # Host and port of the TouchOSC device for outbound feedback messages
  touchosc_host: "192.168.1.100"
  touchosc_port: 9000

buzzers:
  # buzz_timeout_seconds lives here (buzzer input behaviour) rather than under state_machine
  # (which holds hold durations and return targets). It may be overridden per-scene
  # (scalar-replace rule). When null, state_machine.buzz_timeout_hold_seconds and
  # state_machine.return_to_after_buzz_timeout are present but ignored.
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
  # Valid return_to_after_* values: idle, allow_next only.
  # Transient or terminal states are not valid targets (raises config error at startup).
  # All state_machine keys may be overridden per-scene (scalar-replace deep-merge).
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
    player_3_buzz: "/palette/Buzz_P3/start"   # used if player 3 is enabled
    player_4_buzz: "/palette/Buzz_P4/start"   # used if player 4 is enabled
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
    # Audio states only need entries for enabled players.
    # Add player_3_buzz / player_4_buzz here when enabling those players.
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
        lighting: "/palette/Intro/activate"   # one-shot cue; not merged into lighting.states
      buzzers:
        all_enabled: false   # shorthand: sets enabled: false on all players

    - name: "Face Off"
      on_enter:
        obs_scene: "FaceOff_Ready"
        lighting: "/palette/FaceOff/activate"
      buzzers:
        buzz_timeout_seconds: null   # disable timeout for face-off
      lighting:
        states:
          locked: "/palette/FaceOff_Buzz/start"   # overrides global locked cue only
      obs:
        states:
          locked: "FaceOff_Buzz"
          correct: "FaceOff_Correct"

    - name: "Round 1"
      on_enter:
        audio_background: "music/round1_theme.mp3"
        obs_scene: "Round1_Board"
      state_machine:
        return_to_after_incorrect: allow_next   # wrong answer gives other players a chance
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
│   └── obs_client.py       # simpleobsws OBS WebSocket v5 client
├── sounds/
├── music/
├── tests/
│   ├── test_config.py
│   ├── test_bus.py
│   ├── test_state_machine.py
│   ├── test_scene_manager.py
│   ├── test_osc_server.py
│   ├── test_dmx_client.py
│   ├── test_audio.py
│   ├── test_obs_client.py
│   └── test_keyboard.py        # tests key→player mapping logic; pynput hook itself is not unit-tested
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
| `simpleobsws` | OBS WebSocket v5 client (actively maintained) |
