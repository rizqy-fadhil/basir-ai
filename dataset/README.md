# Dataset dan pipeline fine-tuning

Folder ini menyimpan skrip reproducible dan fixture sintetis. Gambar, anotasi
mentah, label hasil konversi, dan cache training Open Images tidak boleh masuk
Git; semuanya ditulis ke `data/open_images/`, yang di-ignore.

Model kalibrasi hanya memakai class `table` dan `chair`. Sumber awal adalah
subset Open Images V7 dari [ringkasan resmi Open Images](https://storage.googleapis.com/openimages/web/factsfigures_v7.html)
dan [halaman download V7](https://storage.googleapis.com/openimages/web/download_v7.html).
Anotasi tersedia di bawah CC BY 4.0, sedangkan lisensi gambar asli harus
diverifikasi satu per satu dari metadata dan URL sumber sebelum dipakai.

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
dataset yang sudah direview:

```powershell
python dataset/train_table_chair.py `
  --data data/open_images/processed/data.yaml `
  --model yolov8n.pt
```

Evaluasi wajib dijalankan pada split `test` yang tidak dipakai untuk training.
Script menyimpan precision, recall, mAP50, dan mAP50-95 per class hanya dari
hasil yang dikembalikan Ultralytics:

```powershell
python dataset/evaluate_table_chair.py `
  --model inference/models/table-chair-best.pt `
  --data data/open_images/processed/data.yaml `
  --split test
```

Sesudah training, script menyimpan training manifest dengan parameter aktual,
split, preprocessing, metrik yang benar-benar dikembalikan Ultralytics, dan
SHA-256 `best.pt`. Bobot final tidak dikomit; rilis model harus mengunggahnya
sebagai GitHub Release asset bersama checksum dan manifest tersebut.

Setelah release tersedia, unduh asset dengan GitHub CLI (ganti tag release
sesuai rilis yang benar-benar dibuat), lalu verifikasi checksum dari manifest:

```powershell
gh release download <release-tag> --repo rizqy-fadhil/basir-ai `
  --pattern table-chair-best.pt --dir inference/models
certutil -hashfile inference/models/table-chair-best.pt SHA256
```

Jangan mengisi tag, checksum, atau metrik sebelum release dan training benar-
benar ada; contoh di atas sengaja hanya berupa prosedur.

Fixture yang tersedia:

- `mock/workspace.ppm` — frame sintetis 32×18 piksel dengan empat area meja
  berwarna. Fixture ini hanya untuk pengujian pipeline lokal, bukan rekaman
  cafe nyata dan tidak mengandung wajah atau data pribadi.
