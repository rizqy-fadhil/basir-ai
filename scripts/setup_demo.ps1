param(
    [switch]$Start
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$releaseTag = "models-v1.0.0"
$releaseBaseUrl = "https://github.com/rizqy-fadhil/basir-ai/releases/download/$releaseTag"
$modelDir = Join-Path $repoRoot "local-models"

$assets = @(
    @{ Name = "yolov8n.pt"; Sha256 = "f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36" },
    @{ Name = "table-chair-best.pt"; Sha256 = "0acccd3e65e4d32f2af5fd94994da4dcf6fa262db6e6b23186f609569276beb9" }
)

New-Item -ItemType Directory -Force -Path $modelDir | Out-Null

foreach ($asset in $assets) {
    $destination = Join-Path $modelDir $asset.Name
    $downloadUrl = "$releaseBaseUrl/$($asset.Name)"
    if (-not (Test-Path -LiteralPath $destination)) {
        Write-Host "Mengunduh $($asset.Name)..."
        Invoke-WebRequest -Uri $downloadUrl -OutFile $destination
    }

    $actualSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash.ToLowerInvariant()
    if ($actualSha256 -ne $asset.Sha256) {
        Remove-Item -Force -LiteralPath $destination
        throw "Checksum $($asset.Name) tidak cocok. Expected $($asset.Sha256), got $actualSha256."
    }
    Write-Host "OK $($asset.Name) ($actualSha256)"
}

if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
    Write-Host "Membuat .env dari .env.example."
}

if ($Start) {
    docker compose up --build -d

    $healthy = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 3 | Out-Null
            $healthy = $true
            break
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if (-not $healthy) {
        throw "Backend belum healthy setelah menunggu 60 detik. Periksa docker compose logs backend."
    }

    docker compose exec backend python -m app.seed
    Write-Host "Aplikasi aktif: http://localhost:3000"
} else {
    Write-Host "Model siap. Jalankan 'docker compose up --build -d' atau ulangi script dengan -Start."
}
