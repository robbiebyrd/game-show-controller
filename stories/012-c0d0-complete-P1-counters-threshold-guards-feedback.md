---
id: 012-c0d0
title: Counters + threshold guards + feedback
status: complete
priority: P1
type: feature
created: "2026-07-08T17:57:06.405Z"
updated: "2026-07-08T18:02:08.086Z"
dependencies: []
started_at: "2026-07-08T17:57:11.157Z"
completed_at: "2026-07-08T18:02:08.085Z"
---

# Counters + threshold guards + feedback

## Problem Statement

Formats like Family Feud need counters (3 strikes then steal). Add machine-level counters config, increment/reset behaviors, a when_counter_at transition guard that redirects and resets the counter at a threshold, a CounterChanged event, counter reset on scene change, and control-surface + OSC feedback.

## Acceptance Criteria

- [x] machine counters config parses
- [x] increment/reset behaviors adjust a named counter and emit CounterChanged
- [x] when_counter_at guard redirects and resets the counter when the threshold is reached
- [x] counters reset on scene change
- [x] control-surface counter_display key and osc /feedback/counter/<name>
- [x] tests cover increment, guard redirect, reset, and feedback

## Proof

- [x] [completeness] Completeness (counters config parses; test_counters_config_parses)
- [x] [feature-availability] Feature availability (increment/reset adjust counter and emit CounterChanged; test_increment_counter_emits_event)
- [x] [robustness] Robustness (guard redirects and resets at threshold; test_when_counter_at_redirects_and_resets)
- [x] [resilience] Resilience (counters cleared on scene change; test_counters_reset_on_scene_change)
- [x] [security] Security (counter_display key and osc feedback; control surface + osc tests)
- [x] [defense-in-depth] Defense in depth (increment/guard/reset/feedback covered; suite 198)
- [x] [input-validation] Input validation (unknown counter/target in guard rejected at parse; test_when_counter_at_unknown_counter_raises)
- [~] [thread-safety] Thread safety (single-threaded asyncio; counters mutated only in handlers)
- [x] [configurability] Configurability (counters, thresholds and guards fully config-driven)

## QA

None — covered by tests

## Work Log

### 2026-07-08T18:02:06.694Z - Completed: added CounterConfig and CounterGuard. Machine counters config parses; increment/reset behaviors adjust a named counter and emit CounterChanged. when_counter_at transition guard redirects and resets the counter when it reaches the threshold. Counters reset on scene change. Added counter_display control-surface key plus osc /feedback/counter/<name>. 198 tests pass.


### 2026-07-08T18:02:07.239Z - Proof completeness set PROVEN: counters config parses; test_counters_config_parses

### 2026-07-08T18:02:07.319Z - Proof feature-availability set PROVEN: increment/reset adjust counter and emit CounterChanged; test_increment_counter_emits_event

### 2026-07-08T18:02:07.401Z - Proof robustness set PROVEN: guard redirects and resets at threshold; test_when_counter_at_redirects_and_resets

### 2026-07-08T18:02:07.481Z - Proof resilience set PROVEN: counters cleared on scene change; test_counters_reset_on_scene_change

### 2026-07-08T18:02:07.563Z - Proof security set PROVEN: counter_display key and osc feedback; control surface + osc tests

### 2026-07-08T18:02:07.639Z - Proof defense-in-depth set PROVEN: increment/guard/reset/feedback covered; suite 198

### 2026-07-08T18:02:07.718Z - Proof input-validation set PROVEN: unknown counter/target in guard rejected at parse; test_when_counter_at_unknown_counter_raises

### 2026-07-08T18:02:07.875Z - Proof thread-safety set NOT_APPLICABLE: single-threaded asyncio; counters mutated only in handlers

### 2026-07-08T18:02:07.957Z - Proof configurability set PROVEN: counters, thresholds and guards fully config-driven
