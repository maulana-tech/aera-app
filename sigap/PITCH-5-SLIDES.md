# SIGAP — Outline PPT, 5 halaman isi

> **Deck jadinya ada di `deck/`** — 27 halaman, dibangun dengan [open-slide](https://github.com/open-slide/open-slide),
> lengkap dengan speaker notes per halaman. File siap pakai di `deck/export/`:
> `sigap-hackathon.pptx` (teks native, bisa diedit di PowerPoint), `sigap-hackathon-image.pptx`
> (tiap halaman satu gambar — pakai ini kalau font di laptop panggung tidak sama), dan
> `sigap-hackathon.pdf`. Ubah isinya di `deck/slides/sigap-hackathon/index.tsx`, lalu
> `cd deck && npm run dev`.
>
> Dokumen ini tetap berguna sebagai **argumennya**: urutan, takeaway tiap halaman, dan
> catatan apa yang tidak boleh ditaruh di slide.


Cover, demo, dan closing **tidak** dihitung di sini. Urutan lengkap saat tampil:

```
[Cover]  →  1 Masalah  →  2 Solusi  →  3 Arsitektur  →  [DEMO LIVE]  →  4 Kenapa bisa dipercaya  →  5 Dampak & roadmap  →  [Closing]
```

Demo diletakkan **setelah halaman 3**: juri sudah tahu apa dan bagaimana, jadi demo
menjadi bukti — bukan perkenalan. Halaman 4 lalu menjelaskan apa yang baru saja mereka
lihat dan kenapa itu sulit, yang jauh lebih kuat dibanding menjanjikannya lebih dulu.

**Total waktu halaman isi: ±4 menit 30 detik.** Satu halaman = satu gagasan. Kalimat di
slide pendek; yang panjang masuk ke "Ucapkan", bukan ke slide.

> Teks slide di bawah ditulis dalam bahasa Indonesia dengan istilah teknis dibiarkan apa
> adanya (TKDN, LARTAS, provenance). Bilang kalau mau versi Inggris.

---

## Halaman 1 — Masalahnya bukan kecepatan saja

**Takeaway (tulis besar di slide):**
> Saat pasokan terputus, keputusan tercepat sering yang paling tidak boleh diambil.

**Isi slide (4 butir, maksimal 8 kata per butir):**
- Topan menutup satu pelabuhan → puluhan material berhenti
- Planner punya jam, bukan hari, untuk memutuskan
- Opsi termurah sering **melanggar TKDN atau tertahan LARTAS**
- Setelahnya: tak ada catatan siapa memutuskan apa, atas dasar apa

**Visual:** satu timeline horizontal — *sinyal → 3 hari menelusuri Excel & WhatsApp →
keputusan → tak ada jejak*. Tanpa ikon berlebihan.

**Ucapkan (±50 detik):**
"Ini bukan masalah ERP yang kurang. Datanya sudah ada di S/4HANA. Yang hilang adalah
**jam-jam di antara sinyal dan keputusan** — dan satu dimensi yang khas Indonesia:
opsi termurah biasanya impor, dan impor menggerus TKDN serta kena LARTAS. Jadi
mempercepat keputusan saja justru berbahaya: yang dipercepat bisa keputusan yang
melanggar kontrak."

**Jangan taruh di slide:** daftar fitur, nama agen, logo teknologi. Belum waktunya.

**Yang perlu kamu isi sendiri:** satu angka nyata milik APP Group atau industri tekstil
Indonesia — misal biaya *downtime* per hari, atau denda keterlambatan kontrak. Satu
angka bersumber jauh lebih kuat dari tiga angka tanpa sumber. *Jangan pakai angka yang
tidak bisa kamu sebutkan sumbernya* — itu persis hal yang produk ini ada untuk menolak.

---

## Halaman 2 — SIGAP: dua belas agen, satu keputusan yang bisa disetujui

**Takeaway:**
> Dari sinyal publik sampai dokumen SAP, otonom — tapi berhenti di tempat yang benar.

**Isi slide — enam langkah, satu baris masing-masing:**
1. **Menangkap** — BMKG, GDACS, NASA EONET, USGS, Open-Meteo (tanpa diminta)
2. **Menelusuri** — 12 agen membaca S/4HANA, master data, feed
3. **Menyaring** — Kira ⚖️ mencoret opsi yang melanggar TKDN/LARTAS
4. **Menghitung** — Tara: biaya, tanggal habis stok, OTIF, dampak TKDN
5. **Mengeksekusi** — stock transfer / draft PO ke SAP, dalam batas wewenang
6. **Menutup** — hasil nyata dicatat; insiden berikutnya bisa mencarinya

**Visual:** diagram agen dari `ARCHITECTURE.md` §4 — Arya di tengah, Kira diberi warna
merah dengan label **veto**. Itu satu-satunya gambar di halaman ini.

**Ucapkan (±60 detik):**
"Dua belas agen, masing-masing punya pekerjaan: dampak, permintaan, inventaris,
sourcing, pengadaan, logistik, aturan, simulasi, preseden, eksekusi, eksposur, dan satu
supervisor. Yang membedakannya bukan jumlahnya — tapi **satu agen punya hak veto, dan
veto itu tidak bisa dibatalkan dengan alasan biaya.** Sistem boleh bertindak sendiri di
bawah Rp 50 juta; di atas itu ia berhenti dan menunggu orang."

**Jangan taruh di slide:** 45 nama tool. Sebut angkanya saja kalau ditanya.

---

## Halaman 3 — Arsitektur & tech stack

**Takeaway:**
> AWS untuk otaknya, SAP untuk datanya dan pintunya — dan jaminannya ada di kode, bukan di prompt.

**Isi slide — kolom kiri/kanan:**

| **AWS** | **SAP** |
|---|---|
| Amazon Bedrock (Mantle) — Claude untuk pengambil keputusan; MiniMax / DeepSeek / Kimi untuk spesialis | SAP S/4HANA Cloud — stok, BOM, PO, order, supplier |
| AgentCore Gateway — tool kami diekspos sebagai **MCP** | SAP AI Core — `gpt-5.4`, dan **`sap-rpt-1.6`** untuk prediksi tabular |
| | SAP Joule — lewat **A2A**, tiga skill read-only |
| | SAP BTP Cloud Foundry — `cf push` |

Satu baris di bawah tabel, dicetak tebal:
> **Agent service: Python 3, standard library saja.** `http.server` + `sqlite3`. xlsx dan
> PDF ditulis sendiri. Satu paket saja terpasang, dan hanya kalau Bedrock dipakai.

**Visual:** [`architecture/sigap-aws-architecture.png`](architecture/sigap-aws-architecture.png)
(2960×1960, atau SVG-nya langsung — PowerPoint menerima SVG dan tetap tajam saat
di-zoom). Taruh **full-bleed** memenuhi slide, tabel AWS|SAP di atas pindah ke slide
cadangan kalau sempit.

Kalau proyektornya kecil dan teks 10px tak terbaca dari belakang: potong saja bagian
**AWS Cloud** (kotak EC2 + Bedrock) dan tampilkan itu diperbesar — sisanya kamu ceritakan.
Jangan mengecilkan diagram utuh sampai tak terbaca; itu lebih buruk daripada tidak ada
diagram.

**Ucapkan (±60 detik):**
"Dua provider model dengan sengaja: pengambil keputusan jalan di model terkuat, sepuluh
spesialis boleh jalan di model murah — dan **tidak satu pun jaminan melemah**, karena
veto Kira, angka Tara, dan setiap label provenance itu Python, bukan instruksi ke model.
Agent service-nya tanpa dependensi sama sekali: bisa dibaca ujung ke ujung, dan jalan di
mesin apa pun yang punya Python."

**Jangan taruh di slide:** nama berkas, versi paket, cuplikan kode.

---

## Halaman 4 — Kenapa angkanya bisa dipercaya *(halaman terpenting)*

Tampilkan **setelah demo**, saat juri baru melihat Kira mencoret opsi termurah.

**Takeaway:**
> Agen lain menjawab dengan percaya diri. Yang ini menolak menjawab kalau datanya tak layak.

**Isi slide — lima butir, masing-masing satu klaim yang bisa dibuktikan:**
- **Setiap angka punya asal:** `live · cached · derived · modelled · missing`
- **Kalkulatornya tanpa model** — dan **menolak** keluarkan rupiah dari data tak terpercaya
- **Veto itu kode**, dan diperiksa ulang: daftar dari model hanya boleh *mempersempit* aturan
- **Batas wewenang di server**, identitas tak pernah dikirim dari browser
- **Kepatuhan punya harga di catatan:** *"patuh itu memakan Rp 46 juta — dan ini aturan yang memakannya"*

**Visual:** screenshot **nyata** dari halaman laporan — bagian *What the rules cost*.
Angka yang keluar dari `engine/simulate.py` pada skenario Ningbo (sudah diverifikasi,
jangan diubah-ubah):

| | Rencana | Biaya |
|---|---|---|
| Dipilih | **C+B** (transfer internal + Gresik) | **Rp 116.000.000** · TKDN 41,6% |
| Lebih murah, dicoret | **C+E** (transfer internal + China) | **Rp 70.000.000** |
| **Harga aturannya** | | **Rp 46.000.000** |

Alasan yang tercetak di bawahnya: *"E — TKDN drops to 34.8%, contract floor 40%"*.
Tambah satu badge `modelled` yang terlihat, supaya juri lihat sistemnya memang mengaku.

**Ucapkan (±70 detik):**
"Opsi termurah tadi dicoret. Pertanyaan yang biasanya tak terjawab: **berapa harga
kepatuhan itu?** SIGAP menghitungnya dengan aritmetika yang sama atas semua opsi,
termasuk yang dicoret, lalu menaruhnya di laporan. Tanpa itu, veto cuma klaim. Dengan
itu, veto punya harga yang bisa dipertanggungjawabkan ke direksi.

Dan perhatikan label `modelled` ini. Rule pack demo kami **belum terverifikasi**, dan
sistemnya mengatakannya sendiri — di halaman, di PDF, di email. Yang kami bangun bukan
agen yang selalu menjawab. Yang kami bangun adalah agen yang bisa **dipercaya saat ia
menjawab**, karena ia menolak saat tidak layak."

**Jangan taruh di slide:** kata "AI-powered", "cutting-edge", "revolutionary". Halaman ini
menang karena spesifik.

---

## Halaman 5 — Dampak, keadaan jujur, dan jalan ke produksi

**Takeaway:**
> Sudah jalan hari ini, dan kami tahu persis apa yang belum.

**Isi slide — tiga kolom:**

**Sudah jalan**
- 12 agen · 46 tool · 56 modul ber-self-check
- Loop penuh: sinyal → keputusan → aksi SAP → hasil nyata
- Laporan deterministik + PDF/Excel, periode WIB
- Lima watcher otonom — termasuk sertifikat TKDN yang mau habis, yang **tak ada feed-nya**
- MCP untuk AgentCore, A2A untuk Joule

**Dampak**
- Penelusuran hitungan hari → **menit**
- Skenario Ningbo: **Rp 116 jt** vs **Rp 186 jt** refleks *air freight* → hemat **38%**
- Veto di **dua pintu**: saat opsi dipilih, dan saat PO diterbitkan — PO ke supplier terblokir **ditolak**
- Jejak audit per keputusan: siapa, kapan, atas bukti apa
- Harga kepatuhan jadi angka, bukan perasaan

**Belum, dan kami katakan**
- Rule pack masih `verified:false` → tiap ruling dilabeli `modelled`
- SQLite di Cloud Foundry **hilang saat restart** → Postgres dulu
- Jalur tulis SAP belum diuji di tenant pelanggan
- Hasil nyata **dicatat & ditampilkan**, belum mempengaruhi ranking — itu urutan terakhir, sengaja

**Visual:** tiga kolom teks saja. Jangan grafik; tidak ada data tren yang jujur untuk
digambar, dan grafik palsu di halaman tentang kejujuran akan menghancurkan halaman 4.

**Soal angka di kolom Dampak:** `Rp 116 jt vs Rp 186 jt (38%)` dan `Rp 46 juta` keluar dari
`engine/simulate.py` pada fixture Ningbo — jalankan `PYTHONPATH=. python3
engine/simulate.py` kalau juri menanyakannya, outputnya mencetak keduanya. Tapi
fixture-nya data skenario, jadi sebut *"pada skenario ini"*, jangan *"rata-rata
penghematan kami"*. Keduanya angka mekanisme, bukan angka pasar.

**Ucapkan (±50 detik):**
"Roadmap-nya berurutan, bukan daftar keinginan: Postgres, lalu rule pack yang
diverifikasi orang bersama tim pengadaan, lalu jalur tulis SAP diuji di tenant
sungguhan. Baru setelah ketiganya — barulah hasil nyata boleh mempengaruhi ranking.
Kami menaruhnya terakhir dengan sengaja: membiarkan sistem belajar dari catatan yang
belum rapi adalah cara tercepat membuatnya salah dengan percaya diri."

---

## Catatan membuat decknya

**Yang paling kuat, urut:** harga kepatuhan (hal. 4) → veto yang ada di kode (hal. 2 & 4)
→ provenance (hal. 4) → nol dependensi (hal. 3). Kalau waktu dipotong di tempat,
**pertahankan halaman 4.**

**Kalau juri cuma kasih 5 menit:** gabung halaman 1 dan 2 jadi satu, buang halaman 3
(tetap siapkan diagramnya sebagai slide cadangan di belakang closing untuk sesi tanya
jawab), lalu demo → halaman 4 → halaman 5.

**Siapkan sebagai slide cadangan (setelah closing, tidak ditampilkan):**
1. Diagram arsitektur utuh (`ARCHITECTURE.md` §1)
2. Sequence satu disrupsi (`ARCHITECTURE.md` §3)
3. Tabel tujuh scheduled job
4. Tabel keputusan arsitektur — apa yang dibeli, apa biayanya (`ARCHITECTURE.md` §10)
5. Screenshot halaman `/log` (trace) — untuk pertanyaan "bagaimana kami tahu agennya
   benar-benar melakukan itu"

**Lima pertanyaan juri yang paling mungkin,** jawaban lengkapnya ada di
[`DEMO.md`](DEMO.md) bagian Q&A. Tiga yang paling sering:
- *"Kalau modelnya halusinasi angka?"* → angkanya tidak dari model; `engine/simulate.py`
  tanpa model, dan menolak input tak terpercaya.
- *"Kenapa 12 agen, bukan satu prompt besar?"* → karena satu di antaranya harus bisa
  **memveto** yang lain, dan veto butuh batas yang jelas antar wewenang.
- *"Apa yang terjadi kalau SAP tidak bisa dihubungi?"* → `Origin.MISSING`, bukan data
  karangan; lead-nya berhenti dan laporannya mengatakannya.
