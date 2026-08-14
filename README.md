# Basir AI

Basir AI adalah MVP sistem ketersediaan meja workspace cafe. Kamera area workspace (atau input mock untuk evaluasi lokal) diproses oleh YOLOv8 untuk mendeteksi orang, dipetakan ke ROI setiap meja, lalu ditampilkan sebagai status `available`, `partial`, atau `occupied` di dashboard publik.

## Status repository

Fondasi teknis, kontrak model, dan pipeline reproducible untuk menyiapkan
dataset Table–Chair sudah tersedia. Pipeline inference runtime dan occupancy
engine memiliki detector person serta penghitungan status per ROI yang teruji
dengan fixture mock. Fine-tuning table-chair masih menunggu review manual
dataset, artifact gambar, dan environment training; bobot atau metric belum
diklaim sebelum eksperimen held-out benar-benar dijalankan.

## Struktur canonical

```text
inference/       capture, YOLO, ROI, occupancy, snapshot
backend/         FastAPI, SQLAlchemy, Alembic
web/             Next.js dashboard publik
dataset/         pipeline Open Images + sample/mock input; sumber wajib dicatat
context/         aturan kompetisi
```

`occupancy-engine/` dilipat ke `inference/` sesuai arsitektur. `frontend/` tidak digunakan; nama canonical frontend adalah `web/`.

## Dokumentasi sumber

- [PRD](PRD.md) — scope, user stories, dan acceptance criteria.
- [Architecture](ARCHITECTURE.md) — stack, struktur, konvensi, dan kontrak API.
- [Database schema](DATABASE_SCHEMA.md) — skema data MVP yang akan dimigrasikan dengan Alembic.
- [Design](DESIGN.md) — token visual, layout, copy, dan aksesibilitas.
- [Competition rules](context/COMPETITION_RULES.md) — batas kepatuhan, reproducibility, dan integritas demo.

## Menjalankan fondasi lokal

Prasyarat: Docker Desktop dengan Docker Compose v2.

```powershell
Copy-Item .env.example .env
docker compose up -d db
```

Perintah di atas hanya menyalakan PostgreSQL untuk fase fondasi. Service backend, inference, dan web akan diaktifkan setelah implementasi masing-masing tersedia.

Fixture mock yang digunakan pada tahap ini adalah `dataset/mock/workspace.ppm`. File tersebut sintetis, hanya untuk pengujian lokal, dan tidak merepresentasikan rekaman cafe nyata.

## Aturan pengembangan

- Gunakan mock mode untuk pengujian tanpa kamera fisik dan tandai hasil mock secara jujur.
- Jangan commit credential, model weight, data privat, atau snapshot yang dapat mengenali wajah.
- Catat sumber dan lisensi setiap dataset/sample input.
- Jangan menambahkan fitur di luar MVP atau klaim yang belum didukung bukti.
- Jalankan test dan lint sebelum commit; gunakan Conventional Commits.
