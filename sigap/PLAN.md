# SIGAP — Rencana Lengkap

> Dokumen utama. Ditulis dengan bahasa sehari-hari.
> Istilah teknis dikumpulkan di bagian akhir (§14), jadi kalau ada kata yang asing,
> lompat ke sana dulu.
>
> Terakhir diperbarui: 21 September 2026

---

## 1. Apa yang kita bangun

Sebuah asisten otomatis untuk pabrik yang bahan bakunya banyak diimpor.

Kalau ada gangguan pasokan — pelabuhan tutup, supplier gagal kirim, barang tertahan bea
cukai — sistem ini langsung menyelidiki sendiri: barang apa yang kena, kapan produksi
berhenti, pelanggan mana yang terancam, dan apa saja pilihan jalan keluarnya. Lalu ia
memberi rekomendasi lengkap dengan alasannya, dan mengeksekusinya ke sistem perusahaan
setelah disetujui orang.

Yang hari ini butuh dua sampai tiga hari kerja manusia, dikerjakan dalam belasan menit.

---

## 2. Cara kerjanya, dijelaskan sederhana

Bayangkan ada satu tim kecil yang kerjanya cuma menangani gangguan pasokan. Ada ketuanya,
ada beberapa orang ahli dengan bidang masing-masing. Ketua tidak mengerjakan sendiri —
dia memanggil ahli yang relevan, satu per satu, sesuai apa yang ditemukan sebelumnya.

SIGAP adalah tim itu, tapi berupa program.

Alurnya:

```
1. Ada kabar gangguan masuk        → sistem menyadarinya sendiri
2. Ketua memanggil ahli dampak     → "barang apa yang kena?"
3. Jawabannya memunculkan pertanyaan baru
4. Ketua memanggil ahli berikutnya → "ada sumber lain nggak?"
5. Ahli aturan mencoret pilihan yang melanggar hukum/kontrak
6. Ahli hitungan menghitung biaya tiap pilihan yang tersisa
7. Ketua menyusun rekomendasi + mengakui risiko yang tersisa
8. Sistem mengeksekusi yang kecil, dan minta persetujuan untuk yang besar
9. Sistem memantau sampai barang benar-benar datang
```

**Yang penting:** urutan langkah 2–6 **tidak ditulis di awal**. Ketua memutuskannya saat
itu juga, berdasarkan jawaban sebelumnya. Kalau masalahnya bisa diselesaikan dengan
memindahkan stok antar pabrik, ahli pencari supplier tidak pernah dipanggil sama sekali.

Ini yang membedakan dari program biasa. Program biasa jalurnya tetap: A lalu B lalu C.
Sistem ini memilih jalannya sendiri.

---

## 3. Daftar agent yang dibangun

Ada 11. Sepuluh untuk menangani gangguan, satu untuk pencegahan.

### Ketua

**1. SIGAP Core (ketua)**
Memutuskan ahli mana yang dipanggil berikutnya, menilai kapan bukti sudah cukup, lalu
menulis rekomendasi akhir beserta alasan dan risiko yang ia terima.
Bagiannya: menerima kabar gangguan.

### Sembilan ahli

**2. Ahli Dampak**
Menjawab: *PO mana yang kena, dan pelanggan mana yang terancam?*
Dia menelusuri dari pesanan pembelian → stok → daftar komponen produk → pesanan pelanggan.
Mengambil data: pesanan pembelian, stok, struktur produk, pesanan penjualan dari SAP.

**3. Ahli Permintaan**
Menjawab: *Pemakaiannya masih segitu, atau permintaan sedang naik?*
Tanpa dia, sistem menganggap pemakaian harian selalu tetap — padahal tidak.
Mengambil data: rencana permintaan dan jadwal produksi.

**4. Ahli Keabsahan Stok**
Menjawab: *Stok yang tercatat itu benar-benar bisa dipakai?*
Ada stok yang tercatat ada tapi sedang ditahan karena gagal uji mutu, atau harus disisakan
sebagai cadangan minimum.
Mengambil data: hasil inspeksi mutu, kebijakan stok cadangan.

**5. Ahli Pencari Sumber**
Menjawab: *Ada sumber lain nggak?*
Supplier alternatif, stok di pabrik lain, atau pengiriman dipercepat.
Mengambil data: daftar sumber pasokan, sistem pengadaan.

**6. Ahli Logistik**
Menjawab: *Kalau dikirim sekarang, realistisnya sampai kapan?*
Menghitung waktu bongkar di pelabuhan, pindah kapal, dan pengurusan bea cukai.
Tanpa dia, semua tanggal kedatangan cuma tebakan.

**7. Ahli Aturan** ⭐ **punya hak veto**
Menjawab: *Boleh nggak kita pakai supplier itu?*
Mengecek aturan kandungan lokal (TKDN), izin impor (LARTAS), isi kontrak dengan pelanggan,
dan kalender libur nasional.
**Kalau dia bilang tidak boleh, tidak ada yang bisa membatalkan — sekalipun pilihan itu
paling murah.** Ini bagian yang paling membedakan kita dari sistem lain.

**8. Ahli Hitungan**
Menjawab: *Berapa biayanya, dan mana yang paling murah?*
Menghitung biaya, ketepatan pengiriman, dampak ke kandungan lokal, dan risiko kurs.
**Ini kalkulator biasa, bukan AI.** Alasannya ada di §6.

**9. Ahli Preseden**
Menjawab: *Dulu pernah kejadian begini? Hasilnya bagaimana?*
Menyimpan dan mencari kembali penanganan kejadian serupa di masa lalu.

**10. Ahli Eksekusi**
Menjalankan keputusan: memindahkan stok, membuat draf pesanan pembelian, memberi tahu
orang-orang terkait, lalu memantau sampai barang diterima.

**11. Ahli Pemindai Risiko** — hanya untuk mode pencegahan
Menjawab: *Apa yang **akan** rusak, padahal sekarang belum ada masalah?*
Mencari barang yang cuma punya satu supplier, jalur pengiriman yang terlalu bergantung pada
satu pelabuhan, sertifikat supplier yang mau habis, dan stok yang akan menipis.

---

## 4. Dua mode kerja

| | **Mode Tanggap** | **Mode Cegah** |
|---|---|---|
| Kapan jalan | Ada kejadian | Terjadwal mingguan |
| Pertanyaannya | Rencana rusak, kita apakan? | Apa yang akan rusak, bisa dicegah nggak? |
| Contoh hasil | Pindahkan 55 ton dari Surabaya | Mulai kualifikasi supplier kedua untuk barang X |
| Buru-buru? | Ya, hitungan jam | Tidak, hitungan minggu |

Keduanya memakai **tim agent yang sama**. Bukan dua aplikasi.

---

## 5. Teknologi yang dipakai: AWS dan SAP

Bukan pilih salah satu. Keduanya dipakai, dengan pembagian tugas yang jelas.

| | **AWS** | **SAP** |
|---|---|---|
| Tugasnya | Tempat agent **berpikir dan berjalan** | Tempat **data asli disimpan** dan **aksi dijalankan** |
| Apa saja | Bedrock (mesin AI-nya), Strands (pengatur tim agent), Lambda, DynamoDB (penyimpanan), EventBridge (pemicu) | S/4HANA (pesanan, stok, produk), Ariba (pengadaan), Business Network (komunikasi supplier) |
| Kalau dicabut | Agent tidak punya otak | Agent tidak punya data, dan tidak bisa berbuat apa-apa |

**Kalimat singkat kalau ditanya:** *AWS yang menjalankan cara berpikirnya, SAP yang memegang
datanya. Agent tidak menggantikan sistem perusahaan — dia mengoperasikannya.*

### Pilihan yang sudah dikunci

| Hal | Pilihan | Kenapa |
|---|---|---|
| Mesin AI | `anthropic.claude-opus-5` di Bedrock | Penalaran bertingkat butuh model terkuat. Nama modelnya pakai awalan `anthropic.` karena lewat Bedrock |
| Bahasa program | Python | Semua alat yang dibutuhkan ada di Python |
| Pengatur tim agent | Strands Agents SDK | Buatan AWS, cocok dengan kriteria lomba |
| Tampilan | Next.js + `twenty-ui` | Lihat §8 |
| Penyimpanan | DynamoDB | Sudah satu paket dengan AWS |

⚠️ **Yang harus dicek duluan:** tidak semua wilayah AWS menyediakan model Claude. Jangan
berasumsi Jakarta punya. Cek di awal, siapkan `us-west-2` sebagai cadangan.

---

## 6. Empat aturan yang tidak boleh dilanggar

**1. Perhitungan biaya harus pakai kalkulator biasa, bukan AI.**
Kalau angka "hemat Rp 70 juta" keluar dari AI, satu pertanyaan juri bisa merobohkan seluruh
klaim kita. AI yang memutuskan, matematika biasa yang menghitung. Sama berlaku untuk
perkiraan tanggal kedatangan.

**2. Setiap data harus punya label asalnya, sejak hari pertama.**
Tiap angka yang dipakai sistem diberi tanda: diambil langsung · dari simpanan · hasil hitungan ·
hanya contoh · tidak ada. Kalau data penting ternyata tidak ada, sistem **menolak mengeluarkan
angka** dan bilang apa yang kurang — bukan menebak.
Menambahkan ini di awal butuh satu potong kode. Menambalnya nanti ke 23 alat butuh berhari-hari.

**3. Hemat biaya AI sejak awal.**
Dalam tim agent, penjelasan yang sama dikirim ulang setiap kali agent bekerja. Kalau tidak
diatur, biayanya berlipat sebanyak jumlah agent. Ada fasilitas penyimpanan sementara untuk
ini — pakai dari awal, dan cek angkanya benar-benar turun.

**4. Jalankan dulu di laptop, jangan langsung di cloud.**
Memecah 23 alat jadi 23 fungsi terpisah di cloud sejak hari pertama akan memperlambat kerja
kalian sendiri. Jalankan sebagai satu program Python biasa dulu. Pindah ke cloud itu urusan
belakangan, dan cuma kalau perlu.

---

## 7. Data: diambil dari mana

| Data | Sumbernya | Status |
|---|---|---|
| Pesanan pembelian, stok, struktur produk, pesanan pelanggan | Sistem uji coba SAP di `sandbox.api.sap.com` | ✅ sudah dipastikan ada, gratis |
| Jadwal produksi | SAP | ✅ |
| Hasil uji mutu, stok cadangan minimum | SAP | ✅ |
| Sumber pasokan alternatif | SAP Ariba | ✅ |
| Kalender libur nasional | SKB 3 Menteri | ✅ |
| Kurs rupiah | Bank Indonesia (JISDOR) | ✅ |
| **Aturan kandungan lokal (TKDN)** | Daftar dari Kementerian Perindustrian | ⚠️ belum dicek caranya |
| **Aturan izin impor (LARTAS)** | INSW | ⚠️ belum dicek caranya |
| **Cuaca & gempa Indonesia** | BMKG `data.bmkg.go.id` | ✅ **ada API JSON, siap pakai** |
| Topan luar negeri (skenario Ningbo) | JTWC / JMA — **bukan BMKG** | ⚠️ perlu dicek |
| Posisi kapal | Data AIS | ⚠️ perlu daftar dulu |

Rinciannya ada di `SUMBER-DATA.md` — sudah dicek satu per satu.
Yang bertanda ⚠️ datanya **nyata dan terbuka untuk umum**, cuma belum dipastikan apakah
bisa diambil otomatis. Kalau ternyata tidak bisa, dimasukkan manual sebagai dokumen aturan
yang diberi versi. Tetap bukan data karangan.

**Yang satu-satunya kita karang: profil perusahaannya.** Daftar pabrik, kecepatan pemakaian
bahan, isi kontrak. Alasannya sederhana — kita belum punya pelanggan. Ini harus dikatakan
terbuka, jangan disembunyikan.

---

## 8. Tampilan aplikasinya

### Ini bukan website yang orang buka setiap pagi

Sistemnya bekerja karena ada kejadian, bukan karena ada orang membuka. Planner tidak duduk
menunggu di layar — sistem yang menghubungi mereka. Tampilan web ini tempat **memeriksa dan
menyetujui**, bukan tempat pekerjaan dimulai.

Tanda kalau kita salah arah: pertanyaan pertama saat coding jadi *"halaman utamanya isi apa?"*.
Kalau itu terjadi, kita sedang membuat dashboard — dan dashboard tanpa agent pasti kalah.

### Bentuk layarnya

Daftar di kiri, penjelasan di kanan. Klik satu, panel kanan menampilkan seluruh jalan pikiran
sistem.

```
┌──────────────────────────┬───────────────────────────────┐
│  YANG PERLU DIPUTUSKAN   │   Ningbo tutup · barang M-4471│
│                          │                               │
│ ● Ningbo    Rp 70 juta ← │   Kabar masuk                 │
│ ○ TKDN      Rp 12 juta   │   12 pesanan kena, Rp 8,4 M   │
│ ○ Priok     Rp 45 juta   │   Stok habis 13 Sep           │
│                          │   2 pilihan dicoret ⛔         │
│                          │   Saran: C + B                │
│                          │                               │
│                          │   [ Setujui ]  [ Naikkan ]    │
└──────────────────────────┴───────────────────────────────┘
```

Satu layar menjawab dua kebutuhan: daftar yang menunggu keputusan, dan alasan di baliknya.
Tombol setuju ada persis di tempat orang membaca alasannya.

### Teknologinya

**Next.js + `twenty-ui`.** `twenty-ui` adalah kumpulan komponen tampilan siap pakai dari
Twenty CRM, bisa dipasang tanpa menjalankan Twenty-nya sama sekali. Butuh React 19, dan
proyek kalian sudah React 19 — jadi langsung cocok.

```bash
npm install twenty-ui react@^19 react-dom@^19
```

Dua catatan jujur:
- Statusnya masih **alpha**, jadi **kunci versinya** dan jangan update di tengah jalan.
- Ini kumpulan komponen, bukan halaman jadi. Tombol, kolom isian, label, ikon dapat — tapi
  susunan halamannya tetap kalian yang buat.

**Kalau waktunya mepet,** ganti ke Streamlit: jadi dalam 2 hari, tapi tampilannya seadanya.
Next.js + twenty-ui kira-kira 4–6 hari untuk satu orang.

---

## 9. Tahapan kerja

Tiap tahap punya tanda selesai yang bisa ditunjukkan ke orang. Jangan lanjut sebelum tandanya
tercapai.

### Tahap 0 — Ambil akses · setengah hari
**Ini menghambat semuanya. Kerjakan paling awal.**

1. Daftar akun SAP gratis di `api.sap.com`, ambil kunci API dari halaman API-nya
2. Buka akun AWS, minta izin pakai model Claude di menu Bedrock
3. **Pastikan wilayah AWS mana yang menyediakan Claude**

✅ **Selesai kalau:** satu perintah `curl` ke SAP mengembalikan data pesanan, dan satu
panggilan ke Bedrock mengembalikan tulisan. Belum ada kode apa pun.

### Tahap 1 — Sambungan paling tipis · 1 hari
Membuktikan seluruh rantai menyala.

- Penghubung ke SAP
- Satu alat: ambil daftar pesanan pembelian
- Penanda asal data (aturan §6 nomor 2)
- Satu agent yang memanggil alat itu

✅ **Selesai kalau:** ditanya pakai bahasa manusia → agent memanggil SAP → jawabannya berisi
nomor pesanan asli, dengan tanda "diambil langsung". **Simpan tangkapan layarnya** — ini bukti
pertama kalian, dan berguna untuk presentasi.

### Tahap 2 — Ahli Dampak lengkap + kalkulator · 2 hari
- Tiga alat sisanya: stok, struktur produk, pesanan pelanggan
- Kalkulator biaya (Python biasa, bukan AI)
- Uji: hitungan skenario Ningbo hasilnya sama persis dengan yang di `DESIGN.md`

✅ **Selesai kalau:** diberi kabar gangguan, agent menemukan **sendiri** barang mana yang kritis
dan kapan produksi berhenti — tanpa diberi tahu barangnya yang mana.

### Tahap 3 — Aturan lokal + hak veto · 2 hari
**Bangun sekarang, jangan ditunda. Ini pembeda utama kalian.**

- Dokumen aturan: TKDN, LARTAS, kalender libur, waktu bongkar pelabuhan
- Alat pengecek aturan
- Ahli Aturan dengan hak veto

✅ **Selesai kalau:** pilihan supplier termurah **ditolak** dengan alasan TKDN yang bisa dibaca,
dan penolakannya tidak bisa dikalahkan oleh skor biaya.

### Tahap 4 — Tim lengkap · 4 hari
- Enam ahli sisanya
- Ketua tim
- Papan bersama tempat semua ahli menulis temuan

✅ **Selesai kalau:** skenario Ningbo jalan sendiri dari awal sampai akhir, **dan** urutan ahli
yang dipanggil **berbeda** saat dijalankan skenario lonjakan permintaan.

### Tahap 5 — Menulis balik ke SAP + persetujuan · 2 hari
- Alat pemindahan stok, pembuatan draf pesanan, pemberitahuan, pemantauan
- Batas wewenang ditulis **di kode**, bukan di instruksi AI

✅ **Selesai kalau:** pemindahan stok jalan sendiri, tapi pesanan pembelian berhenti sebagai
draf menunggu persetujuan orang.

### Tahap 6 — Tampilan · 4–6 hari
- Next.js + twenty-ui
- Daftar kiri, panel kanan
- Label asal data di tiap angka

✅ **Selesai kalau:** orang bisa mengikuti jalan pikiran sistem tanpa dijelaskan.

### Tahap 7 — Kumpulan uji coba · 2 hari
- 10 skenario gangguan
- Dijalankan otomatis setiap ada perubahan kode

✅ **Selesai kalau:** sepuluh-sepuluhnya lulus, dan catatannya menunjukkan **kombinasi ahli
yang berbeda** di tiap skenario.

### Tahap 8 — Mode Cegah · 3 hari
- Ahli Pemindai Risiko + 4 alat tambahan
- Pemicu terjadwal, daftar rekomendasi, catatan tindakan
- Uji coba skenario 11–14

✅ **Selesai kalau:** tanpa ada gangguan apa pun, sistem mengeluarkan daftar tindakan pencegahan
yang sudah diurutkan berdasarkan nilai kerugian yang bisa dicegah.

### Tahap 9 — Pindah ke cloud · 2 hari, **hanya kalau perlu**
Untuk presentasi, satu program biasa sudah cukup. Jangan habiskan waktu di sini sebelum
Tahap 7 lulus.

**Total sekitar 20–22 hari kerja.** Dengan tiga orang bekerja paralel setelah Tahap 3,
realistis **3 minggu**.

---

## 10. Siapa mengerjakan apa

| Tahap | Backend | Data | Frontend | Domain |
|---|---|---|---|---|
| 0 | ambil akses | — | — | — |
| 1–2 | penghubung SAP + alat | kalkulator biaya | mulai rancang layar | siapkan skenario |
| 3 | alat pengecek aturan | — | rangka tampilan | **tulis dokumen aturan** |
| 4 | ketua + papan bersama + 2 ahli | 2 ahli | 1 ahli + tampilan | susun skenario uji |
| 5–6 | menulis balik ke SAP | — | tampilan | — |
| 7 | — | kumpulan uji coba | — | tinjau hasil |
| 8 | pemindai risiko | — | daftar rekomendasi | — |

Yang paling sering terlupa: **orang domain paling sibuk di Tahap 3**, bukan di awal. Dokumen
aturan TKDN dan LARTAS itu isinya pengetahuan, bukan kode — dan itu bagian yang tidak bisa
dikerjakan programmer.

---

## 11. Susunan folder

```
sigap/
├── references/          dokumen aturan (TKDN, LARTAS, kalender, pelabuhan)
├── prompts/             instruksi tiap agent, dalam file terpisah
├── clients/             penghubung ke SAP, ke daftar aturan, ke sumber kabar
├── tools/               23 alat, satu file satu alat
│   └── _provenance.py   penanda asal data — dipakai semua alat
├── engine/              kalkulator biaya & perkiraan tanggal (Python biasa)
├── agents/              ketua + 10 ahli
├── graph.py             pengatur tim
├── evals/               14 skenario uji
└── web/                 tampilan Next.js
```

**Urutan menulisnya dari bawah ke atas:** penghubung → alat → kalkulator → ahli → ketua →
tampilan → uji coba. Jangan mulai dari `graph.py`.

---

## 12. Perkiraan biaya

| | Perkiraan |
|---|---|
| Satu kejadian gangguan ditangani | **Rp 60.000 – 120.000** |
| Seluruh masa pembangunan | **Rp 500.000 – 1.500.000** |

Dibandingkan Rp 70 juta biaya kirim darurat yang dihindari, perbandingannya sekitar **500 : 1**.

⚠️ Angka ini memakai tarif resmi Anthropic sebagai acuan. **Bedrock dikelola AWS dan tarifnya
berbeda** — cek `aws.amazon.com/bedrock/pricing` sebelum angka ini ditulis di dokumen mana pun.
Ukur yang sebenarnya di Tahap 4.

---

## 13. Risiko dan cara menghindarinya

| Risiko | Seberapa besar | Cara menghindari |
|---|---|---|
| Claude belum ada di wilayah AWS terdekat | **Besar** | Cek di Tahap 0. Siapkan `us-west-2` |
| Data contoh SAP tidak cocok dengan skenario kita | Sedang | Petakan di Tahap 1. Kalau tidak cocok, **sesuaikan skenarionya** — jangan kembali ke data karangan |
| Agent berputar-putar tidak berhenti | Sedang | Pasang batas jumlah langkah dan batas waktu sejak Tahap 4 |
| Biaya AI membengkak saat uji coba berulang | Sedang | Aturan §6 nomor 3, sejak Tahap 1 |
| Aturan TKDN/LARTAS tidak bisa diambil otomatis | Sedang | Sudah diantisipasi — masuk sebagai dokumen aturan |
| Tampilan dikerjakan sebelum agent jalan | **Besar** | Urutannya agent dulu. Tampilan cantik tanpa agent = kalah |
| Tahap 9 dikerjakan terlalu awal | Kecil tapi mahal | Setelah Tahap 7 lulus, bukan sebelumnya |

---

## 14. Daftar istilah

Kalau harus bicara dengan juri atau programmer, ini padanan teknisnya.

| Yang dipakai di sini | Istilah teknisnya | Artinya |
|---|---|---|
| Tim agent dengan ketua | *supervised swarm* / multi-agent system | Beberapa AI yang punya tugas masing-masing, dikoordinasi satu ketua |
| Ketua | *supervisor agent* | AI yang memutuskan siapa bekerja berikutnya |
| Alat | *tool* | Satu fungsi yang bisa dipanggil AI, misalnya "ambil daftar pesanan" |
| Papan bersama | *shared blackboard* | Tempat semua agent menulis dan membaca temuan |
| Label asal data | *provenance* | Tanda apakah angka itu diambil langsung, dari simpanan, atau cuma contoh |
| Hak veto | *veto authority* | Ahli aturan bisa mencoret pilihan, dan tidak bisa dibantah |
| Kalkulator biasa | *deterministic engine* | Perhitungan matematika, bukan AI — hasilnya selalu sama |
| Urutan ditentukan saat jalan | *runtime routing* | Langkah berikutnya dipilih saat itu juga, bukan ditulis di awal |
| Kumpulan uji coba | *eval suite* | Sekumpulan skenario untuk menguji apakah sistem masih benar |
| Sistem uji coba SAP | *sandbox* | Sistem SAP asli berisi data contoh, gratis, untuk belajar |
| Pindah ke pelanggan | *tenant swap* | Cukup ganti alamat dan kunci — kodenya tidak berubah |
| Kandungan lokal | TKDN | Persentase komponen dalam negeri; kontrak pelanggan menetapkan batas minimum |
| Izin impor | LARTAS | Aturan larangan dan pembatasan impor |
| Ketepatan pengiriman | OTIF (*on-time-in-full*) | Ukuran apakah barang datang tepat waktu dan lengkap |

---

## 15. Yang dikerjakan minggu ini

1. **Ambil kunci API SAP** di `api.sap.com` — hari ini, ini yang menghambat semuanya
2. **Minta izin model Claude di AWS Bedrock**, dan pastikan wilayah mana yang menyediakannya
3. **Tahap 1:** penghubung SAP + satu alat + penanda asal data + satu agent
4. **Simpan tangkapan layar** hasil panggilan SAP pertama yang berhasil

Kalau keempat ini beres, bagian tersulit sudah lewat. Sisanya penambahan.
