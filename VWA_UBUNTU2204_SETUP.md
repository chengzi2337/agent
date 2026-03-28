# VisualWebArena From Scratch on Ubuntu-22.04-D

This workspace now includes a clean bootstrap path that targets the `Ubuntu-22.04-D` WSL distro instead of the older `Ubuntu` environment.

## What this bootstrap does

- clones a fresh official `web-arena-x/visualwebarena` checkout into `$HOME/visualwebarena`
- creates a dedicated virtual environment at `$HOME/.venvs/visualwebarena`
- installs Python dependencies and Playwright
- writes `/root/visualwebarena/.env` with localhost-oriented defaults for VWA and optional WebArena compatibility targets
- verifies that `playwright` and `browser_env` import correctly

## Files

- [bootstrap_visualwebarena_ubuntu2204.sh](/D:/code/agent/bootstrap_visualwebarena_ubuntu2204.sh)
- [bootstrap_visualwebarena_ubuntu2204.ps1](/D:/code/agent/bootstrap_visualwebarena_ubuntu2204.ps1)
- [codex_vwa_ubuntu2204_helper.sh](/D:/code/agent/codex_vwa_ubuntu2204_helper.sh)
- [install_vwa_sites_ubuntu2204.sh](/D:/code/agent/install_vwa_sites_ubuntu2204.sh)

## Typical usage

From PowerShell on Windows:

```powershell
Set-Location D:\code\agent
.\bootstrap_visualwebarena_ubuntu2204.ps1 all
```

Or step-by-step:

```powershell
.\bootstrap_visualwebarena_ubuntu2204.ps1 clone
.\bootstrap_visualwebarena_ubuntu2204.ps1 python
.\bootstrap_visualwebarena_ubuntu2204.ps1 env
.\bootstrap_visualwebarena_ubuntu2204.ps1 verify
```

Inside `Ubuntu-22.04-D` directly:

```bash
cd /mnt/d/code/agent
bash bootstrap_visualwebarena_ubuntu2204.sh all
```

## What still remains after bootstrap

The official VisualWebArena codebase expects the standalone websites to be available. After the bootstrap finishes, continue with:

1. Review `$HOME/visualwebarena/environment_docker`
2. Load or build the required site assets
3. Source `$HOME/visualwebarena/.env`
4. Generate config files:

```bash
cd $HOME/visualwebarena
python scripts/generate_test_data.py
```

5. Prepare login cookies:

```bash
cd $HOME/visualwebarena
bash prepare.sh
```

## Helper commands inside Ubuntu-22.04-D

After the bootstrap completes, you can use the helper script in this workspace:

```bash
cd /mnt/d/code/agent
bash codex_vwa_ubuntu2204_helper.sh repo-status
bash codex_vwa_ubuntu2204_helper.sh env-check
bash codex_vwa_ubuntu2204_helper.sh docker-status
bash codex_vwa_ubuntu2204_helper.sh generate-configs
bash codex_vwa_ubuntu2204_helper.sh smoke
bash install_vwa_sites_ubuntu2204.sh start-homepage
bash install_vwa_sites_ubuntu2204.sh probe-shopping
```

The helper prefers `/var/run/docker.sock`, but if Docker Desktop is only integrated with another WSL distro it will also fall back to `/mnt/wsl/docker-desktop-bind-mounts/Ubuntu/docker.sock`.

When the Docker sites are available, the same helper also wraps:

```bash
bash codex_vwa_ubuntu2204_helper.sh prepare
bash codex_vwa_ubuntu2204_helper.sh reset-reddit
bash codex_vwa_ubuntu2204_helper.sh reset-shopping
bash codex_vwa_ubuntu2204_helper.sh reset-classifieds
```

## Full site install from scratch

To download, load, and start the VisualWebArena sites in `Ubuntu-22.04-D`:

```bash
cd /mnt/d/code/agent
bash install_vwa_sites_ubuntu2204.sh all
```

Or break it into phases:

```bash
bash install_vwa_sites_ubuntu2204.sh download
bash install_vwa_sites_ubuntu2204.sh start-all
bash install_vwa_sites_ubuntu2204.sh smoke
```

## External Homepage Smoke

For the current external-validation mainline, start with the lightweight homepage slice before touching Docker-heavy sites:

```powershell
Set-Location D:\code\agent
.\run_external_homepage_smoke.ps1 -Backend zhipu -Runs 1 -SuiteName external_homepage_smoke_v1
```

This runs the 3 homepage smoke tasks against the 6-config external set and renders:

- `outputs/reports/<suite>/summary.md`
- `outputs/reports/<suite>/external_smoke_tables.md`

## Defaults written to `.env`

```bash
export DATASET="visualwebarena"
export CLASSIFIEDS="http://localhost:9980"
export CLASSIFIEDS_RESET_TOKEN="4b61655535e7ed388f0d40a93600254c"
export SHOPPING="http://localhost:7770"
export REDDIT="http://localhost:9999"
export WIKIPEDIA="http://localhost:8888"
export HOMEPAGE="http://localhost:4399"
export SHOPPING_ADMIN="http://localhost:7780/admin"
export GITLAB="http://localhost:8023"
export MAP="http://localhost:3000"
```

These are localhost defaults meant for a local Docker-based sandbox in `Ubuntu-22.04-D`.
