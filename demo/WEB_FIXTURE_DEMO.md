# Web Fixture Demo Lane

This demo lane is intentionally separate from the benchmark suites.

## Included tasks

- `tasks/web_demo/web_demo_constraint_export.json`
- `tasks/web_demo/web_demo_deadend_finish.json`
- `tasks/web_demo/web_demo_triple_mix.json`

## Open the demo pages in Edge

```powershell
.\demo\open_web_fixture_demo.ps1 -Task all
```

Use one of these values for `-Task`:

- `constraint_export`
- `deadend_finish`
- `triple_mix`
- `all`

## Run the demo suite with cer_full only

```powershell
python evaluate_memory.py --task-dir tasks\web_demo --config-dir outputs\web_fixture_tmp\configs\cer_full_only --runs 1 --suite-name web_demo_lane_v1 --output-dir outputs
```

The demo lane is for visible walkthroughs; keep benchmark claims tied to `tasks/web`.
