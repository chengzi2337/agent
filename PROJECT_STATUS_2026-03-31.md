# Project Status 2026-03-31

## Project Positioning

The strongest current project claim is not "the agent is smarter". The stronger and more accurate claim is:

> structured context isolation + finish routing/gating + dead-end recovery + runtime interception improve long-horizon agent reliability by reducing constraint drift, premature finish, dead-end looping, and unsafe execution.

The safest wording on the safety side remains:

> the project supports `safe execution + post-block recovery`, not `safe reasoning`.

## What Is Already Solid

### Internal Controlled Evidence

The repo already contains a full controlled evidence chain across mock and local web fixtures:

- structured slots outperform repeat-style baselines on constraint retention
- finish routing is necessary for mixed-failure tasks such as `triple_mix`
- dead-end memory is not cosmetic; it improves dead-end-heavy tasks
- interception alone is not enough; the value is in `blocked proposal -> revise -> success`

Key stored assets are under `artifacts/benchmark_results/`, including:

- `mock_full_matrix_v7_summary.md`
- `mock_full_matrix_v8_summary.md`
- `mock_interaction_matrix_v2_summary.md`
- `interaction_ablation_v2_index.md`
- `external_homepage_smoke_v2_summary.md`
- `external_homepage_smoke_v2_index.md`

### External Homepage Smoke v2

`external_homepage_smoke_v2` is the frozen minimal external evidence pack.

What it supports:

- `context_only > vanilla`
- `interceptor_only` drives risk-bearing `execution_rate` to `0.00%`
- `safe execution + post-block recovery` is externally auditable in a lightweight real browser environment

What it does not support:

- `safe reasoning`
- a clean claim that `cer_full > interceptor_only` on recovery completion itself

## New Result Added In This Push

### External Homepage Control v1

This push adds the finalized external control slice and the first complete 36-run matrix:

- suite: `external_homepage_control_v1_rerun1`
- environment: real Playwright browser interaction against the local `webarena-homepage` service
- tasks: `3`
- configs: `4`
- runs: `3` each
- total: `36`

Artifacts:

- `artifacts/benchmark_results/external_homepage_control_v1_summary.md`
- `artifacts/benchmark_results/external_homepage_control_v1_summary.json`
- `artifacts/benchmark_results/external_homepage_control_v1_index.md`
- `artifacts/benchmark_results/external_homepage_control_v2_probe_index.md`

Headline result:

- `cer_full`: `100.00%`
- `context_only`: `55.56%`
- `interceptor_only`: `11.11%`
- `vanilla`: `11.11%`

Most important lane:

- `homepage_control_recovery`
  - `cer_full = 100.00%`
  - `context_only = 0.00%`
  - `interceptor_only = 0.00%`
  - `vanilla = 0.00%`

Why this matters:

- this is the first lightweight external slice that cleanly separates the full runtime scaffold from both lighter baselines
- the difference is not just "blocking unsafe actions"
- the difference is that `cer_full` can absorb the blocked risky lure, revise, and still finish the downstream plan under a tight step budget

Interpretation:

- `context_only` is a strong base layer but not enough for compositional blocked-route recovery
- `interceptor_only` protects execution safety but does not recover completion
- `cer_full` closes the loop

## Code Paths That Matter Now

Core control logic:

- `cer_architecture.py`
- `benchmarks/evaluator.py`
- `envs/web/playwright_env.py`

External control slice:

- `tasks/external_homepage_control/`
- `agents/configs_external_control/`
- `test_external_homepage_control.py`
- `test_external_homepage_deadend_fallback.py`

Controlled benchmark entry points:

- `evaluate_memory.py`
- `benchmarks/runners/run_suite.py`
- `benchmarks/reports/render_report.py`

## Environment Reality

The project currently uses three different evaluation layers and they should not be conflated:

1. `mock` suites
   - controlled synthetic environments
2. `fixtures/web`
   - local HTML browser fixtures
3. `external_homepage_*`
   - real Playwright browser interaction against a locally served homepage web app

Important note:

- `external_homepage_*` is local deployment, but it is still real page interaction, not a fake environment
- Docker-heavy sites are intentionally not yet the mainline because the current objective is to isolate control differences before adding heavier environment variance

## What This Push Proves vs. What It Does Not

Supported now:

- modular reliability control is already supported in mock + local web fixtures
- minimal external safety/recovery evidence is supported by homepage smoke v2
- full-stack compositional runtime controls improve external long-horizon completion robustness on the homepage control slice
- `cer_full > context_only` is now supported on the external recovery lane

Still not supported:

- `safe reasoning`
- broad claims over full WebArena / VisualWebArena
- multi-model or statistically broad external generalization
- strong OOD or sequence-sensitivity claims

## Recommended Next Steps

The next step is not to add more mechanisms. The repo is now at the stage where evaluation breadth matters more than feature count.

Recommended order:

1. Keep `external_homepage_smoke_v2` and `external_homepage_control_v1` frozen.
2. Choose the next external site only after deciding whether the goal is:
   - broader utility validation, or
   - stronger risk-bearing recovery validation.
3. If a second external site is added, prefer a site whose task structure naturally supports:
   - risky route lure
   - blocked-or-error revision
   - multi-step downstream completion.
4. Continue to avoid overstating safety; the correct framing is still reliability control, not safe reasoning.

## Handoff Note

For a new Codex/GPT window, the fastest way to recover context is:

1. read `Project Status 2026-03-31`
2. read `artifacts/benchmark_results/external_homepage_smoke_v2_index.md`
3. read `artifacts/benchmark_results/external_homepage_control_v1_index.md`
4. inspect the selected raw runs listed in those two index files if a result needs to be audited

This is the current high-signal summary of the project state as of 2026-03-31.
