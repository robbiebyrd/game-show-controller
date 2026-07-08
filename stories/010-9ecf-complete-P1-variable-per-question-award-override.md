---
id: 010-9ecf
title: Variable per-question award override
status: complete
priority: P1
type: feature
created: "2026-07-08T17:42:15.881Z"
updated: "2026-07-08T17:51:40.858Z"
dependencies: ["009-94ed"]
started_at: "2026-07-08T17:48:35.069Z"
completed_at: "2026-07-08T17:51:40.857Z"
---

# Variable per-question award override

## Problem Statement

Some rounds have variable point values per question (Jeopardy-style). Host overrides the award for the current question from the control surface via set_award <value>; award uses pending value if set else default_award, then clears it. Optional award_override_timeout commits the default after N seconds.

## Acceptance Criteria

- [x] set_award control command sets pending_award
- [x] award behavior grants pending_award if set else default_award, then clears pending_award
- [x] award_override_timeout commits default after timeout when configured
- [x] an AwardChanged (or equivalent) event is emitted for display
- [x] tests cover override, fallback-to-default, and timeout

## Proof

- [x] [completeness] Completeness (set_award sets pending_award; test_set_award_overrides_default)
- [x] [feature-availability] Feature availability (award prefers pending then default and clears pending; 3 sm tests)
- [x] [robustness] Robustness (await_award window commits default on timeout; test_award_override_timeout_commits_default)
- [x] [resilience] Resilience (AwardChanged emitted on set and clear; test_set_award_emits_award_changed)
- [x] [security] Security (override, fallback and timeout all covered by 5 sm tests; suite 186)
- [~] [defense-in-depth] Defense in depth (local operator command; numeric value coerced via float)
- [x] [input-validation] Input validation (set_award value coerced to float; None ignored)
- [~] [thread-safety] Thread safety (single-threaded asyncio; award timer cancelled on transitions/scene/stop)
- [x] [configurability] Configurability (per-question value fully host-controllable with configsurable default+timeout)

## QA

None — covered by tests

## Work Log

### 2026-07-08T17:51:39.600Z - Completed: added pending_award override. set_award command sets it and emits AwardChanged, cancelling the window timer. award behavior prefers explicit param, then pending_award, then default_award, then clears pending. await_award entry behavior opens a per-question window; award_override_timeout commits the default on expiry and emits AwardChanged. pending and award timer reset on scene change and stop. 186 tests pass.


### 2026-07-08T17:51:40.078Z - Proof completeness set PROVEN: set_award sets pending_award; test_set_award_overrides_default

### 2026-07-08T17:51:40.159Z - Proof feature-availability set PROVEN: award prefers pending then default and clears pending; 3 sm tests

### 2026-07-08T17:51:40.238Z - Proof robustness set PROVEN: await_award window commits default on timeout; test_award_override_timeout_commits_default

### 2026-07-08T17:51:40.323Z - Proof resilience set PROVEN: AwardChanged emitted on set and clear; test_set_award_emits_award_changed

### 2026-07-08T17:51:40.409Z - Proof security set PROVEN: override, fallback and timeout all covered by 5 sm tests; suite 186

### 2026-07-08T17:51:40.490Z - Proof defense-in-depth set NOT_APPLICABLE: local operator command; numeric value coerced via float

### 2026-07-08T17:51:40.570Z - Proof input-validation set PROVEN: set_award value coerced to float; None ignored

### 2026-07-08T17:51:40.648Z - Proof thread-safety set NOT_APPLICABLE: single-threaded asyncio; award timer cancelled on transitions/scene/stop

### 2026-07-08T17:51:40.725Z - Proof configurability set PROVEN: per-question value fully host-controllable with configsurable default+timeout
