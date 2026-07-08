---
id: 004-790f
title: Update state consumers to string states
status: pending
priority: P1
type: feature
created: "2026-07-08T16:33:24.204Z"
updated: "2026-07-08T16:33:31.576Z"
dependencies: ["002-4a9d"]
---

# Update state consumers to string states

## Problem Statement

obs_client, audio, dmx_client, control_surface use event.new_state.name.lower(); osc_server compares GameState members. All must consume the state string.

## Acceptance Criteria

- [ ] obs_client/audio/dmx_client/control_surface use event.new_state directly
- [ ] osc_server drops GameState; emits duration feedback when event.duration is not None; resets player when event.player_id is None
- [ ] Consumer tests publish string StateChanged and still assert lookups/feedback

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

