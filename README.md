# Basir AI

Basir AI adalah MVP sistem ketersediaan meja workspace cafe. Kamera area workspace (atau input mock untuk evaluasi lokal) diproses oleh YOLOv8 untuk mendeteksi orang, dipetakan ke ROI setiap meja, lalu ditampilkan sebagai status `available`, `partial`, atau `occupied` di dashboard publik.

## Status repository

Fondasi teknis, kontrak model, dan pipeline reproducible untuk dataset
Table–Chair sudah tersedia. Pipeline inference runtime dan occupancy engine
memiliki detector person, mock frame/video capture, dan penghitungan status per
ROI yang teruji. Backend API tersedia dan dapat dijalankan bersama service
inference melalui Docker Compose. Fine-tuning table-chair sudah dijalankan
secara lokal pada dataset Roboflow yang didokumentasikan di `dataset/README.md`;
dataset, hasil run, dan bobot tetap tidak dikomit.

## Struktur canonical

```text
inference/       capture, YOLO, ROI, occupancy, snapshot
backend/         FastAPI, SQLAlchemy, Alembic
web/             Next.js dashboard publik
dataset/         pipeline Open Images + sample/mock input; sumber wajib dicatat
context/         aturan kompetisi
```

`occupancy-engine/` dilipat ke `inference/` sesuai arsitektur. `frontend/` tidak digunakan; nama canonical frontend adalah `web/`.

Runtime AI berada di `inference/main.py`: mode `--once` menjalankan capture →
person detection → occupancy → POST status ke backend. Model calibration hanya
menghasilkan saran reviewable melalui `inference/calibration.py`; saran tidak
pernah menggantikan `roi_config.json` tanpa konfirmasi manusia.

## Dokumentasi sumber

- [PRD](PRD.md) — scope, user stories, dan acceptance criteria.
- [Architecture](ARCHITECTURE.md) — stack, struktur, konvensi, dan kontrak API.
- [Database schema](DATABASE_SCHEMA.md) — skema data MVP yang akan dimigrasikan dengan Alembic.
- [Design](DESIGN.md) — token visual, layout, copy, dan aksesibilitas.
- [Competition rules](context/COMPETITION_RULES.md) — batas kepatuhan, reproducibility, dan integritas demo.

## Menjalankan lokal via Docker Compose

Prasyarat: Docker Desktop dengan Docker Compose v2.

```powershell
# 1. Salin file konfigurasi lingkungan
Copy-Item .env.example .env

# 2. Jalankan database, backend, dan inference (migrasi backend berjalan otomatis)
docker compose up --build -d

# 3. (Opsional) Jalankan seed data untuk data demo
docker compose exec backend python -m app.seed
```

Setelah `docker compose up` selesai:

| Service  | URL                            |
|----------|-------------------------------|
| Backend API | http://localhost:8000       |
| API Docs    | http://localhost:8000/docs  |
| Health      | http://localhost:8000/health|
| Inference   | background service          |

**Catatan seed data**: Seed tidak berjalan otomatis. Jalankan `docker compose exec backend python -m app.seed` untuk mengisi data demo (cafe dan meja). Tanpa seed, endpoint `/cafes/{id}/status` akan mengembalikan 404 karena belum ada data cafe.

## Menjalankan backend secara lokal (tanpa Docker)

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
# Pastikan PostgreSQL lokal berjalan dan DATABASE_URL di .env sudah benar
alembic upgrade head
uvicorn app.main:app --reload
```

Untuk menjalankan unit test (tidak memerlukan PostgreSQL — menggunakan SQLite):

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests/ -v
```

Untuk menjalankan satu cycle inference setelah dependency dan `.env` siap:

```powershell
python -m inference.main --once
```

Mode mock default memakai `dataset/mock/workspace.ppm`. Untuk menguji file
video lokal, letakkan video yang tidak berisi data privat di `dataset/mock/`,
lalu set `MOCK_VIDEO_PATH=dataset/mock/nama-video.mp4` dan opsional
`MOCK_VIDEO_LOOP=false` di `.env`. Compose me-mount folder mock secara read-only;
video lokal tidak boleh dikomit.

Penyimpanan snapshot default-nya nonaktif untuk melindungi privasi. Jika demo
memang memerlukan snapshot, aktifkan `SNAPSHOT_STORAGE_ENABLED=true` dan pilih
`SNAPSHOT_STORAGE_BACKEND=local` atau `s3`; jangan menaruh credential di file
yang dikomit. Gambar yang disimpan diturunkan ke resolusi rendah dan JPEG
quality yang dikonfigurasi sebelum ditulis.

Jika backend tidak tersedia atau satu meja gagal di-update, cycle mencatat
error lalu melanjutkan tanpa menghentikan proses meja lainnya. Endpoint internal
menggunakan `X-API-Key` dan payload status yang didokumentasikan di
`ARCHITECTURE.md`.

## Aturan pengembangan

- Gunakan mock mode untuk pengujian tanpa kamera fisik dan tandai hasil mock secara jujur.
- Jangan commit credential, model weight, data privat, atau snapshot yang dapat mengenali wajah.
- Catat sumber dan lisensi setiap dataset/sample input.
- Jangan menambahkan fitur di luar MVP atau klaim yang belum didukung bukti.
- Jalankan test dan lint sebelum commit; gunakan Conventional Commits.
