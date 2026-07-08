---
id: 001-72a8
title: Config schema + validation for data-driven state machine
status: complete
priority: P1
type: feature
created: "2026-07-08T16:33:05.149Z"
updated: "2026-07-08T16:44:10.038Z"
dependencies: []
started_at: "2026-07-08T16:40:39.670Z"
completed_at: "2026-07-08T16:44:10.037Z"
---

# Config schema + validation for data-driven state machine

## Problem Statement

config.py has a flat StateMachineConfig (return_to_after_*, *_hold_seconds) with VALID_RETURN_TARGETS. Replace it with a states/initial/global schema that expresses a transition table plus typed behaviors, and validate it at parse time.

## Acceptance Criteria

- [x] StateMachineConfig(initial, states, global_) with StateConfig(on, behaviors, hold, hold_from_arg, then) and TransitionConfig(to, do, when_all_banned)
- [x] String and mapping transitions both parse
- [x] Validation raises ValueError on unknown state target, unknown behavior, missing initial, or absent states block
- [x] Old flat fields and VALID_RETURN_TARGETS/_validate_return_targets removed
- [x] tests/test_config.py covers parse + each validation failure

## Proof

- [x] [completeness] Completeness (all schema fields implemented and parsed; 32 config tests pass)
- [x] [feature-availability] Feature availability (new state_machine schema parsed into AppConfig.state_machine; verified by test_state_machine_parses_initial_and_states)
- [x] [robustness] Robustness (invalid target/behavior/guard/missing keys raise ValueError; 7 validation tests)
- [~] [resilience] Resilience (no concurrency introduced; pure sync parse of local YAML)
- [~] [security] Security (local operator-authored config; no untrusted input or auth surface)
- [~] [defense-in-depth] Defense in depth (no security boundary in config parsing)
- [x] [input-validation] Input validation (_validate_state_machine rejects unknown targets/behaviors/guards + missing initial/states; covered by tests)
- [~] [thread-safety] Thread safety (single-threaded asyncio app; config parsed once at startup)
- [x] [configurability] Configurability (states/transitions/behaviors/global all sourced from config.yaml; test_config covers parse)

## QA

None — covered by tests

## Work Log

### 2026-07-08T16:43:28.157Z - Completed: replaced flat StateMachineConfig with initial/states/global schema (StateConfig, TransitionConfig, StateMachineConfig), added _parse_state_machine + _validate_state_machine (unknown target/behavior/guard, missing initial/states). Renamed transition key to 'transitions' to avoid YAML on->True coercion. Removed VALID_RETURN_TARGETS/_validate_return_targets. 32 config tests pass.


### 2026-07-08T16:43:55.701Z - Proof feature-availability set PROVEN: new state_machine schema parsed into AppConfig.state_machine; verified by test_state_machine_parses_initial_and_states

### 2026-07-08T16:43:55.782Z - Proof robustness set PROVEN: invalid target/behavior/guard/missing keys raise ValueError; 7 validation tests

### 2026-07-08T16:43:55.864Z - Proof resilience set NOT_APPLICABLE: no concurrency introduced; pure sync parse of local YAML

### 2026-07-08T16:43:56.020Z - Proof security set NOT_APPLICABLE: local operator-authored config; no untrusted input or auth surface

### 2026-07-08T16:43:56.103Z - Proof defense-in-depth set NOT_APPLICABLE: no security boundary in config parsing

### 2026-07-08T16:43:56.187Z - Proof input-validation set PROVEN: _validate_state_machine rejects unknown targets/behaviors/guards + missing initial/states; covered by tests

### 2026-07-08T16:43:56.270Z - Proof thread-safety set NOT_APPLICABLE: single-threaded asyncio app; config parsed once at startup

### 2026-07-08T16:43:56.357Z - Proof configurability set PROVEN: states/transitions/behaviors/global all sourced from config.yaml; test_config covers parse

### 2026-07-08T16:44:09.905Z - Proof completeness set PROVEN: all schema fields implemented and parsed; 32 config tests pass
