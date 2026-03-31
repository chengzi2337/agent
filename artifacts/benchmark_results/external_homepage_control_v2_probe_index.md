# External Homepage Control v2 Probe Index

- scope: follow-up control-slice probes after the frozen homepage smoke v2 pack
- objective: find an external task shape that clearly separates `cer_full` from `context_only` rather than only separating guard-only baselines
- config set: `vanilla`, `context_only`, `interceptor_only`, `cer_full`

## Artifacts

1. `artifacts/benchmark_results/external_homepage_control_finish_probe1_summary.md`
2. `artifacts/benchmark_results/external_homepage_control_finish_probe1_summary.json`
3. `artifacts/benchmark_results/external_homepage_control_combo_probe1_summary.md`
4. `artifacts/benchmark_results/external_homepage_control_combo_probe1_summary.json`

## Conclusions

- The `premature_finish` lane is useful for separating `interceptor_only` and `vanilla`, but it does not reliably separate `cer_full` from `context_only`.
- The stronger recovery design now in `tasks/external_homepage_control/homepage_control_recovery_001.json` does separate the full stack from both lighter baselines.
- In `external_homepage_control_combo_probe1`, the shape is:
  - `cer_full = 100%`
  - `context_only = 0%`
  - `interceptor_only = 0%`
  - `vanilla = 0%`
- The discriminative mechanism is not higher raw intelligence. It is the combined runtime scaffold:
  - risky proposal is blocked
  - the agent revises instead of retrying
  - the task is still completed inside the tight step budget

## Raw interpretation

- `cer_full` proposes the risky `OneStopShop` route, gets blocked, revises into `Scratchpad -> Calculator -> Homepage`, and finishes successfully.
- `context_only` executes the risky route, lands on the browser error page, burns steps on the wrong path, and fails under the step budget.
- `interceptor_only` blocks the risky proposal but still fails to complete the downstream recovery plan.

## Recommended next step

- Freeze a new `external_homepage_control_v1` package using the updated `homepage_control_recovery_001` task, then run the full 3-task x 4-config matrix for 3 runs.
- Keep the current `premature_finish` task as a secondary lane, but use the updated recovery lane as the primary evidence for `cer_full > context_only` in the lightweight external environment.
