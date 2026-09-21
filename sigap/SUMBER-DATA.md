# Sumber Data SIGAP — hasil pengecekan

> Diverifikasi 21 September 2026 dengan membuka sumbernya langsung.
> Sebelumnya beberapa baris cuma ditandai "belum dicek" — sekarang sudah.

---

## Ringkasan

| Data | Status | Cara dapat |
|---|---|---|
| Pesanan, stok, produk, pelanggan, jadwal produksi, uji mutu | ✅ **Siap** | Sandbox SAP, kunci API gratis |
| Cuaca & gempa Indonesia | ✅ **Siap, ada API JSON** | `data.bmkg.go.id` |
| Kalender libur nasional | ✅ Terbit tahunan | Salin manual |
| Kurs rupiah | ✅ Terbit harian | Bank Indonesia |
| TKDN | ⚠️ Portal publik, **tanpa API** | Ambil salinan → dokumen aturan |
| LARTAS | ⚠️ Portal publik, **tanpa API terbuka** | Salin dari Permendag → dokumen aturan |
| Topan luar negeri | ❌ **Bukan dari BMKG** | Lihat §5 |
| Posisi kapal | ⚠️ Perlu daftar | Layanan AIS |
| Profil perusahaan | 🔵 **Dikarang, dan diakui terbuka** | Lihat §7 |

---

## 1. Data perusahaan — beres, tidak perlu riset

**Sumber:** SAP Business Accelerator Hub, alamat `https://sandbox.api.sap.com/`

**Cara dapat:** daftar akun SAP ID gratis di `api.sap.com`, buka halaman API yang dibutuhkan,
klik *Show API Key*. Selesai.

Ini sistem S/4HANA Cloud asli berisi data contoh — bentuk data, penomoran halaman, dan pesan
errornya sama persis dengan sistem pelanggan sungguhan.

**Yang tersedia:**

| Butuh | Nama layanannya |
|---|---|
| Pesanan pembelian | `API_PURCHASEORDER_PROCESS_SRV` |
| Stok material | `API_MATERIAL_STOCK_SRV` |
| Struktur produk | `API_BILL_OF_MATERIAL_SRV` |
| Pesanan pelanggan | `API_SALES_ORDER_SRV` |
| Jadwal produksi | `API_PRODUCTION_ORDER_2_SRV` |
| Hasil uji mutu | `API_INSPECTIONLOT_SRV` |
| Stok cadangan minimum | `API_PRODUCT_SRV` |
| Buat permintaan pembelian | `API_PURCHASEREQ_PROCESS_SRV` |

**Pindah ke pelanggan nanti:** ganti alamat dan kunci. Kodenya tidak berubah.

---

## 2. TKDN — terbuka, tapi diambil manual

**Portal resmi:**
- https://tkdn.kemenperin.go.id/ — pencarian dan pengecekan sertifikat
- http://pusatp3dn.kemenperin.go.id/Sertifikattkdn — rekapitulasi per kelompok komoditas

**Hasil pengecekan:** halaman webnya publik dan bisa dicari, **tapi tidak ada API yang
didokumentasikan**. Tidak ditemukan dokumentasi endpoint resmi.

**Yang dikerjakan:** ambil salinannya sekali, simpan jadi `references/tkdn-rules.md`. Isinya:

- Ambang minimum kandungan lokal per sektor
- Cara menghitung rasionya
- Sertifikat 5–6 supplier yang dipakai di skenario, beserta masa berlakunya

**Tidak perlu seluruh database.** Yang dibutuhkan agent adalah **aturannya**, bukan ribuan
sertifikat. Dan aturan TKDN tidak berubah tiap hari.

> **Ini justru lebih baik daripada API.** Dokumen aturan bisa dibaca juri, bisa diaudit, dan
> jadi aset yang kelihatan. Kalau tersembunyi di balik panggilan API, tidak ada yang bisa
> memeriksa dasar penolakan agent.

---

## 3. LARTAS — pakai peraturannya, bukan hasil pencarian

**Portal:** https://insw.go.id/ — menu INTR, masukkan kode HS, keluar bea masuk, PPN, PPh,
dan status larangan/pembatasannya.

**Hasil pengecekan:** ada [katalog layanan SINSW](https://panduan.insw.go.id/en/katalog-layanan)
berisi 19 layanan, tapi untuk pelaku usaha terdaftar — bukan API terbuka.

**Jalan yang lebih baik:** LARTAS diatur di **Permendag No. 18 Tahun 2021**. Itu dokumen
peraturan, bisa dibaca langsung, dan justru dasar yang lebih tepat daripada mencari satu per
satu di portal.

**Yang dikerjakan:** `references/lartas-procedure.md` berisi:

- Jenis barang apa yang kena pembatasan
- Izin apa yang diperlukan
- **Berapa lama pengurusannya** ← ini yang dipakai agent untuk mencoret pilihan
- Apa yang berubah kalau negara asalnya baru

---

## 4. Cuaca dan gempa Indonesia — ✅ ada API, gratis, siap pakai

**Sumber:** https://data.bmkg.go.id/

**Ini satu-satunya sinyal gangguan yang benar-benar bisa disambungkan tanpa usaha besar.**

| Data | Alamat | Format |
|---|---|---|
| Prakiraan cuaca 3 hari, per kecamatan | `data.bmkg.go.id/prakiraan-cuaca/` | JSON |
| Gempa terbaru | `autogempa.json` | JSON & XML |
| 15 gempa M5.0+ terakhir | `gempaterkini.json` | JSON & XML |
| 15 gempa dirasakan | `gempadirasakan.json` | JSON & XML |

Contoh kode resminya ada di [infoBMKG/data-cuaca](https://github.com/infoBMKG/data-cuaca) dan
[infoBMKG/data-gempabumi](https://github.com/infoBMKG/data-gempabumi).

---

## 5. ❌ Koreksi: BMKG bukan sumber untuk topan Ningbo

**Kesalahan yang perlu diperbaiki.** Dokumen sebelumnya menulis *"BMKG tropical-cyclone
bulletins"* sebagai pemicu skenario Ningbo. Itu keliru.

BMKG memantau **perairan Indonesia**. Topan yang menutup Pelabuhan Ningbo ada di Laut Cina
Timur — di luar wilayah tanggung jawabnya.

**Pemetaan yang benar:**

| Jenis gangguan | Sumber sinyal | Status |
|---|---|---|
| Topan Asia Timur (skenario Ningbo) | JTWC atau JMA | Perlu dicek terpisah |
| **Gempa di Indonesia** | ✅ **BMKG** | Siap pakai |
| **Cuaca ekstrem & banjir Indonesia** | ✅ **BMKG** | Siap pakai |
| Pelabuhan Indonesia | Pengumuman otoritas pelabuhan | Perlu dicek |
| Keterlambatan kapal | Data AIS | Perlu daftar |

### Saran: tambah satu skenario domestik

BMKG paling berguna justru untuk gangguan dalam negeri — gempa yang memutus jalur darat Jawa,
banjir yang menutup akses ke Priok. Dan datanya paling mudah diambil.

**Tambahkan satu skenario dengan gempa BMKG sebagai pemicu sungguhan.** Nilainya besar: kalian
bisa mengatakan *"sinyal ini datang dari API BMKG yang sedang berjalan sekarang"* — bukan dari
data contoh. Satu sumber yang benar-benar hidup jauh lebih meyakinkan daripada empat yang cuma
disebut di slide.

---

## 6. Kalender libur dan kurs — gampang

| Data | Sumber | Catatan |
|---|---|---|
| Libur nasional & cuti bersama | SKB 3 Menteri | Terbit sekali setahun. Salin manual, taruh di `references/holiday-calendar.md` |
| Kurs rupiah | JISDOR Bank Indonesia | Terbit harian. Untuk demo, nilai tetap sudah cukup |

Jangan habiskan waktu mengotomatiskan dua ini. Nilainya kecil.

---

## 7. Profil perusahaan — satu-satunya yang dikarang

Daftar pabrik, kecepatan pemakaian bahan harian, isi kontrak dan denda keterlambatan.

**Tidak ada sumbernya, karena kita belum punya pelanggan.** Tiap pemasangan nanti mengisi ini
dari data induk perusahaannya sendiri di hari pertama.

**Harus dinyatakan terbuka di proposal.** Sudah tertulis di sana, dan jangan dihapus — juri jauh
lebih menghargai batas yang dinyatakan jelas daripada klaim yang tidak bisa dipertanggungjawabkan.

---

## 8. Urutan pengerjaan

| Urutan | Yang dikerjakan | Lama | Kapan |
|---|---|---|---|
| 1 | Ambil kunci API SAP | 15 menit | **Hari ini** |
| 2 | Sambungkan BMKG (gempa + cuaca) | 2 jam | Tahap 1 |
| 3 | Tulis `references/tkdn-rules.md` | 1 hari | Tahap 3 · orang domain |
| 4 | Tulis `references/lartas-procedure.md` | 1 hari | Tahap 3 · orang domain |
| 5 | Salin kalender libur | 1 jam | Tahap 3 |
| 6 | Cari sumber topan luar negeri | — | Kalau skenario Ningbo dipertahankan |
| 7 | Daftar layanan AIS | — | Opsional, Tahap 4 |

**Yang paling penting:** nomor 3 dan 4 dikerjakan **orang domain, bukan programmer**. Isinya
pengetahuan aturan, bukan kode. Ini yang paling sering salah dijadwalkan.

---

## 9. Aturan yang berlaku

1. **Yang ✅ boleh diklaim tegas** di proposal dan presentasi.
2. **Yang ⚠️ ditulis sebagai** *"dimasukkan sebagai dokumen aturan berversi"* — jujur, dan tetap
   bukan data karangan karena sumbernya nyata.
3. **Jangan pernah menaikkan** yang ⚠️ jadi klaim "ada API"-nya sebelum kalian sendiri
   membuktikan.
4. **Profil perusahaan selalu disebut** sebagai yang dimodelkan, dengan alasannya.
