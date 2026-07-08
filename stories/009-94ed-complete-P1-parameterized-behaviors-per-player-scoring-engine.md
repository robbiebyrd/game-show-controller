---
id: 009-94ed
title: Parameterized behaviors + per-player scoring engine
status: complete
priority: P1
type: feature
created: "2026-07-08T17:42:15.777Z"
updated: "2026-07-08T17:47:13.535Z"
dependencies: []
started_at: "2026-07-08T17:43:43.430Z"
completed_at: "2026-07-08T17:47:13.534Z"
---

# Parameterized behaviors + per-player scoring engine

## Problem Statement

Behaviors are bare strings with no scoring. Add parameterized behavior grammar (str or {name: param}), a per-player score store in StateMachine, award/deduct/reset_scores behaviors, machine-level scoring config (default_award/default_deduct), and a ScoreChanged event. Scores persist across scenes; reset_scores_on_enter forces a fresh start.

## Acceptance Criteria

- [x] Behavior entries parse as bare string or single-key {name: param}, back-compatible with existing string lists
- [x] machine scoring config parses
- [x] award/deduct/reset_scores adjust the locked/current player score and emit ScoreChanged
- [x] scores persist across scene changes; per-scene reset_scores_on_enter resets them
- [x] unknown behavior names still raise at parse
- [x] tests cover grammar, award/deduct/reset, and scene persistence

## Proof

- [x] [completeness] Completeness (grammar parses str and single-key map; back-compatible; test_behavior_string_and_map_parse plus bare-string test)
- [x] [feature-availability] Feature availability (machine scoring config parses; test_scoring_config_parses)
- [x] [robustness] Robustness (award/deduct/reset adjust locked player score and emit ScoreChanged; 4 sm tests)
- [x] [resilience] Resilience (scores persist across scene change; reset_scores_on_enter clears; 2 sm tests)
- [x] [security] Security (unknown map behavior raises; test_unknown_map_behavior_raises)
- [~] [defense-in-depth] Defense in depth (local app; no untrusted input or auth)
- [x] [input-validation] Input validation (unknown behavior names rejected at parse)
- [~] [thread-safety] Thread safety (single-threaded asyncio; scores mutated only in handlers)
- [x] [configurability] Configurability (scoring behaviors and amounts fully config-driven per machine)

## QA

None — covered by tests

## Work Log

### 2026-07-08T17:47:12.223Z - Completed: added Behavior dataclass with str or single-key map grammar, normalized in TransitionConfig/StateConfig post_init so bare-string lists stay compatible. Added ScoringConfig on the machine plus reset_scores_on_enter. StateMachine gained per-player scores; award/deduct/reset_scores behaviors run async and emit ScoreChanged. Scores persist across scene changes unless the new machine sets reset_scores_on_enter. 181 tests pass.


### 2026-07-08T17:47:12.764Z - Proof completeness set PROVEN: grammar parses str and single-key map; back-compatible; test_behavior_string_and_map_parse plus bare-string test

### 2026-07-08T17:47:12.844Z - Proof feature-availability set PROVEN: machine scoring config parses; test_scoring_config_parses

### 2026-07-08T17:47:12.924Z - Proof robustness set PROVEN: award/deduct/reset adjust locked player score and emit ScoreChanged; 4 sm tests

### 2026-07-08T17:47:13.010Z - Proof resilience set PROVEN: scores persist across scene change; reset_scores_on_enter clears; 2 sm tests

### 2026-07-08T17:47:13.089Z - Proof security set PROVEN: unknown map behavior raises; test_unknown_map_behavior_raises

### 2026-07-08T17:47:13.169Z - Proof defense-in-depth set NOT_APPLICABLE: local app; no untrusted input or auth

### 2026-07-08T17:47:13.248Z - Proof input-validation set PROVEN: unknown behavior names rejected at parse

### 2026-07-08T17:47:13.325Z - Proof thread-safety set NOT_APPLICABLE: single-threaded asyncio; scores mutated only in handlers

### 2026-07-08T17:47:13.402Z - Proof configurability set PROVEN: scoring behaviors and amounts fully config-driven per machine
