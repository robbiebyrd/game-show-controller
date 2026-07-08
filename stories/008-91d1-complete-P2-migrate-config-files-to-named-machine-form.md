---
id: 008-91d1
title: Migrate config files to named-machine form
status: complete
priority: P2
type: feature
created: "2026-07-08T17:33:00.912Z"
updated: "2026-07-08T17:39:52.790Z"
dependencies: ["006-a364", "007-e0b5"]
started_at: "2026-07-08T17:38:01.631Z"
completed_at: "2026-07-08T17:39:52.789Z"
---

# Migrate config files to named-machine form

## Problem Statement

config.yaml/config.example.yaml define a single inline state_machine. Restructure into a state_machines library with the current flow named (e.g. standard), reference it top-level, and convert the Round 1 scene override to {extends: standard, ...}.

## Acceptance Criteria

- [x] config.yaml and config.example.yaml use state_machines library + top-level reference
- [x] Round 1 scene override uses extends
- [x] both files load clean and full suite is green
- [x] end-to-end smoke through real config still works

## Proof

- [x] [completeness] Completeness (both files use library plus top-level reference; verified by load script)
- [x] [feature-availability] Feature availability (Round 1 extends standard resolves to allow_next; base stays idle)
- [x] [robustness] Robustness (both load clean; full suite 169 green)
- [x] [resilience] Resilience (end-to-end smoke on real config: idle to locked to correct to idle)
- [~] [security] Security (operator-authored local YAML)
- [~] [defense-in-depth] Defense in depth (no security boundary)
- [x] [input-validation] Input validation (unknown machine refs rejected at parse per story 006)
- [~] [thread-safety] Thread safety (config parsed once at startup)
- [x] [configurability] Configurability (config expresses a machine library scenes can pick from)

## QA

None — covered by tests + smoke

## Work Log

### 2026-07-08T17:39:51.585Z - Completed: both config files now define a state_machines library with the current flow named standard and reference it via top-level state_machine standard. Round 1 scene override uses extends standard. Docs updated. Both parse clean, extends resolves, end-to-end smoke passes, full suite 169.


### 2026-07-08T17:39:51.918Z - Proof completeness set PROVEN: both files use library plus top-level reference; verified by load script

### 2026-07-08T17:39:52.029Z - Proof feature-availability set PROVEN: Round 1 extends standard resolves to allow_next; base stays idle

### 2026-07-08T17:39:52.186Z - Proof robustness set PROVEN: both load clean; full suite 169 green

### 2026-07-08T17:39:52.265Z - Proof resilience set PROVEN: end-to-end smoke on real config: idle to locked to correct to idle

### 2026-07-08T17:39:52.347Z - Proof security set NOT_APPLICABLE: operator-authored local YAML

### 2026-07-08T17:39:52.428Z - Proof defense-in-depth set NOT_APPLICABLE: no security boundary

### 2026-07-08T17:39:52.511Z - Proof input-validation set PROVEN: unknown machine refs rejected at parse per story 006

### 2026-07-08T17:39:52.593Z - Proof thread-safety set NOT_APPLICABLE: config parsed once at startup

### 2026-07-08T17:39:52.674Z - Proof configurability set PROVEN: config expresses a machine library scenes can pick from
