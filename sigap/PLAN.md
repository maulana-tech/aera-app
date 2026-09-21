# SIGAP — Rencana & Status

> Konteks: **masa pengembangan aplikasi.** Bukan proyek lomba.
> Istilah teknis ada di §8 kalau ada kata yang asing.
>
> Diperbarui: 21 September 2026

---

## 1. Apa yang dibangun

Asisten otomatis untuk pabrik yang bahan bakunya banyak diimpor.

Kalau ada gangguan pasokan — pelabuhan tutup, supplier gagal kirim, barang tertahan bea
cukai — sistem menyelidiki dampaknya sendiri, menyusun pilihan jalan keluar, mencoret yang
melanggar aturan atau kontrak, menghitung mana yang paling murah, lalu mengeksekusinya ke
SAP setelah disetujui orang yang berwenang.

Yang hari ini butuh 2–3 hari kerja manusia, dikerjakan dalam belasan menit.

**Ini bukan website yang orang buka tiap pagi.** Sistemnya bekerja karena ada kejadian.
Tampilan web adalah tempat memeriksa dan menyetujui, bukan tempat pekerjaan dimulai.

---

## 2. Status sekarang

| Bagian | Status | Catatan |
|---|---|---|
| Label asal data | ✅ **jalan** | Melekat di semua alat. Kegagalan → `TIDAK_ADA`, bukan tebakan |
| Kalkulator biaya | ✅ **jalan** | Python murni. Menolak memberi angka kalau masukan belum tepercaya |
| Penghubung SAP (baca) | ✅ **siap** | Otomatis pakai sandbox begitu `SAP_API_KEY` diisi |
| Penghubung SAP (tulis) | ⚠️ **jalur lengkap, belum diuji** | Token CSRF sudah ditangani; nama entitas perlu dicocokkan |
| Penyimpanan | ✅ **jalan** | SQLite. Aksi idempoten, persetujuan sekali pakai |
| Auth & wewenang | ✅ **jalan** | Identitas dari token; batas nilai dicek di server |
| Layanan API | ✅ **jalan** | 6 endpoint |
| Antarmuka | ✅ **jalan** | Masuk, antrean, detail, persetujuan. twenty-ui |
| Alat | 🔶 **12 dari 23** | Sisanya masih nama di `agents/definisi.py` |
| Tim agent (`graph.py`) | ⚠️ **ditulis, belum pernah jalan** | Menunggu `AWS_REGION` |
| Dokumen aturan (`references/`) | ❌ **belum ada** | Penghambat utama. Tugas orang domain |
| Kumpulan uji skenario | ❌ **belum ada** | |
| Mode Cegah | ❌ **belum ada** | |

### Tiga hal yang menghambat

1. **`SAP_API_KEY`** — gratis, 15 menit. Begitu diisi, 5 alat baca langsung pakai data
   sungguhan dan label asalnya berubah dari `contoh` jadi `langsung`.
2. **`AWS_REGION`** — `graph.py` belum pernah dieksekusi sekali pun. Sampai ini ada,
   sistem jujur menahan diri dan tidak membuat keputusan apa pun.
3. **`references/tkdn-rules.md` dan `lartas-procedure.md`** — Ahli Aturan sudah membacanya
   kalau ada; tanpa itu ia menilai dari parameter dan menandai hasilnya `contoh`. **Ini
   pekerjaan pengetahuan, bukan kode** — programmer tidak bisa menulisnya.

---

## 3. Cara kerjanya

Bayangkan satu tim kecil: ada ketua, ada beberapa ahli dengan bidang masing-masing. Ketua
tidak mengerjakan sendiri — dia memanggil ahli yang relevan, satu per satu, sesuai apa yang
ditemukan sebelumnya.

```
kabar gangguan masuk
  → ketua memanggil ahli dampak      "barang apa yang kena?"
  → jawabannya memunculkan pertanyaan baru
  → ketua memanggil ahli berikutnya  "ada sumber lain nggak?"
  → ahli aturan mencoret yang melanggar
  → ahli hitungan menghitung sisanya
  → ketua menyusun rekomendasi + mengakui risiko yang tersisa
  → yang kecil dijalankan sendiri, yang besar minta persetujuan
  → dipantau sampai barang benar-benar datang
```

**Urutannya tidak ditulis di awal.** Kalau masalahnya selesai dengan memindahkan stok antar
pabrik, ahli pencari supplier tidak pernah dipanggil sama sekali.

### Sebelas agent

| Agent | Pertanyaan yang ia miliki |
|---|---|
| **SIGAP Core** (ketua) | Siapa dipanggil berikutnya, dan kapan bukti cukup? |
| Ahli Dampak | PO mana yang kena, pelanggan mana yang terancam? |
| Ahli Permintaan | Pemakaiannya masih segitu, atau permintaan naik? |
| Ahli Keabsahan Stok | Stok yang tercatat itu benar-benar bisa dipakai? |
| Ahli Pencari Sumber | Ada sumber lain nggak? |
| Ahli Logistik | Realistisnya sampai kapan? |
| **Ahli Aturan** ⭐ | Boleh nggak kita pakai supplier itu? **Punya hak veto** |
| Ahli Hitungan | Berapa biayanya, mana yang paling murah? |
| Ahli Preseden | Dulu pernah begini? Hasilnya gimana? |
| Ahli Eksekusi | Jalankan, lalu pantau sampai barang datang |
| Ahli Pemindai Risiko | Apa yang **akan** rusak? *(mode Cegah)* |

Rincian alat tiap agent ada di `DESIGN.md` §3.

---

## 4. Teknologi

| | AWS | SAP |
|---|---|---|
| Tugasnya | Tempat agent **berpikir dan berjalan** | Tempat **data asli** dan **aksi dijalankan** |
| Apa saja | Bedrock (mesin AI), Strands, Lambda | S/4HANA, Ariba, Business Network |

Keputusan yang sudah dikunci:

| Hal | Pilihan |
|---|---|
| Mesin AI | `anthropic.claude-opus-5` lewat Bedrock |
| Bahasa | Python (agent) · TypeScript (antarmuka) |
| Penyimpanan | SQLite — pindah ke Postgres kalau sudah multi-perusahaan |
| Antarmuka | Next.js + `twenty-ui` |
| Layanan API | `http.server` stdlib — pindah ke FastAPI kalau butuh >10 rps |

⚠️ Tidak semua wilayah AWS menyediakan Claude. Cek dulu; siapkan `us-west-2` sebagai cadangan.

---

## 5. Enam jaminan yang ditegakkan kode

Bukan instruksi ke AI — ini dipaksakan oleh program, jadi tidak bisa dilanggar prompt.

1. **Kegagalan tidak mengarang nilai.** Alat gagal → `TIDAK_ADA`.
2. **Kalkulator menolak** memberi angka rupiah kalau masukannya belum tepercaya.
3. **Aksi idempoten.** Kunci yang sama tidak pernah membuat pesanan kedua.
4. **Identitas hanya dari token sesi.** Mengaku peran lain lewat badan permintaan diabaikan.
5. **Wewenang dicek di server**, bukan di tombol.
6. **Produksi menolak start** tanpa SAP dan model — tidak boleh menebak apa pun.

---

## 6. Urutan kerja berikutnya

| # | Yang dikerjakan | Siapa | Lama |
|---|---|---|---|
| 1 | Ambil `SAP_API_KEY` di api.sap.com | siapa saja | 15 menit |
| 2 | Aktifkan Bedrock, pastikan wilayahnya | backend | 1 jam |
| 3 | Jalankan `graph.py` sungguhan, perbaiki yang pecah | backend | 1–2 hari |
| 4 | Tulis `references/tkdn-rules.md` + `lartas-procedure.md` | **domain** | 2 hari |
| 5 | Cocokkan nama entitas tulis SAP di `pengirim.py` | backend | 1 hari |
| 6 | 11 alat sisanya | backend + data | 3 hari |
| 7 | Kumpulan uji 10 skenario | data | 2 hari |
| 8 | Mode Cegah + Ahli Pemindai Risiko | backend | 3 hari |

Nomor 4 bisa jalan paralel sejak sekarang dan **tidak menunggu apa pun.**

---

## 7. Susunan berkas

```
sigap/
├── PLAN.md           berkas ini — rencana & status
├── DESIGN.md         angka skenario, 23 alat, 11 agent, aturan lokal
├── TEKNIS.md         nama fungsi & parameter persis
├── SUMBER-DATA.md    hasil pengecekan tiap sumber data
└── agent/            kode
    ├── core/         asal data · identitas · penyimpanan · konfigurasi · registry
    ├── clients/      penghubung SAP
    ├── tools/        12 alat terdaftar
    ├── engine/       kalkulator — Python murni
    ├── agents/       definisi 11 agent
    ├── prompts/      instruksi tiap agent
    ├── graph.py      tim agent
    ├── api.py        layanan HTTP
    └── pengirim.py   kirim aksi yang disetujui ke SAP

app/sigap/            antarmuka Next.js
app/api/              jembatan ke layanan agent
```

---

## 8. Daftar istilah

| Yang dipakai di sini | Istilah teknisnya |
|---|---|
| Tim agent dengan ketua | multi-agent system · *supervised swarm* |
| Ketua | *supervisor agent* |
| Alat | *tool* |
| Label asal data | *provenance* |
| Kalkulator biasa | *deterministic engine* |
| Urutan ditentukan saat jalan | *runtime routing* |
| Aksi tidak berganda | *idempotency* |
| Sistem uji coba SAP | *sandbox* |
| Pindah ke pelanggan | *tenant swap* |
| Kandungan lokal | TKDN |
| Izin impor | LARTAS |
| Ketepatan pengiriman | OTIF |
