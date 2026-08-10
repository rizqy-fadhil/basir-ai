# Basir AI

Basir AI adalah MVP sistem ketersediaan meja workspace cafe. Kamera area workspace (atau input mock untuk evaluasi lokal) diproses oleh YOLOv8 untuk mendeteksi orang, dipetakan ke ROI setiap meja, lalu ditampilkan sebagai status `available`, `partial`, atau `occupied` di dashboard publik.

## Status repository

Repository ini sedang dibangun bertahap. Fase fondasi (Plan 0) menyiapkan kontrak teknis, konfigurasi lokal, skema database, dependency manifest, dan kerangka Docker Compose. Pipeline inference, API, dan dashboard belum diimplementasikan pada fase ini.

## Struktur canonical

```text
inference/       capture, YOLO, ROI, occupancy, snapshot
backend/         FastAPI, SQLAlchemy, Alembic
web/             Next.js dashboard publik
dataset/         sample/mock input; sumber dan lisensi wajib dicatat
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

## Aturan pengembangan

- Gunakan mock mode untuk pengujian tanpa kamera fisik dan tandai hasil mock secara jujur.
- Jangan commit credential, model weight, data privat, atau snapshot yang dapat mengenali wajah.
- Catat sumber dan lisensi setiap dataset/sample input.
- Jangan menambahkan fitur di luar MVP atau klaim yang belum didukung bukti.
- Jalankan test dan lint sebelum commit; gunakan Conventional Commits.
