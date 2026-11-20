$ErrorActionPreference = 'Stop'
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$installation = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 Microsoft.VisualStudio.Component.VC.CMake.Project -property installationPath
if (-not $installation) {
    throw 'Install Visual Studio Build Tools with x64 C++ and CMake tools.'
}
& (Join-Path $installation 'Common7\Tools\Launch-VsDevShell.ps1') -Arch amd64 -HostArch amd64 -SkipAutomaticLocation
# Keep CMake's detected /showIncludes prefix in the same encoding as MSVC.
chcp.com 65001 | Out-Null

$bin = Join-Path $PSScriptRoot '..\out\tools\xbdepends\build\bin'
if (Test-Path -LiteralPath (Join-Path $bin 'xbdepends.exe')) {
    $bin = (Resolve-Path -LiteralPath $bin).Path
    if ($bin -notin ($env:Path -split ';')) { $env:Path = "$bin;$env:Path" }
}
