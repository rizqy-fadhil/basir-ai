#!/usr/bin/env bash

set -euo pipefail

start=0
if [[ "${1:-}" == "--start" ]]; then
    start=1
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

release_tag="models-v1.0.0"
release_base_url="https://github.com/rizqy-fadhil/basir-ai/releases/download/${release_tag}"
model_dir="$repo_root/local-models"
mkdir -p "$model_dir"

assets=(
  "yolov8n.pt f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36"
  "table-chair-best.pt 0acccd3e65e4d32f2af5fd94994da4dcf6fa262db6e6b23186f609569276beb9"
)

sha256_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
        return
    fi
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
        return
    fi
    echo "Perintah sha256sum atau shasum wajib tersedia." >&2
    exit 1
}

for asset_record in "${assets[@]}"; do
    asset="${asset_record%% *}"
    expected_sha256="${asset_record#* }"
    destination="$model_dir/$asset"
    if [[ ! -f "$destination" ]]; then
        echo "Mengunduh $asset..."
        curl --fail --location --retry 3 --output "$destination" "$release_base_url/$asset"
    fi

    actual_sha256="$(sha256_file "$destination")"
    if [[ "$actual_sha256" != "$expected_sha256" ]]; then
        rm -f "$destination"
        echo "Checksum $asset tidak cocok." >&2
        exit 1
    fi
    echo "OK $asset ($actual_sha256)"
done

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "Membuat .env dari .env.example."
fi

if [[ "$start" -eq 1 ]]; then
    docker compose up --build -d
    for attempt in $(seq 1 30); do
        if curl --fail --silent http://localhost:8000/health >/dev/null; then
            break
        fi
        if [[ "$attempt" -eq 30 ]]; then
            echo "Backend belum healthy setelah menunggu 60 detik." >&2
            exit 1
        fi
        sleep 2
    done
    docker compose exec backend python -m app.seed
    echo "Aplikasi aktif: http://localhost:3000"
else
    echo "Model siap. Jalankan 'docker compose up --build -d' atau ulangi script dengan --start."
fi
