# SIGAP — Proposal Content & Structure

> **Apa ini.** Naskah kanonik proposal dalam bentuk teks. File HTML di folder yang sama adalah
> *tata letak* dari isi ini. Kalau ada angka atau kalimat yang diubah di sini, mirror ke HTML —
> dan sebaliknya. Gunakan file ini untuk copy-paste ke form pendaftaran, review bersama tim,
> atau kalau panitia minta format lain (Word/PDF template mereka).
>
> Sumber angka: `../sigap/DESIGN.md` §2. Jangan ubah satu angka tanpa mengecek turunannya di sana.

**Batas: maksimal 3 halaman.** Struktur di bawah sudah dipetakan per halaman. Kalau menambah
sesuatu, hapus sesuatu yang lain.

---

## Header dokumen

| Field | Isi |
|---|---|
| Judul | **SIGAP — an autonomous supply-disruption response agent for Indonesian manufacturers** |
| Track | 01 · Intelligent Supply Chain |
| Team | `[team name]` ⚠️ |
| University | `[university]` ⚠️ |
| Members | `[name 1]` · `[name 2]` · `[name 3]` ⚠️ |
| Date | September 2026 |

⚠️ = placeholder yang wajib diisi sebelum submit, di **ketiga** file cetak.

### Lede (paragraf pembuka)

> When a port closes, an Indonesian manufacturer loses two to three days deciding what to do
> about it — and by the time the decision is made, the cheap options have expired. SIGAP is an
> agent that detects the disruption, traces it through purchase orders, stock and customer
> commitments, generates and simulates its own mitigation options against local regulatory
> constraints, and executes the approved plan in SAP.

---

# HALAMAN 1 — Problem

## 01 · Three days of manual replanning, spent on a decision that has a 24-hour window

**Perusahaan referensi:** PT Karya Presisi Nusantara (KPN), Tier-1 komponen otomotif, Karawang.

| Atribut | Nilai |
|---|---|
| Plant | KRW1 Karawang (utama) · SBY1 Surabaya |
| Produk | Brake caliper & transmission housing assembly untuk OEM |
| Kontrak | Just-in-time, dengan penalti keterlambatan |
| Material aktif | 340 |
| Nilai raw material impor | 61%, mayoritas via Tanjung Priok |
| TKDN portfolio saat ini | 38,2% (ambang kontrak OEM: **40%**) |

**Narasi masalah.** Sekitar **14 kali setahun** pasokan material terganggu: topan menutup
pelabuhan muat, clearance bea cukai tertahan, supplier menyatakan force majeure. Urutannya
selalu sama — planner menyadari kiriman telat, membuka tiga sistem untuk mencari PO mana yang
kena, mengecek stok manual terhadap rencana produksi di spreadsheet, menelepon procurement soal
alternatif. Dua sampai tiga hari kemudian keputusan diambil, dan yang tersisa cuma air freight
dengan biaya empat kali lipat.

**Inti masalahnya bukan kekurangan data.** Semua fakta yang dibutuhkan sudah ada di S/4HANA.
Yang manual adalah **merangkai fakta itu menjadi keputusan** — dan pekerjaan itu bersaing dengan
tugas harian planner.

### Kotak: kenapa ini lebih sulit di Indonesia daripada versi textbook

Mengganti supplier di sini bukan sekadar hitungan biaya dan lead time. Tiga kendala lokal rutin
membatalkan jawaban yang secara matematis paling optimal:

- **TKDN** (Tingkat Komponen Dalam Negeri) — kontrak OEM menetapkan ambang minimum. Impor yang
  lebih murah bisa melanggarnya.
- **LARTAS** (larangan & pembatasan impor) — negara asal baru menambah ±10 hari kerja sebelum
  kiriman pertama bisa clear.
- **Dwell time Tanjung Priok** bersifat variabel, bukan konstanta; dan libur nasional membekukan
  bea cukai sepenuhnya.

### Catatan kaki halaman 1 (wajib ada)

> The operating profile — plants, consumption rates, contract terms — is modelled on publicly
> documented Indonesian Tier-1 automotive patterns; every deployment supplies its own from master
> data. The regulatory, market and weather data the agent reasons over is live. Assumptions are
> stated where used.

## 02 · Biaya status quo per event

| Metrik | Nilai | Keterangan |
|---|---|---|
| Decision latency | **2–3 hari** | dari sinyal pertama sampai mitigasi disetujui |
| Avoidable expedite | **Rp 70 juta** (ditulis `Rp 70 million` di proposal) | premi median yang dibayar per event karena telat memutuskan |
| Revenue exposed | **Rp 2,14 miliar** | order pelanggan yang terancam dalam satu event tipikal |
| Planner effort | **70 hari-orang/tahun** | waktu yang habis untuk replanning |

**Asumsi:** 14 event disrupsi per tahun; dua planner terlibat 2,5 hari masing-masing; premi
expedite dihitung sebagai selisih opsi yang tersedia di hari ke-1 dengan opsi yang tersisa di
hari ke-3.

## 03 · Kenapa tool yang ada tidak menutup celah ini

| Kategori | Berhenti di mana |
|---|---|
| **Supply chain visibility platform** | Menampilkan kiriman yang telat, lalu berhenti tepat di titik pekerjaan beratnya dimulai: tidak ada yang memberi tahu finished good mana yang kena, kapan lini benar-benar berhenti, atau opsi mana yang lolos aturan TKDN |
| **Chatbot / asisten RAG** | Menjawab pertanyaan tentang dokumen. Tidak bisa membaca PO hidup, tidak bisa mensimulasikan rencana, tidak bisa menulis purchase requisition kembali ke SAP |

**Yang hilang adalah pelaku, bukan pemberi informasi** — sesuatu yang menjalankan seluruh rantai
penalaran planner secara otonom: *scope the impact, quantify it, invent the options, discard the
illegal ones, price the survivors, recommend with reasoning, execute under approval, and verify
the outcome.*

Rantai itu adalah rangkaian keputusan saling bergantung di mana hasil tiap langkah menentukan
query berikutnya. Ini kasus kanonik untuk agent — dan inilah yang SIGAP lakukan.

---

# HALAMAN 2 — Solusi

## 04 · Worked event: topan menutup Pelabuhan Ningbo 6 hari

**Pemicu:** Ningbo–Zhoushan tutup **8–13 September**.

> **Framing wajib:** ini adalah *"the reasoning path SIGAP is designed to take"*, bukan rekaman
> eksekusi. Jangan tulis dengan bahasa yang menyiratkan sudah dijalankan.

| Tahap | Yang dilakukan | Agent → tool |
|---|---|---|
| **DETECT** | Advisory maritim masuk: Ningbo tutup 8–13 Sep. Agent mengenali pelabuhan itu sebagai jalur yang ia gantungi | Supervisor → `detect_disruption` |
| **SCOPE** | Menemukan **12 PO terbuka senilai Rp 8,4 miliar** lewat Ningbo, mencakup 5 material dari 3 supplier | Impact Analyst → `get_open_purchase_orders(port="CNNGB")` |
| **IMPACT** | Menyaring tiap material terhadap stok dan konsumsi. Hanya satu yang kritis: **M-4471** (ADC12 aluminium ingot) di KRW1 — 84 t, konsumsi 9,2 t/hari, **habis 13 Sep**. PO pengganti 4500018872 (120 t) mundur dari 14 Sep ke **22 Sep**. Gap produksi: **9 hari** | Impact Analyst → `get_material_stock` · `get_bom_explosion` · `get_sales_order_commitments` |
| **QUANTIFY** | Menelusuri M-4471 lewat BOM ke caliper FG-1120, lalu ke **3 sales order OEM senilai Rp 2,14 miliar**, dengan penalti 0,5%/hari cap 10% — eksposur penalti maksimum **Rp 214 juta** di atas revenue yang terancam | Impact Analyst |
| **GENERATE** | Menyusun lima kandidat mitigasi lewat tiga strategi — percepat sumber lama, ganti sumber, realokasi stok internal — tanpa diberi tahu strateginya apa | Sourcing → `find_alternate_sources` |
| **FILTER** | Menguji tiap kandidat terhadap kendala lokal dan **mengeliminasi dua** atas dasar yang tidak ada hubungannya dengan harga | Compliance → `check_local_constraints` ◆ veto |
| **SIMULATE** | Menghitung yang lolos pada landed cost, tanggal tiba, OTIF, dampak TKDN, eksposur kurs — lalu mengujinya **dalam kombinasi**, dan di situlah jawaban terbaik ditemukan | Simulation → `simulate_scenario` |
| **DECIDE** | Merekomendasikan **C + B** ketimbang jawaban tunggal yang obvious, dan menyatakan risiko sisa yang ia terima alih-alih menyembunyikannya | Supervisor |
| **ACT** | Menerbitkan transfer stok secara otonom (di bawah batas Rp 50 juta) dan mengangkat purchase order sebagai **draft menunggu approval buyer**. Memberi tahu planner, buyer, QA lengkap dengan rantai buktinya | Execution → `create_stock_transfer` · `create_draft_po` ⚠ · `notify` |
| **VERIFY** | Memantau kedua kiriman sampai diterima, memastikan KRW1 dan SBY1 tidak pernah stockout, dan menulis hasilnya ke memory agar event Ningbo berikutnya mulai dari yang sudah dipelajari | Execution → `monitor_shipment` |

**Design target: di bawah 20 menit**, tanpa pendampingan, versus 2–3 hari replanning manual.
Akan diukur terhadap eval suite saat enablement.

## 05 · Lima opsi yang agent susun — dan dua yang ia tolak

| | Opsi | Tiba | Biaya tambahan | TKDN | Putusan & alasan |
|---|---|---|---|---|---|
| **A** | Air freight 40 t dari incumbent SUP-2201 | 11 Sep | +Rp 186 jt | 38,2% | ✅ **Viable** — tercepat, tapi cara termahal untuk membeli sembilan hari yang sama |
| **B** | Supplier lokal PT Logam Andalan (SUP-4417), Gresik, 60 t | 12 Sep | +Rp 94 jt | **41,6% ↑** | ✅ **Viable** — butuh requalifikasi metalurgi 3 hari, masih muat di window. Menaikkan TKDN |
| **C** | Realokasi 55 t stok dari plant SBY1 | 10 Sep | +Rp 22 jt | — | ✅ **Viable** — termurah dan tercepat, tapi menyisakan SBY1 hanya 4 hari cover |
| **D** | Sumber impor baru SUP-3390 (Vietnam) | 26 Sep | +Rp 61 jt | 36,1% ↓ | ❌ **Rejected** — LARTAS untuk negara asal baru menambah 10 hari kerja; tiba 13 hari setelah lini berhenti |
| **E** | Sumber termurah SUP-5501 (Tiongkok), 100 t | 19 Sep | +Rp 48 jt | 34,8% ↓ | ❌ **Rejected** — menjatuhkan konten lokal ke 34,8%, melanggar ambang 40% di kontrak OEM |

> **Ini bagian terpenting seluruh proposal.** Dua baris Rejected adalah bukti *constraint
> reasoning*: opsi E justru yang paling murah. Model biaya murni akan memilihnya dan membuat
> perusahaan melanggar kontrak.

### Rekomendasi agent: C + B paralel

**Move 55 t dari SBY1 segera** (tiba 10 Sep, menutup produksi sampai 19 Sep) **dan** pesan
kualifikasi 60 t ke supplier lokal (tiba 12 Sep, memperpanjang cover ke 25 Sep), menyambung
bersih ke PO 4500018872 pada 22 Sep.

```
stok awal 4 Sep       84 t                        → habis 13 Sep
+ C: 55 t, 10 Sep     55 ÷ 9,2 = 6,0 hari         → cover s/d 19 Sep
+ B: 60 t, 12 Sep     60 ÷ 9,2 = 6,5 hari         → cover s/d 25 Sep
PO 4500018872, 22 Sep 120 t                       → tersambung, tanpa stockout
```

**Hasil: Rp 116 juta versus Rp 186 juta untuk air freight — 38% lebih hemat — sambil melindungi
Rp 2,14 miliar revenue terikat dan menaikkan TKDN dari 38,2% ke 41,6%.**

**Risiko sisa yang agent nyatakan sendiri:** SBY1 berjalan dengan 4 hari cover sampai PO
4500018901 miliknya mendarat 24 Sep. Agent memberi tahu planner SBY1 dan memasukkannya ke daftar
pantau, bukan menganggap rencana sudah selesai.

---

# HALAMAN 3 — Arsitektur, wewenang, dampak, feasibility

## 06 · System architecture — supervised swarm, 10 agent

**Kalimat pembuka wajib:** SIGAP adalah sepuluh agent. Supervisor memegang tujuan dan audit
trail; sembilan spesialis masing-masing memiliki domain keputusan, data, dan tools sendiri.
Ini **supervised swarm**, bukan pipeline, karena dua hal: semua spesialis membaca dan menulis
satu **shared blackboard**, dan spesialis mana pun boleh **oper langsung ke rekannya** saat
menemukan sesuatu di domain rekan itu — tanpa kembali ke supervisor. **Rutenya karena itu
ditentukan saat runtime**, dan tidak ada dua disrupsi yang mengaktifkan set agent yang sama.

> **Siapkan jawaban ini.** Kalau juri bertanya *"bukankah swarm justru punya orchestrator?"* —
> benar, tapi bedakan **orchestrator runtime** (plumbing: menjalankan loop, berbagi konteks,
> membatasi handoff) dari **supervisor agent** (memutuskan siapa jalan dan kapan berhenti).
> Swarm murni punya yang pertama, tidak punya yang kedua. SIGAP punya keduanya — karena
> purchase order yang melanggar kontrak butuh jalur keputusan yang bisa dipertanggungjawabkan,
> bukan yang emergent.

| Agent | Peran | Tools |
|---|---|---|
| **Supervisor · SIGAP Core** | Memasukkan agent ke swarm, menilai kapan bukti cukup, menulis rekomendasi + trade-off + risiko sisa | `detect_disruption` |
| **Impact Analyst** | Menelusuri disrupsi lewat order, stok, BOM ke komitmen yang benar-benar terancam | `get_open_purchase_orders` `get_material_stock` `get_bom_explosion` `get_sales_order_commitments` |
| **Demand & Consumption** | Memiliki sisi permintaan. Konsumsi adalah variabel yang bisa bergerak, bukan konstanta yang diasumsikan semua orang | `get_demand_signal` `get_production_schedule` |
| **Inventory Integrity** | Stok tercatat mana yang benar-benar bisa dipakai — quality hold, batch ditolak, kebijakan safety stock | `get_quality_holds` `get_safety_stock_policy` |
| **Sourcing** | Mencari & mengkualifikasi pasokan alternatif — supplier luar, stok internal, freight dipercepat | `find_alternate_sources` |
| **Logistics & ETA** | Memodelkan tanggal tiba yang tahan uji: distribusi dwell Priok, transhipment, bea cukai, moda angkut | `get_shipment_status` `estimate_eta` |
| **Compliance** ◆ **veto** | Ambang TKDN, izin LARTAS, klausul kontrak, kalender libur. **Penolakannya tidak bisa dikalahkan biaya** | `check_local_constraints` |
| **Simulation** | Menghitung opsi yang lolos beserta kombinasinya pada biaya, OTIF, TKDN, kurs. **Deterministik** | `simulate_scenario` |
| **Precedent** | Memori institusional — apa yang dilakukan pada kejadian serupa, dan hasilnya bagaimana | `search_past_incidents` |
| **Execution** | Menulis balik ke SAP dalam batas wewenang, memberi tahu peran terdampak, memantau sampai diterima | `create_stock_transfer` `create_draft_po` `notify` `monitor_shipment` |

**19 tools, 10 agent.**

### Shared blackboard

Setiap temuan ditulis dengan **provenance**-nya — `LIVE` · `CACHED` · `DERIVED` · `MODELLED` ·
`MISSING` — di tempat yang bisa dibaca semua agent. Inilah yang memungkinkan Inventory Integrity
mengoper quality hold langsung ke Impact Analyst dan memaksa tanggal stockout dihitung ulang,
tanpa supervisor menjadi perantara.

Aturan: kalau input di jalur kritis bernilai `MISSING` atau `MODELLED`, Simulation tidak boleh
mengeluarkan angka penghematan.

### Bukti routing runtime — aktivasi subset

| Disrupsi | Agent yang dipanggil, berurutan |
|---|---|
| Pelabuhan tutup · Ningbo | Impact → Inventory Integrity → Sourcing → Logistics → Compliance → Simulation → **Compliance lagi** → Execution |
| Permintaan OEM naik 40% | **Demand** → Impact → Inventory Integrity → Simulation → Execution *(Sourcing tidak pernah dipanggil)* |
| Batch gagal inspeksi | **Inventory Integrity** → Impact → Sourcing → Compliance → Simulation → Execution |
| Tertahan bea cukai Priok | **Logistics** → Impact → Precedent → Sourcing → Compliance → Execution |
| Supplier hilang sertifikasi TKDN | **Compliance** → Sourcing → Precedent → Simulation → Execution *(tidak ada disrupsi fisik)* |

Titik masuk beda, panjang beda, keanggotaan beda. **Pipeline tetap tidak bisa menghasilkan lima
baris ini.**

### Pemetaan ke interface SAP

| Tool | Interface produksi |
|---|---|
| `get_open_purchase_orders` | `API_PURCHASEORDER_PROCESS_SRV` (EKKO/EKPO) |
| `get_material_stock` | `API_MATERIAL_STOCK_SRV` (MARD/MARC) |
| `get_sales_order_commitments` | `API_SALES_ORDER_SRV` (VBAK/VBAP) |
| `get_bom_explosion` | `API_BILL_OF_MATERIAL_SRV` |
| `get_production_schedule` | `API_PRODUCTION_ORDER_2_SRV` |
| `get_quality_holds` | `API_INSPECTIONLOT_SRV` |
| `get_safety_stock_policy` | `API_PRODUCT_SRV` (MARC) |
| `get_demand_signal` | SAP IBP demand plan · `API_SALES_ORDER_SRV` |
| `get_shipment_status` | SAP Business Network |
| `find_alternate_sources` | Purchasing info record (EINA/EINE) · SAP Ariba Sourcing |
| `check_local_constraints` | Register TKDN · aturan LARTAS · kalender libur |
| `search_past_incidents` | Bedrock Knowledge Bases |
| `create_draft_po` | `API_PURCHASEREQ_PROCESS_SRV` · SAP Ariba Buying |
| `estimate_eta` · `simulate_scenario` | Mesin deterministik internal |

### Lapisan teknologi

| Lapisan | Isi |
|---|---|
| **AWS agentic** | Claude di **Amazon Bedrock** · **Strands Agents SDK** primitif swarm dengan supervisor untuk auditability · **Bedrock AgentCore** runtime, memory, observability · Lambda per tool · **Knowledge Bases** · dibangun dengan **Kiro** |
| **SAP** | **S/4HANA** OData · **Ariba** Sourcing & Buying · **Business Network** · **BAIP / Joule** sebagai permukaan planner |
| **Domain rules** | TKDN, LARTAS, kalender libur, dwell Priok sebagai **dokumen referensi berversi di samping kode** |

## 07 · Batas wewenang agent

| Aksi | Wewenang |
|---|---|
| Baca, analisis, simulasi, rekomendasi | ✅ Otonom |
| Transfer stok, dampak < Rp 50 juta | ✅ Otonom, dilaporkan setelahnya |
| Menerbitkan purchase order | Draft saja — **buyer approve** |
| Supplier baru, atau nilai > Rp 500 juta | **Eskalasi** ke procurement lead |
| Apa pun yang melanggar TKDN atau LARTAS | ❌ **Diblokir** secara desain |

*Bounded autonomy adalah yang membuat sistem ini bisa dideploy di lingkungan terikat kontrak.*

## 08 · Dampak, disetahunkan untuk satu pasang plant

| Ukuran | Hari ini | Dengan SIGAP |
|---|---|---|
| Decision latency | 2–3 hari | **<20 menit** |
| Premi expedite / event | Rp 186 juta | **Rp 116 juta** |
| Planner effort / tahun | 70 hari | **~12 hari** |
| Rasio konten lokal | 38,2% | **41,6%** |

**Sekitar Rp 980 juta per tahun** dalam biaya expedite yang dihindari lintas 14 event, sebelum
memperhitungkan penalti keterlambatan yang tidak jadi dibayar dan rating OEM scorecard yang
terlindungi.

> **Target, bukan hasil pengukuran.** Mengasumsikan 14 event per tahun dan penghematan Rp 70 juta
> yang diturunkan dari worked scenario. Kenaikan TKDN mengasumsikan sumber lokal dipertahankan
> setelah requalifikasi.

## 09 · Feasibility dan langkah berikutnya

### Specified against live interfaces, not mocks
Setiap tool menyasar endpoint nyata. Lapisan ERP ditulis terhadap **SAP S/4HANA Cloud sandbox**
di SAP Business Accelerator Hub — OData services nyata dengan payload shape, pagination, dan
error semantics nyata, bisa dijangkau hari ini dengan API key gratis — dan reasoning ke **Amazon
Bedrock**. Kami menolak simulated backend secara sengaja: dengan sandbox hidup tersedia gratis,
mock hanya menciptakan pekerjaan yang nanti harus dibongkar.

### The constraint engine reads real Indonesian sources
Status sertifikasi TKDN dari register konten lokal Kemenperin, klasifikasi LARTAS dari INSW,
keputusan libur nasional, kurs referensi JISDOR Bank Indonesia, dan buletin siklon tropis BMKG —
diserap ke dalam rule pack berversi alih-alih di-hardcode, sehingga perubahan aturan adalah
perubahan data.

### The only thing we model is the customer
Daftar plant, laju konsumsi, dan klausul penalti kontrak datang dari master data perusahaan
sendiri di hari pertama; kami belum punya pelanggan, jadi kami menyediakan profil representatif.
Tidak ada bagian darinya yang dibentuk agar agent berhasil.

### Build status, stated plainly
Saat submission ini adalah spesifikasi, bukan software berjalan. Yang sudah lengkap: topologi
agent, dua belas tool contract terhadap API SAP yang dipublikasikan, rule set kendala, worked
scenario beserta aritmetikanya, dan eval suite. Implementasi dimulai segera, milestone pertama
skenario Ningbo end-to-end terhadap sandbox. Kami lebih memilih memberi tahu persis di mana kami
berdiri daripada mendemokan sesuatu yang dibangun di atas data karangan.

### Prior art
Sistem multi-agent replenishment open-source membagi pekerjaan ke spesialis paralel di jalur yang
sudah ditentukan. SIGAP berbeda di sumbu yang justru dinilai di sini: rutenya dipilih saat
runtime. Seluruh kode adalah karya sendiri.

### How we will prove it is genuinely autonomous
Eval suite sudah dispesifikasikan — **sepuluh skenario disrupsi**, masing-masing melatih rute
penalaran berbeda. Semuanya **ditulis sebelum implementasi, bukan sesudahnya**, sehingga sistem
tidak bisa disetel agar lulus. Di Demo Day kami mengundang juri memilih satu secara acak: agent
yang cuma hafal skrip akan gagal tes itu, dan milik kami dibangun untuk lulus.

## Pemetaan ke kriteria juri

| Kriteria | Di mana buktinya |
|---|---|
| **Innovation** | Constraint reasoning atas TKDN dan LARTAS — opsi ditolak dengan alasan yang tidak akan ditemukan model biaya mana pun |
| **Feasibility** | Ditulis terhadap sandbox S/4HANA yang bisa dijangkau bebas dan sumber regulasi nyata; produksi adalah tenant swap |
| **Use of AWS / SAP agentic AI** | Bedrock + Strands + AgentCore menggerakkan S/4HANA dan Ariba write-back |
| **Potential impact** | Rp 980 jt/tahun untuk satu pasang plant; polanya berlaku umum di manufaktur Indonesia yang bergantung impor |

---

# LAMPIRAN — tidak masuk hitungan 3 halaman

## A. Eval suite — 10 skenario

| # | Skenario | Menguji |
|---|---|---|
| 1 | Topan menutup Ningbo 6 hari | Baseline — jalur lengkap |
| 2 | Pabrik supplier kebakaran, kapasitas 0 selama 3 minggu | Gangguan tanpa batas waktu jelas |
| 3 | Dokumen COO bermasalah, tertahan bea cukai Priok 12 hari | Disrupsi dalam negeri, bukan di laut |
| 4 | OEM menaikkan permintaan 40% mendadak | Disrupsi sisi permintaan |
| 5 | Tarif impor naik mendadak pada satu HS code | Perubahan ekonomi, bukan fisik |
| 6 | Batch masuk gagal inspeksi, 80 ton ditolak | Stok yang "ada" ternyata tidak terpakai |
| 7 | Transhipment Singapura tertunda | Keterlambatan bertingkat |
| 8 | Rupiah melemah 8% dalam sepekan | Ekonomi opsi impor berubah |
| 9 | Cuti bersama membekukan bea cukai 9 hari | Constraint kalender |
| 10 | Supplier lokal kehilangan sertifikasi TKDN | Constraint berubah di tengah rencana |

Skenario **8, 9, 10** khusus menguji constraint reasoning — bagian paling membedakan.

## B. Status sumber data

| Lapisan | Sumber | Status | Cara tulis di proposal |
|---|---|---|---|
| ERP | S/4HANA Cloud sandbox, `sandbox.api.sap.com` | ✅ terkonfirmasi | Boleh tegas |
| Reasoning | Claude di Amazon Bedrock | ✅ | Boleh tegas |
| Kalender libur | SKB 3 Menteri | ✅ | Boleh tegas |
| Kurs | JISDOR Bank Indonesia | ✅ | Boleh tegas |
| TKDN | Register Kemenperin (P3DN) | ⚠️ belum diverifikasi | *"ingested into a versioned rule pack"* |
| LARTAS | Klasifikasi INSW | ⚠️ belum diverifikasi | *"ingested into a versioned rule pack"* |
| Cuaca / siklon | Buletin TCWC BMKG | ⚠️ bentuk feed belum pasti | *"ingested into a versioned rule pack"* |
| Posisi kapal | AIS (mis. aisstream.io) | ⚠️ belum diverifikasi | Sebut sebagai sumber sinyal, bukan API |

**Jangan naikkan yang ⚠️ jadi klaim API sebelum diverifikasi sendiri.**

## C. Dokumen pendamping

| File | Isi | Cetak |
|---|---|---|
| `sigap-proposal.html` | Proposal 3 halaman — **yang disubmit** | A4 potret |
| `sigap-architecture.html` | Chart arsitektur + runtime routing | A4 **landscape** |
| `sigap-business-model-canvas.html` | Business Model Canvas 9 blok | A4 **landscape** |
| `PROPOSAL.md` | Naskah kanonik (file ini) | — |
| `../sigap/DESIGN.md` | Dokumen kerja tim, sumber semua angka | — |

Batas 3 halaman berlaku untuk `sigap-proposal.html` saja. **Jangan gabungkan** chart arsitektur
atau BMC ke dalam PDF proposal — kirim terpisah kalau form mengizinkan, atau simpan untuk Demo Day.

## D. Checklist submit

- [ ] Placeholder terisi di ketiga file cetak: `[team name]`, `[university]`, `[name 1..3]`
- [ ] Tidak ada klaim present-tense soal kode yang berjalan
- [ ] Angka latensi tertulis sebagai **target**, bukan hasil pengukuran
- [ ] Klaim sumber data ⚠️ tetap sebagai *"ingested into a versioned rule pack"*
- [ ] Proposal tetap 3 halaman setelah export PDF
- [ ] Semua angka konsisten dengan `../sigap/DESIGN.md` §2
- [ ] **Notasi rupiah dieja penuh** — `Rp 70 million`, `Rp 2.14 billion`. Jangan pakai `jt` / `M` di dokumen berbahasa Inggris: juri internasional membaca "M" sebagai juta, bukan miliar — salah baca 1000×
- [ ] Istilah lokal punya penjelasan di halaman tempat ia pertama muncul: TKDN, LARTAS, Priok, OTIF, Ningbo
- [ ] Dinyatakan terbuka bahwa hanya profil pelanggan yang dimodelkan, beserta alasannya
- [ ] Submit sebelum 10 September — **jangan di jam terakhir**
