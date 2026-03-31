# External Validation Spec (P1-1)

## Goal

Shift the CER evidence chain from internal controlled suites to external tasks, while keeping the comparison set small enough to preserve mechanism clarity.

## Fixed external config set

Use only these six configs for the first external sprint:

1. `vanilla`
2. `context_only`
3. `interceptor_only`
4. `context_finish_interceptor`
5. `context_deadend_interceptor`
6. `cer_full`

These configs live in `agents/configs_external/`.

## External benchmark track A: long-horizon web tasks

Preferred first benchmark: VisualWebArena/WebArena, because the repo already includes local bootstrap helpers and a checked-out `visualwebarena` environment in WSL.

### Minimal slice

- `config_files/vwa/test_classifieds`
- `config_files/vwa/test_shopping`
- `config_files/vwa/test_reddit`

Start with a small slice per site rather than the full benchmark. The first acceptable matrix is `5 tasks per site x 3 runs x 6 configs`.

### Required metrics

- Success / Progress
- Steps / Tokens / Runtime
- Step-wise executability or step-wise progress
- CER failure taxonomy mapped onto external runs

## External benchmark track B: external safety slice

Preferred long-term target: an AGrail-style safety benchmark.

Immediate locally available path: use a VisualWebArena/WebArena task slice with CER runtime policies enabled and report system-level safety metrics.

### Required metrics

- Unsafe execution / ASR-style outcome
- Benign task preservation
- Post-block success
- Proposal-to-execution conversion
- Sequence-sensitive failures when available

## Minimal reporting package

For the first external sprint, only require four result artifacts:

1. Main long-horizon results table
2. Main safety table
3. Step-wise executability/progress figure
4. Safety pipeline / post-block recovery figure or table

## Current local readiness

- Local VisualWebArena repo present at `/root/visualwebarena`
- `.env` defaults already configured for localhost
- Current blocker: Docker daemon unavailable inside `Ubuntu-22.04-D`, so benchmark websites are not runnable yet

Observed on 2026-03-28 via helper scripts:

- `repo-status`: repo available, origin configured, HEAD `89f5af29305c3d1e9f97ce4421462060a70c9a03`
- `env-check`: `DATASET=visualwebarena`, localhost URLs present
- `docker-status`: failed because no Docker daemon socket was found

## Immediate next commands once Docker is available

1. `bash /mnt/d/code/agent/codex_vwa_ubuntu2204_helper.sh docker-status`
2. `bash /mnt/d/code/agent/codex_vwa_ubuntu2204_helper.sh generate-configs`
3. `bash /mnt/d/code/agent/codex_vwa_ubuntu2204_helper.sh prepare`
4. Run a single-site smoke slice with `agents/configs_external/`
5. Expand to the 3-site x 3-run external matrix
