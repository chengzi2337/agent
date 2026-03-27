# mock_full_matrix_v6

- backend: local
- model: glm-4.6v
- runs_per_task: 5
- task_count: 12
- config_count: 9

## Overall Summary

| config | success | compliance | premature_finish | dead_end_repeat | unsafe_proposal | unsafe_execution | avg_tokens | avg_latency_step_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cer_full | 100.00% | 100.00% | 0.00% | 0.00% | 25.00% | 0.00% | 4402.6 | 24.17 |
| guard_only | 16.67% | 16.67% | 0.00% | 33.33% | 25.00% | 0.00% | 4905.5 | 24.75 |
| naive_summary | 0.00% | 0.00% | 16.67% | 16.67% | 25.00% | 25.00% | 2811.8 | 23.46 |
| repeat_constraints | 8.33% | 8.33% | 16.67% | 16.67% | 25.00% | 25.00% | 3473.3 | 23.46 |
| slots_deadend | 58.33% | 58.33% | 16.67% | 0.00% | 25.00% | 25.00% | 3065.3 | 23.21 |
| slots_finish | 50.00% | 50.00% | 0.00% | 25.00% | 25.00% | 25.00% | 4120.0 | 24.04 |
| slots_only | 41.67% | 41.67% | 16.67% | 16.67% | 25.00% | 25.00% | 3379.7 | 23.46 |
| truncation | 0.00% | 0.00% | 16.67% | 16.67% | 25.00% | 25.00% | 3003.0 | 23.46 |
| vanilla | 0.00% | 0.00% | 16.67% | 16.67% | 25.00% | 25.00% | 3169.8 | 23.46 |

## Table 1: Main Results

| task_family | config | success | compliance | premature_finish | dead_end_repeat | unsafe_execution | avg_tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| constraint_deadend | cer_full | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% | 3237.0 |
| constraint_deadend | guard_only | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 5414.0 |
| constraint_deadend | naive_summary | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 4711.0 |
| constraint_deadend | repeat_constraints | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 5888.0 |
| constraint_deadend | slots_deadend | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% | 3237.0 |
| constraint_deadend | slots_finish | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 5793.0 |
| constraint_deadend | slots_only | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 5793.0 |
| constraint_deadend | truncation | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 5076.0 |
| constraint_deadend | vanilla | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 5414.0 |
| constraint_drowning | cer_full | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% | 5618.0 |
| constraint_drowning | guard_only | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 5259.6 |
| constraint_drowning | naive_summary | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 4640.0 |
| constraint_drowning | repeat_constraints | 20.00% | 20.00% | 0.00% | 0.00% | 0.00% | 5783.8 |
| constraint_drowning | slots_deadend | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% | 5618.0 |
| constraint_drowning | slots_finish | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% | 5618.0 |
| constraint_drowning | slots_only | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% | 5618.0 |
| constraint_drowning | truncation | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 4972.2 |
| constraint_drowning | vanilla | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 5259.6 |
| constraint_risk | cer_full | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% | 1595.0 |
| constraint_risk | guard_only | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 1515.0 |
| constraint_risk | naive_summary | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 437.0 |
| constraint_risk | repeat_constraints | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 475.0 |
| constraint_risk | slots_deadend | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 464.0 |
| constraint_risk | slots_finish | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 464.0 |
| constraint_risk | slots_only | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 464.0 |
| constraint_risk | truncation | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 437.0 |
| constraint_risk | vanilla | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 437.0 |
| dead_end_loop | cer_full | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% | 3089.0 |
| dead_end_loop | guard_only | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 4092.0 |
| dead_end_loop | naive_summary | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 3597.0 |
| dead_end_loop | repeat_constraints | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 4428.0 |
| dead_end_loop | slots_deadend | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% | 3089.0 |
| dead_end_loop | slots_finish | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 4305.0 |
| dead_end_loop | slots_only | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 4305.0 |
| dead_end_loop | truncation | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 3866.0 |
| dead_end_loop | vanilla | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 4092.0 |
| deadend_premature_finish | cer_full | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% | 4924.0 |
| deadend_premature_finish | guard_only | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 7335.0 |
| deadend_premature_finish | naive_summary | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 449.0 |
| deadend_premature_finish | repeat_constraints | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 490.0 |
| deadend_premature_finish | slots_deadend | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 476.0 |
| deadend_premature_finish | slots_finish | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 7855.0 |
| deadend_premature_finish | slots_only | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 476.0 |
| deadend_premature_finish | truncation | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 449.0 |
| deadend_premature_finish | vanilla | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 449.0 |
| premature_finish | cer_full | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% | 1931.0 |
| premature_finish | guard_only | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% | 1825.0 |
| premature_finish | naive_summary | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 399.0 |
| premature_finish | repeat_constraints | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 445.0 |
| premature_finish | slots_deadend | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 426.0 |
| premature_finish | slots_finish | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% | 1931.0 |
| premature_finish | slots_only | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 426.0 |
| premature_finish | truncation | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 399.0 |
| premature_finish | vanilla | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 399.0 |
| triple_mix | cer_full | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% | 8431.0 |
| triple_mix | guard_only | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 10933.0 |
| triple_mix | naive_summary | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 526.0 |
| triple_mix | repeat_constraints | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 572.0 |
| triple_mix | slots_deadend | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 553.0 |
| triple_mix | slots_finish | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 553.0 |
| triple_mix | slots_only | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 553.0 |
| triple_mix | truncation | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 526.0 |
| triple_mix | vanilla | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 526.0 |
| unsafe_action | cer_full | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% | 1534.0 |
| unsafe_action | guard_only | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% | 1454.0 |
| unsafe_action | naive_summary | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 422.0 |
| unsafe_action | repeat_constraints | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 463.0 |
| unsafe_action | slots_deadend | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 449.0 |
| unsafe_action | slots_finish | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 449.0 |
| unsafe_action | slots_only | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 449.0 |
| unsafe_action | truncation | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 422.0 |
| unsafe_action | vanilla | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 422.0 |

## Table 2: Ablation

| config | success | compliance | premature_finish | dead_end_repeat | unsafe_execution | avg_tokens | finish_gate_blocks | interceptor_blocks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| vanilla | 0.00% | 0.00% | 16.67% | 16.67% | 25.00% | 3169.8 | 0.00 | 0.00 |
| slots_only | 41.67% | 41.67% | 16.67% | 16.67% | 25.00% | 3379.7 | 0.00 | 0.00 |
| slots_finish | 50.00% | 50.00% | 0.00% | 25.00% | 25.00% | 4120.0 | 0.25 | 0.00 |
| slots_deadend | 58.33% | 58.33% | 16.67% | 0.00% | 25.00% | 3065.3 | 0.00 | 0.00 |
| cer_full | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% | 4402.6 | 0.25 | 0.25 |

## Table 3: Failure Taxonomy

| config | total_failures | constraint_violation | premature_finish | repeated_dead_end | unsafe_execution | other |
| --- | --- | --- | --- | --- | --- | --- |
| cer_full | 0 | 0 | 0 | 0 | 0 | 0 |
| guard_only | 50 | 30 | 0 | 20 | 0 | 0 |
| naive_summary | 60 | 25 | 10 | 10 | 15 | 0 |
| repeat_constraints | 55 | 20 | 10 | 10 | 15 | 0 |
| slots_deadend | 25 | 0 | 10 | 0 | 15 | 0 |
| slots_finish | 30 | 0 | 0 | 15 | 15 | 0 |
| slots_only | 35 | 0 | 10 | 10 | 15 | 0 |
| truncation | 60 | 25 | 10 | 10 | 15 | 0 |
| vanilla | 60 | 25 | 10 | 10 | 15 | 0 |
