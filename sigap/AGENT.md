# Dokumentasi Agent SIGAP

> Rujukan lengkap sebelas agent: apa yang dimiliki masing-masing, alat apa yang
> dipegang, dari mana datanya, dan apa yang **tidak** boleh dikerjakannya.
>
> Diambil dari registry yang berjalan, 22 September 2026 · **11 agent · 19/23 alat**

Bacaan pendamping: `PLAN.md` (rencana & status) · `DESIGN.md` (angka & skenario) ·
`TEKNIS.md` (nama fungsi & parameter) · `SUMBER-DATA.md` (asal data)

---

## 1. Cara timnya bekerja

Bayangkan satu tim kecil penanganan gangguan. **Arya** ketuanya. Dia tidak mengerjakan
sendiri — dia memanggil ahli yang relevan, satu per satu, berdasarkan apa yang ditemukan
sebelumnya.

```
kabar gangguan masuk
   ↓
Arya memanggil ahli        →  jawabannya memunculkan pertanyaan baru
   ↓                          ↓
Arya memanggil berikutnya  ←  ahli juga bisa saling oper langsung
   ↓
Kira mencoret yang melanggar aturan     ⛔ tidak bisa dibantah
   ↓
Tara menghitung yang tersisa            kalkulator, bukan AI
   ↓
Arya menyusun rekomendasi + risiko sisa
   ↓
Bram menjalankan yang kecil, mengajukan yang besar
```

**Urutannya tidak ditulis di awal.** Kalau masalahnya selesai dengan memindahkan stok
antar pabrik, Clint tidak pernah dipanggil sama sekali. Inilah yang membedakan ini dari
program biasa: program biasa jalurnya tetap A→B→C, tim ini memilih jalannya sendiri.

### Papan bersama

Semua ahli menulis dan membaca di satu papan, dan **tiap temuan membawa label asalnya**.
Ini yang memungkinkan Iris mengoper tahanan mutu langsung ke Elsa — tanggal habis stok
dihitung ulang tanpa lewat Arya.

### Label asal data

| Label | Artinya |
|---|---|
| `langsung` | Diambil dari SAP atau register resmi |
| `simpanan` | Pernah langsung, ada waktunya — termasuk data yang diunggah |
| `hitungan` | Dihitung dari yang langsung |
| `contoh` | Data contoh atau profil perusahaan — ditandai terbuka |
| `tidak ada` | Alat gagal. **Tidak diganti tebakan** |

**Aturan keras:** kalau masukan di jalur penting bernilai `tidak ada` atau `contoh`,
Tara menolak mengeluarkan angka penghematan.

---

## 2. Arya — Ketua tim
`supervisor` · effort **high** · 1 alat

**Pertanyaan yang ia miliki:** siapa yang dipanggil berikutnya, dan kapan bukti sudah cukup?

Memasukkan ahli ke dalam tim sesuai temuan terakhir, menilai kapan bukti cukup, lalu
menulis rekomendasi beserta trade-off yang ia terima dan risiko sisa yang ia akui.

| Alat | Parameter | Mengembalikan |
|---|---|---|
| `detect_disruption` | `peristiwa_id` ✱ | Isi peristiwa dari tabel |

> Sinyal gangguan masuk lewat `POST /peristiwa`, bukan dari agent yang memantau feed.
> Alat ini membaca yang sudah tercatat.

**Yang TIDAK boleh ia lakukan**
- Menghitung sendiri. Angka rupiah hanya boleh datang dari Tara.
- Merekomendasikan pilihan yang sudah ditolak Kira, sekalipun paling murah.
- Mengeluarkan angka penghematan kalau data pentingnya berlabel `contoh` atau `tidak ada`.
- Memanggil semua ahli hanya karena mereka ada. Berhenti begitu buktinya cukup.

---

## 3. Elsa — Dampak
`impact` · effort medium · 4 alat

**Pertanyaan:** pesanan mana yang kena, dan pelanggan mana yang terancam?

Menelusuri rantainya: gangguan → pesanan pembelian → stok → struktur produk → pesanan
pelanggan. Biasanya ahli pertama yang dipanggil Arya.

| Alat | Parameter | Mengembalikan |
|---|---|---|
| `get_open_purchase_orders` | `port`, `material` | Pesanan terbuka, bisa disaring per pelabuhan muat |
| `get_material_stock` | `material`, `plant` | Stok per plant + laju pemakaian harian |
| `get_bom_explosion` | `material` ✱ | Produk jadi yang memakai material ini |
| `get_sales_order_commitments` | `finished_goods` ✱ | Pesanan pelanggan + nilainya |

**Sumber:** `API_PURCHASEORDER_PROCESS_SRV` · `API_MATERIAL_STOCK_SRV` ·
`API_BILL_OF_MATERIAL_SRV` · `API_SALES_ORDER_SRV`

**Batasnya:** menganggap pemakaian harian tetap. Kalau permintaan sedang bergerak, itu
wilayah Dara. Menganggap stok tercatat bisa dipakai — keabsahannya wilayah Iris.

---

## 4. Dara — Permintaan
`demand` · effort medium · 2 alat

**Pertanyaan:** pemakaiannya masih segitu, atau permintaan sedang naik?

Tanpa Dara, seluruh sistem menganggap pemakaian harian angka tetap. Padahal lonjakan
permintaan menggeser tanggal habis stok sama efektifnya dengan pasokan yang putus.

| Alat | Parameter | Mengembalikan |
|---|---|---|
| `get_demand_signal` | `material` ✱ | Perubahan permintaan yang belum tercermin di jadwal produksi |
| `get_production_schedule` | `material` ✱, `plant` ✱ | Jadwal produksi + laju pemakaian |

**Catatan jujur:** `get_demand_signal` butuh SAP IBP yang belum tersambung, jadi sekarang
mengembalikan `tidak ada` — bukan angka karangan.

---

## 5. Iris — Keabsahan Stok
`inventory` · effort medium · 2 alat

**Pertanyaan:** stok yang tercatat itu benar-benar bisa dipakai?

Ada stok yang tercatat ada tapi ditahan karena gagal uji mutu, dan ada yang harus
disisakan sebagai cadangan minimum. Keduanya membuat stok efektif lebih kecil dari
angka di sistem.

| Alat | Parameter | Mengembalikan |
|---|---|---|
| `get_quality_holds` | `material` ✱, `plant` ✱ | Stok yang ditahan hasil inspeksi mutu |
| `get_safety_stock_policy` | `material` ✱, `plant` ✱ | Kebijakan cadangan minimum |

**Sumber:** `API_INSPECTIONLOT_SRV` · `API_PRODUCT_SRV` (MARC)

**Contoh operan langsung:** Iris menemukan 6 ton kena tahanan mutu, menulisnya ke papan,
dan Elsa membacanya lalu memajukan tanggal habis stok satu hari — tanpa lewat Arya.

---

## 6. Clint — Pencari Sumber
`sourcing` · effort medium · 1 alat

**Pertanyaan:** ada sumber lain nggak?

Menyusun kandidat lewat tiga strategi — percepat sumber lama, ganti sumber, realokasi
stok internal — tanpa diberi tahu strateginya apa.

| Alat | Parameter | Mengembalikan |
|---|---|---|
| `find_alternate_sources` | `material` ✱ | Pilihan pasokan + jumlah, tanggal tiba, biaya, dampak TKDN |

**Sumber:** purchasing info record (EINA/EINE) · SAP Ariba Sourcing

**Batasnya:** Clint hanya mencari dan mengkualifikasi. Boleh atau tidaknya urusan Kira;
tanggal tibanya yang realistis urusan Milo; murah atau mahalnya urusan Tara.

---

## 7. Milo — Logistik
`logistics` · effort medium · 2 alat

**Pertanyaan:** kalau dikirim sekarang, realistisnya sampai kapan?

Tanpa Milo, semua tanggal tiba cuma angka yang ditulis supplier. Dia menambahkan waktu
bongkar pelabuhan, pindah kapal, dan pengurusan bea cukai.

| Alat | Parameter | Mengembalikan |
|---|---|---|
| `get_shipment_status` | `purchase_order` ✱ | Status kiriman + tanggal semula vs revisi |
| `estimate_eta` | `opsi_id` ✱, `dwell_hari` | Tanggal tiba efektif + dasar perhitungannya |

> `estimate_eta` **deterministik** — model tidak menebak tanggal, dia memanggil hitungan.

---

## 8. ⛔ Kira — Aturan
`compliance` · effort **high** · 1 alat · **PUNYA VETO**

**Pertanyaan:** boleh nggak kita pakai supplier itu?

Ini bagian yang tidak dimiliki sistem supply chain mana pun di luar Indonesia. Kira
menguji tiap kandidat terhadap kandungan lokal, izin impor, klausul kontrak, dan
kalender libur.

| Alat | Parameter | Mengembalikan |
|---|---|---|
| `check_local_constraints` | `opsi_id` ✱ | Layak/tidak + alasan yang menyebut aturan dan angkanya |

### Aturan yang ia tegakkan

**TKDN** — yang dilarang adalah **memperburuk**, bukan mempertahankan:
- Menurunkan TKDN dari posisi sekarang → **ditolak**
- Menjatuhkannya ke bawah ambang kontrak dari posisi yang masih di atas → **ditolak**
- Mempertahankan atau menaikkan → lolos

**LARTAS** — negara asal yang baru bagi perusahaan menambah **10 hari kerja** untuk izin
impor. Sering membuat pilihan yang tampak murah jadi terlambat.

**Kalender libur** — libur nasional dan cuti bersama membekukan bea cukai dan logistik.

### Kenapa vetonya mutlak

Penolakan Kira **tidak bisa dikalahkan pertimbangan biaya**. Pilihan termurah yang
melanggar kontrak OEM bukan pilihan yang lebih murah — itu pelanggaran yang belum
ketahuan. Arya dilarang merekomendasikan apa pun yang sudah dicoret Kira.

**Kalau data aturannya tidak tersedia, Kira bilang tidak bisa dinilai.** Tidak menebak.
Menebak di sini berarti perusahaan bisa melanggar kontrak.

> ⚠️ `references/tkdn-rules.md` dan `lartas-procedure.md` **belum ditulis**. Selama itu,
> Kira menilai dari parameter fixture dan menandai hasilnya `contoh`.
> **Ini pekerjaan pengetahuan, bukan kode** — programmer tidak bisa menulisnya.

---

## 9. Tara — Hitungan
`simulation` · effort medium · 1 alat

**Pertanyaan:** berapa biayanya, dan mana yang paling murah?

| Alat | Parameter | Mengembalikan |
|---|---|---|
| `simulate_scenario` | `material` ✱, `plant` ✱, `opsi_layak` | Biaya, tanggal habis, OTIF, TKDN per pilihan dan kombinasinya |

### Tara tidak menalar, dia memanggil kalkulator

Isinya `engine/simulate.py` — **Python biasa, tanpa AI**. Alasannya keras: kalau angka
"hemat Rp 70 juta" keluar dari model bahasa, satu pertanyaan cukup untuk merobohkan
seluruh klaimnya. Model yang memutuskan, aritmetika yang menghitung.

### Dua hal yang membuatnya berbeda

**Menguji kombinasi, bukan cuma pilihan tunggal.** Di skenario Ningbo, jawaban terbaik
adalah C+B — dua pilihan yang sendirian tidak cukup. Model yang memilih satu per satu
tidak akan menemukannya.

**Menolak kalau datanya belum tepercaya:**

> *"Masukan 'stok' berasal dari contoh. Angka penghematan tidak dikeluarkan sampai
> datanya langsung."*

Ini yang membuat sistem tidak bisa mengarang penghematan dari data contoh.

---

## 10. Otto — Preseden
`precedent` · effort medium · 1 alat

**Pertanyaan:** dulu pernah kejadian begini? Hasilnya bagaimana?

| Alat | Parameter | Mengembalikan |
|---|---|---|
| `search_past_incidents` | `kata_kunci` ✱ | Kejadian serupa + bagaimana penanganannya berakhir |

**Sumber:** Bedrock Knowledge Bases

**Contoh sanggahan:** Tara bilang opsi B paling murah; Otto bilang supplier itu pernah
gagal requalifikasi 14 bulan lalu. Angkanya tidak berubah, tapi risikonya berbeda.

**Catatan jujur:** basis pengetahuan insiden belum diisi, jadi tiap gangguan sekarang
adalah kejadian pertama. Otto baru berguna setelah ada riwayat.

---

## 11. Bram — Eksekusi
`execution` · effort medium · 4/6 alat

**Pertanyaan:** jalankan keputusannya, lalu pantau sampai barang datang.

| Alat | Parameter | Wewenang |
|---|---|---|
| `create_stock_transfer` | material, dari/ke plant, jumlah, biaya | **Otonom** di bawah Rp 50 juta |
| `create_draft_po` | supplier, material, jumlah, tanggal, biaya | **Draf** — selalu menunggu buyer |
| `notify` | peran, pesan | Otonom |
| `monitor_shipment` | referensi | Otonom |
| `create_sourcing_event` | — | ○ belum ada · mode Cegah |
| `propose_safety_stock_change` | — | ○ belum ada · mode Cegah |

### Batas wewenang

| Aksi | Siapa yang memutuskan |
|---|---|
| Baca, analisis, simulasi, rekomendasi | Otonom |
| Transfer stok < Rp 50 juta | Otonom, dilaporkan sesudahnya |
| Menerbitkan purchase order | **Draf — buyer approve** |
| Supplier baru, atau > Rp 500 juta | Eskalasi ke procurement lead |
| Melanggar TKDN atau LARTAS | **Diblokir secara desain** |

### Tiga jaminan yang ditegakkan kode

1. **Idempoten.** Kunci yang sama tidak pernah membuat pesanan kedua.
2. **Persetujuan sekali pakai.** Aksi yang sudah diputus tidak bisa diputus ulang.
3. **Gagal kirim tidak mengubah status.** Aksi tetap `disetujui` dan dicoba lagi.

> Bram **mencatat dan mengajukan**; yang benar-benar mengirim ke SAP adalah
> `pengirim.py`, terpisah dan berjalan berkala. Agent mengusulkan, manusia menyetujui,
> pengirim mengirim.

---

## 12. Vega — Pemindai Risiko
`exposure` · effort medium · **0/2 alat — belum dibangun**

**Pertanyaan:** apa yang **akan** rusak, padahal sekarang belum ada masalah?

Sepuluh agent di atas bekerja karena ada kejadian. Vega bekerja **tanpa menunggu
kejadian** — terjadwal mingguan, mencari risiko yang belum terjadi.

| Alat | Rencana |
|---|---|
| `scan_supply_exposure` | Material bersumber tunggal, jalur terkonsentrasi satu pelabuhan, cover yang akan jatuh di bawah policy |
| `get_supplier_certifications` | Sertifikat TKDN supplier yang mendekati kedaluwarsa |

**Contoh sanggahan:** Clint bilang supplier A memadai; Vega bilang A adalah satu-satunya
sumber untuk tiga material sekaligus — titik gagal tunggal yang belum terlihat siapa pun.

---

## 13. Uji kelayakan: kapan sesuatu layak jadi agent?

**Sebuah agent layak berdiri sendiri kalau ia bisa tidak setuju dengan agent lain.**
Kalau hanya menghitung dan tidak pernah punya pandangan yang bertabrakan, itu alat.

| Pertentangan | Isinya |
|---|---|
| Dara vs Elsa | Elsa: habis 13 Sep. Dara: permintaan naik 40%, jadi habis 9 Sep |
| Iris vs Elsa | Elsa: ada 84 t. Iris: 23 t kena tahanan mutu, 15 t cadangan → tersedia 46 t |
| Milo vs Clint | Clint: supplier sanggup 12 Sep. Milo: dwell Priok → 15 Sep, opsi gugur |
| Otto vs Tara | Tara: opsi B termurah. Otto: supplier itu pernah gagal requalifikasi |
| Kira vs semua | Veto — opsi termurah melanggar ambang kontrak |

### Yang ditolak jadi agent terpisah

| Kandidat | Kenapa tidak |
|---|---|
| **FX / Keuangan** | Kurs itu aritmetika, tidak pernah bisa tidak setuju. Masuk ke Tara sebagai variabel |
| **Negosiasi** | Negosiasi butuh berhari-hari; window keputusan gangguan hitungan jam |

---

## 14. Menambah agent atau alat

### Alat baru

```python
# tools/berkasmu.py
from core.provenance import Asal, Hasil
from core.registry import daftarkan

@daftarkan("nama_alat", "kode_agent",
           "Deskripsi yang DIBACA MODEL. Tulis seperti menjelaskan ke rekan baru.",
           {"param": {"type": "string"}}, ["param"])
def nama_alat(param: str) -> Hasil:
    ...
    return Hasil(nilai, Asal.LANGSUNG, "API_YANG_DIPANGGIL")
```

Lalu tambahkan namanya ke `agents/definisi.py`, dan impor berkasnya di `api.py`.

> ⚠️ **Jebakan yang sudah tiga kali memakan kami:** menulis fungsinya tapi lupa
> `@daftarkan`. Fungsinya jalan, tapi model tidak akan pernah melihatnya, dan agent
> itu duduk diam tanpa alat. Halaman `/agent` menampilkan hitungan `x/y` persis untuk
> menangkap ini.

### Agent baru

1. Lewati uji kelayakan §13 — bisa tidak setuju dengan siapa?
2. Tambahkan ke `agents/definisi.py` dengan **nama panggilan berhuruf awal unik**
   (ada pengecekan yang memaksanya)
3. Tulis `prompts/<kode>.txt`
4. Daftarkan alatnya
5. Tambahkan contoh pertanyaan di `app/(app)/agent/[kode]/page.tsx`

### Pengecekan

```bash
cd sigap/agent
python3 -m agents.definisi    # jumlah agent, alat, keunikan nama
python3 -m core.provenance    # label asal data
python3 -m engine.simulate    # kalkulator mereproduksi angka DESIGN.md §2
```

---

## 15. Ringkasan

| Nama | Peran | Alat | Catatan |
|---|---|---|---|
| **Arya** | Ketua tim | 1/1 | Memilih rute, menilai kecukupan bukti |
| **Elsa** | Dampak | 4/4 | Biasanya dipanggil pertama |
| **Dara** | Permintaan | 2/2 | Sinyal permintaan belum tersambung |
| **Iris** | Keabsahan Stok | 2/2 | |
| **Clint** | Pencari Sumber | 1/1 | |
| **Milo** | Logistik | 2/2 | ETA deterministik |
| **Kira** ⛔ | Aturan | 1/1 | **Veto mutlak.** `references/` belum ditulis |
| **Tara** | Hitungan | 1/1 | Kalkulator, bukan AI |
| **Otto** | Preseden | 1/1 | Basis pengetahuan belum diisi |
| **Bram** | Eksekusi | 4/6 | Dua alat mode Cegah belum ada |
| **Vega** | Pemindai Risiko | 0/2 | Mode Cegah, belum dibangun |

**Yang menahan sekarang bukan alatnya.** Untuk penanganan gangguan, timnya sudah lengkap
19/19 — empat yang kurang semuanya milik mode Cegah. Yang menahan adalah `AWS_REGION`
dan `references/`.
