# Database Schema — Basir AI MVP

PostgreSQL menyimpan konfigurasi cafe, definisi meja, status meja terbaru, dan snapshot terbaru per area. MVP tidak menyimpan histori okupansi atau data identitas pengunjung.

## `cafe`

| Kolom | Tipe | Aturan |
|---|---|---|
| `id` | `bigint` | Primary key |
| `nama` | `varchar(120)` | Wajib |
| `slug` | `varchar(120)` | Wajib, unik |
| `timezone` | `varchar(64)` | Default `Asia/Jakarta` |
| `aktif` | `boolean` | Default `true` |
| `created_at` | `timestamptz` | Wajib, default waktu database |
| `updated_at` | `timestamptz` | Wajib, diperbarui saat perubahan |

## `meja`

| Kolom | Tipe | Aturan |
|---|---|---|
| `id` | `bigint` | Primary key |
| `cafe_id` | `bigint` | Foreign key ke `cafe.id` |
| `nomor_meja` | `integer` | Wajib, unik per cafe |
| `kapasitas` | `smallint` | Wajib, lebih besar dari 0 |
| `roi` | `jsonb` | Polygon GeoJSON dalam koordinat frame kamera |
| `aktif` | `boolean` | Default `true` |
| `created_at` | `timestamptz` | Wajib, default waktu database |
| `updated_at` | `timestamptz` | Wajib, diperbarui saat perubahan |

Constraint: `unique (cafe_id, nomor_meja)`.

## `status_meja`

Tepat satu baris status terbaru disimpan untuk setiap meja.

| Kolom | Tipe | Aturan |
|---|---|---|
| `meja_id` | `bigint` | Primary key sekaligus foreign key ke `meja.id` |
| `terisi` | `smallint` | Default `0`, tidak negatif |
| `status` | `varchar(16)` | Hanya `available`, `partial`, atau `occupied` |
| `updated_at` | `timestamptz` | Wajib, waktu hasil inferensi diterima |

## `snapshot`

Satu baris snapshot terbaru disimpan untuk setiap area kamera. Baris di-upsert, bukan dijadikan tabel histori.

| Kolom | Tipe | Aturan |
|---|---|---|
| `id` | `bigint` | Primary key |
| `cafe_id` | `bigint` | Foreign key ke `cafe.id` |
| `area_kamera` | `varchar(120)` | Wajib, unik per cafe |
| `url` | `text` | Wajib, URL object storage atau file demo |
| `captured_at` | `timestamptz` | Wajib, waktu frame diambil |
| `updated_at` | `timestamptz` | Wajib, waktu baris diperbarui |

Constraint: `unique (cafe_id, area_kamera)`.

## Relasi

```text
cafe 1───* meja 1───1 status_meja
cafe 1───* snapshot
```

## Aturan integritas

- Status API dan database selalu memakai lowercase `available`, `partial`, dan `occupied`.
- Label Indonesia hanya diterjemahkan di frontend.
- `terisi` tidak boleh negatif dan tidak boleh melebihi `kapasitas` saat hasil inference disimpan.
- ROI wajib berupa polygon yang valid dan dikonversi ke objek Shapely saat diproses.
