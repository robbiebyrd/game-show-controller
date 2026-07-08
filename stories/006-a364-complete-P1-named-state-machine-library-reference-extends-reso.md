---
id: 006-a364
title: Named state-machine library + reference/extends resolution
status: complete
priority: P1
type: feature
created: "2026-07-08T17:33:00.624Z"
updated: "2026-07-08T17:34:47.000Z"
dependencies: []
started_at: "2026-07-08T17:33:08.571Z"
completed_at: "2026-07-08T17:34:46.999Z"
---

# Named state-machine library + reference/extends resolution

## Problem Statement

Scenes can only deep-merge onto one base state machine. Add a top-level state_machines library; the state_machine value (top-level or per-scene) may be a name string, an inline machine, or {extends: name, ...overrides}. parse_config resolves it to the single active StateMachineConfig.

## Acceptance Criteria

- [x] state_machines library parses into named machines
- [x] state_machine as string resolves from the library
- [x] state_machine as {extends: name, ...} deep-merges overrides onto the named machine
- [x] inline state_machine dict still works
- [x] validation raises on unknown machine name and unknown extends target
- [x] tests cover string, inline, extends, and error cases

## Proof

- [x] [completeness] Completeness (library parses; string/inline/extends resolution covered by 7 new tests)
- [x] [feature-availability] Feature availability (string reference resolves from library; test_state_machine_string_reference_resolves)
- [x] [robustness] Robustness (extends deep-merges overrides; base states preserved; test_state_machine_extends_merges_overrides)
- [~] [resilience] Resilience (parse-time resolution; no timers/concurrency)
- [~] [security] Security (operator-authored local YAML)
- [~] [defense-in-depth] Defense in depth (no security boundary)
- [x] [input-validation] Input validation (unknown name/extends and malformed library entries raise ValueError; 3 negative tests)
- [~] [thread-safety] Thread safety (single-threaded startup parse)
- [x] [configurability] Configurability (each scene/top-level can reference any library machine)

## QA

None — covered by tests

## Work Log

### 2026-07-08T17:34:45.716Z - Completed: added state_machines library + _resolve_state_machine_raw (string reference / inline dict / {extends: name, ...overrides} via deep_merge). All library entries validated up front. Unknown reference and unknown extends base raise ValueError. Inline form still works. 38 config tests pass, full suite 167.


### 2026-07-08T17:34:46.269Z - Proof completeness set PROVEN: library parses; string/inline/extends resolution covered by 7 new tests

### 2026-07-08T17:34:46.349Z - Proof feature-availability set PROVEN: string reference resolves from library; test_state_machine_string_reference_resolves

### 2026-07-08T17:34:46.427Z - Proof robustness set PROVEN: extends deep-merges overrides; base states preserved; test_state_machine_extends_merges_overrides

### 2026-07-08T17:34:46.509Z - Proof resilience set NOT_APPLICABLE: parse-time resolution; no timers/concurrency

### 2026-07-08T17:34:46.587Z - Proof security set NOT_APPLICABLE: operator-authored local YAML

### 2026-07-08T17:34:46.661Z - Proof defense-in-depth set NOT_APPLICABLE: no security boundary

### 2026-07-08T17:34:46.729Z - Proof input-validation set PROVEN: unknown name/extends and malformed library entries raise ValueError; 3 negative tests

### 2026-07-08T17:34:46.801Z - Proof thread-safety set NOT_APPLICABLE: single-threaded startup parse

### 2026-07-08T17:34:46.871Z - Proof configurability set PROVEN: each scene/top-level can reference any library machine
