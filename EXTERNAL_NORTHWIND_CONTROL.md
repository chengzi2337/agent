# External Northwind Control

This is the lightweight second external-site slice that does not depend on Docker.

## Positioning

- The site is locally served over HTTP and exercised through real Playwright page interaction.
- It is intentionally lightweight so the project can test control generalization before adding Docker-heavy environment variance.
- The task grammar mirrors `external_homepage_control_v1`: risky lure, blocked-or-error revision, premature finish pressure, and dead-end revision.

## Fixed Task Slice

Task directory: `tasks/external_northwind_control/`

1. `northwind_control_recovery_001`
2. `northwind_control_premature_finish_001`
3. `northwind_control_deadend_001`

Config directory: `agents/configs_external_control/`

1. `vanilla`
2. `context_only`
3. `interceptor_only`
4. `cer_full`

## Local Site

Static site directory: `sites/northwind_hub/`

The site exposes:

- hub home page
- catalog search page
- item detail page
- cart page
- one risky lure route (`Operations Console`)
- one safe dead-end lure route (`Archive Mirror`)

## Run Command

```powershell
Set-Location D:\code\agent
.\run_external_northwind_control.ps1 -Backend zhipu -Runs 1 -SuiteName external_northwind_control_v1
```

The run script starts a local HTTP server for the site, runs the 3-task x 4-config slice, and then stops the server.
