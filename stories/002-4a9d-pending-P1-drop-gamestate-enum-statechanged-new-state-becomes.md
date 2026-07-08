---
id: 002-4a9d
title: Drop GameState enum; StateChanged.new_state becomes a string
status: pending
priority: P1
type: feature
created: "2026-07-08T16:33:16.153Z"
updated: "2026-07-08T16:33:31.367Z"
dependencies: ["001-72a8"]
---

# Drop GameState enum; StateChanged.new_state becomes a string

## Problem Statement

events.py defines a hard-coded GameState enum and StateChanged.new_state is typed as GameState. States must be plain config strings.

## Acceptance Criteria

- [ ] GameState enum removed from events.py
- [ ] StateChanged.new_state typed as str
- [ ] No GameState references remain anywhere in gameshow/ or tests/
- [ ] tests/test_events.py updated to string states

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

