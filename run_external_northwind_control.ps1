param(
    [ValidateSet("local", "zhipu")]
    [string]$Backend = "zhipu",
    [int]$Runs = 1,
    [string]$SuiteName = "external_northwind_control_v1",
    [string]$OutputDir = "outputs",
    [string]$Model = $(if ($env:ZHIPU_MODEL) { $env:ZHIPU_MODEL } else { "glm-4.6v" }),
    [int]$Port = 4410,
    [switch]$StartSite = $true
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$serverProcess = $null

try {
    if ($StartSite) {
        $siteDir = Join-Path $root "sites\\northwind_hub"
        $serverProcess = Start-Process `
            -FilePath "python" `
            -ArgumentList @("-m", "http.server", "$Port", "--bind", "127.0.0.1", "--directory", $siteDir) `
            -PassThru `
            -WindowStyle Hidden
        Start-Sleep -Seconds 2
    }

    python evaluate_memory.py `
      --backend $Backend `
      --task-dir tasks/external_northwind_control `
      --config-dir agents/configs_external_control `
      --suite-name $SuiteName `
      --runs $Runs `
      --output-dir $OutputDir `
      --model $Model
}
finally {
    if ($serverProcess -and -not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -Force
    }
}
