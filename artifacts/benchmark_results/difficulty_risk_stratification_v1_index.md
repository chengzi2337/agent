# Difficulty and Risk Stratification v1

- source_commit: `4a9fd556fc10df59bd9b404dadb3307d08cbad8f`
- scope: mock full matrix + web fixture full matrix

## Read Order

1. `mock_full_matrix_v8_summary.md`
2. `web_fixture_full_matrix_v6_summary.md`

## Key Takeaways

- `cer_full` stays at `100%` across the current mock difficulty buckets (`easy`, `medium`, `hard`) and across the current web buckets (`medium`, `hard`).
- On web fixtures, the gap widens with difficulty: `slots_only` drops from `60%` on `medium` to `14.29%` on `hard`, while `repeat_constraints` drops from `40%` to `0%`; `cer_full` remains at `100%`.
- The horizon view shows the same pattern on web: `cer_full` is `100%` on `short`, `medium`, and `long`, while non-full configs collapse on `medium` and `long` horizons.
- Risk complexity stays honest: on web we currently have `contextual` and `compositional` risk buckets, not a pure `explicit` bucket. In both buckets, `cer_full` keeps `blocked_rate=100%`, `execution_rate=0%`, and `post_block_success=100%`.
- `guard_only` still demonstrates the key contrast: it keeps `execution_rate=0%`, but `post_block_success=0%` on web risk buckets, so interception alone does not preserve utility under harder risk composition.
