param(
    [ValidateSet("local", "zhipu")]
    [string]$Backend = "zhipu",
    [int]$Runs = 1,
    [string]$SuiteName = "external_homepage_smoke_v1",
    [string]$OutputDir = "outputs",
    [string]$Model = $(if ($env:ZHIPU_MODEL) { $env:ZHIPU_MODEL } else { "glm-4.6v" }),
    [string]$Distro = "Ubuntu-22.04-D",
    [switch]$StartHomepage = $true
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if ($StartHomepage) {
    $siteScript = Join-Path $root "install_vwa_sites_ubuntu2204.sh"
    $linuxPath = ((Resolve-Path $siteScript).Path -replace '^([A-Za-z]):', '/mnt/$1' -replace '\\', '/').ToLower()
    wsl -d $Distro -- bash $linuxPath start-homepage
}

python evaluate_memory.py `
  --backend $Backend `
  --task-dir tasks/external_homepage_smoke `
  --config-dir agents/configs_external `
  --suite-name $SuiteName `
  --runs $Runs `
  --output-dir $OutputDir `
  --model $Model

$summaryJson = Join-Path $root "$OutputDir\reports\$SuiteName\summary.json"
python benchmarks\reports\render_external_smoke.py --summary-json $summaryJson
