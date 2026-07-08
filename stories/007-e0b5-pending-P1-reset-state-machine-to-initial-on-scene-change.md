---
id: 007-e0b5
title: Reset state machine to initial on scene change
status: pending
priority: P1
type: feature
created: "2026-07-08T17:33:00.810Z"
updated: "2026-07-08T17:33:08.369Z"
dependencies: ["006-a364"]
---

# Reset state machine to initial on scene change

## Problem Statement

With per-scene machines, the current self.state may not exist in the new scene machine, leaving the FSM stuck. StateMachine must reset flow (state->new initial, clear bans/locked, cancel timers/countdown) when the scene changes. Scores persist (later phase).

## Acceptance Criteria

- [ ] StateMachine subscribes to SceneChanged and resets self.state to the new machine initial
- [ ] bans, locked_player_id, timers and countdown are cleared on scene change
- [ ] a scene referencing a different named machine drives that machine after the switch
- [ ] tests verify reset behavior and that buzzing works in the new machine

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

