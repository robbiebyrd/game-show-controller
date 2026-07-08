# Plan: Config-Driven State Machine

**Created:** 2026-07-08 | **Status:** Draft | **Effort:** L | **Branch:** feat/configurable-state-machine

## Summary

Replace the hard-coded `GameState` enum and imperative transition logic in `state_machine.py` with a data-driven finite state machine defined entirely in `config.yaml`. States, the transition table (each state + trigger → next state), and typed side-effect behaviors (ban, countdown, hold/auto-return, buzz-timeout branching) all come from config. The state machine becomes a small interpreter over the config.

## Architecture Context

- **Event bus flow:** OSC / control-surface / keyboard publish `BuzzerPressed` and `ControlCommand(command=…)` → `StateMachine` consumes them → publishes `StateChanged(new_state, player_id, duration)` + `PlayerBuzzed` + `CountdownTick/Ended`.
- **Commands are triggers.** `ControlCommand.command` values (`correct`, `incorrect`, `allow_next`, `clear`, `game_over`, `round_start`, `timed_lockout`) and `BuzzerPressed` (`buzz` trigger) drive transitions 1:1. Control-surface `state` buttons and OSC `_SIMPLE_COMMANDS` already emit these.
- **Consumers key off the state string.** `obs_client.py:30`, `audio.py:61`, `dmx_client.py:27`, `control_surface.py:612` all use `event.new_state.name.lower()` → config dict lookup. Only `osc_server.py:60-62` compares against enum members.
- **Gap:** the enum + all flow/side-effects live in `state_machine.py` (`_TRANSIENT_HOLD_MAP`, `_RETURN_TO_MAP`, `_on_control_command`, `_buzz_timeout_return`, ban logic). This is what moves into config + a generic interpreter.
- **Scene overrides** (`scene_manager` → `apply_scene_override` → `deep_merge` → `parse_config`) deep-merge the whole `state_machine` subtree per scene, so nested `states.*` overrides work unchanged.

## Config Schema (target)

```yaml
state_machine:
  initial: idle
  # Transitions valid from ANY state (globals win over per-state `on`).
  global:
    clear:        { to: idle,      do: [clear_bans, clear_player] }
    game_over:    { to: game_over, do: [clear_bans, clear_player] }
    round_start:  round_start
    timed_lockout: timed_lockout          # duration comes from the command arg
  states:
    idle:
      transitions: { buzz: locked }       # `buzz` sets locked_player_id + emits PlayerBuzzed
    locked:
      behaviors: [countdown]              # start buzz-timeout countdown on entry
      transitions:
        countdown_expire: buzz_timeout    # fired by the countdown behavior on expiry
        correct: correct
        incorrect: { to: incorrect, do: [ban_current] }
        allow_next:
          to: allow_next
          do: [ban_current, clear_player]
          when_all_banned: idle           # if every enabled player is banned: clear bans + go here
    correct:      { hold: 2.0, then: idle }
    incorrect:
      hold: 2.0
      then: idle
      transitions: { buzz: locked }       # INCORRECT still accepts a re-buzz (matches current code)
    allow_next:   { transitions: { buzz: locked } }
    buzz_timeout:
      hold: 0.5
      then: { to: allow_next, do: [ban_current, clear_player], when_all_banned: idle }
    timed_lockout: { hold_from_arg: 5.0, then: idle }
    round_start:  { hold: 2.0, then: idle }
    game_over:    {}
```

**Grammar:**
- The per-state transition table key is `transitions:` (NOT `on:` — PyYAML/YAML 1.1 coerces an unquoted `on` key to the boolean `True`).
- Transition value is either a `str` (target state) or a mapping `{ to, do?, when_all_banned? }`.
- `behaviors: [..]` = entry side-effects. `hold`/`hold_from_arg` + `then` = auto-return timer (`then` uses the same string|mapping grammar).
- **Behavior vocabulary** (typed, in code, `config.STATE_BEHAVIORS`): `ban_current`, `clear_bans`, `clear_player`, `countdown`.
- **Reserved triggers:** `buzz` (from `BuzzerPressed`, carries player), `countdown_expire` (from countdown behavior). Countdown *controls* (`countdown_pause|resume|reset|cancel`) stay handled directly — they manipulate the live countdown, not the FSM.
- `when_all_banned`: after running `do`, if `banned ⊇ enabled players`, clear bans and go to that target instead of `to`.

## Research Findings

- Consumers only need the lowercase state key; switching `StateChanged.new_state` from `GameState` → `str` collapses every `.name.lower()` to a bare field read.
- `osc_server.py` has 2 enum comparisons: TIMED_LOCKOUT-duration feedback (drive off `event.duration is not None` instead) and player-reset on CORRECT/INCORRECT/IDLE (make config-agnostic — see Step 4).
- Control-surface `state` buttons pass `state:` verbatim as the command (`control_surface.py:345`), so config state names and trigger names are already the same namespace — no button changes needed.
- `deep_merge` (`config.py:180`) already handles nested dict merge, so scene-level `state_machine.states.*` overrides just work; the `Round 1` scene's `return_to_after_incorrect: allow_next` becomes `states.incorrect.then: allow_next`.
- No backward compat: flat `StateMachineConfig` fields (`return_to_after_*`, `*_hold_seconds`) and `VALID_RETURN_TARGETS` are removed, not kept alongside.

## Security Considerations

- None — local YAML config authored by the operator; no external/untrusted input. Config parse errors must fail loudly at startup (validation below).

## Performance Considerations

- None — transitions fire at human interaction rates. Interpreter builds a dict-based lookup once at parse; per-transition cost is dict access. Countdown tick cadence unchanged (`COUNTDOWN_TICK_SECONDS`).

## Resolved Decisions

1. **Missing `state_machine.states`** → raise a clear startup `ValueError`. No hidden Python default; config is the single source of truth.
2. **No backward compat** → flat `return_to_after_*` / `*_hold_seconds` fields and `VALID_RETURN_TARGETS` are removed outright; `config.yaml` and tests are migrated to the new schema.
3. **`osc_server` player-reset feedback** → REVISED during implementation. The `player_id is None` idea would change UX: `correct`/`incorrect` carry the locked player's id, so they would stop clearing the on-screen player label (and an existing test encodes clear-on-result). Behavior is therefore preserved via a `_PLAYER_RESET_STATES = {"correct","incorrect","idle"}` string set. Duration feedback IS decoupled: it now fires whenever `event.duration is not None`.

## Steps

### Step 1: Config schema + parser + validation
- **Test:** `tests/test_config.py` — parsing the target schema yields `StateMachineConfig(initial, states, global_)`; each `StateConfig` has `on`, `behaviors`, `hold`/`hold_from_arg`, `then`; string and mapping transitions both parse; validation raises on (unknown state target, unknown behavior, missing `initial`, unknown trigger reserved-word misuse).
- **Implement:** `gameshow/config.py` — replace `StateMachineConfig` and `VALID_RETURN_TARGETS`/`_validate_return_targets` with the schema below and a `_validate_state_machine`.
- **Code:**
```python
@dataclass
class TransitionConfig:
    to: str
    do: list[str] = field(default_factory=list)
    when_all_banned: Optional[str] = None

@dataclass
class StateConfig:
    on: dict[str, TransitionConfig] = field(default_factory=dict)
    behaviors: list[str] = field(default_factory=list)
    hold: Optional[float] = None
    hold_from_arg: Optional[float] = None   # default hold when the trigger carries no arg
    then: Optional[TransitionConfig] = None

@dataclass
class StateMachineConfig:
    initial: str
    states: dict[str, StateConfig] = field(default_factory=dict)
    global_: dict[str, TransitionConfig] = field(default_factory=dict)

_BEHAVIORS = {"ban_current", "clear_bans", "clear_player", "countdown"}

def _parse_transition(raw) -> TransitionConfig:
    if isinstance(raw, str):
        return TransitionConfig(to=raw)
    return TransitionConfig(to=raw["to"], do=list(raw.get("do", [])),
                            when_all_banned=raw.get("when_all_banned"))

def _parse_state_machine(raw: dict) -> StateMachineConfig:
    states = {}
    for name, s in (raw.get("states") or {}).items():
        s = s or {}
        states[name] = StateConfig(
            on={t: _parse_transition(v) for t, v in (s.get("on") or {}).items()},
            behaviors=list(s.get("behaviors", [])),
            hold=s.get("hold"), hold_from_arg=s.get("hold_from_arg"),
            then=_parse_transition(s["then"]) if "then" in s else None,
        )
    global_ = {t: _parse_transition(v) for t, v in (raw.get("global") or {}).items()}
    sm = StateMachineConfig(initial=raw["initial"], states=states, global_=global_)
    _validate_state_machine(sm)
    return sm
```
  Validation: `initial in states`; every `to`/`when_all_banned`/`then.to` references a known state; every behavior in `_BEHAVIORS`; raise `ValueError` with the offending name.
- **Validation:** `pytest tests/test_config.py`

### Step 2: Drop `GameState`, make state a string
- **Test:** `tests/test_events.py` — `StateChanged(new_state="locked")` holds a `str`; remove GameState-based assertions.
- **Implement:** `gameshow/events.py` — delete `GameState` enum; `StateChanged.new_state: str`. Grep-remove `GameState` imports across the package.
- **Code:**
```python
@dataclass(frozen=True)
class StateChanged:
    new_state: str                       # config state key, e.g. "locked"
    player_id: Optional[int] = None
    duration: Optional[float] = None     # set when entering a hold_from_arg state
```
- **Depends on:** Step 1
- **Validation:** `grep -rn "GameState" gameshow/ tests/` returns nothing; `pytest tests/test_events.py`

### Step 3: Rewrite `StateMachine` as a config interpreter
- **Test:** `tests/test_state_machine.py` — rewrite `make_config` to build the new schema; preserve every existing behavioral assertion: idle-buzz→locked emits PlayerBuzzed; disabled/banned players ignored; correct/incorrect/allow_next only act in locked; incorrect bans; allow_next branches to idle when all banned else allow_next; buzz_timeout after countdown bans + branches; hold auto-return honors `then`; timed_lockout uses arg duration + emits `StateChanged.duration`; countdown pause/resume/reset/cancel; clear/game_over reset bans+player; commands ignored in game_over.
- **Implement:** `gameshow/state_machine.py` — keep `Countdown` unchanged. Replace state constants/maps and both handlers with a generic driver.
- **Code:**
```python
async def _fire(self, trigger: str, arg=None, player_id=None) -> None:
    sm = self._config().state_machine
    st = sm.states.get(self.state)
    tr = (st.on.get(trigger) if st else None) or sm.global_.get(trigger)
    if tr is None:
        return                                   # trigger not valid here → ignore
    if player_id is not None:                    # `buzz` semantics
        self.locked_player_id = player_id
        await self._bus.publish(PlayerBuzzed(player_id=player_id,
                                             player_name=self._player_name(player_id)))
    await self._run_do(tr.do)
    target = tr.to
    if tr.when_all_banned and self._banned >= self._enabled_player_ids():
        self._banned.clear(); target = tr.when_all_banned
    await self._enter_state(target, arg=arg)

def _run_do(self, names):                        # ban_current / clear_bans / clear_player
    for n in names:
        if n == "ban_current" and self.locked_player_id is not None:
            self._banned.add(self.locked_player_id)
        elif n == "clear_bans": self._banned.clear()
        elif n == "clear_player": self.locked_player_id = None

async def _enter_state(self, name, arg=None):
    self._cancel_timer(); await self._stop_countdown("superseded")
    self.state = name
    cfg = self._config().state_machine.states[name]
    duration = arg if arg is not None else cfg.hold_from_arg
    await self._bus.publish(StateChanged(new_state=name, player_id=self.locked_player_id,
                                         duration=duration if cfg.hold_from_arg is not None else None))
    if "countdown" in cfg.behaviors:
        self._start_buzz_countdown()             # expiry → self._fire("countdown_expire")
    hold = duration if cfg.hold_from_arg is not None else cfg.hold
    if hold is not None and cfg.then is not None:
        self._timer = asyncio.create_task(self._auto_return(hold, cfg.then))
```
  `_on_buzzer_pressed`: enabled + not banned → `await self._fire("buzz", player_id=pid)`. `_on_control_command`: route countdown-control commands directly; else `await self._fire(cmd, arg=float(args[0]) if args else None)`. `_auto_return(delay, tr)`: sleep, run `tr.do`, apply `when_all_banned`, enter `tr.to`. Countdown expiry callback calls `_fire("countdown_expire")`.
- **Depends on:** Step 1, Step 2
- **Validation:** `pytest tests/test_state_machine.py`

### Step 4: Update consumers to string states
- **Test:** `tests/test_osc_server.py`, `tests/test_obs_client.py`, `tests/test_audio.py`, `tests/test_dmx_client.py`, `tests/test_control_surface.py` — publish `StateChanged(new_state="…")` strings; assert lookups + feedback still fire.
- **Implement:** replace `event.new_state.name.lower()` → `event.new_state` in `obs_client.py:30`, `audio.py:61`, `dmx_client.py:27`, `control_surface.py:612`. In `osc_server.py`: drop `GameState` import; emit duration feedback when `event.duration is not None`; reset player feedback when `event.player_id is None`.
- **Code:**
```python
# osc_server.py
async def _on_state_changed(self, event: StateChanged) -> None:
    self._feedback("/feedback/state", event.new_state)
    if event.duration is not None:
        self._feedback("/feedback/timed_lockout/duration", event.duration)
    if event.player_id is None:
        self._feedback("/feedback/player", "None")
```
- **Depends on:** Step 2
- **Validation:** `pytest tests/test_osc_server.py tests/test_obs_client.py tests/test_audio.py tests/test_dmx_client.py tests/test_control_surface.py`

### Step 5: Migrate config files
- **Implement:** `config.yaml` + `config.example.yaml` — replace the flat `state_machine:` block with the target schema (Config Schema section). Update the `Round 1` scene override from `state_machine: { return_to_after_incorrect: allow_next }` → `state_machine: { states: { incorrect: { then: allow_next } } }`. Lighting/audio/obs/`show` blocks unchanged (their keys are already the state strings).
- **Validation:** `python -c "from gameshow.config import load_config; load_config('config.yaml')"` parses clean; full `pytest` green; manual smoke: run app, buzz → locked → correct → idle, verify OBS/audio/lighting fire.
- **Depends on:** Step 1

## Acceptance Criteria

- [x] `GameState` enum is gone; states are strings sourced from `config.yaml`.
- [x] Adding/renaming a state or rewiring a `trigger → state` in `config.yaml` (no code change) alters the flow.
- [x] Typed behaviors `ban_current`, `clear_bans`, `clear_player`, `countdown` and the `when_all_banned` guard reproduce current buzz/ban/timeout behavior exactly.
- [x] Invalid config (bad target, unknown behavior, missing `initial`) fails at startup with a clear error.
- [x] All existing tests pass (rewritten where they referenced `GameState`/flat config).

## Checklist (non-TDD cleanup)

- [ ] `flake8` clean; type hints on new dataclasses/methods
- [ ] `grep -rn "GameState\|return_to_after\|_hold_seconds" gameshow/` returns nothing
- [ ] `config.example.yaml` documents the schema with inline comments
