# Unsafe Proposal Recovery Analysis v1

- source_commit: `fdfbc2ff7e5a4098eba0809ffe7a3caa04fafe75`
- scope: web fixture main matrix + interaction ablation

## Read Order

1. `web_fixture_full_matrix_v5_summary.md`
2. `web_interaction_matrix_v3_summary.md`

## Key Takeaways

- `cer_full` now has a dedicated risk-only pipeline table: on 15 web risk-task runs it keeps `proposal_rate=100%`, `execution_rate=0%`, and `post_block_success=100%`.
- This supports a precise claim: the current stack guarantees safe execution and reliable post-block recovery, but it does not yet eliminate unsafe proposals at the reasoning stage.
- `guard_only` also blocks unsafe execution, but on the same 15 risk-task runs its `post_block_success=0%`, which shows that interception alone is not enough.
- In interaction ablation, `context_finish_interceptor` and `context_deadend_interceptor` both reach `post_block_success=60%`, while `interceptor_only` stays at `0%`; recovery needs context plus another control module, not just a guard.
