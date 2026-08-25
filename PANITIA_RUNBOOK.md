# Basir AI — Runbook Panitia

Dokumen ini menjalankan MVP dari clone baru tanpa menyalin bobot model secara
manual. Docker Compose menjalankan PostgreSQL, backend, inference, dan frontend.

## Prasyarat

- Docker Desktop dengan Linux containers dan Docker Compose.
- Git.
- Koneksi internet saat setup pertama untuk mengunduh image Docker dan model.

Clone versi repository yang sudah diuji:

```bash
git clone https://github.com/rizqy-fadhil/basir-ai.git
cd basir-ai
git checkout main
```

## Setup satu perintah

Windows PowerShell:

```powershell
.\scripts\setup_demo.ps1 -Start
```

Linux/macOS/WSL:

```bash
bash scripts/setup_demo.sh --start
```

Script tersebut mengunduh dan memverifikasi dua asset release, membuat `.env`
dari `.env.example` bila belum ada, membangun semua image, menunggu backend
healthy, lalu menjalankan seed cafe dan meja demo.

Jika port PostgreSQL host `5432` sudah dipakai, gunakan port host lain tanpa
mengubah port database di dalam jaringan Compose:

```powershell
$env:POSTGRES_PORT="55432"
.\scripts\setup_demo.ps1 -Start
```

```bash
POSTGRES_PORT=55432 bash scripts/setup_demo.sh --start
```

## Akses dan verifikasi

- Dashboard: <http://localhost:3000>
- Backend health: <http://localhost:8000/health>
- Backend API docs: <http://localhost:8000/docs>

Untuk melihat log inference:

```bash
docker compose logs -f inference
```

Mode demo memakai fixture `dataset/mock/workspace.ppm`; ini adalah input
sintetis untuk reproduksi lokal. Runtime occupancy memakai model pretrained
COCO `person` dan ROI statis yang sudah dikonfirmasi. Model `table/chair`
dipakai pada tahap kalibrasi/visualisasi, bukan setiap frame occupancy.

## Asset model

Asset tersedia di GitHub Release `models-v1.0.0` dan diverifikasi oleh setup
script:

| Asset | Peran | SHA-256 |
|---|---|---|
| `yolov8n.pt` | pretrained COCO person supporting component | `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36` |
| `table-chair-best.pt` | model fine-tuned untuk kalibrasi | `0acccd3e65e4d32f2af5fd94994da4dcf6fa262db6e6b23186f609569276beb9` |

Bobot person bukan hasil fine-tuning tim. Bobot table/chair berasal dari
dataset `restaurant inference` yang provenance, lisensi, parameter training,
dan metrik held-out-nya didokumentasikan di `dataset/README.md` serta asset
manifest release.

## Stop dan reset demo

```bash
docker compose down
```

Perintah tersebut mempertahankan volume database. Jangan gunakan `docker
compose down -v` kecuali memang ingin menghapus seluruh database dan cache
demo.

Foto cafe pribadi tidak diperlukan untuk menjalankan runbook dan tidak
disimpan di repository publik. Untuk uji visual lokal, gunakan file sendiri di
folder yang di-ignore. Contoh visualisasi fixture di dalam container:

```bash
docker compose exec inference python -m inference.visualize_detection \
  /app/dataset/mock/tomoro.png \
  --output /app/snapshots/tomoro_annotated.png
mkdir -p docker-output
docker compose cp inference:/app/snapshots/tomoro_annotated.png \
  ./docker-output/tomoro_annotated.png
```

Script ini hanya demo visual dan tidak mengubah pipeline occupancy maupun
mengirim status ke backend.
