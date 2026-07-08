---
id: 007-e0b5
title: Reset state machine to initial on scene change
status: complete
priority: P1
type: feature
created: "2026-07-08T17:33:00.810Z"
updated: "2026-07-08T17:37:43.597Z"
dependencies: ["006-a364"]
started_at: "2026-07-08T17:35:58.913Z"
completed_at: "2026-07-08T17:37:43.596Z"
---

# Reset state machine to initial on scene change

## Problem Statement

With per-scene machines, the current self.state may not exist in the new scene machine, leaving the FSM stuck. StateMachine must reset flow (state->new initial, clear bans/locked, cancel timers/countdown) when the scene changes. Scores persist (later phase).

## Acceptance Criteria

- [x] StateMachine subscribes to SceneChanged and resets self.state to the new machine initial
- [x] bans, locked_player_id, timers and countdown are cleared on scene change
- [x] a scene referencing a different named machine drives that machine after the switch
- [x] tests verify reset behavior and that buzzing works in the new machine

## Proof

- [x] [completeness] Completeness (subscribes SceneChanged; resets to new machine initial; covered by test_scene_change_resets_to_new_machine_initial)
- [x] [feature-availability] Feature availability (swap machine then SceneChanged drives new machine; buzz works after switch)
- [x] [robustness] Robustness (same-scene refresh guarded by test_repeated_scene_changed_same_scene_does_not_reset)
- [x] [resilience] Resilience (timers and countdown cancelled on reset; full suite 169 green)
- [~] [security] Security (local app; no untrusted input)
- [~] [defense-in-depth] Defense in depth (no security boundary)
- [~] [input-validation] Input validation (no external input parsed here)
- [~] [thread-safety] Thread safety (single-threaded asyncio event handling)
- [x] [configurability] Configurability (runtime per-scene machine switch supported)

## QA

None — covered by tests

## Work Log

### 2026-07-08T17:37:13.014Z - Completed: StateMachine subscribes to SceneChanged and resets flow - state to new machine initial, clear bans and locked player, cancel timer and countdown. Guards refresh publishes with same scene index/name so scene_current does not wipe an in-progress round. Reset is silent to avoid clobbering on_enter visuals. 24 sm tests, full suite 169.


### 2026-07-08T17:37:42.777Z - Proof completeness set PROVEN: subscribes SceneChanged; resets to new machine initial; covered by test_scene_change_resets_to_new_machine_initial

### 2026-07-08T17:37:42.850Z - Proof feature-availability set PROVEN: swap machine then SceneChanged drives new machine; buzz works after switch

### 2026-07-08T17:37:42.921Z - Proof robustness set PROVEN: same-scene refresh guarded by test_repeated_scene_changed_same_scene_does_not_reset

### 2026-07-08T17:37:43.000Z - Proof resilience set PROVEN: timers and countdown cancelled on reset; full suite 169 green

### 2026-07-08T17:37:43.150Z - Proof security set NOT_APPLICABLE: local app; no untrusted input

### 2026-07-08T17:37:43.232Z - Proof defense-in-depth set NOT_APPLICABLE: no security boundary

### 2026-07-08T17:37:43.312Z - Proof input-validation set NOT_APPLICABLE: no external input parsed here

### 2026-07-08T17:37:43.392Z - Proof thread-safety set NOT_APPLICABLE: single-threaded asyncio event handling

### 2026-07-08T17:37:43.472Z - Proof configurability set PROVEN: runtime per-scene machine switch supported
