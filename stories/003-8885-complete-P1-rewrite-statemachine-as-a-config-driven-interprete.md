---
id: 003-8885
title: Rewrite StateMachine as a config-driven interpreter
status: complete
priority: P1
type: feature
created: "2026-07-08T16:33:16.256Z"
updated: "2026-07-08T16:50:18.748Z"
dependencies: ["001-72a8", "002-4a9d"]
started_at: "2026-07-08T16:45:35.937Z"
completed_at: "2026-07-08T16:50:18.747Z"
---

# Rewrite StateMachine as a config-driven interpreter

## Problem Statement

state_machine.py has hard-coded state maps and imperative command handlers. It must interpret the config transition table + typed behaviors (ban_current, clear_bans, clear_player, countdown) and the when_all_banned guard, preserving all current behavior.

## Acceptance Criteria

- [x] Generic _fire(trigger)/_enter_state driver replaces hard-coded maps and _on_control_command branches
- [x] buzz sets locked player + emits PlayerBuzzed; countdown_expire routes via config
- [x] when_all_banned clears bans and redirects; timed_lockout uses arg duration + emits StateChanged.duration
- [x] countdown pause/resume/reset/cancel still handled directly
- [x] tests/test_state_machine.py rewritten; all prior behavioral assertions pass

## Proof

- [x] [completeness] Completeness (interpreter implemented; 22 behavioral tests pass)
- [x] [feature-availability] Feature availability (all triggers/transitions sourced from config; verified by test_state_machine suite)
- [x] [robustness] Robustness (ban/countdown/timeout/exhaustion paths covered by 22 tests)
- [x] [resilience] Resilience (pause/resume/reset/cancel + supersede/expire timers covered by tests)
- [~] [security] Security (local operator input only; no untrusted data or auth surface)
- [~] [defense-in-depth] Defense in depth (no security boundary in FSM interpreter)
- [x] [input-validation] Input validation (unknown triggers ignored; config validated at parse time in story 001)
- [~] [thread-safety] Thread safety (single-threaded asyncio; no shared mutable state across threads)
- [x] [configurability] Configurability (states/transitions/behaviors/flow fully driven by config.state_machine)

## QA

None — covered by tests

## Work Log

### 2026-07-08T16:50:16.979Z - Completed: rewrote StateMachine as a config interpreter. _fire resolves trigger via state.transitions then global_; _resolve_target runs do-behaviors + when_all_banned guard; _enter_state applies entry behaviors/countdown/hold+then; buzz sets locked player + emits PlayerBuzzed; countdown expiry fires countdown_expire; timed_lockout uses arg duration via hold_from_arg + emits StateChanged.duration; countdown controls handled directly. 22 state_machine tests pass.


### 2026-07-08T16:50:17.781Z - Proof completeness set PROVEN: interpreter implemented; 22 behavioral tests pass

### 2026-07-08T16:50:17.955Z - Proof feature-availability set PROVEN: all triggers/transitions sourced from config; verified by test_state_machine suite

### 2026-07-08T16:50:18.093Z - Proof robustness set PROVEN: ban/countdown/timeout/exhaustion paths covered by 22 tests

### 2026-07-08T16:50:18.205Z - Proof resilience set PROVEN: pause/resume/reset/cancel + supersede/expire timers covered by tests

### 2026-07-08T16:50:18.296Z - Proof security set NOT_APPLICABLE: local operator input only; no untrusted data or auth surface

### 2026-07-08T16:50:18.385Z - Proof defense-in-depth set NOT_APPLICABLE: no security boundary in FSM interpreter

### 2026-07-08T16:50:18.465Z - Proof input-validation set PROVEN: unknown triggers ignored; config validated at parse time in story 001

### 2026-07-08T16:50:18.545Z - Proof thread-safety set NOT_APPLICABLE: single-threaded asyncio; no shared mutable state across threads

### 2026-07-08T16:50:18.623Z - Proof configurability set PROVEN: states/transitions/behaviors/flow fully driven by config.state_machine
