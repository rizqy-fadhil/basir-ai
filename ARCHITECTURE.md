# Tech Stack & Konvensi Teknis: Basir AI MVP

Pelengkap `architecture.md`. Dokumen ini mengunci pilihan library, versi, struktur folder, dan aturan kode supaya semua anggota tim — dan AI agent yang membantu coding — menghasilkan kode yang konsisten. Kalau mau tambah/ganti library, update dokumen ini dulu sebelum dipakai di kode, biar semua orang (dan semua sesi AI agent) baca sumber yang sama.

## 1. Aturan untuk AI Agent

Baca ini sebelum generate kode apa pun untuk proyek ini:

1. **Jangan ganti library di luar tabel section 2** tanpa alasan eksplisit dari user. Kalau butuh kapabilitas baru, tanya dulu, jangan diam-diam pasang package lain yang fungsinya mirip.
2. **Ikuti struktur folder di section 3 persis.** Jangan bikin folder/file baru di luar struktur itu kecuali diminta.
3. **Ikuti skema database di `architecture.md` section 5 dan konvensi penamaan di section 4 dokumen ini.** Jangan improvisasi nama tabel/kolom baru dengan gaya beda (mis. `camelCase` di satu file, `snake_case` di file lain).
4. **ROI point-in-polygon pakai `shapely`, bukan hitung manual.** Sudah ada library yang benar dan teruji, jangan reinvent.
5. **Semua endpoint API mengikuti kontrak di section 6.** Kalau perlu endpoint baru, tambahkan ke dokumen ini dulu, baru diimplementasi.
6. **Environment variable mengikuti daftar di section 7.** Jangan hardcode credential, path, atau URL di kode.
7. **Commit message dan branch name ikuti section 8.**
8. Kalau ragu antara dua pendekatan yang sama-sama valid, pilih yang paling sederhana dan paling dekat dengan apa yang sudah ada di dokumen ini — bukan yang paling "canggih".

## 2. Stack Terkunci (Pinned Versions)

### Backend & Inference

| Layer | Tool | Versi | Alasan |
|---|---|---|---|
| Bahasa | Python | 3.11 | Kompatibel penuh dengan Ultralytics + FastAPI terbaru |
| Web framework | FastAPI | 0.111.x | Async native, auto OpenAPI docs, satu bahasa dengan pipeline CV |
| ASGI server | Uvicorn | 0.30.x | Standar pasangan FastAPI |
| Validasi data | Pydantic | 2.7.x | Built-in di FastAPI 0.111 |
| ORM | SQLAlchemy | 2.0.x | Sintaks modern (2.0-style), hindari mixing 1.x/2.0 |
| Migrasi DB | Alembic | 1.13.x | Pasangan resmi SQLAlchemy |
| Database | PostgreSQL | 15 | Cukup untuk MVP, gampang di-host di semua cloud |
| Object detection | Ultralytics (YOLOv8) | 8.2.x, model `yolov8n.pt` | Nano cukup untuk 1 kamera CPU-only |
| Computer vision util | OpenCV (`opencv-python-headless`) | 4.10.x | Baca RTSP stream, resize frame |
| Geometri ROI | Shapely | 2.0.x | Point-in-polygon check untuk pemetaan meja |
| Scheduler | APScheduler | 3.10.x | Trigger inference job tiap interval, jalan di dalam proses Python yang sama |
| Storage client | boto3 | 1.34.x | S3-compatible client (AWS S3 / Cloudflare R2) |
| Env config | python-dotenv | 1.0.x | Baca `.env` |
| Testing | pytest | 8.x | Standar Python |
| Lint/format | ruff + black | ruff 0.5.x, black 24.x | ruff untuk lint, black untuk format — jalankan sebelum commit |

### Frontend

| Layer | Tool | Versi | Alasan |
|---|---|---|---|
| Framework | Next.js | 14.x (App Router) | React + routing + build tool dalam satu paket |
| Bahasa | TypeScript | 5.x | Type safety, kontrak API lebih jelas |
| Styling | Tailwind CSS | 3.4.x | Cepat translate token dari `design.md` ke class |
| Data fetching/polling | SWR | 2.2.x | Polling interval bawaan (`refreshInterval`), pas untuk US-005/006/007 |
| Lint/format | ESLint + Prettier | eslint 8.x, prettier 3.x | Standar Next.js |

### Infra

| Layer | Tool | Versi | Alasan |
|---|---|---|---|
| Container | Docker + Docker Compose | Docker 26.x, Compose v2 | Reproducible environment untuk demo |
| CI (opsional) | GitHub Actions | — | Lint + test on push, cukup minimal |

## 3. Struktur Folder (Monorepo)

```
basir-ai/
├── inference/                  # Python — capture, detection, occupancy engine
│   ├── main.py                 # entrypoint scheduler
│   ├── capture.py              # ambil frame dari RTSP
│   ├── detect.py               # jalankan YOLOv8n
│   ├── roi.py                  # mapping bounding box -> ROI (shapely)
│   ├── occupancy.py            # hitung status per meja + agregat
│   ├── storage.py              # upload snapshot ke object storage
│   ├── config/
│   │   └── roi_config.json     # koordinat ROI per meja (atau baca dari DB)
│   └── requirements.txt
│
├── backend/                    # FastAPI — API + koneksi DB
│   ├── app/
│   │   ├── main.py
│   │   ├── models.py           # SQLAlchemy models
│   │   ├── schemas.py          # Pydantic schemas
│   │   ├── routers/
│   │   │   ├── cafe.py
│   │   │   ├── meja.py
│   │   │   └── status.py
│   │   └── db.py
│   ├── alembic/
│   └── requirements.txt
│
├── web/                         # Next.js dashboard publik
│   ├── app/
│   │   └── page.tsx             # halaman utama (US-007)
│   ├── components/
│   │   ├── TableCard.tsx        # kartu meja (viewfinder bracket, design.md)
│   │   ├── SnapshotHero.tsx
│   │   └── OccupancyBar.tsx
│   ├── lib/
│   │   └── api.ts               # fetcher untuk backend API
│   └── package.json
│
├── docker-compose.yml
├── .env.example
├── architecture.md
├── design.md
├── tasks/
│   └── prd-basir-ai-mvp.md
└── tech-stack.md               # dokumen ini
```

## 4. Konvensi Penamaan

- **Database**: `snake_case` untuk tabel dan kolom, nama tabel singular (`cafe`, bukan `cafes`) — konsisten dengan skema di `architecture.md`.
- **Python**: `snake_case` untuk variabel/fungsi, `PascalCase` untuk class, file module `snake_case.py`.
- **TypeScript/React**: `camelCase` untuk variabel/fungsi, `PascalCase` untuk component dan nama file component (`TableCard.tsx`).
- **API JSON response**: `snake_case` di key (biar konsisten dengan DB), contoh: `{"nomor_meja": 4, "kapasitas": 4, "status": "occupied"}`.
- **Status enum**: nilai baku di seluruh sistem (backend, DB, API) adalah `available` / `partial` / `occupied` (bahasa Inggris, huruf kecil). Terjemahan ke "Tersedia/Sebagian Terisi/Penuh" hanya terjadi di layer frontend (lihat `design.md` section 5) — jangan terjemahkan di backend/DB.

## 5. Environment Variables

Semua service baca dari `.env` (jangan hardcode). Template ada di `.env.example`:

```
# inference service
RTSP_URL=
DETECTION_INTERVAL_SECONDS=45
YOLO_MODEL_PATH=yolov8n.pt

# backend API
DATABASE_URL=postgresql://user:pass@db:5432/basirai
BACKEND_API_KEY=              # dipakai inference service untuk POST ke backend

# object storage
S3_ENDPOINT_URL=
S3_BUCKET_NAME=
S3_ACCESS_KEY=
S3_SECRET_KEY=

# frontend
NEXT_PUBLIC_API_BASE_URL=
```

## 6. Kontrak API (MVP)

Base URL: `NEXT_PUBLIC_API_BASE_URL`. Semua response JSON, `snake_case`.

| Method | Endpoint | Deskripsi | Dipanggil oleh |
|---|---|---|---|
| `POST` | `/internal/status` | Inference service kirim hasil deteksi (status per meja + snapshot url) | inference service (pakai `BACKEND_API_KEY`) |
| `GET` | `/cafes/{cafe_id}/status` | Ambil status okupansi terkini + daftar meja | web dashboard (polling) |
| `GET` | `/cafes/{cafe_id}/snapshot` | Ambil URL snapshot terbaru | web dashboard |
| `GET` | `/cafes/{cafe_id}/meja` | Ambil daftar meja + kapasitas + ROI (untuk admin/config, bukan publik) | tooling internal |

`GET /cafes/{cafe_id}/status` contoh response:

```json
{
  "cafe_id": 1,
  "okupansi_persen": 62,
  "updated_at": "2026-08-06T10:15:00Z",
  "meja": [
    {"nomor_meja": 1, "kapasitas": 2, "terisi": 2, "status": "occupied"},
    {"nomor_meja": 2, "kapasitas": 2, "terisi": 0, "status": "available"},
    {"nomor_meja": 3, "kapasitas": 4, "terisi": 3, "status": "partial"}
  ]
}
```

## 7. Git & Kolaborasi

- **Branch naming**: `feature/nama-fitur`, `fix/nama-bug`, contoh `feature/roi-mapping`, `fix/snapshot-upload-error`.
- **Commit message**: Conventional Commits — `feat: tambah endpoint status meja`, `fix: perbaiki bounding box overlap`, `chore: update dependency`.
- **Satu PR = satu US** dari PRD (mis. PR untuk US-004 khusus klasifikasi status, tidak dicampur dengan US-005 dashboard).
- **Sebelum merge**: jalankan `ruff check` + `black --check` (Python) atau `eslint` (frontend), pastikan tidak ada error.

## 8. Yang Sengaja Belum Dipakai (MVP)

Supaya AI agent tidak menambah kompleksitas yang belum perlu — ini di luar scope MVP sesuai Non-Goals PRD, jangan diimplementasi dulu:

- Autentikasi/login (dashboard publik, satu cafe saja)
- WebSocket/real-time push (polling SWR sudah cukup untuk interval 30–60 detik)
- Message queue (Kafka/RabbitMQ) — satu kamera, satu service, tidak perlu
- Kubernetes — Docker Compose cukup untuk MVP
- Tabel time-series/histori okupansi — `status_meja` cukup satu baris ter-update per meja