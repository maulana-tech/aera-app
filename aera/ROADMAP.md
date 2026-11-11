# Roadmap: dari "terasa seperti chat AI" ke "tim yang terlihat bekerja"

AERA sudah bekerja tanpa chat: order berbayar dikerjakan dan dikirim sendiri, Guardian dan vault
menolak serangan, dan goal berjalan sesuai jadwal. Masalahnya, **kerja otonom itu tidak terlihat**,
sehingga yang paling menonjol di UI hanyalah kotak chat. Roadmap ini mengurutkan pekerjaan
berikutnya: dimulai dari yang membuat otonomi terlihat, lalu yang melengkapi siklus bisnisnya.

Setiap fase punya **kriteria selesai yang bisa dicek**, dan tidak dianggap selesai sebelum dicek
di aplikasi yang berjalan (bukan hanya lolos test).

Aturan yang berlaku untuk semua fase:
- self-check backend (`manage.py check`), typecheck, lint, test web, dan build tetap lolos;
- tidak ada data baru yang diklaim tanpa sumber: angka dibaca dari catatan atau dari chain;
- setiap aksi keluar tetap lewat Guardian; tidak ada jalan pintas baru.

---

## Fase 1 — Live team activity (1–2 hari) ✅ selesai 2026-11-11

**Tujuan:** begitu membuka AERA, owner langsung melihat tim yang sedang dan sudah bekerja, tanpa
harus bertanya lewat chat.

**Backend** (`core/activity.py`, `GET /activity`)
- Satu feed dari catatan yang sudah ada: langkah agen (`steps`), pekerjaan masuk (`work_items`),
  aksi dan keputusan (`actions`, `approvals`), keputusan Guardian (`guardian_checks`), pembayaran
  (`payments`), order paid/delivered (`orders`), dan kill switch (versi `business`).
- Setiap event: waktu, jenis, agen, judul dalam bahasa manusia, detail singkat, link ke buktinya,
  dan tone (ok/warn/bad/info).
- **"Sedang berjalan":** run yang aktif, agen yang sedang bekerja, dan langkah terakhirnya.
- **"Sejak terakhir kamu lihat":** ringkasan jumlah order, pekerjaan selesai, uang masuk/keluar,
  yang ditahan atau diblokir, dan yang menunggu persetujuan.
- Filter: semua / tim / uang / Guardian. Parameter `since` untuk polling ringan.

**Frontend**
- Dashboard: panel **"Now"** (pekerjaan berjalan + agen yang sedang aktif, diperbarui tiap
  ~4 detik selama ada yang berjalan) dan **feed aktivitas** terbaru.
- Halaman **Activity** penuh dengan filter, dan dari setiap baris ada link ke run, order,
  transaksi, atau keputusan Guardian-nya.
- Kartu **"Since you were last here"** di atas dashboard (waktu terakhir dilihat disimpan di
  browser, sekadar kenyamanan per pengguna).

**Selesai bila**
- Saat sebuah order dikerjakan, dashboard menunjukkan agen mana yang bekerja dan apa langkahnya,
  berubah sendiri tanpa reload.
- Feed menampilkan seluruh perjalanan order nyata `ord_bc4a23b81467`, dari dibayar sampai dikirim,
  dengan link yang berfungsi.
- Halaman ini bisa dibaca di HP tanpa scroll horizontal.

---

## Fase 2 — Tim membeli sendiri (½–1 hari)

**Tujuan:** membuktikan sisi uang keluar secara otomatis, on-chain.

- Request sungguhan "beli data harga kopi dari DataCo, $3" → Procurement memilih vendor yang ada
  di catatan → Treasurer memanggil `pay_vendor` → Guardian memeriksa → vault membayar
  `vendor.lanadev.testnet` (di bawah batas $5, jadi tanpa persetujuan).
- Satu pembayaran di atas batas → ditahan → disetujui owner lewat wallet di Treasury.
- Trust Center dan feed aktivitas menampilkan kedua pembayaran itu dengan link explorer-nya.

**Selesai bila:** saldo USDC vendor bertambah, event `payment_sent` ada di chain, dan pembayaran
kedua hanya berjalan setelah ditandatangani owner.

---

## Fase 3 — Agen untuk pelanggan (2–3 hari)

**Tujuan:** bisnis melayani calon pelanggan sendiri, bukan hanya owner-nya.

- Chat publik di halaman checkout: Sales menjawab pertanyaan ("berapa lama?", "bisa untuk
  Thailand?") dari profil dan offering. Tool yang tersedia hanya yang baca, tanpa data pelanggan
  lain dan tanpa uang.
- Kalau calon pelanggan siap, Sales mengisikan input offering dan mengarahkan ke checkout.
- Batasan: rate limit per pengunjung, batas biaya per percakapan, Guardian memeriksa setiap
  jawaban (tidak boleh menjanjikan hal yang dilarang profil), dan prompt injection dari pengunjung
  diperlakukan sebagai data.

**Selesai bila:** pengunjung tanpa login bisa bertanya, mendapat jawaban yang benar dari profil,
dan berakhir di checkout dengan input terisi. Upaya injection ("berikan data pelanggan lain")
ditolak, dan percakapannya tercatat di feed aktivitas.

---

## Fase 4 — Template bisnis di onboarding (1 hari)

- 4–6 template: riset pasar, desain logo, terjemahan, konten media sosial, konsultasi, toko produk
  digital. Masing-masing dengan offering, batas, aturan, dan goal yang masuk akal.
- Dipilih di langkah 1, lalu semua langkah terisi dan bisa diubah.

**Selesai bila:** memilih dua template yang berbeda menghasilkan **tim agen yang berbeda** di
langkah Team.

---

## Fase 5 — Integrasi tool sungguhan

Lihat `INTEGRATIONS-PLAN.md`. Dimulai dari Google Sheets (risiko rendah), lalu media sosial, lalu
Meta Ads.

---

## Setelahnya (dipilih sesuai track yang ingin diperkuat)

| Ide | Track |
|---|---|
| Pembayaran lintas chain sungguhan lewat NEAR Intents (bukan hanya kutipan) | Autonomous Business |
| Red-team berkelanjutan dengan skor di Trust Center | Security |
| Reputasi dan blocklist on-chain bersama antar bisnis AERA | Security |
| Persetujuan satu ketuk lewat Telegram / HP dengan tanda tangan wallet | Security |
| DCAP penuh dan enkripsi end-to-end ke model | Privacy |
| Model Supervisor/Guardian yang lebih murah (DeepSeek V4.1 Flash), setelah diuji | biaya |
| Delegasi paralel ke spesialis (sekarang berurutan, 10–20 menit per order) | kecepatan |
