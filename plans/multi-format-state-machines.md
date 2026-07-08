---
status: draft
created: 2026-07-08
---
# Plan: Multi-Format State Machines (named machines + scoring/counters/turns)

**Created:** 2026-07-08 | **Status:** Draft — schema needs sign-off | **Effort:** XL | **Branch:** feat/configurable-state-machine

## Summary

Build on the config-driven state machine so a single show can run many game formats. Two axes:
1. **Named machines + scene reference** — a top-level `state_machines:` library of complete machines; each scene picks one by name (or defines one inline). Replaces the merge-on-one-base model.
2. **Richer mechanics** — parameterized behaviors for **scoring** (per player/team), **counters** (e.g. Feud's 3 strikes) with threshold guards, and **turn/control** (board control, pass/steal).

Delivered in independently-shippable phases; each phase keeps the suite green.

## Architecture Context

- `StateMachine` (gameshow/state_machine.py) interprets `config().state_machine`: `_fire(trigger)` → resolve via `state.transitions` then `global_` → `_resolve_target` runs `do` behaviors + `when_all_banned` guard → `_enter_state` applies entry behaviors/countdown/hold+then. Runtime state today: `self.state`, `locked_player_id`, `_banned`.
- `SceneManager` deep-merges each scene's raw override onto base raw and re-`parse_config`s → `current_config`. `StateMachine` reads `config()` live, so the active machine is whatever `current_config.state_machine` resolves to.
- Consumers subscribe to `StateChanged`/`PlayerBuzzed`/`CountdownTick`; OSC/control-surface render feedback. New runtime facts (scores/counters/turn) need new events to reach them.
- Behaviors are currently bare strings validated against `config.STATE_BEHAVIORS`. Parameterized behaviors require the grammar to accept `{name: param}` entries.

## Proposed Config Schema (NEEDS SIGN-OFF)

```yaml
# A library of complete machines. `state_machine` (top-level and per-scene) is
# either a NAME referencing this library, or an inline machine, or
# { extends: <name>, ... } to tweak a named one.
state_machines:
  buzz_qa:
    initial: idle
    scoring: { default_award: 100, default_deduct: 0 }   # optional; enables scores
    global: { clear: { to: idle, do: [clear_bans, clear_player, reset_scores] } }
    states:
      idle:   { transitions: { buzz: locked } }
      locked:
        behaviors: [countdown]
        transitions:
          correct:   { to: correct,   do: [award] }        # award default_award to locked player
          incorrect: { to: incorrect, do: [deduct, ban_current] }
      correct:   { hold: 2.0, then: idle }
      incorrect: { hold: 2.0, then: idle, transitions: { buzz: locked } }

  face_off:                                                # Feud-style
    initial: ready
    counters: { strikes: { max: 3 } }
    turn: { order: [1, 2] }                                # or "teams"
    states:
      ready: { transitions: { buzz: answering } }
      answering:
        transitions:
          correct:   { to: answering, do: [{ award: 10 }] }
          incorrect:
            to: answering
            do: [{ increment: strikes }]
            guards: [ { when_counter_at: { strikes: 3 }, to: steal } ]
          pass: { to: answering, do: [next_turn] }
      steal: { transitions: { correct: won, incorrect: won } }
      won:   {}

show:
  scenes:
    - name: "Face Off"
      state_machine: face_off                              # reference by name
    - name: "Round 1"
      state_machine: { extends: buzz_qa, states: { incorrect: { then: allow_next } } }
```

**Grammar additions:**
- `state_machine` value (top-level or scene): `str` (library name) | inline machine `dict` | `{ extends: <name>, <overrides> }` (deep-merge overrides onto the named machine).
- Behavior list entries: bare `str` (existing) **or** single-key map `{name: param}` (e.g. `{award: 100}`, `{increment: strikes}`).
- **Scoring behaviors:** `award` / `deduct` (amount = param, else machine `scoring.default_*`), `reset_scores`. Target = locked/current player (or their team when `teams` defined).
- **Counter behaviors:** `{increment: <name>}`, `{reset: <name>}`; machine-level `counters: {<name>: {max, initial}}`.
- **Turn behaviors:** `next_turn`, `{set_turn: <player|buzzer>}`; machine-level `turn: {order: [...] | teams}`. Turn-restricted triggers only fire for the current-turn player.
- **Guards:** generalize `when_all_banned` into an optional ordered `guards: [{ when_<cond>: {...}, to: <state>, do: [...] }]` list; `when_all_banned` kept as sugar. Conditions: `when_all_banned`, `when_counter_at: {<name>: <value>}`.

## Phasing (each independently shippable + tested)

**Phase A — Named machines + scene reference. ✅ DONE** (stories 006/007/008). Added `state_machines` library; `state_machine` resolves str | inline | `{extends}`; `StateMachine` resets to the new machine's `initial` on scene change (refresh-guarded); config files migrated to the `standard` named machine. *This alone satisfies "each scene sets its own state machine."*

**Phase B — Parameterized behaviors + scoring (incl. variable per-question award). ✅ DONE** (stories 009/010/011). Behavior grammar accepts `{name: param}`; per-player `scores`; `award`/`deduct`/`reset_scores`; machine `scoring`; `ScoreChanged`/`AwardChanged` events; `set_award` override + `await_award` window; control-surface `set_award`/`score_display` + OSC feedback.

*Variable per-question award (resolved decision #2):* the host may override the point value for the current question from the control surface.
```yaml
scoring:
  default_award: 100
  award_override_timeout: 10        # optional: seconds to punch in a custom value
```
- Runtime `pending_award: Optional[float]`.
- Control command `set_award <value>` (a control-surface button/keypad) sets `pending_award`.
- The `award` behavior grants `pending_award if set else default_award`, then clears `pending_award`.
- If `award_override_timeout` is set, entering the "question live" state starts a timer; on expiry `pending_award` commits to `default_award` (for display). Emits an event so the value shows on the surface.

**Phase C — Counters + guards. ✅ DONE** (story 012). Machine `counters`; `increment`/`reset` behaviors; `when_counter_at` transition guard (redirect + reset at threshold); `CounterChanged` event; counters reset per scene; `counter_display` key + OSC feedback.

**Phase D — Buzz-in mode presets (REPLACES the turn/control idea). ✅ DONE** (story 013). Clarified with Robbie: there is NO turn-pointer system. A "Player" is a single scoring/control entity (may represent multiple humans), so teams are not needed. Buzzer/player control is entirely the per-scene state machine (Phase A). The variation is three buzz-in modes, each a named machine a scene picks:
- `buzz_open` — any player can buzz at any time (a new buzz re-locks to the presser; no bans/timeout).
- `buzz_timeout` — a second player may buzz only after the first times out (the current `standard` machine).
- `buzz_after_incorrect` — a second player may buzz only after Incorrect is pressed (`incorrect → allow_next`).
Ship these three in the config library, documented, with behavior tests.

## Resolved Decisions

1. **Scene-change reset:** entering a scene resets flow (state → new machine's `initial`, counters, turn, `pending_award`). Player **scores persist** across scenes (running game total). Per-scene `reset_scores_on_enter: true` forces a fresh start.
2. **Variable question values:** yes — control-surface `set_award <value>` override, `default_award` fallback after `award_override_timeout`. See Phase B.
3. **Teams:** per-player scoring in Phase B; teams deferred to a later follow-on.
4. **Inline `state_machine` stays valid:** the `state_machines` library is additive; an inline machine (today's form) still works, and top-level/scene `state_machine` may be a name, an inline dict, or `{extends: <name>, ...}`.

## Security / Performance

- None — local operator YAML, human-rate transitions. Validation must fail loudly at parse (unknown machine name, unknown counter/behavior, turn order referencing unknown players).

## Next Step

Confirm/adjust the schema and the four open decisions. Then I'll create stories per phase (Phase A first) and implement TDD. NOT starting code until the schema is signed off.
