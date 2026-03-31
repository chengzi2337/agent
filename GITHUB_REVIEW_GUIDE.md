# GitHub Review Guide

This branch contains the core benchmark and evaluation components for the recent CER reliability-layer work.

## What changed

The repository is no longer organized around a single benchmark script. It now exposes a small research harness whose job is:

> for any method change, quickly produce reproducible baselines, ablations, failure cases, and a report.

The main additions are:

- configuration-driven agent ablations
- task-spec driven mock benchmarks
- unified environment interfaces
- richer event logging
- report generation for summary tables and failure bundles

## Start here

If a reviewer or GPT model should understand the new benchmark structure, these are the most important files:

- `cer_architecture.py`
- `evaluate_memory.py`
- `benchmarks/runners/run_suite.py`
- `benchmarks/agent_factory.py`
- `benchmarks/evaluator.py`
- `benchmarks/reports/render_report.py`
- `envs/base_env.py`
- `envs/mock/constraint_drowning_env.py`
- `envs/mock/composite_hazard_env.py`
- `agents/configs/*.json`
- `tasks/mock/*.json`

## New benchmark focus

The mock benchmark now emphasizes two things:

1. Stronger `constraint_drowning` variants that specifically separate `slots` from `repeat_constraints`
2. Compositional failure-mode tasks instead of only one-hot tasks

### Constraint-drowning variants

- `constraint_drowning_hierarchy_001.json`
- `constraint_drowning_pseudo_001.json`
- `constraint_drowning_semantic_001.json`
- `constraint_drowning_budget_001.json`

These are designed to test:

- hard vs soft constraint hierarchy
- resistance to injected pseudo-constraints
- semantic preservation rather than exact token survival
- tighter context-budget pressure

### Compositional mock tasks

- `constraint_deadend_001.json`
- `deadend_premature_finish_001.json`
- `constraint_risk_001.json`
- `triple_mix_001.json`

These are intended to show whether improvements come from real component interaction rather than from one-module-per-task overfitting.

## Current ablation set

The configs under `agents/configs/` currently include:

- `vanilla`
- `repeat_constraints`
- `truncation`
- `naive_summary`
- `guard_only`
- `slots_only`
- `slots_finish`
- `slots_deadend`
- `cer_full`

## Notes for reviewers

- `outputs/` and local report dumps are intentionally not committed as core source.
- The local benchmark backend is deterministic, so repeated runs mainly validate harness consistency rather than stochastic variance.
- The most informative current failure is the compositional `triple_mix` task, where `cer_full` still exposes a coarse finish-gate weakness after a blocked risky action.
