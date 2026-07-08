---
id: 011-4328
title: Control surface + OSC feedback for scores and award value
status: pending
priority: P2
type: feature
created: "2026-07-08T17:42:15.985Z"
updated: "2026-07-08T17:43:43.365Z"
dependencies: ["009-94ed", "010-9ecf"]
---

# Control surface + OSC feedback for scores and award value

## Problem Statement

Scores and the pending award value need to reach the operator. Add a control-surface button type to set the award value (preset grid), a score display, and OSC feedback for ScoreChanged and pending award.

## Acceptance Criteria

- [ ] control-surface button emits set_award <value> (preset value buttons)
- [ ] a score display button shows current player scores
- [ ] osc_server emits feedback for ScoreChanged and pending award
- [ ] tests cover the new button dispatch and feedback

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

