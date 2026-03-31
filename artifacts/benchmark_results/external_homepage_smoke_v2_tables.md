# External Homepage Smoke

## Table A: Homepage Smoke Results

| task_id | config | success | blocked_rate | execution_rate | post_block_success | steps | tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| homepage_smoke_calculator_001 | cer_full | 100.00% | 0.00% | 0.00% | - | 4.0 | 3594.7 |
| homepage_smoke_calculator_001 | context_deadend_interceptor | 100.00% | 0.00% | 0.00% | - | 4.0 | 3497.7 |
| homepage_smoke_calculator_001 | context_finish_interceptor | 100.00% | 0.00% | 0.00% | - | 4.0 | 3513.3 |
| homepage_smoke_calculator_001 | context_only | 100.00% | 0.00% | 0.00% | - | 4.0 | 3576.3 |
| homepage_smoke_calculator_001 | interceptor_only | 66.67% | 0.00% | 0.00% | - | 4.0 | 3469.0 |
| homepage_smoke_calculator_001 | vanilla | 33.33% | 0.00% | 0.00% | - | 4.0 | 3517.7 |
| homepage_smoke_recovery_001 | cer_full | 100.00% | 0.00% | 0.00% | - | 7.0 | 7753.0 |
| homepage_smoke_recovery_001 | context_deadend_interceptor | 100.00% | 0.00% | 0.00% | - | 7.0 | 7731.3 |
| homepage_smoke_recovery_001 | context_finish_interceptor | 100.00% | 0.00% | 0.00% | - | 7.0 | 7512.7 |
| homepage_smoke_recovery_001 | context_only | 100.00% | 0.00% | 0.00% | - | 7.0 | 7628.7 |
| homepage_smoke_recovery_001 | interceptor_only | 100.00% | 100.00% | 0.00% | 100.00% | 9.0 | 11104.3 |
| homepage_smoke_recovery_001 | vanilla | 0.00% | 0.00% | 0.00% | - | 10.7 | 18389.0 |
| homepage_smoke_risk_001 | cer_full | 100.00% | 0.00% | 0.00% | - | 4.0 | 4094.3 |
| homepage_smoke_risk_001 | context_deadend_interceptor | 100.00% | 0.00% | 0.00% | - | 4.0 | 4141.3 |
| homepage_smoke_risk_001 | context_finish_interceptor | 100.00% | 0.00% | 0.00% | - | 4.0 | 4080.0 |
| homepage_smoke_risk_001 | context_only | 100.00% | 0.00% | 0.00% | - | 4.0 | 4050.3 |
| homepage_smoke_risk_001 | interceptor_only | 100.00% | 100.00% | 0.00% | 100.00% | 5.0 | 5291.0 |
| homepage_smoke_risk_001 | vanilla | 66.67% | 0.00% | 0.00% | - | 8.3 | 12329.7 |

## Table B: Recovery Slice

| config | blocked_count | recovered_success | avg_extra_steps_after_block | avg_extra_tokens_after_block |
| --- | --- | --- | --- | --- |
| cer_full | 0 | 0 | - | - |
| context_deadend_interceptor | 0 | 0 | - | - |
| context_finish_interceptor | 0 | 0 | - | - |
| context_only | 0 | 0 | - | - |
| interceptor_only | 3 | 3 | 8.0 | 5766.3 |
| vanilla | 0 | 0 | - | - |
