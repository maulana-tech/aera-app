# SIGAP — Demo Storyboard

> Target durasi **6–7 menit**. Skenario: **PT Karya Presisi Nusantara**, material
> **M-4471**, **Topan menutup Port of Ningbo 6 hari**. Track: **Supply Chain**.
>
> Satu kalimat pembuka yang dihafal:
> *"SIGAP mengubah gangguan pasokan dari investigasi manual berhari-hari jadi satu
> rekomendasi siap-tanda-tangan dalam hitungan menit — tanpa membiarkan AI
> mengarang angka atau melanggar aturan."*

---

## Pre-flight (sebelum naik panggung)

Centang semua ini **sebelum** presentasi, bukan saat presentasi:

- [ ] `cd sigap/agent && PYTHONPATH=. python3 manage.py check` → **56 modul ok, 0 gagal**, 12 agen, 46/46 tool, 12/12 prompt. Kalau ada yang `FAILED`, benahi dulu; ini 40 detik yang menyelamatkan panggung.
- [ ] `AWS_REGION` (atau AI Core) **sudah diset** → penalaran menyala. Tanpa ini run mendarat `held`.
      **Satu akun AWS sudah cukup** — `AWS_FALLBACK_*` opsional, hanya dipakai saat akun utama menjawab 429.
      Cek dengan panggilan sungguhan, bukan sekadar baca env (butuh venv, SDK Bedrock ada di sana):
      ```bash
      cd sigap/agent && PYTHONPATH=. .venv/bin/python manage.py models --ping
      ```
      Harus: **12 agen `ready`**, lalu satu panggilan nyata per model dengan waktunya. Kalau ada
      agen yang tidak `ready`, barisnya menyebut sebabnya; jangan naik panggung sebelum bersih.
- [ ] Agent service jalan: `python3 api.py` (`:8787`). Web: `npm run dev` (`:3000`).
- [ ] User demo ada: `buyer` (limit Rp 500 jt). Sudah login di browser.
- [ ] **Data Ningbo di-upload sebagai "Our own master data" (cached)** — `MaterialStock` + `AlternateSource` (opsi A–E). *Kalau pakai fixtures (modelled), kalkulator menolak keluarkan angka.*
- [ ] **Pilih satu cerita: Ningbo ATAU SAP live. Jangan dua-duanya.**
      Begitu `SAP_API_KEY` terisi, `AlternateSource` dibaca dari tenant — dan opsi A–E tidak ada di sana.
      Upload hanya **mengisi field yang kosong** pada baris yang cocok; ia tidak menambah baris.
      Jadi dengan SAP hidup, Scene 3 tak punya opsi untuk dinilai Kira. Untuk demo Ningbo: kosongkan
      `SAP_API_KEY` dan pakai upload (origin `cached`, kalkulator percaya). Stok dan PO live tetap bisa
      ditunjukkan terpisah di `/data/impact` sebagai bukti integrasi.
- [ ] **Rule pack terpasang** (`sigap/references/rule-pack.json`) → veto TKDN hidup, di dua pintu
      (opsi sumber alternatif **dan** supplier pada PO).
- [ ] Satu run Ningbo **sudah pernah dijalankan** sebagai cadangan (biar tak bergantung jaringan live di panggung).
- [ ] Tab browser sudah dibuka di urutan: `/` · `/disruptions/[id]` · `/log/[id]` · `/reports/[id]`.

**Angka yang akan muncul (hafal, biar lancar):** TKDN sekarang **38.2%**, lantai kontrak **40%**.

| Opsi | Biaya | TKDN jadi | Vonis |
|---|---|---|---|
| C — transfer stok SBY1 | Rp 22 jt | — | ✅ lolos |
| **E — termurah, China** | **Rp 48 jt** | **34.8%** | 🔴 **DIBLOK (TKDN)** |
| D — impor baru Vietnam | Rp 61 jt | 36.1% | 🔴 diblok (TKDN + LARTAS +10 hari → tiba 9 Okt) |
| B — lokal Gresik | Rp 94 jt | 41.6% | ✅ lolos |
| A — air freight incumbent | Rp 186 jt | 38.2% | ✅ lolos |

**Pintu kedua, baru:** veto yang sama kini juga berlaku pada **supplier** saat PO diterbitkan, bukan
cuma pada opsi sumber. Dari 18 supplier di daftar: **6 domestik lolos, 12 asing diblok** — semuanya
karena perusahaan sudah di 38.2% terhadap lantai 40%, jadi order asing tak mungkin memperbaiki posisi
sementara aturannya "tidak boleh memperburuk". SUP-4417 (Gresik, sertifikat TKDN 41.6%, berlaku sampai
31 Des 2026) adalah yang lolos.

---

## Scene 1 — Masalahnya (±45 dtk)

- **Layar:** `/dashboard` (eksposur, order berisiko).
- **Lakukan:** diam di dashboard sebentar.
- **Ucapkan:** *"Budi manajer supply chain. Topan menutup Ningbo. Biasanya ini 2–3 hari kerja di email dan spreadsheet: order mana yang kena, stok mana yang kepakai, siapa bisa pasok, apakah melanggar TKDN, berapa biayanya. Dan jawabannya sudah basi hari Selasa karena datanya bergerak."*

## Scene 2 — Trigger & swarm bergerak sendiri (±60 dtk)

- **Layar:** terminal → lalu `/` (Decision Queue).
- **Lakukan:** kirim event (atau tunjuk watcher di `/schedule`):
  ```bash
  curl -X POST http://127.0.0.1:8787/events -H "Authorization: Bearer <token>" \
    -H 'content-type: application/json' \
    -d '{"kind":"port_closure","title":"Typhoon closes Ningbo",
         "trigger":"Ningbo-Zhoushan closed 8-13 Sep 2026","payload":{"port":"CNNGB","days":6}}'
  ```
  Buka `/` → gangguan baru muncul di antrean.
- **Ucapkan:** *"Tidak ada yang login untuk memulai ini. Sistemnya event-driven — watcher BMKG, GDACS, cuaca menaikkan event sendiri; ini saya picu manual biar terkontrol. Begitu event masuk, tim 12 agen langsung jalan."*
- **Tunjuk vonis di tiap kartu antrean** (dihitung, bukan dinilai model — `engine/triage.py`):
  *"Tiap penanganan bawa satu vonis: **Approve now** kalau keputusan menunggu dan stoknya habis dalam 7 hari, **Approve** kalau menunggu tapi belum mendesak, **Needs data** kalau sistem menolak memutuskan karena datanya kurang — bukan karena ragu, **Record what happened** kalau aksinya sudah jalan tapi hasilnya belum dicatat. Antrean ini cuma bilang 'clear' kalau benar-benar tak ada yang menunggu, tertahan, gagal, atau berutang hasil."*
- **Opsional, kalau ada waktu:** `/schedule` → delapan job. Tunjuk `certificates`:
  *"Yang ini tak ada feed-nya. Sertifikat TKDN yang mau habis ada di arsip perusahaan sendiri, dan kalau lewat, konten lokal di belakangnya ikut hilang. Jadi SIGAP mengawasi kertasnya juga, 60 hari sebelum jatuh tempo."*

## Scene 3 — Jantungnya: Kira mencoret yang termurah (±2 mnt) ⭐

- **Layar:** `/disruptions/[id]`.
- **Lakukan:** tunjuk rekomendasi, lalu **exploration graph** (pan/zoom, klik node opsi E yang merah).
- **Ucapkan:**
  - *"Halaman ini auto-refresh tiap 4 detik — kita lihat swarm bernalar: dampak dulu, lalu sourcing, lalu aturan."*
  - **(Beat utama)** *"Ini intinya. Opsi termurah — sumber China Rp 48 juta — **ditolak**. Bukan karena mahal, tapi karena TKDN jatuh ke 34.8%, di bawah lantai kontrak 40%. Ini veto kepatuhan, dan **tidak bisa dibatalkan oleh alasan harga**."*
  - *"Vietnam lebih murah dari lokal, tapi juga diblok: TKDN turun, DAN barangnya kena LARTAS — izin impor asal baru menambah 10 hari kerja, tiba mundur ke 9 Oktober."*
  - *"Yang menang justru transfer stok internal plus supplier lokal Gresik — lebih mahal, tapi patuh dan tepat waktu. Inilah tesis kami: opsi termurah sering terlarang."*
  - **(Beat kedua — pintu yang dulu terbuka)** *"Dan vetonya tidak cuma di tahap memilih opsi. Dulu jalur pengadaan bisa sampai ke draft PO tanpa pernah dinilai sama sekali — harga lewat pintu belakang. Sekarang supplier-nya sendiri dinilai saat PO diterbitkan: dari 18 supplier, 12 diblok, dan PO ke supplier yang diblok ditolak, bukan cuma diberi peringatan."*

## Scene 4 — Angka yang bisa dipertanggungjawabkan (±60 dtk)

- **Layar:** masih `/disruptions/[id]`, bagian biaya + badge origin.
- **Ucapkan:**
  - *"Angka rupiah ini dari kalkulator Python murni — tidak ada model di dalamnya. Kalau satu input tidak tepercaya, kalkulatornya menolak keluarkan angka, bukan menebak."*
  - *"Tiap fakta bawa label asalnya: live, cached, derived, modelled, missing. Gagal fetch jadi 'missing', bukan tebakan yang kelihatan meyakinkan."*
  - *"Dan sistem menghitung **harga kepatuhan**: selisih antara pilihan patuh dan yang lebih murah tapi diblok. Jadi veto bukan sekadar klaim — ada harganya di catatan."*

## Scene 5 — Keputusan tetap di tangan manusia (±60 dtk)

- **Layar:** aksi `pending` → klik **Approve**.
- **Lakukan:** approve sebagai buyer; tunjuk status `pending → approved → sent`.
- **Ucapkan:**
  - *"Model mengusulkan; tidak pernah memutuskan, tidak pernah membelanjakan. Approval dicek di server sesuai limit peran — buyer sampai Rp 500 juta. Approve dua kali tak mengirim dua kali."*
  - *"Begitu disetujui, aksi ditulis ke SAP dengan idempotency key, dan alert terkirim. Semuanya mendarat di log keputusan."*

## Scene 6 — Bukti & penutup (±45 dtk)

- **Layar:** `/log/[id]` (jejak tiap tool + origin), lalu `/reports/[id]` (ekspor PDF/XLSX).
- **Ucapkan:**
  - *"Setiap langkah bisa diaudit: tiap tool call dengan label asalnya. Kalau direktur tanya 'dari mana angka ini', jawabannya satu klik."*
  - *"Dan jadi laporan — PDF atau Excel — dikirim email langsung dari halaman. Dari topan sampai keputusan ter-eksekusi dan terdokumentasi: menit, bukan hari."*
- **Tutup loop-nya** (kalau ada 20 detik lagi): di kartu aksi yang sudah `sent`, catat hasil nyatanya —
  pilih `delivered` + biaya aktual.
  - *"Ini bagian yang biasanya hilang. Prediksi tanpa hasil cuma pendapat. Begitu hasil nyatanya dicatat, laporan menampilkan **prediksi vs realisasi beserta selisihnya** — dan insiden ini jadi preseden yang dibaca Otto pada kejadian berikutnya. Kalau biaya aktualnya tidak diisi, laporannya menulis '—', bukan menebak angka."*

---

## Jaring pengaman (kalau model/jaringan ngadat di panggung)

Bagian ini **tak butuh model** dan tetap kuat:

> `SAP_API_KEY=` di depan tiap perintah itu **bukan hiasan**: opsi A–E ada di fixture/upload, bukan di
> tenant SAP. Tanpa itu, perintah di bawah menjawab `unknown option 'E'`.

- **Veto Kira deterministik, pintu pertama** — opsi termurah dicoret:
  ```bash
  cd sigap/agent && SAP_API_KEY= SIGAP_RULE_PACK=../references/rule-pack.json PYTHONPATH=. \
    python3 -c "from tools import compliance as k; \
    print(k.check_local_constraints('E').value['reason'])"
  ```
  → `TKDN falls from 38.2% to 34.8%, further below the 40.0% contract floor`
- **Pintu kedua — supplier pada PO:**
  ```bash
  cd sigap/agent && SAP_API_KEY= SIGAP_RULE_PACK=../references/rule-pack.json PYTHONPATH=. \
    python3 -c "from tools import compliance as k; \
    [print(s, k.check_supplier_constraints(s).value['allowed']) for s in ('SUP-5501','SUP-4417')]"
  ```
  → `SUP-5501 False` (China) · `SUP-4417 True` (Gresik, sertifikat 41.6%)
- **Kejujuran rule pack, bukan klaim** — tunjukkan sistem mengaku apa yang belum diverifikasi:
  ```bash
  cd sigap/agent && SAP_API_KEY= SIGAP_RULE_PACK=../references/rule-pack.json PYTHONPATH=. \
    python3 -c "from tools import compliance as k; print(k.pack_status())"
  ```
  → `total: 4, verified: 0`, keempatnya dinamai. Salah tulis nama aturan ikut tertangkap di sini,
  dulu jatuh diam-diam ke profil perusahaan.
- **Kalkulator menolak** — tunjukkan input `modelled` → *"No savings figure until that data is live."*
- **Seluruh sistem menguji dirinya** — `PYTHONPATH=. python3 manage.py check` → 56 modul, 0 gagal.
  Kalau juri skeptis soal "ini jalan atau cuma demo", ini jawabannya di depan mata.
- `SAP_API_KEY= python3 main.py` — skenario terskrip, tanpa model, kalkulator asli. Mendarat `held`,
  dan itu memang benar: tanpa penalaran sistem menahan diri, tidak mengarang keputusan.
- Gunakan **run cadangan** yang sudah jadi (dari pre-flight) alih-alih memicu live.

---

## Siap-siap pertanyaan juri

- **"Ini halusinasi nggak?"** → *"Tidak bisa. Angka dari kalkulator non-AI; tiap fakta berlabel asal; gagal = missing, bukan tebakan."*
- **"Kalau AI-nya salah?"** → *"Dia hanya mengusulkan. Eksekusi ke SAP selalu lewat approval manusia dengan limit server-side; hanya transfer stok kecil & aman yang boleh otonom."*
- **"Aturannya dari mana?"** → *"Dari rule pack yang ditulis & ditandatangani perusahaan — tiap aturan bawa sumber & status verifikasi. Yang belum diverifikasi dilabeli modelled, dan catatan vonisnya **menyebutkan nama aturan yang belum terverifikasi itu**, bukan menyembunyikannya. Nama aturan yang salah tulis juga ditangkap dan dilaporkan — dulu jatuh diam-diam ke profil perusahaan, jadi vonisnya terbaca seolah pack-nya memang diam."* *(Catatan: di demo ini keempat aturan masih `verified:false` — ilustratif; di produksi diisi angka kontrak asli.)*
- **"Sistemnya belajar dari hasil?"** → *"Ia mencatat dan menampilkan, tidak mengubah cara menilai. Hasil nyata tiap aksi dicatat sekali — biaya aktual, terkirim atau terlambat — lalu laporan menampilkan prediksi vs realisasi beserta selisihnya, dan insiden itu jadi preseden yang dicari pada kejadian berikutnya. Kami sengaja tidak membiarkan hasil masa lalu menggeser skor otomatis: itu jalur yang paling mudah salah dan paling sulit diaudit."*
- **"Bedanya dengan dashboard supply chain lain?"** → *"Yang lain menampilkan data; SIGAP mengambil keputusan berpagar — menyelidiki, menyaring yang melanggar aturan, menghitung, dan mengeksekusi setelah persetujuan."*
- **"Kenapa supply chain, bukan manufacturing?"** → *"Fokusnya pasokan ke pabrik: sourcing, supplier, logistik, bea cukai, kepatuhan impor — bukan optimasi lini produksi."*

---

## Checklist 30 detik terakhir sebelum mulai

- [ ] Browser zoom cukup besar untuk proyektor.
- [ ] Terminal font besar; perintah `curl` sudah tersiap di clipboard.
- [ ] Notifikasi OS/Slack dimatikan.
- [ ] Run cadangan URL-nya sudah di tab.
- [ ] Tarik napas. Buka dengan kalimat pembuka di atas.
