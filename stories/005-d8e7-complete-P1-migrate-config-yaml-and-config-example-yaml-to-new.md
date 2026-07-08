---
id: 005-d8e7
title: Migrate config.yaml and config.example.yaml to new schema
status: complete
priority: P1
type: feature
created: "2026-07-08T16:33:24.308Z"
updated: "2026-07-08T16:57:34.612Z"
dependencies: ["001-72a8"]
started_at: "2026-07-08T16:55:59.074Z"
completed_at: "2026-07-08T16:57:34.612Z"
---

# Migrate config.yaml and config.example.yaml to new schema

## Problem Statement

config.yaml and config.example.yaml still use the flat state_machine block and the Round 1 scene override return_to_after_incorrect.

## Acceptance Criteria

- [x] state_machine block replaced with initial/global/states transition table + behaviors
- [x] Round 1 scene override becomes states.incorrect.then: allow_next
- [x] config.example.yaml documents the schema with inline comments
- [x] load_config(config.yaml) parses clean and full pytest is green

## Proof

- [x] [completeness] Completeness (both files load_config clean; states set verified via script)
- [x] [feature-availability] Feature availability (scene override resolves incorrect.then to allow_next; base stays idle)
- [x] [robustness] Robustness (end-to-end smoke through real config.yaml exercises full flow)
- [~] [resilience] Resilience (config load happens once at startup; no timers)
- [~] [security] Security (operator-authored local YAML; no untrusted input)
- [~] [defense-in-depth] Defense in depth (no security boundary)
- [x] [input-validation] Input validation (invalid configs rejected by _validate_state_machine from story 001)
- [~] [thread-safety] Thread safety (single-threaded startup parse)
- [x] [configurability] Configurability (entire game flow now lives in config.yaml states/transitions/global)

## QA

None — covered by tests + end-to-end smoke

## Work Log

### 2026-07-08T16:57:33.436Z - Completed: migrated config.yaml + config.example.yaml to the initial/global/states schema; Round 1 scene override now uses states.incorrect.then=allow_next; config.example.yaml documents the full schema and the transitions-not-on gotcha. Both parse clean, scene override resolves, 161 tests pass, end-to-end smoke through real config verified idle->locked->incorrect->locked->correct->game_over->clear->idle.


### 2026-07-08T16:57:33.846Z - Proof completeness set PROVEN: both files load_config clean; states set verified via script

### 2026-07-08T16:57:33.928Z - Proof feature-availability set PROVEN: scene override resolves incorrect.then to allow_next; base stays idle

### 2026-07-08T16:57:34.010Z - Proof robustness set PROVEN: end-to-end smoke through real config.yaml exercises full flow

### 2026-07-08T16:57:34.093Z - Proof resilience set NOT_APPLICABLE: config load happens once at startup; no timers

### 2026-07-08T16:57:34.173Z - Proof security set NOT_APPLICABLE: operator-authored local YAML; no untrusted input

### 2026-07-08T16:57:34.255Z - Proof defense-in-depth set NOT_APPLICABLE: no security boundary

### 2026-07-08T16:57:34.333Z - Proof input-validation set PROVEN: invalid configs rejected by _validate_state_machine from story 001

### 2026-07-08T16:57:34.412Z - Proof thread-safety set NOT_APPLICABLE: single-threaded startup parse

### 2026-07-08T16:57:34.486Z - Proof configurability set PROVEN: entire game flow now lives in config.yaml states/transitions/global
