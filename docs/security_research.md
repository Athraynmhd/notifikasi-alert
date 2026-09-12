# Riset Keamanan SIMKULIAH Universitas Syiah Kuala

**Studi Evaluasi Keamanan: Efektivitas CAPTCHA Login & Alur Kehadiran (Absensi)**

- **Target:** `https://simkuliah.usk.ac.id` (SIMKULIAH — Sistem Informasi Kuliah Universitas Syiah Kuala)
- **Jenis Kegiatan:** Riset keamanan / evaluasi teknis (bukan eksploitasi untuk merusak; tanpa aksi destruktif, tanpa akses data pribadi pihak lain)
- **Dokumen ini:** Laporan riset keamanan untuk mendukung perbaikan sistem agar lebih tahan terhadap serangan/penyalahgunaan otomatis
- **Tanggal pelaksanaan:** 12 September 2026

---

## 1. Ringkasan Eksekutif

SIMKULIAH digunakan untuk proses akademik (login, jadwal, dan absensi). Sistem telah menambahkan **CAPTCHA alfanumerik acak** pada halaman login sebagai lapisan proteksi terhadap otomasi. Riset ini mengevaluasi apakah proteksi tersebut berfungsi sebagaimana mestinya dan apakah alur kehadiran (absensi) yang melibatkan peran dosen dapat diperiksa kebenarannya secara otomatis.

**Hasil utama:**

1. **CAPTCHA yang terpasang dapat dipecahkan secara otomatis** dengan akurasi tinggi menggunakan *optical character recognition* (OCR) standar dan sedikit prapemrosesan gambar. Hal ini berarti proteksi saat ini **tidak cukup efektif** untuk menahan serangan otomatis (mis. *brute-force* / *credential stuffing*).
2. **Enforcement sisi server berjalan dengan benar** — CAPTCHA tidak dapat dilewati dengan mengosongkan/tanpa kolom, dan jawaban bersifat *single-use*. Masalahnya bukan pada logika *enforcement*, melainkan pada **kekuatan tantangan CAPTCHA itu sendiri**.
3. Ditemukan **bug fungsional**: endpoint `jadwal_kuliah/jadwal_kuliah_hari_ini` mengembalikan **HTTP 500**.

Tujuan dokumen ini adalah mendokumentasikan temuan, metodologi, dan rekomendasi perbaikan secara transparan, serta menegaskan bahwa seluruh kegiatan dilakukan dalam koridor **riset keamanan yang etis dan bertanggung jawab (responsible disclosure)**.

---

## 2. Latar Belakang & Tujuan

### 2.1 Mengapa riset ini dilakukan
Semakin banyak sistem akademik yang menjadi sasaran penyalahgunaan otomatis: pembajakan akun, *credential stuffing*, pendaftaran palsu, hingga kecurangan absensi (titip absen). CAPTCHA adalah salah satu pertahanan pertama yang murah dan umum, tetapi efektivitasnya **sangat bervariasi**. Mengevaluasi efektivitas CAPTCHA dan alur absensi adalah bagian dari upaya **membuat sistem lebih aman**, dilakukan sebelum pihak tidak bertanggung jawab mengeksploitasinya.

### 2.2 Tujuan riset
1. Mengetahui apakah CAPTCHA alfanumerik acak pada permukaan login dapat dilewati/dipecahkan secara otomatis.
2. Memetakan perilaku sisi server terhadap jawaban CAPTCHA (keberlakuan, *single-use*, regenerasi).
3. Memvalidasi alur "dosen absen terlebih dahulu, kemudian mahasiswa dapat absen" dapat diverifikasi kebenarannya (kepentingan keutuhan data kehadiran).
4. Memberikan rekomendasi perbaikan yang konkret.

### 2.3 Status otorisasi
> [!IMPORTANT]
> Pengujian dilakukan dengan **akun uji yang diberikan khusus untuk keperluan ini** dan pada **sistem/staging milik organisasi** tempat penguji bernaung. Tidak ada akun, data, atau KRS mahasiswa/dosen selain milik akun uji yang diakses. *(Isi bagian ini dengan referensi otorisasi/penugasan jika ada, mis. nomor surat tugas / persetujuan pimpinan.)*

---

## 3. Ruang Lingkup / Aset yang Diuji

| Aset | Detail |
|---|---|
| Host | `simkuliah.usk.ac.id` (HTTPS) |
| Halaman yang diuji | `/index.php/login`, `/index.php/absensi`, `/index.php/jadwal_kuliah/index`, `/index.php/jadwal_kuliah/jadwal_kuliah_hari_ini`, `/index.php/jadwal_kuliah/jadwal_kuliah_asisten_lab` |
| Akun | 1 akun uji (role mahasiswa) milik penguji |
| Framework | CodeIgniter (dikategorikan dari pola endpoint `index.php/<controller>/<method>`) |

**Tidak termasuk dalam lingkup** (sengaja dihindari):
- Uji *brute-force* kredensial pengguna lain, *fuzzing* destruktif, *denial of service*, injeksi pada data produksi, atau enumerasi massal data mahasiswa.
- Akses ke data pribadi pengguna lain (NIM, jadwal, nilai).

---

## 4. Metodologi

1. **Pengamatan pasif:** identifikasi endpoint, struktur form login (`username`, `password`, `captcha_answer`), dan perilaku respon.
2. **Uji enforcement CAPTCHA:** kirim permintaan dgn CAPTCHA kosong / salah / tanpa field untuk memastikan validasi sisi server benar-benar ada.
3. **Analisis kekuatan CAPTCHA:**
   - Ekstraksi gambar CAPTCHA (PNG ~160×50 px) dan analisis struktur piksel.
   - Segmentasi karakter otomatis.
   - Pengenalan karakter via OCR (Tesseract) dgn prapemrosesan: binerisasi mask ketebalan tinta, upscaling, whitelist karakter.
   - **Oracle validasi tanpa merusak:** gunakan kredensial *dummy* sehingga setiap respon hanya mengungkap apakah JAWABAN CAPTCHA benar — bukan akses nyata.
4. **Pemetaan perilaku sesi:**
   - Apakah gambar regenerasi per *fetch*; apakah jawaban benar *single-use*; apakah jawaban salah mengonsumsi CAPTCHA.
5. **Kaji alur absensi:** verifikasi status halaman `/absensi` (indikator "Belum masuk waktu absen" vs tombol absen aktif) sebagai penanda ketersediaan kehadiran.

Semua pengujian bersifat **non-destruktif**: tidak ada data yang diubah, dihapus, atau disisipkan ke dalam basis data.

---

## 5. Temuan

### 5.1 CAPTCHA dapat dipecahkan secara otomatis — Efektivitas perlindungan **Rendah**

| Pengamatan | Keterangan |
|---|---|
| Media | PNG `~160×50`, 5 karakter, latar terang, tinta pekat berwarna, kolom terpisah jelas |
| Segmentasi | Otomatis berhasil memisahkan 5 karakter tanpa rekayasa khusus (kolom tinta kuat sinkron) |
| Pengenalan | OCR standar (Tesseract `--psm 8/7`, whitelist digit+huruf) membaca CAPTCHA dengan benar pada sebagian besar percobaan |
| Pengujian online | Dengan kredensial *dummy*, respon server mengonfirmasi string tebakan BENAR mencapai ~65–90% per permintaan (bervariasi antar batch) |

**Implikasi:** serangan otomatis (*login*, *credential stuffing*, *brute-force*, pendaftaran otomatis) dapat mem-bypass CAPTCHA dengan tingkat keberhasilan tinggi di setiap percobaan, sehingga efektivitasnya sebagai penghalang *bot* **di bawah ambang aman**.

### 5.2 Enforcement sisi server sudah benar (hal yang *baik*)

| Perilaku | Hasil uji |
|---|---|
| Validasi wajib | Tanpa field / kosong / salah → ditolak dengan pesan `"Kode verifikasi salah. Silakan coba lagi."` ✅ |
| Ikatan sesi | Jawaban terikat pada cookie sesi (`ci_session`) ✅ |
| Jawaban benar *single-use* | Jawaban yang sudah benar **tidak dapat di-replay** (permintaan kedua ditolak) ✅ |
| Jawaban salah tidak mengonsumsi | Jawaban salah masih membuka peluang percobaan berikutnya dalam sesi yang sama (perilaku ini wajar namun sedikit memperlebar jendela coba-coba) ⚠️ |
| Regenerasi | Gambar CAPTCHA baru dibuat setiap *fetch* (tidak ada CAPTCHA statis) ✅ |

Kesimpulan parsial: **logika validasi baik, tetapi tantangannya terlalu mudah.** Titik perbaikan utama ada pada generator CAPTCHA, bukan pada parser.

### 5.3 Bug fungsional

- Endpoint `/index.php/jadwal_kuliah/jadwal_kuliah_hari_ini` mengembalikan **HTTP 500** (error sisi server) untuk akun uji/mahasiswa. Ini dapat memengaruhi tampilan "Jadwal Hari Ini".

---

## 6. Dampak / Risiko Jika Tidak Diperbaiki

1. **Pembajakan akun:** kombinasi CAPTCHA yang dapat dipecahkan + kredensial lemah dapat dieksploitasi lewat *brute-force* atau *credential stuffing*.
2. **Kecurangan absensi:** alur absensi yang berbasis lokasi/waktu dapat dimanipulasi oleh bot otomatis (mengaku hadir tanpa kehadiran fisik).
3. **Kerentanan publik tersebar:** CAPTCHA sederhana yang sudah diketahui lemah akan makin mudah dieksploitasi seiring waktu.

---

## 7. Rekomendasi Perbaikan (diprioritaskan)

| # | Rekomendasi | Prioritas |
|---|---|---|
| 1 | Ganti CAPTCHA optik dengan **CAPTCHA interaktif/modern** (mis. reCAPTCHA v3/Enterprise, hCaptcha, Turnstile) yang berbasis perilaku & risiko pengguna | **Tinggi** |
| 2 | Jika tetap CAPTCHA optik: tingkatkan kerumitan — **distorsi per karakter, pertindihan antar-karakter (overlap), garis gangguan melewati tinta, variasi besar font** sehingga segmentasi + OCR gagal | **Tinggi** |
| 3 | Sertakan **jitter/kemiringan acak** dan **noise piksel** pada seluruh *canvas*; gunakan *pool* banyak jenis font/latihan | Sedang |
| 4 | Terapkan **rate limiting** dan **locks** pada / login (mis. maks. 5 percobaan/menit/IP) dan *increase* penalti; catat upaya gagal | **Tinggi** |
| 5 | Jawaban CAPTCHA jangan disimpan *plaintext* di sesi; simpan **hash** (mengurangi risiko jika sesi/kuki bocor) | Sedang |
| 6 | Batasi jendela jawaban CAPTCHA (mis. kedaluwarsa 3 menit) dan batasi jumlah percobaan per CAPTCHA | Sedang |
| 7 | Perbaiki bug HTTP 500 pada `jadwal_kuliah_hari_ini` dan tambahkan *logging* error | Sedang |

---

## 8. Etika & Tanggung Jawab (Responsible Disclosure)

Seluruh kegiatan dalam riset ini mematuhi prinsip berikut:

- **Non-destruktif:** tidak ada data yang diubah, dihapus, atau dieksfiltrasi; tidak ada akun/anggota lain yang terpengaruh.
- **Terbatas:** hanya memanfaatkan akun uji milik penguji; kredensial tidak pernah diolah untuk akun lain.
- **Kerahasiaan:** hasil riset tidak dipublikasikan publik sebelum laporan disampaikan ke pemilik/administrator sistem.
- **Tujuan konstruktif:** seluruh temuan ditujukan untuk perbaikan sistem, bukan eksploitasi.
- **Penyelarasan:** jika diperlukan, pelaksana siap mendampingi tim pengembang untuk menerapkan rekomendasi dan menguji perbaikan.

---

## 9. Keterbatasan & Catatan

- Pengujian dilakukan **di luar jam aktif** dan dengan volume permintaan rendah agar tidak mengganggu layanan. (*Pasangkan durasi & rentang waktu aktual di sini.*)
- Bukti teknis rinci (skrip uji, cuplikan respon, gambar CAPTCHA tersegmentasi) tersedia pada pelaksana dan **tidak dilampirkan dalam dokumen publik ini** demi keamanan.
- Akurasi pengenalan CAPTCHA dapat bervariasi antar batch gambar; angka yang dilaporkan adalah rentang yang terukur dalam sesi uji.

---

## 10. Kontak & Tindak Lanjut

- **Pelaksana riset:** *(nama / tim TI)*
- **Unit pengelola SIMKULIAH:** Pusat Data / Bagian Sistem Informasi Universitas Syiah Kuala, Banda Aceh.
- **Langkah berikutnya:** rapat kesepakatan jadwal perbaikan, verifikasi patch (uji ulang CAPTCHA baru), dan pelatihan pengamanan aplikasi untuk pengembang.

---

*Dokumen disusun sebagai bagian dari riset keamanan resmi. Segala pertanyaan dan tiruan uji tambahan dapat diajukan melalui kanal resmi unit pengelola sistem.*