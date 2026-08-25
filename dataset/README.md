# Dataset dan pipeline fine-tuning

Folder ini menyimpan skrip reproducible dan fixture sintetis. Gambar, anotasi
mentah, label hasil konversi, dataset Roboflow, dan cache training tidak boleh
masuk Git; semuanya ditulis ke folder `data/` yang di-ignore.

Model kalibrasi hanya memakai class `table` dan `chair`. Sumber awal adalah
subset Open Images V7 dari [ringkasan resmi Open Images](https://storage.googleapis.com/openimages/web/factsfigures_v7.html)
dan [halaman download V7](https://storage.googleapis.com/openimages/web/download_v7.html).
Anotasi tersedia di bawah CC BY 4.0, sedangkan lisensi gambar asli harus
diverifikasi satu per satu dari metadata dan URL sumber sebelum dipakai.

## Pivot darurat: Roboflow Universe

Pipeline kandidat Open Images V7 dihentikan sebelum training karena hasil
query/filter awal mengandung gambar yang tidak relevan. Model yang dilatih
untuk submission ini memakai dataset publik berikut:

- Nama: `restaurant inference`, version 1.
- Halaman dataset: [Roboflow Universe](https://universe.roboflow.com/datasetvision/restaurant-inference).
- Author/workspace: `datasetvision`.
- Lisensi yang tercantum di halaman dataset dan export: `CC BY 4.0`.
- Task dan sumber anotasi: object detection, export YOLOv8.
- Class sumber: `chair`, `customer`, `staff`, `table`.
- Versi export lokal: 382 gambar (`275 train`, `71 validation`, `36 test`);
  halaman project mencantumkan 357 gambar sebelum versi/augmentasi export.
- Contoh frame yang diperiksa menunjukkan adegan indoor restoran/seating;
  halaman dataset tidak memberikan deskripsi scene yang lebih rinci, sehingga
  hasil ini tidak boleh dipresentasikan sebagai jaminan bahwa setiap gambar
  bebas dari domain shift.

Dataset export tetap lokal di `data/roboflow/` dan tidak dikomit. Script
`prepare_roboflow_table_chair.py` mempertahankan seluruh gambar export,
menghapus box `customer` dan `staff`, lalu meremap `table` menjadi class `0`
dan `chair` menjadi class `1`. Provenance per gambar disimpan di
`provenance.csv`, sedangkan ringkasan preprocessing, jumlah box, source URL,
lisensi, dan SHA-256 arsip export disimpan di `preparation_manifest.json`.

Arsip export yang dipakai pada run ini memiliki SHA-256:
`9311f5efa243dc488e317712c5df0fb4b837c54f29c9a694eacb823c9b7a88d4`.
Nilai ini hanya mengidentifikasi artifact lokal yang benar-benar dipakai; ia
bukan klaim checksum resmi dari Roboflow.

Perintah konversi reproducible:

```bash
python dataset/prepare_roboflow_table_chair.py \
  --source-dir data/roboflow/restaurant-inference-1 \
  --output-dir data/roboflow/restaurant-inference-table-chair \
  --source-url https://universe.roboflow.com/datasetvision/restaurant-inference \
  --author datasetvision \
  --license "CC BY 4.0" \
  --source-archive-sha256 <sha256-arsip-export>
```

Konversi ini bukan kurasi manual satu per satu. Ia hanya melakukan filtering
class yang deterministik agar model calibration tetap berisi tepat dua class.
Penerimaan lisensi final dan atribusi tetap harus mengikuti rule kompetisi.

Skrip memakai endpoint CSV yang ditautkan halaman download resmi tersebut:

- [class descriptions](https://storage.googleapis.com/openimages/v5/class-descriptions-boxable.csv);
- [train bounding boxes](https://storage.googleapis.com/openimages/v6/oidv6-train-annotations-bbox.csv);
- [validation bounding boxes](https://storage.googleapis.com/openimages/v5/validation-annotations-bbox.csv);
- [validation image metadata](https://storage.googleapis.com/openimages/2018_04/validation/validation-images-with-rotation.csv).

URL train/test yang sesuai tercantum sebagai konstanta di
`prepare_open_images.py`; endpoint tersebut dipakai karena itulah URL yang
dirujuk oleh halaman Open Images V7, meskipun nama bucket mempertahankan versi
rilis sebelumnya.

## Menyiapkan kandidat

Perintah ini mengunduh CSV resmi ke lokasi lokal yang di-ignore dan membuat
manifest kandidat. `--max-images` hanya untuk smoke test; hapus opsi itu saat
menyiapkan split training/validation sebenarnya.

```powershell
python dataset/prepare_open_images.py `
  --split validation `
  --fetch-sources `
  --max-images 128
```

Untuk menyiapkan preview lokal sebelum review manual, jalankan downloader
terpisah berikut:

```powershell
python dataset/download_candidate_previews.py `
  --input data/open_images/processed/candidates_validation.csv `
  --output-dir data/open_images/preview
```

Image preview dan `preview_manifest.csv` ditulis ke `data/open_images/preview/`
yang di-ignore Git. Downloader hanya menyalin status review ke manifest dan
tidak pernah mengubah `curation_status`, `license_verified`, atau
`scene_verified`. Buka preview dan landing URL sumber untuk memverifikasi
lisensi serta relevansi indoor/seating secara manual; hanya reviewer manusia
yang boleh mengisi ketiga flag tersebut.

Review `data/open_images/processed/candidates_validation.csv`. Untuk setiap
gambar yang benar-benar boleh dipakai, isi:

- `curation_status=include`;
- `license_verified=true` setelah lisensi gambar dan atribusinya diperiksa;
- `scene_verified=true` setelah adegan indoor/seating diperiksa secara manual.

Baris yang belum memenuhi ketiga syarat itu tidak pernah dibuat menjadi label
training. Setelah review, jalankan ulang:

```powershell
python dataset/prepare_open_images.py `
  --split validation `
  --curation-file data/open_images/processed/candidates_validation.csv `
  --download-images
```

Ulangi proses untuk `--split train`. Skrip akan mengeluarkan label YOLO
normalized `xywh`, manifest provenance, dan `data.yaml`. Box `IsGroupOf` dan
`IsDepiction` dikeluarkan; box occluded/truncated tetap dipertahankan agar
model kalibrasi menghadapi kondisi seating yang realistis.

## Split reproducible

Setelah kandidat ditinjau dan artifact gambar/label tersedia, buat split lokal
70/15/15. Split dilakukan per kombinasi label dengan hash SHA-256 yang stabil,
sehingga tidak berubah antar-run dan tidak membocorkan image ID antar subset:

```powershell
python dataset/split_manifest.py `
  --input data/open_images/processed/candidates_validation.csv `
  --processed-dir data/open_images/processed `
  --materialize
```

Perintah ini menulis `splits/{train,validation,test}.csv`,
`splits/split_manifest.json`, dan `data.yaml`. Ia akan berhenti jika belum ada
baris `include` dengan `license_verified=true` serta `scene_verified=true`,
atau jika gambar/label yang akan dimaterialisasi belum tersedia.

## Fine-tuning dan manifest

`train_table_chair.py` menginisialisasi model kedua dari `yolov8n.pt` (nilai
default mengikuti `YOLO_PERSON_MODEL_PATH`) dan tidak mengubah model person
runtime. Validasi konfigurasi tanpa mengimpor Ultralytics:

```powershell
python dataset/train_table_chair.py --dry-run
```

Training nyata membutuhkan dependency di `inference/requirements.txt` dan
dataset dua class yang sudah disiapkan. Untuk run Roboflow yang tercatat di
repo ini:

```powershell
python dataset/train_table_chair.py `
  --data data/roboflow/restaurant-inference-table-chair/data.yaml `
  --model yolov8n.pt `
  --epochs 10 `
  --imgsz 320 `
  --batch 16 `
  --device cpu `
  --workers 0
```

Evaluasi wajib dijalankan pada split `test` yang tidak dipakai untuk training.
Script menyimpan precision, recall, mAP50, dan mAP50-95 per class hanya dari
hasil yang dikembalikan Ultralytics:

```powershell
python dataset/evaluate_table_chair.py `
  --model inference/models/table-chair-best.pt `
  --data data/roboflow/restaurant-inference-table-chair/data.yaml `
  --split test
```

### Hasil run Roboflow yang benar-benar dijalankan

Run darurat menggunakan `yolov8n.pt`, CPU, `epochs=10`, `imgsz=320`,
`batch=16`, `workers=0`, dan seed `42`. Run 50 epoch pada 640 px tidak
dilanjutkan karena estimasi waktu CPU berjam-jam; tidak ada angka dari run
yang dihentikan itu yang dipakai sebagai hasil.

Evaluasi held-out `test` berisi 36 gambar dan 221 box. Angka berikut berasal
langsung dari Ultralytics, bukan dari halaman Roboflow:

| Class | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| table | 0.6182 | 0.5303 | 0.5408 | 0.2497 |
| chair | 0.5077 | 0.4000 | 0.4154 | 0.1759 |
| aggregate | 0.5630 | 0.4652 | 0.4781 | 0.2128 |

Keterbatasan utama: dataset memiliki background setelah box non-target
dibuang, run hanya 10 epoch pada CPU, dan belum ada evaluasi pada kamera cafe
Basir AI. Angka ini tidak boleh disebut sebagai akurasi produksi atau jaminan
performa kompetisi.

Artifact lokal run ini:

- Bobot: `inference/models/table-chair-best.pt`.
- SHA-256 bobot: `0acccd3e65e4d32f2af5fd94994da4dcf6fa262db6e6b23186f609569276beb9`.
- Training manifest: `runs/calibration/restaurant-inference-table-chair-emergency/training_manifest.json`.
- Held-out metrics: `runs/calibration/restaurant-inference-table-chair-emergency/test_evaluation.json`.
- Bobot dan folder `runs/` tetap di-ignore; sebelum submission bobot harus
  diunggah sebagai GitHub Release asset bersama manifest dan checksum.

Sesudah training, script menyimpan training manifest dengan parameter aktual,
split, preprocessing, metrik yang benar-benar dikembalikan Ultralytics, dan
SHA-256 `best.pt`. Bobot final tidak dikomit; bobot, checksum, dan manifest
run ini tersedia sebagai asset GitHub Release `models-v1.0.0`.

Unduh asset dengan GitHub CLI lalu verifikasi checksum dari manifest:

```powershell
gh release download models-v1.0.0 --repo rizqy-fadhil/basir-ai `
  --pattern table-chair-best.pt --dir inference/models
certutil -hashfile inference/models/table-chair-best.pt SHA256
```

Jangan mengisi tag, checksum, atau metrik sebelum release dan training benar-
benar ada; contoh di atas sengaja hanya berupa prosedur.

Fixture yang tersedia:

- `mock/workspace.ppm` — frame sintetis 32×18 piksel dengan empat area meja
  berwarna. Fixture ini hanya untuk pengujian pipeline lokal, bukan rekaman
  cafe nyata dan tidak mengandung wajah atau data pribadi.
