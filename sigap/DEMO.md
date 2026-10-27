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

- [ ] `AWS_REGION` (atau AI Core) **sudah diset** → penalaran menyala. Tanpa ini run mendarat `held`.
- [ ] Agent service jalan: `python3 api.py` (`:8787`). Web: `npm run dev` (`:3000`).
- [ ] User demo ada: `buyer` (limit Rp 500 jt). Sudah login di browser.
- [ ] **Data Ningbo di-upload sebagai "Our own master data" (cached)** — `MaterialStock` + `AlternateSource` (opsi A–E). *Kalau pakai fixtures (modelled), kalkulator menolak keluarkan angka.*
- [ ] **Rule pack terpasang** (`sigap/references/rule-pack.json`) → veto TKDN hidup.
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

## Scene 3 — Jantungnya: Kira mencoret yang termurah (±2 mnt) ⭐

- **Layar:** `/disruptions/[id]`.
- **Lakukan:** tunjuk rekomendasi, lalu **exploration graph** (pan/zoom, klik node opsi E yang merah).
- **Ucapkan:**
  - *"Halaman ini auto-refresh tiap 4 detik — kita lihat swarm bernalar: dampak dulu, lalu sourcing, lalu aturan."*
  - **(Beat utama)** *"Ini intinya. Opsi termurah — sumber China Rp 48 juta — **ditolak**. Bukan karena mahal, tapi karena TKDN jatuh ke 34.8%, di bawah lantai kontrak 40%. Ini veto kepatuhan, dan **tidak bisa dibatalkan oleh alasan harga**."*
  - *"Vietnam lebih murah dari lokal, tapi juga diblok: TKDN turun, DAN barangnya kena LARTAS — izin impor asal baru menambah 10 hari kerja, tiba mundur ke 9 Oktober."*
  - *"Yang menang justru transfer stok internal plus supplier lokal Gresik — lebih mahal, tapi patuh dan tepat waktu. Inilah tesis kami: opsi termurah sering terlarang."*

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

---

## Jaring pengaman (kalau model/jaringan ngadat di panggung)

Bagian ini **tak butuh model** dan tetap kuat:

- **Veto Kira deterministik** — jalankan dari terminal, tampilkan opsi termurah dicoret:
  ```bash
  cd sigap/agent && SIGAP_RULE_PACK=../references/rule-pack.json PYTHONPATH=. \
    python3 -c "from tools import compliance as k; \
    print(k.check_local_constraints('E').value['reason'])"
  ```
- **Kalkulator menolak** — tunjukkan input `modelled` → *"No savings figure until that data is live."*
- `python3 main.py` — jalan skenario terskrip, tanpa model, kalkulator asli.
- Gunakan **run cadangan** yang sudah jadi (dari pre-flight) alih-alih memicu live.

---

## Siap-siap pertanyaan juri

- **"Ini halusinasi nggak?"** → *"Tidak bisa. Angka dari kalkulator non-AI; tiap fakta berlabel asal; gagal = missing, bukan tebakan."*
- **"Kalau AI-nya salah?"** → *"Dia hanya mengusulkan. Eksekusi ke SAP selalu lewat approval manusia dengan limit server-side; hanya transfer stok kecil & aman yang boleh otonom."*
- **"Aturannya dari mana?"** → *"Dari rule pack yang ditulis & ditandatangani perusahaan — tiap aturan bawa sumber & status verifikasi. Yang belum diverifikasi dilabeli modelled, jujur."* *(Catatan: di demo ini rule pack masih `verified:false` — ilustratif; di produksi diisi angka kontrak asli.)*
- **"Bedanya dengan dashboard supply chain lain?"** → *"Yang lain menampilkan data; SIGAP mengambil keputusan berpagar — menyelidiki, menyaring yang melanggar aturan, menghitung, dan mengeksekusi setelah persetujuan."*
- **"Kenapa supply chain, bukan manufacturing?"** → *"Fokusnya pasokan ke pabrik: sourcing, supplier, logistik, bea cukai, kepatuhan impor — bukan optimasi lini produksi."*

---

## Checklist 30 detik terakhir sebelum mulai

- [ ] Browser zoom cukup besar untuk proyektor.
- [ ] Terminal font besar; perintah `curl` sudah tersiap di clipboard.
- [ ] Notifikasi OS/Slack dimatikan.
- [ ] Run cadangan URL-nya sudah di tab.
- [ ] Tarik napas. Buka dengan kalimat pembuka di atas.
