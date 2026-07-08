---
id: 013-3165
title: Buzz-in mode preset machines (open / after-timeout / after-incorrect)
status: complete
priority: P1
type: feature
created: "2026-07-08T18:09:09.421Z"
updated: "2026-07-08T18:13:18.300Z"
dependencies: []
started_at: "2026-07-08T18:10:14.018Z"
completed_at: "2026-07-08T18:13:18.299Z"
---

# Buzz-in mode preset machines (open / after-timeout / after-incorrect)

## Problem Statement

Each scene needs to choose how a second player may buzz in. Provide three ready-made named machines in the config library: buzz_open (any player anytime), buzz_timeout (only after the first times out), buzz_after_incorrect (only after Incorrect). No turn-pointer or teams; a Player is a single entity.

## Acceptance Criteria

- [x] buzz_open: a new buzz re-locks to the presser at any time; correct/incorrect return to open buzzing
- [x] buzz_timeout: while locked others cannot buzz; after timeout others may buzz
- [x] buzz_after_incorrect: while locked others cannot buzz; after Incorrect others may buzz
- [x] the three machines are defined in config.yaml/config.example.yaml library and documented
- [x] state machine tests verify the distinctive buzz-in behavior of each mode

## Proof

- [x] [completeness] Completeness (buzz_open re-locks to any presser; test_buzz_open_relocks_to_any_presser + smoke)
- [x] [feature-availability] Feature availability (buzz_timeout blocks second buzz while locked; test_buzz_timeout_blocks_second_buzz_while_locked)
- [x] [robustness] Robustness (buzz_after_incorrect opens only after Incorrect; test_buzz_after_incorrect_opens_only_after_incorrect)
- [x] [resilience] Resilience (both shipped configs define the three machines; test_shipped_config_defines_buzz_in_mode_machines)
- [x] [security] Security (three behavior tests plus config load test; suite 202)
- [~] [defense-in-depth] Defense in depth (local config; no untrusted input)
- [x] [input-validation] Input validation (malformed machines rejected at parse per story 006 validation)
- [~] [thread-safety] Thread safety (single-threaded asyncio)
- [x] [configurability] Configurability (buzz-in behavior fully selected per scene by named machine)

## QA

None — covered by tests + smoke

## Work Log

### 2026-07-08T18:13:17.015Z - Completed: shipped three buzz-in mode machines in the config library. buzz_open re-locks to any presser at any time; buzz_timeout blocks others until the locked player times out; buzz_after_incorrect opens to others only after Incorrect. config.yaml references buzz_timeout by default and Round 1 uses buzz_after_incorrect; config.example.yaml documents all three and keeps an extends demo. Behavior tests cover each mode; both shipped configs validated to define the three machines. No turn-pointer or teams - a Player is one entity. 202 tests pass.


### 2026-07-08T18:13:17.469Z - Proof completeness set PROVEN: buzz_open re-locks to any presser; test_buzz_open_relocks_to_any_presser + smoke

### 2026-07-08T18:13:17.547Z - Proof feature-availability set PROVEN: buzz_timeout blocks second buzz while locked; test_buzz_timeout_blocks_second_buzz_while_locked

### 2026-07-08T18:13:17.627Z - Proof robustness set PROVEN: buzz_after_incorrect opens only after Incorrect; test_buzz_after_incorrect_opens_only_after_incorrect

### 2026-07-08T18:13:17.705Z - Proof resilience set PROVEN: both shipped configs define the three machines; test_shipped_config_defines_buzz_in_mode_machines

### 2026-07-08T18:13:17.784Z - Proof security set PROVEN: three behavior tests plus config load test; suite 202

### 2026-07-08T18:13:17.935Z - Proof defense-in-depth set NOT_APPLICABLE: local config; no untrusted input

### 2026-07-08T18:13:18.015Z - Proof input-validation set PROVEN: malformed machines rejected at parse per story 006 validation

### 2026-07-08T18:13:18.096Z - Proof thread-safety set NOT_APPLICABLE: single-threaded asyncio

### 2026-07-08T18:13:18.176Z - Proof configurability set PROVEN: buzz-in behavior fully selected per scene by named machine
