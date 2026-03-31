param(
  [ValidateSet("constraint_export", "deadend_finish", "triple_mix", "all")]
  [string]$Task = "all"
)

$root = Split-Path -Parent $PSScriptRoot
$targets = @{
  "constraint_export" = (Resolve-Path (Join-Path $root "fixtures\web\constraint_export.html")).Path
  "deadend_finish" = (Resolve-Path (Join-Path $root "fixtures\web\deadend_finish.html")).Path
  "triple_mix" = (Resolve-Path (Join-Path $root "fixtures\web\triple_mix.html")).Path
}

$selected = if ($Task -eq "all") { $targets.Keys } else { @($Task) }
foreach ($name in $selected) {
  $uri = "file:///" + ($targets[$name] -replace "\\", "/")
  Start-Process msedge $uri
}
