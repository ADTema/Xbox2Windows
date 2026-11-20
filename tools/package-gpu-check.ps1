[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    & "$PSScriptRoot\dev.ps1"
    $revision = git rev-parse HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve the source revision.' }
    $build = 'out/build/gpu-check-release'
    cmake --preset dev -B $build -DCMAKE_BUILD_TYPE=Release -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded
    if ($LASTEXITCODE -ne 0) { throw 'Release configuration failed.' }
    cmake --build $build --target offscreen_check
    if ($LASTEXITCODE -ne 0) { throw 'Release build failed.' }

    $output = New-Item -ItemType Directory -Force -Path 'out/gpu-check'
    $stage = New-Item -ItemType Directory -Force -Path "$build/package"
    Copy-Item -LiteralPath "$build/offscreen_check.exe", "$PSScriptRoot/gpu-check/Run-GpuCheck.ps1", "$PSScriptRoot/gpu-check/README.md", 'LICENSE' -Destination $stage
    Set-Content -LiteralPath "$stage/SOURCE_COMMIT.txt" -Value $revision -Encoding ascii
    $files = 'offscreen_check.exe', 'Run-GpuCheck.ps1', 'README.md', 'LICENSE', 'SOURCE_COMMIT.txt' |
        ForEach-Object { Join-Path $stage $_ }
    $name = 'Xbox2Windows-GpuCheck-win-x64.zip'
    $zip = Join-Path $output $name
    Compress-Archive -LiteralPath $files -DestinationPath $zip -Force
    $hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath "$zip.sha256" -Encoding ascii -Value "$hash  $name"

    $smoke = Join-Path $build ('smoke-' + [guid]::NewGuid().ToString('N'))
    Expand-Archive -LiteralPath $zip -DestinationPath $smoke
    & powershell.exe -NoProfile -File "$smoke/Run-GpuCheck.ps1" -Backend warp
    if ($LASTEXITCODE -ne 0) { throw 'The extracted package failed its WARP tests.' }
    $report = Get-Content -Raw -LiteralPath "$smoke/gpu-report-warp.md"
    if ($report -notmatch 'bvh_waves_warp - PASS' -or $report -notmatch [regex]::Escape($revision)) {
        throw 'The WARP smoke test must execute the waves fixture and report the source commit.'
    }
} finally {
    Pop-Location
}
