---
id: 003-8885
title: Rewrite StateMachine as a config-driven interpreter
status: pending
priority: P1
type: feature
created: "2026-07-08T16:33:16.256Z"
updated: "2026-07-08T16:33:31.510Z"
dependencies: ["001-72a8", "002-4a9d"]
---

# Rewrite StateMachine as a config-driven interpreter

## Problem Statement

state_machine.py has hard-coded state maps and imperative command handlers. It must interpret the config transition table + typed behaviors (ban_current, clear_bans, clear_player, countdown) and the when_all_banned guard, preserving all current behavior.

## Acceptance Criteria

- [ ] Generic _fire(trigger)/_enter_state driver replaces hard-coded maps and _on_control_command branches
- [ ] buzz sets locked player + emits PlayerBuzzed; countdown_expire routes via config
- [ ] when_all_banned clears bans and redirects; timed_lockout uses arg duration + emits StateChanged.duration
- [ ] countdown pause/resume/reset/cancel still handled directly
- [ ] tests/test_state_machine.py rewritten; all prior behavioral assertions pass

## Proof

- [ ] [completeness] Completeness
- [ ] [feature-availability] Feature availability
- [ ] [robustness] Robustness
- [ ] [resilience] Resilience
- [ ] [security] Security
- [ ] [defense-in-depth] Defense in depth
- [ ] [input-validation] Input validation
- [ ] [thread-safety] Thread safety
- [ ] [configurability] Configurability

## Work Log

