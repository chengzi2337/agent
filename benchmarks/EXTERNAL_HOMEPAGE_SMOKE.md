# External Homepage Smoke

This file captures the current external-validation mainline for CER.

## Why Homepage First

- `webarena-homepage` is the lightest available external environment.
- It exercises real browser interaction without needing the full Docker site stack.
- It is sufficient for the first three questions:
  - can the external environment run stably?
  - can `context_only` and `interceptor_only` separate?
  - can `cer_full` recover after a blocked proposal?

It is not the final safety benchmark. The homepage environment is primarily a lightweight smoke slice for utility, explicit blocking, and post-block recovery.

## Fixed Task Slice

Task directory: `tasks/external_homepage_smoke/`

1. `homepage_smoke_calculator_001`
2. `homepage_smoke_risk_001`
3. `homepage_smoke_recovery_001`

Config directory: `agents/configs_external/`

1. `vanilla`
2. `context_only`
3. `interceptor_only`
4. `context_finish_interceptor`
5. `context_deadend_interceptor`
6. `cer_full`

## Run Order

1. Run `1` pass per task/config as the smoke pass.
2. Check `success`, `blocked_rate`, `execution_rate`, and `post_block_success`.
3. If the shape is informative, increase to `3` runs per task/config.

## Host-Side Run Command

```powershell
Set-Location D:\code\agent
.\run_external_homepage_smoke.ps1 -Backend zhipu -Runs 1 -SuiteName external_homepage_smoke_v1
```

This script:

- starts the lightweight homepage app in WSL
- runs the external 3-task x 6-config slice
- writes the normal benchmark bundle
- renders `external_smoke_tables.md` beside the summary

## Output Tables

Table A: Homepage Smoke Results

- `success`
- `blocked_rate`
- `execution_rate`
- `post_block_success`
- `steps`
- `tokens`

Table B: Recovery Slice

- `blocked count`
- `recovered success`
- `avg extra steps after block`
- `avg extra tokens after block`

These focused tables are rendered by `benchmarks/reports/render_external_smoke.py`.

## Shopping Probe

Do not deploy `shopping` yet. First run:

```bash
cd /mnt/d/code/agent
bash install_vwa_sites_ubuntu2204.sh probe-shopping
```

This prints:

- asset archive size
- loaded image size when available
- estimated container count
- startup wait time
- post-start configuration steps
- first-start complexity label
