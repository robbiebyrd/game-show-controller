---
id: 010-9ecf
title: Variable per-question award override
status: pending
priority: P1
type: feature
created: "2026-07-08T17:42:15.881Z"
updated: "2026-07-08T17:43:43.234Z"
dependencies: ["009-94ed"]
---

# Variable per-question award override

## Problem Statement

Some rounds have variable point values per question (Jeopardy-style). Host overrides the award for the current question from the control surface via set_award <value>; award uses pending value if set else default_award, then clears it. Optional award_override_timeout commits the default after N seconds.

## Acceptance Criteria

- [ ] set_award control command sets pending_award
- [ ] award behavior grants pending_award if set else default_award, then clears pending_award
- [ ] award_override_timeout commits default after timeout when configured
- [ ] an AwardChanged (or equivalent) event is emitted for display
- [ ] tests cover override, fallback-to-default, and timeout

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

