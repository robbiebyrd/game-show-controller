---
id: 008-91d1
title: Migrate config files to named-machine form
status: pending
priority: P2
type: feature
created: "2026-07-08T17:33:00.912Z"
updated: "2026-07-08T17:33:08.501Z"
dependencies: ["006-a364", "007-e0b5"]
---

# Migrate config files to named-machine form

## Problem Statement

config.yaml/config.example.yaml define a single inline state_machine. Restructure into a state_machines library with the current flow named (e.g. standard), reference it top-level, and convert the Round 1 scene override to {extends: standard, ...}.

## Acceptance Criteria

- [ ] config.yaml and config.example.yaml use state_machines library + top-level reference
- [ ] Round 1 scene override uses extends
- [ ] both files load clean and full suite is green
- [ ] end-to-end smoke through real config still works

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

