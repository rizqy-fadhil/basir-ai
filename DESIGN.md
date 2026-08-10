# Design Spec: Basir AI — Dashboard Okupansi Cafe

Berdasarkan `PRD.md`. Fokus: halaman publik yang dilihat pengguna WFC sebelum berangkat (US-005, US-006, US-007), dengan status meja per US-004.

## 1. Subjek dan Ketegangan Inti

Basir AI hidup di persimpangan dua dunia yang biasanya tidak bertemu: kehangatan cafe (kopi, meja kayu, obrolan) dan presisi machine vision (bounding box, confidence score, deteksi objek). Desain ini tidak menyembunyikan sisi teknis di balik UI yang "ramah" generik — ketegangan itu justru jadi materi desainnya. Pengguna sedang melihat data yang berasal dari kamera, dan sebuah dashboard yang jujur soal itu terasa lebih dipercaya daripada yang menyamarkannya jadi ikon kopi lucu.

Audiens: mahasiswa dan freelancer Indonesia yang membuka halaman ini di HP, sambil buru-buru, sebelum memutuskan berangkat atau tidak. Satu tugas halaman: jawab "meja kosong ada, nggak?" dalam waktu di bawah 3 detik tanpa perlu scroll.

## 2. Design Tokens

### Warna

| Token | Hex | Peran |
|---|---|---|
| `--ink` | `#1B140F` | Background utama — espresso gelap, bukan hitam pekat |
| `--roast` | `#332419` | Surface kartu di atas ink — coklat kopi sangrai |
| `--oat` | `#EDE3D0` | Teks & area terang — warna susu/oat, dipakai secukupnya, bukan dominan |
| `--scan` | `#4FBEB0` | Aksen deteksi/status Tersedia — teal fosfor monitor, bukan hijau neon |
| `--amber` | `#E3A93F` | Status Sebagian Terisi |
| `--ember` | `#D2622E` | Status Penuh — merah-oranye bara, dipakai fungsional bukan dekoratif |

Kenapa bukan kombinasi klise: bukan cream-background + serif terracotta (semua konten tetap di atas dasar gelap espresso), dan bukan near-black + hijau neon tunggal (aksen `--scan` adalah teal fosfor CRT/monitor lama, bukan acid green; dan tiga warna status punya peran fungsional berbeda, bukan satu aksen dekoratif).

### Tipografi

- **Display/data tag** — monospace teknis (mis. *Space Mono* atau *JetBrains Mono*), dipakai untuk angka besar, label status, dan timestamp. Alasan: label confidence score pada bounding box deteksi objek selalu monospace — font ini secara literal meniru output mesin, bukan estetika sembarangan.
- **Body** — sans humanis (mis. *Inter* atau *Public Sans*), dipakai untuk deskripsi, copy, dan teks panjang. Kontras dengan mono: mono = keluaran mesin, sans = suara manusia yang menjelaskan.
- **Skala**: hero number 56–72px mono bold, judul meja 18px mono medium, body 16px sans regular, caption/timestamp 13px mono regular.

### Layout

Konsep: setiap meja ditampilkan sebagai kartu bergaya *viewfinder* — bingkai sudut siku (seperti fokus kamera saat mengunci objek) mengelilingi info meja, meniru tampilan bounding box asli dari model deteksi.

```
┌ Basir AI ─────────────────────────────┐
│                                        │
│  ⌐ SNAPSHOT AREA WORKSPACE        ⌐   │
│  ┆   [gambar area, low-res]        ┆  │
│  └                                 ┘  │
│  update terakhir: 2 menit lalu        │
│                                        │
│  OKUPANSI CAFE: 62%                   │
│  ▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░               │
│                                        │
│  ⌐MEJA 01⌐   ⌐MEJA 02⌐   ⌐MEJA 03⌐   │
│  ┆ 2/2   ┆   ┆ 0/2   ┆   ┆ 3/4   ┆   │
│  ┆ PENUH ┆   ┆TERSEDIA┆  ┆SEBAGIAN┆  │
│  └       ┘   └       ┘   └       ┘   │
│  (ember)      (scan)      (amber)     │
│                                        │
└────────────────────────────────────────┘
```

Mobile-first: kartu meja jadi grid 2 kolom, snapshot dan angka okupansi total tetap di atas tanpa scroll (US-007 — jawaban utama harus terlihat < 3 detik).

### Signature Element

Bingkai sudut siku ala viewfinder (empat garis L di tiap pojok kartu) adalah satu elemen yang dipakai berulang — di snapshot hero, di tiap kartu meja, dan (tipis) di tombol utama. Warna bingkai mengikuti status meja itu sendiri (scan/amber/ember). Ini satu-satunya elemen "berani" di desain; sisanya tenang dan datar supaya bingkai ini yang diingat.

## 3. Self-Critique

Draf pertama sempat mengarah ke pola umum: dasar near-black + satu aksen hijau neon tunggal, mirip pola AI-generik #2. Revisi: dasar diganti jadi coklat espresso hangat (bukan hitam pekat), aksen deteksi diganti dari hijau neon ke teal fosfor monitor lama, dan ditambah dua warna status fungsional lain (amber, ember) supaya palet punya alasan struktural, bukan sekadar satu aksen dekoratif. Angka meja (01, 02, 03) sempat terasa seperti penomoran generik ala "langkah 1-2-3" — tapi ini nomor meja sungguhan dari cafe, jadi dipertahankan karena membawa informasi asli, bukan dekorasi urutan proses.

## 4. Motion

- Saat halaman dimuat: garis sapuan tipis (scan line) lewat sekali di atas snapshot hero, dari atas ke bawah — meniru proses kamera mengunci frame. Sekali saja, tidak berulang.
- Saat kartu meja di-hover/tap: bingkai sudut sedikit mengetat ke dalam (seperti autofocus mengunci target). Durasi singkat, ~150ms.
- Hormati `prefers-reduced-motion`: sapuan hero dan animasi bingkai dimatikan, ganti dengan fade sederhana.

## 5. Copy / Teks UI

Suara: langsung, kalimat aktif, tanpa basa-basi promosi.

| Konteks | Teks |
|---|---|
| Judul hero | "Cek dulu sebelum berangkat" |
| Status meja | Tersedia / Sebagian Terisi / Penuh |
| Label okupansi | "Okupansi cafe: 62%" |
| Timestamp | "Update 2 menit lalu" |
| Kosong/tanpa data kamera | "Kamera area ini belum mengirim data. Coba lagi sebentar." |
| Semua meja penuh | "Semua meja penuh saat ini. Coba cek lagi dalam beberapa menit." |
| Footer privasi | "Basir AI hanya mendeteksi keberadaan orang dan status meja. Tidak ada identifikasi wajah atau data biometrik yang disimpan." |

Aturan: nama status di UI (Tersedia/Sebagian Terisi/Penuh) selalu sama persis di semua tempat — jangan berubah jadi "Kosong" di satu halaman dan "Available" di halaman lain. Pesan error dan empty state menjelaskan apa yang terjadi dan apa yang bisa dilakukan pengguna, bukan permintaan maaf generik.

## 6. Aksesibilitas & Responsif

- Kontras teks oat (`#EDE3D0`) di atas ink (`#1B140F`) memenuhi WCAG AA untuk body text.
- Status meja tidak hanya dibedakan lewat warna — tiap kartu juga punya label teks (Tersedia/Sebagian/Penuh), penting untuk pengguna buta warna.
- Fokus keyboard terlihat jelas pada kartu meja (outline mengikuti warna status, bukan dihilangkan).
- Breakpoint utama: mobile (< 640px, grid 2 kolom), tablet (640–1024px, grid 3 kolom), desktop (> 1024px, grid 4 kolom + snapshot lebih besar).

## 7. Pemetaan ke PRD

- US-005 (Dashboard okupansi) → grid kartu meja + bar okupansi total.
- US-006 (Snapshot) → area hero dengan scan-line motion dan timestamp.
- US-007 (Tampilan sederhana) → hero + ringkasan okupansi tanpa login, load < 3 detik.
- FR-8 (pengelompokan per kapasitas) → label kapasitas di tiap kartu meja (mis. "2/4").
- FR-10 (tanpa identifikasi individu) → footer privasi + snapshot resolusi rendah secara desain, bukan hanya kebijakan.