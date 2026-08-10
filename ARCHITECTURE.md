# Tech Stack & Konvensi Teknis: Basir AI MVP

Dokumen ini mengunci pilihan library, versi, struktur folder, dan aturan kode supaya semua anggota tim — dan AI agent yang membantu coding — menghasilkan kode yang konsisten. Dokumen ini menjadi sumber teknis utama repository; setiap perubahan stack atau kontrak harus diperbarui di sini terlebih dahulu.

## 1. Aturan untuk AI Agent

Baca ini sebelum generate kode apa pun untuk proyek ini:

1. **Jangan ganti library di luar tabel section 2** tanpa alasan eksplisit dari user. Kalau butuh kapabilitas baru, jelaskan alasannya dan perbarui dokumen ini terlebih dahulu.
2. **Ikuti struktur folder di section 3 persis.** Jangan bikin folder/file baru di luar struktur itu kecuali diminta.
3. **Ikuti skema database di section 5 dan konvensi penamaan di section 4.** Jangan improvisasi nama tabel/kolom baru dengan gaya berbeda (mis. `camelCase` di satu file, `snake_case` di file lain).
4. **ROI point-in-polygon pakai `shapely`, bukan hitung manual.** Sudah ada library yang benar dan teruji, jangan reinvent.
5. **Semua endpoint API mengikuti kontrak di section 7.** Kalau perlu endpoint baru, tambahkan ke dokumen ini dulu, baru diimplementasi.
6. **Environment variable mengikuti daftar di section 6.** Jangan hardcode credential, path, atau URL di kode.
7. **Commit message dan branch name ikuti section 8.**
8. Kalau ragu antara dua pendekatan yang sama-sama valid, pilih yang paling sederhana dan paling dekat dengan apa yang sudah ada di dokumen ini — bukan yang paling canggih.

## 2. Stack Terkunci (Pinned Versions)

### Backend & Inference

| Layer | Tool | Versi | Alasan |
|---|---|---|---|
| Bahasa | Python | 3.11 | Kompatibel dengan Ultralytics dan FastAPI |
| Web framework | FastAPI | 0.111.x | Async native dan OpenAPI otomatis |
| ASGI server | Uvicorn | 0.30.x | Standar pasangan FastAPI |
| Validasi data | Pydantic | 2.7.x | Validasi request/response |
| ORM | SQLAlchemy | 2.0.x | Sintaks modern 2.0-style |
| Migrasi DB | Alembic | 1.13.x | Pasangan resmi SQLAlchemy |
| Database | PostgreSQL | 15 | Database MVP yang mudah direproduksi |
| PostgreSQL driver | psycopg | 3.2.x | Driver SQLAlchemy untuk PostgreSQL |
| Object detection | Ultralytics (YOLOv8) | 8.2.x, model `yolov8n.pt` | Model ringan untuk satu kamera |
| Computer vision util | OpenCV (`opencv-python-headless`) | 4.10.x | Baca stream, resize, dan encode frame |
| Geometri ROI | Shapely | 2.0.x | Point-in-polygon yang teruji |
| Scheduler | APScheduler | 3.10.x | Trigger inference sesuai interval |
| Storage client | boto3 | 1.34.x | S3-compatible storage |
| Env config | python-dotenv | 1.0.x | Membaca `.env` |
| Testing | pytest | 8.x | Test Python |
| Lint/format | ruff + black | ruff 0.5.x, black 24.x | Validasi sebelum commit |

### Frontend

| Layer | Tool | Versi | Alasan |
|---|---|---|---|
| Framework | Next.js | 14.x (App Router) | React, routing, dan build tool |
| Bahasa | TypeScript | 5.x | Type safety dan kontrak API |
| Styling | Tailwind CSS | 3.4.x | Implementasi design tokens |
| Data fetching/polling | SWR | 2.2.x | Polling 30–60 detik |
| Lint/format | ESLint + Prettier | eslint 8.x, prettier 3.x | Konsistensi frontend |

### Infra

| Layer | Tool | Versi | Alasan |
|---|---|---|---|
| Container | Docker + Docker Compose | Docker 26.x, Compose v2 | Reproducible environment |
| CI (opsional) | GitHub Actions | — | Lint dan test saat push |

## 3. Struktur Folder (Monorepo)

```text
basir-ai/
├── inference/                  # Python — capture, detection, occupancy engine
│   ├── main.py                 # entrypoint scheduler
│   ├── capture.py              # ambil frame dari RTSP atau mock file
│   ├── detect.py               # jalankan YOLOv8n
│   ├── roi.py                  # mapping bounding box -> ROI (shapely)
│   ├── occupancy.py            # hitung status per meja + agregat
│   ├── storage.py              # upload snapshot ke object storage/local demo
│   ├── config/
│   │   └── roi_config.json     # koordinat ROI per meja
│   ├── tests/
│   └── requirements.txt
│
├── dataset/                    # sample/mock input; sumber dan lisensi wajib dicatat
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
│   ├── tests/
│   └── requirements.txt
│
├── web/                        # Next.js dashboard publik
│   ├── app/
│   │   └── page.tsx            # halaman utama (US-007)
│   ├── components/
│   │   ├── TableCard.tsx
│   │   ├── SnapshotHero.tsx
│   │   └── OccupancyBar.tsx
│   ├── lib/
│   │   └── api.ts              # fetcher untuk backend API
│   └── package.json
│
├── docker-compose.yml
├── .env.example
├── ARCHITECTURE.md
├── DATABASE_SCHEMA.md
├── DESIGN.md
├── PRD.md
└── context/
    └── COMPETITION_RULES.md
```

## 4. Konvensi Penamaan

- **Database**: `snake_case` untuk tabel dan kolom, nama tabel singular (`cafe`, bukan `cafes`).
- **Python**: `snake_case` untuk variabel/fungsi, `PascalCase` untuk class, file module `snake_case.py`.
- **TypeScript/React**: `camelCase` untuk variabel/fungsi, `PascalCase` untuk component dan nama file component.
- **API JSON response**: `snake_case`, contoh `{"nomor_meja": 4, "kapasitas": 4, "status": "occupied"}`.
- **Status enum**: nilai baku di backend, DB, dan API adalah `available` / `partial` / `occupied`. Terjemahan ke bahasa Indonesia hanya dilakukan di frontend.

## 5. Skema Database (MVP)

Detail kolom dan constraint berada di [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md). Model yang wajib ada:

- `cafe`: identitas dan status aktif cafe.
- `meja`: kapasitas dan polygon ROI setiap meja.
- `status_meja`: satu baris status terbaru per meja.
- `snapshot`: satu baris snapshot terbaru per area kamera.

MVP tidak menyimpan histori okupansi, wajah, identitas, atau data biometrik pengunjung.

## 6. Environment Variables

Semua service membaca dari `.env`; jangan hardcode credential, path, atau URL.

```dotenv
# inference service
RTSP_URL=
DETECTION_INTERVAL_SECONDS=45
YOLO_MODEL_PATH=yolov8n.pt
MOCK_MODE=true
MOCK_FRAME_PATH=dataset/mock/workspace.ppm

# backend API
DATABASE_URL=postgresql://user:pass@db:5432/basirai
BACKEND_API_KEY=

# local PostgreSQL container
POSTGRES_DB=basirai
POSTGRES_USER=basirai
POSTGRES_PASSWORD=
POSTGRES_PORT=5432

# object storage
S3_ENDPOINT_URL=
S3_BUCKET_NAME=
S3_ACCESS_KEY=
S3_SECRET_KEY=

# frontend
NEXT_PUBLIC_API_BASE_URL=
```

`MOCK_MODE` wajib tersedia untuk evaluasi lokal tanpa hardware. Nilai secret pada `.env.example` harus kosong atau placeholder lokal dan tidak boleh dipakai untuk production.

## 7. Kontrak API (MVP)

Base URL: `NEXT_PUBLIC_API_BASE_URL`. Semua response JSON memakai `snake_case`.

| Method | Endpoint | Deskripsi | Dipanggil oleh |
|---|---|---|---|
| `POST` | `/internal/status` | Inference service mengirim status per meja dan URL snapshot | inference service, memakai `BACKEND_API_KEY` |
| `GET` | `/cafes/{cafe_id}/status` | Status okupansi terkini dan daftar meja | web dashboard, polling |
| `GET` | `/cafes/{cafe_id}/snapshot` | URL snapshot terbaru | web dashboard |
| `GET` | `/cafes/{cafe_id}/meja` | Daftar meja, kapasitas, dan ROI | tooling internal |

Contoh `GET /cafes/{cafe_id}/status`:

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

## 8. Git & Kolaborasi

- **Branch naming**: `feature/nama-fitur`, `fix/nama-bug`, contoh `feature/roi-mapping`.
- **Commit message**: Conventional Commits — `feat: tambah endpoint status meja`, `fix: perbaiki bounding box overlap`.
- **Satu PR = satu US** dari PRD jika perubahan cukup besar untuk PR terpisah.
- **Sebelum merge**: jalankan `ruff check` + `black --check` (Python) atau `npm run lint` (frontend), lalu test.

## 9. Yang Sengaja Belum Dipakai (MVP)

- Autentikasi/login.
- WebSocket/real-time push; polling SWR sudah cukup.
- Message queue seperti Kafka/RabbitMQ.
- Kubernetes.
- Tabel time-series atau histori okupansi.
- Aplikasi mobile native.
