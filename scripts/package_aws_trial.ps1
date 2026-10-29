param(
    [string]$OutputDirectory = ".local/aws-trial-bundle"
)

$ErrorActionPreference = "Stop"
$repository = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$destination = [IO.Path]::GetFullPath((Join-Path $repository $OutputDirectory))
$localRoot = [IO.Path]::GetFullPath((Join-Path $repository ".local"))

if (-not $destination.StartsWith($localRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputDirectory must be a new directory under the ignored .local folder."
}
if (Test-Path -LiteralPath $destination) {
    throw "The output directory already exists. Choose a new bundle name to avoid overwriting it."
}

Push-Location $repository
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker is required." }
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "npm is required." }

    Push-Location (Join-Path $repository "frontend")
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    } finally {
        Pop-Location
    }

    docker build --tag image-origin-studio:aws-trial .
    if ($LASTEXITCODE -ne 0) { throw "API Docker build failed." }

    New-Item -ItemType Directory -Path $destination | Out-Null
    $imageTar = Join-Path $destination "image-origin-api.tar"
    docker save --output $imageTar image-origin-studio:aws-trial
    if ($LASTEXITCODE -ne 0) { throw "Docker image export failed." }
    Copy-Item -LiteralPath (Join-Path $repository "frontend/dist") -Destination (Join-Path $destination "dist") -Recurse

    $commit = (git rev-parse HEAD).Trim()
    $dirty = @(git status --porcelain)
    $manifest = [ordered]@{
        created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        git_commit = $commit
        working_tree_dirty = ($dirty.Count -gt 0)
        image_tag = "image-origin-studio:aws-trial"
        image_tar_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $imageTar).Hash.ToLowerInvariant()
    }
    $manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $destination "manifest.json") -Encoding UTF8
    Write-Output "Bundle ready: $destination"
    Write-Output "Image archive SHA-256: $($manifest.image_tar_sha256)"
    if ($manifest.working_tree_dirty) {
        Write-Warning "The working tree is dirty; record the exact source state before public deployment."
    }
} finally {
    Pop-Location
}
