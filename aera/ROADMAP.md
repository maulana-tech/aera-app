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

## Fase 2 — Tim membeli sendiri ✅ selesai 2026-11-12

**Tujuan:** membuktikan sisi uang keluar secara otomatis, on-chain.

- Request sungguhan "beli data harga kopi dari DataCo, $3" → Procurement memilih vendor yang ada
  di catatan → Treasurer memanggil `pay_vendor` → Guardian memeriksa → vault membayar
  `vendor.lanadev.testnet` (di bawah batas $5, jadi tanpa persetujuan).
- Satu pembayaran di atas batas → ditahan → disetujui owner lewat wallet di Treasury.
- Trust Center dan feed aktivitas menampilkan kedua pembayaran itu dengan link explorer-nya.

**Selesai bila:** saldo USDC vendor bertambah, event `payment_sent` ada di chain, dan pembayaran
kedua hanya berjalan setelah ditandatangani owner.

Status 2026-11-12:
- ✅ $3 di bawah batas: dibayar otomatis oleh vault (tx `E7B2f1UB…`).
- ✅ $8 di atas batas: Procurement → Guardian (`autonomous_cap`: warn) → Treasurer mengajukan → aksi
  `act_16e239c4eda1` **pending**; tidak ada uang bergerak.
- ✅ Owner menyetujui di Treasury → vault menahan request `payment:5c6db9a80152149b` (di atas batas
  kontrak $5) → owner `lanadev.testnet` menandatangani `approve` dari wallet (tx `31BQURup…`):
  event `payment_approved` + `ft_transfer` 8 USDC ke vendor. Saldo vault $12 → $4, vendor $3 → $11.
- Ditemukan saat verifikasi: pembayaran yang ditahan vault tercatat dengan tx `request_payment` agen
  (yang hanya memarkir), bukan tx approve yang memindahkan uang. Sekarang `fill_approval_txs` mencari
  tx approve (NearBlocks → dikonfirmasi event `payment_approved` di RPC); tx request disimpan sebagai
  `request_tx`.

---

## Fase 2b — Finance: buku keuangan yang dihitung kode ✅ selesai 2026-11-11

- `core/finance.py`: receipt PDF per order (hanya setelah dibayar, byte-nya selalu sama), laporan bulanan
  (pendapatan, refund, bagi hasil, vendor, biaya AI, bersih, margin), rekonsiliasi AERA ↔ vault.
- Agen **Finance** (capability `finance`: baca dan tulis dokumen, tidak bisa memindahkan uang), skill
  `monthly_close`, otomatis masuk tim bila bisnis punya offering.
- Receipt di halaman Orders dan di halaman status checkout pelanggan; bagian **Books** di Ledger.
- Terbukti pada data nyata: rekonsiliasi *balanced* (vault $12.00 = $15 − $3), November: bersih $11.42,
  margin 76.1%. Finance menolak menutup bulan yang belum selesai dan menandai pemasukan vault tanpa tx hash.
- Tx hash order vault kini dicari sendiri (NearBlocks mempersempit, RPC memastikan event `order_paid`
  untuk order itu) dan dicatat di receipt serta buku; order lama `ord_bc4a23b81467` sudah terisi.

## Fase 2c — Legal & Compliance dan Tech Lead (CTO) ✅ selesai 2026-11-12

- **Compliance** (`core/compliance.py`, capability `compliance`): `review_for_compliance` (setiap temuan
  mengutip kata yang melanggar), `legal_pages_status` (terms / privacy / refund: ada, draf, atau hilang),
  `privacy_register` (data pribadi yang disimpan, dihitung dari tabel), `save_compliance_register`.
  Masuk tim otomatis bila bisnis menyimpan materi klien; Quality Review juga menjalankan cek ini.
- **Tech Lead** (`core/systems.py`, capability `systems`): `systems_status` (model & attestation, fallback,
  tool yang gagal, run, server luar, vault, batas yang berlaku), `recent_incidents` (dengan alasan dan
  apakah sudah diselesaikan run berikutnya), `save_tech_review`. Tidak mengubah setting apa pun.
- Halaman Team: **Add from the role library** (ditulis ke profil, tetap ada saat recompose).
- Trust Center: *Personal data we hold*, *Policy pages*, *Systems health*.
- Terbukti live: Compliance mengisi register (20 record, 2 halaman hilang, 1 draf); Tech Lead membedakan
  kegagalan lama dari masalah terbuka dan menunjuk goal yang masih tertahan.

## Fase 3 — Agen untuk pelanggan (2–3 hari) ✅ selesai 2026-11-12

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

## Fase 4 — Template bisnis di onboarding (1 hari) ✅ selesai 2026-11-12

- 4–6 template: riset pasar, desain logo, terjemahan, konten media sosial, konsultasi, toko produk
  digital. Masing-masing dengan offering, batas, aturan, dan goal yang masuk akal.
- Dipilih di langkah 1, lalu semua langkah terisi dan bisa diubah.

**Selesai bila:** memilih dua template yang berbeda menghasilkan **tim agen yang berbeda** di
langkah Team.

---

## Fase 5 — Integrasi tool sungguhan (fondasi ✅ 2026-11-12; tinggal akun nyata)

Lihat `INTEGRATIONS-PLAN.md`. Dimulai dari Google Sheets (risiko rendah), lalu media sosial, lalu
Meta Ads.

---

## Fase 6 — Bisnis yang benar-benar otonom (dikerjakan 2026-11-12/13)

**Keandalan agen**
- Model yang menjawab tapi merangkak (lebih dari 60 dtk dengan kurang dari 10 token/dtk) menyerahkan sisa
  run ke fallback. Pada 12 Nov `glm-5.3-flash` menghabiskan 11 dari 20 menit tanpa pernah gagal.
- Run yang terhenti mencantumkan draf yang sudah ditulis; menjalankan ulang melanjutkan dari draf itu.
  Terbukti: goal sampel mingguan ke-2 dan ke-3 meneruskan brief, bukan menulis ulang.

**Akun demo hanya-lihat** — viewer ditolak di satu tempat (dispatcher) untuk semua POST kecuali login dan
halaman publik; banner di setiap halaman.

**Laporan otonomi dan unit economics** (`core/economics.py`, panel di Dashboard, tool Finance, skill
`autonomy_review`) — dihitung kode: % pekerjaan selesai tanpa orang, setiap kali orang turun tangan dan
untuk apa, margin per order, harga minimum per offering, overhead. Data nyata 30 hari: 55,6% tanpa orang,
order pertama margin 97,8% setelah AI, terkirim dalam 0,92 jam.

**Loop pertumbuhan** — Marketing menerbitkan sampel gratis ke `/samples` (`publish_sample`): diperiksa kode
dulu (compliance + aturan Guardian: tanpa kontak, tanpa janji), lalu tautan checkout membawa
`?src=sample:<slug>` sehingga order dari sampel terhitung (dibaca → checkout → dibayar).
- Live: brief sampel selesai (`fil_de99d74de386`); publikasinya terblokir oleh kill switch (lihat di bawah)
  dan oleh salah-deteksi tanggal sebagai nomor telepon (diperbaiki).

**Bisnis agen membeli dari bisnis agen** (`core/peers.py`) — tanpa ubah kontrak. Pembeli memesan di checkout
AERA penjual dengan vault-nya sebagai pembayar; penjual harus minta dibayar di akun payout yang tercatat;
pembayaran lewat jalur `pay_vendor` biasa dengan purpose `AERA order <id>`; penjual mengonfirmasi dari
catatan request di vault pengirim (memo transfer → `get_request`); hasil kerja kembali sebagai teks luar.
- Bisnis kedua (DataCo) berjalan lokal di :8788 dengan database dan tim sendiri, menerima di
  `vendor.lanadev.testnet`. Katalognya terbaca oleh Procurement Lumen.

**Tim mencari pelanggannya sendiri** (`core/prospects.py`, `tools/prospecting.py`, `clients/inbox.py`, halaman
`/leads`) — profil punya bagian *Finding customers* (pelanggan ideal, batas pesan dingin per hari, follow-up);
bila diisi, Composer menambah **Lead Researcher** dan Sales mendapat kemampuan `prospecting`.
- Lead hanya tersimpan bersama halaman publik yang menampilkan alamatnya (alamat tebakan ditolak kode).
- Pesan pertama ke setiap lead menunggu persetujuan orang; satu pesan menunggu per lead; follow-up hanya saat
  jatuh tempo dan sebatas jumlah di profil; batas pesan dingin per hari (maks 50); footer berhenti ditulis kode.
- Lead jadi `contacted` saat email benar-benar terkirim, `won` saat ada order dibayar dari alamatnya.
- Balasan masuk lewat IMAP (job tiap 2 menit), webhook bertanda tangan, atau ditempel manual: permintaan
  berhenti langsung opt-out tanpa model, auto-reply diabaikan, bounce menutup lead, balasan jadi work item
  `reply` yang hanya membawa id (kata-katanya dibaca `read_reply`, yang menandai run sebagai membaca teks luar).
- Funnel (ditemukan → dihubungi → membalas → menang) dan biaya AI per lead masuk laporan otonomi.
- Pencarian web: Brave atau Tavily dengan key (tier gratis); tanpa key DuckDuckGo hanya upaya terbaik
  (saat diuji, ia meminta pemeriksaan manusia, dan AERA melaporkannya apa adanya).
- ⏳ Uji live end-to-end: perlu key pencarian, SMTP + `AERA_EXTERNAL_REDIRECT` ke alamat sendiri, dan inbox.

**Temuan saat uji live, sudah diperbaiki**
- Guardian membekukan vault dan menyalakan kill switch karena pembelian yang sama saya jalankan ulang
  berkali-kali untuk tes ("repeated attempts"), dengan alasan yang memuat fakta usang (aksi $8 "masih
  pending"). Rem itu bekerja; penyebabnya diperbaiki: `search_past_work` kini menyertakan status aksi
  saat ini, work item mencatat siapa yang menjalankannya ulang, dan prompt Guardian membedakan itu dari serangan.
- Guardian pernah mengaku memanggil `freeze_payments` tanpa memanggilnya; kini ditandai di catatan.
- Riwayat pembayaran ke counterparty kini dinyatakan oleh kode, bukan disimpulkan model.
- ⏳ Owner membuka beku vault (`unfreeze`, tanda tangan wallet) dan mematikan kill switch; lalu publikasi
  sampel dan pembelian DataCo dijalankan sekali lagi.

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
