# PRD: Basir AI MVP — Real-Time Workspace Availability System

## 1. Ringkasan

Basir AI mendeteksi status ketersediaan meja di cafe secara real-time lewat computer vision, lalu menampilkannya ke pengguna sebelum mereka berangkat. Pengguna Work From Cafe (WFC) — mahasiswa, freelancer, tim startup — kini mengecek rating dan foto di Google Maps, tiba di cafe, dan sering menemukan area kerja penuh. Basir AI mengganti tebakan itu dengan data okupansi aktual.

MVP menyasar satu cafe mitra. Kamera area tempat duduk mengirim video ke server, model YOLO mendeteksi orang di setiap ROI (meja), sistem mengklasifikasikan tiap meja sebagai Available, Partially Occupied, atau Occupied, dan dashboard menampilkan hasilnya ke pengguna.

## 2. Tujuan

- Pengguna melihat jumlah meja kosong per kapasitas (2 orang, 4 orang, dst) sebelum berangkat ke cafe.
- Status tiap meja diperbarui secara berkala tanpa campur tangan pegawai cafe.
- Sistem berjalan stabil di satu cafe mitra selama periode kompetisi/demo.
- Pengguna mengurangi failed trip — datang ke cafe dan gagal dapat tempat kerja.

## 3. User Stories

### US-001: Ingest video dari kamera area workspace
**Deskripsi:** Sebagai sistem, saya perlu menerima feed video dari kamera area tempat duduk secara berkala agar ada data untuk dianalisis.

**Acceptance Criteria:**
- [ ] Server menerima frame video dari kamera pada interval tetap (misal setiap 30–60 detik)
- [ ] Frame tersimpan sementara untuk diproses model
- [ ] Sistem tetap berjalan jika satu frame gagal diambil (tidak crash)

### US-002: Deteksi orang per meja dengan YOLO
**Deskripsi:** Sebagai sistem, saya perlu mendeteksi keberadaan orang di setiap area meja agar bisa menentukan status okupansi.

**Acceptance Criteria:**
- [ ] Model YOLO mendeteksi bounding box objek "person" pada tiap frame
- [ ] Sistem tidak menyimpan wajah atau identitas — hanya koordinat bounding box
- [ ] Deteksi berjalan dalam waktu wajar untuk update near-real-time (di bawah interval polling)

### US-003: Pemetaan meja lewat Region of Interest (ROI)
**Deskripsi:** Sebagai admin cafe, saya perlu mendefinisikan area tiap meja di frame kamera agar sistem tahu batas satu meja dengan meja lain.

**Acceptance Criteria:**
- [ ] Setiap meja punya ROI dengan koordinat tetap dan kapasitas (jumlah kursi) terdaftar
- [ ] Bounding box orang yang overlap dengan ROI tertentu terhitung sebagai okupansi meja itu
- [ ] Konfigurasi ROI bisa diubah tanpa mengubah kode (file config atau tabel database)

### US-004: Klasifikasi status meja
**Deskripsi:** Sebagai pengguna, saya ingin tahu status tiap meja (Available / Partially Occupied / Occupied) agar saya tahu masih ada tempat yang cocok untuk saya.

**Acceptance Criteria:**
- [ ] Meja berstatus Available jika jumlah orang terdeteksi = 0
- [ ] Meja berstatus Partially Occupied jika jumlah orang < kapasitas meja
- [ ] Meja berstatus Occupied jika jumlah orang = kapasitas meja
- [ ] Status tersimpan dengan timestamp update terakhir

### US-005: Dashboard okupansi cafe
**Deskripsi:** Sebagai pengguna, saya ingin melihat jumlah meja tersedia per kapasitas dan persentase keterisian cafe sebelum berangkat.

**Acceptance Criteria:**
- [ ] Dashboard menampilkan jumlah meja Available, Partially Occupied, dan Occupied
- [ ] Dashboard mengelompokkan meja berdasarkan kapasitas
- [ ] Dashboard menampilkan persentase okupansi keseluruhan cafe
- [ ] Data di dashboard mengikuti update terbaru dari sistem deteksi
- [ ] Verify in browser using dev-browser skill

### US-006: Snapshot kondisi area workspace
**Deskripsi:** Sebagai pengguna, saya ingin melihat snapshot terbaru area cafe agar punya gambaran visual, bukan cuma angka.

**Acceptance Criteria:**
- [ ] Sistem menyimpan snapshot frame terbaru per area
- [ ] Dashboard/app menampilkan snapshot dengan timestamp
- [ ] Snapshot tidak menampilkan identitas wajah yang bisa dikenali (blur atau resolusi rendah cukup)
- [ ] Verify in browser using dev-browser skill

### US-007: Tampilan sederhana untuk pengguna akhir
**Deskripsi:** Sebagai pengguna WFC, saya ingin membuka aplikasi atau web sebelum berangkat dan langsung tahu apakah cafe layak dikunjungi.

**Acceptance Criteria:**
- [ ] Halaman utama menampilkan status okupansi cafe dalam satu tampilan ringkas
- [ ] Pengguna bisa melihat tanpa login (MVP, single cafe)
- [ ] Waktu muat halaman di bawah 3 detik pada koneksi normal
- [ ] Verify in browser using dev-browser skill

## 4. Functional Requirements

- FR-1: Sistem menerima frame video dari kamera area tempat duduk pada interval yang bisa dikonfigurasi.
- FR-2: Model YOLO mendeteksi objek "person" pada tiap frame dan menghasilkan bounding box.
- FR-3: Sistem memetakan tiap bounding box ke ROI meja yang sesuai.
- FR-4: Sistem menghitung jumlah orang per meja dan membandingkannya dengan kapasitas meja.
- FR-5: Sistem mengklasifikasikan tiap meja ke salah satu dari tiga status: Available, Partially Occupied, Occupied.
- FR-6: Sistem menyimpan status tiap meja beserta timestamp update.
- FR-7: Sistem menghitung persentase okupansi total cafe dari agregat status semua meja.
- FR-8: Dashboard/web menampilkan jumlah meja per status, dikelompokkan per kapasitas.
- FR-9: Sistem menyimpan dan menampilkan snapshot terbaru per area kamera.
- FR-10: Sistem tidak melakukan identifikasi wajah atau menyimpan data biometrik individu.
- FR-11: Update status berjalan otomatis tanpa input manual dari pegawai cafe.

## 5. Non-Goals (Out of Scope untuk MVP)

- Tidak ada integrasi sistem reservasi meja.
- Tidak ada prediksi okupansi berdasarkan pola historis.
- Tidak ada analitik perilaku pengunjung (dwell time, repeat visit, dll).
- Tidak ada dukungan multi-cafe — MVP berjalan di satu cafe mitra.
- Tidak ada aplikasi mobile native — cukup web app responsif untuk MVP.
- Tidak ada identifikasi individu, pelacakan wajah, atau penyimpanan data biometrik dalam bentuk apa pun.

## 6. Design Considerations

- Dashboard menampilkan status meja dengan indikator warna (hijau = Available, kuning = Partially Occupied, merah = Occupied) agar cepat dipahami sekilas.
- Snapshot ditampilkan dalam resolusi rendah — cukup untuk konteks visual, tidak untuk mengenali wajah.
- Halaman publik (dilihat pengguna) fokus ke tiga angka utama: jumlah meja tersedia, persentase okupansi, waktu update terakhir.

## 7. Technical Considerations

- Model deteksi: YOLO (versi ringan agar bisa jalan near-real-time di server yang tersedia).
- ROI per meja disimpan sebagai koordinat statis, dikonfigurasi ulang jika layout cafe berubah atau posisi kamera bergeser.
- Interval polling kamera jadi trade-off utama: makin sering, makin real-time, tapi makin berat beban server.
- Istilah "CCTV" dihindari di materi publik/proposal — gunakan "kamera area workspace" untuk mengurangi kekhawatiran privasi.
- Kalimat etika AI wajib ada di dokumentasi publik: sistem hanya mendeteksi keberadaan objek dan status okupansi, tanpa identifikasi individu atau penyimpanan data biometrik.

## 8. Success Metrics

- Dashboard mencerminkan kondisi meja aktual dengan selisih waktu update di bawah interval polling yang ditentukan.
- Sistem berjalan tanpa crash selama sesi demo/kompetisi penuh.
- Pengguna uji coba bisa menentukan meja mana yang tersedia dalam satu kali lihat dashboard, tanpa perlu klik tambahan.

## 9. Open Questions

- Berapa interval polling kamera yang realistis untuk server MVP (30 detik? 60 detik?)
- Apakah cafe mitra sudah dikonfirmasi dan kameranya sudah terpasang di posisi yang cukup untuk cover semua meja?
- Berapa jumlah meja dan kapasitas variasi (2 orang, 4 orang, dst) di cafe mitra — ini menentukan jumlah ROI yang perlu dikonfigurasi?
- Snapshot disimpan berapa lama sebelum dihapus/diganti (storage constraint)?