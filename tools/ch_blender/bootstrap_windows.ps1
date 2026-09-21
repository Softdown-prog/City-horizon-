param(
    [string]$Workspace = "$env:USERPROFILE\Documents\CityHorizon\ch_blender",
    [switch]$Reset
)

$ErrorActionPreference = "Stop"

$Upstream = "https://projects.blender.org/blender/blender.git"
$Tag = "v4.2.3"
$SourceDir = Join-Path $Workspace "blender-src"

Write-Host "CH Blender bootstrap"
Write-Host "Workspace: $Workspace"
Write-Host "Upstream:  $Upstream"
Write-Host "Tag:       $Tag"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git was not found in PATH. Install Git before running this bootstrap."
}

New-Item -ItemType Directory -Force -Path $Workspace | Out-Null

if ($Reset -and (Test-Path $SourceDir)) {
    Write-Host "Removing existing source checkout: $SourceDir"
    Remove-Item -Recurse -Force $SourceDir
}

if (-not (Test-Path (Join-Path $SourceDir ".git"))) {
    Write-Host "Cloning Blender source..."
    git clone --filter=blob:none --no-checkout $Upstream $SourceDir
    if ($LASTEXITCODE -ne 0) { throw "Blender clone failed." }
}

Push-Location $SourceDir
try {
    Write-Host "Fetching frozen upstream tag $Tag..."
    git fetch --tags origin $Tag
    if ($LASTEXITCODE -ne 0) { throw "Failed to fetch Blender tag $Tag." }

    git checkout --detach $Tag
    if ($LASTEXITCODE -ne 0) { throw "Failed to checkout Blender tag $Tag." }

    $Head = (git rev-parse HEAD).Trim()
    $Describe = (git describe --tags --exact-match HEAD).Trim()

    if ($Describe -ne $Tag) {
        throw "Unexpected Blender checkout. Expected $Tag, got $Describe ($Head)."
    }

    Write-Host ""
    Write-Host "Frozen Blender source ready."
    Write-Host "Tag:    $Describe"
    Write-Host "Commit: $Head"
    Write-Host "Source: $SourceDir"
    Write-Host ""
    Write-Host "No Blender source files were modified by this bootstrap."
    Write-Host "Next step: apply only versioned City Horizon patches from tools/ch_blender/patches."
}
finally {
    Pop-Location
}
