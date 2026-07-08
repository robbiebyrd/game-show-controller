---
id: 005-d8e7
title: Migrate config.yaml and config.example.yaml to new schema
status: pending
priority: P1
type: feature
created: "2026-07-08T16:33:24.308Z"
updated: "2026-07-08T16:33:31.706Z"
dependencies: ["001-72a8"]
---

# Migrate config.yaml and config.example.yaml to new schema

## Problem Statement

config.yaml and config.example.yaml still use the flat state_machine block and the Round 1 scene override return_to_after_incorrect.

## Acceptance Criteria

- [ ] state_machine block replaced with initial/global/states transition table + behaviors
- [ ] Round 1 scene override becomes states.incorrect.then: allow_next
- [ ] config.example.yaml documents the schema with inline comments
- [ ] load_config(config.yaml) parses clean and full pytest is green

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

