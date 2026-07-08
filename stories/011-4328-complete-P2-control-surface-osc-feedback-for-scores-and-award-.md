---
id: 011-4328
title: Control surface + OSC feedback for scores and award value
status: complete
priority: P2
type: feature
created: "2026-07-08T17:42:15.985Z"
updated: "2026-07-08T17:55:56.238Z"
dependencies: ["009-94ed", "010-9ecf"]
started_at: "2026-07-08T17:52:56.011Z"
completed_at: "2026-07-08T17:55:56.237Z"
---

# Control surface + OSC feedback for scores and award value

## Problem Statement

Scores and the pending award value need to reach the operator. Add a control-surface button type to set the award value (preset grid), a score display, and OSC feedback for ScoreChanged and pending award.

## Acceptance Criteria

- [x] control-surface button emits  <value>
- [x] a score display button shows current player scores
- [x] osc_server emits feedback for ScoreChset_awardanged and pending award
- [x] tests cover the new button dispatch and feedback

## Proof

- [x] [completeness] Completeness (set_award button dispatches ControlCommand with value; parametrized dispatch test)
- [x] [feature-availability] Feature availability (score_display key reflects ScoreChanged; test_score_display_reflects_score_changes)
- [x] [robustness] Robustness (osc emits score and award feedback; 2 osc tests)
- [x] [resilience] Resilience (button dispatch and feedback covered; suite 190)
- [~] [security] Security (local operator surface; no untrusted input)
- [~] [defense-in-depth] Defense in depth (no security boundary)
- [x] [input-validation] Input validation (None award coerced for OSC; numeric value via ButtonConfig)
- [~] [thread-safety] Thread safety (single-threaded asyncio UI updates)
- [x] [configurability] Configurability (award buttons and score display fully config-driven)

## QA

- [ ] Visual: verify score_display and award value render legibly on the physical Stream Deck

## Work Log

### 2026-07-08T17:55:55.041Z - Completed: added set_award control-surface button type via a value field and the _DIRECT_COMMANDS map, plus a score_display live key that tracks ScoreChanged. osc_server now emits /feedback/score/<id> on ScoreChanged and /feedback/award on AwardChanged, coercing None to the string None for OSC safety. 190 tests pass.


### 2026-07-08T17:55:55.466Z - Proof completeness set PROVEN: set_award button dispatches ControlCommand with value; parametrized dispatch test

### 2026-07-08T17:55:55.549Z - Proof feature-availability set PROVEN: score_display key reflects ScoreChanged; test_score_display_reflects_score_changes

### 2026-07-08T17:55:55.632Z - Proof robustness set PROVEN: osc emits score and award feedback; 2 osc tests

### 2026-07-08T17:55:55.716Z - Proof resilience set PROVEN: button dispatch and feedback covered; suite 190

### 2026-07-08T17:55:55.798Z - Proof security set NOT_APPLICABLE: local operator surface; no untrusted input

### 2026-07-08T17:55:55.881Z - Proof defense-in-depth set NOT_APPLICABLE: no security boundary

### 2026-07-08T17:55:55.962Z - Proof input-validation set PROVEN: None award coerced for OSC; numeric value via ButtonConfig

### 2026-07-08T17:55:56.040Z - Proof thread-safety set NOT_APPLICABLE: single-threaded asyncio UI updates

### 2026-07-08T17:55:56.115Z - Proof configurability set PROVEN: award buttons and score display fully config-driven
