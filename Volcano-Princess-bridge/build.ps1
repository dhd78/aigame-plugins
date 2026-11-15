param(
    [Parameter(Mandatory = $true)]
    [string]$GameDir
)

$ErrorActionPreference = "Stop"
$GameDir = (Resolve-Path $GameDir).Path
$BepInEx = Join-Path $GameDir "BepInEx"
$Managed = Join-Path $GameDir "VolcanoPrincess_Data\Managed"
$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { throw "csc.exe not found: $csc" }

$refs = @(
    (Join-Path $BepInEx "core\BepInEx.dll"),
    (Join-Path $Managed "Assembly-CSharp.dll"),
    (Join-Path $Managed "UnityEngine.dll"),
    (Join-Path $Managed "UnityEngine.CoreModule.dll"),
    (Join-Path $Managed "UnityEngine.UI.dll"),
    (Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\System.dll"),
    (Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\System.Core.dll"),
    (Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\System.Net.dll"),
    (Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\netstandard.dll")
)

foreach ($ref in $refs) {
    if (-not (Test-Path $ref)) { throw "reference not found: $ref" }
}

$outDir = Join-Path $PSScriptRoot "dist"
New-Item -ItemType Directory -Path $outDir -Force | Out-Null
$buildRoot = Join-Path $env:TEMP "volcano-bridge-build"
New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
$src = Join-Path $buildRoot "VolcanoBridge.cs"
Copy-Item (Join-Path $PSScriptRoot "VolcanoBridge.cs") $src -Force
$out = Join-Path $buildRoot "VolcanoBridge.dll"
$rsp = Join-Path $buildRoot "build.rsp"
$rspLines = @("/target:library", "/platform:x64", "/optimize+", "/out:`"$out`"")
foreach ($ref in $refs) { $rspLines += "/reference:`"$ref`"" }
$rspLines += "`"$src`""
Set-Content -LiteralPath $rsp -Value $rspLines -Encoding ASCII
try {
    & $csc "@$rsp"
    if ($LASTEXITCODE -ne 0) { throw "csc failed: $LASTEXITCODE" }
    Copy-Item $out (Join-Path $outDir "VolcanoBridge.dll") -Force
} finally {
    Remove-Item $rsp -Force -ErrorAction SilentlyContinue
}
Write-Host "built: $(Join-Path $outDir 'VolcanoBridge.dll')"
