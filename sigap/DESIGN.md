# SIGAP — Dokumen Desain Kerja

> Sistem Intelijen Gangguan & Antisipasi Pasokan
> AI Agentic Hackathon 2026 · Track 01 Intelligent Supply Chain
> Status: pra-submit · Deadline proposal **10 September 2026**

Dokumen ini adalah sumber kebenaran tunggal untuk tim. Proposal (`proposal/sigap-proposal.html`)
adalah ringkasan 3 halaman dari isi dokumen ini.

---

## 1. Keputusan yang sudah dikunci

| Keputusan | Pilihan | Alasan |
|---|---|---|
| Track | Intelligent Supply Chain | Dampak rupiah paling jelas, cerita paling mudah dijual |
| Nama | **SIGAP** | Akronim yang berarti "tanggap" — mudah diingat juri lokal |
| Vertikal | Manufaktur komponen otomotif Tier-1, Karawang | Impor tinggi + JIT + kontrak OEM berpenalti = disrupsi terasa nyata |
| Pembeda utama | Constraint reasoning atas **TKDN & LARTAS** | Tidak ada model biaya yang menemukan alasan penolakan ini |
| Bentuk agent | **Multi-agent: 1 supervisor + 5 spesialis, 12 tools** | Lihat §3. Kuncinya: routing ditentukan saat runtime, bukan pipeline tetap |
| Orkestrasi | **Strands Agents SDK** (supervisor pattern) | Memenuhi kriteria "Use of AWS Agentic AI" dan mendukung delegasi dinamis |
| Model | **Claude di Amazon Bedrock** | Wajib AWS sebagai inti |
| UI | Streamlit | Agent trace jadi dalam sehari |
| Data | **SAP S/4HANA Cloud sandbox** (`sandbox.api.sap.com`) | Sistem nyata, semantik OData nyata — tidak ada mock yang bisa dipatahkan juri |

---

## 2. Skenario induk — dataset lengkap

Semua angka di bawah ini konsisten satu sama lain. Jangan ubah satu tanpa mengecek turunannya.

### 2.1 Perusahaan

**PT Karya Presisi Nusantara (KPN)** — Tier-1 komponen otomotif.

- Plant **KRW1** Karawang (utama), plant **SBY1** Surabaya
- 340 material aktif, **61% nilai raw material diimpor**, mayoritas via Tanjung Priok
- Produk: brake caliper assembly, transmission housing — untuk OEM dengan kontrak JIT
- Kontrak OEM mensyaratkan **TKDN minimal 40%**; TKDN portfolio saat ini **38,2%**

### 2.2 Material kritis

| Field | Nilai |
|---|---|
| Kode | **M-4471** |
| Nama | Aluminium alloy ingot ADC12 |
| Plant | KRW1 |
| Stok awal (4 Sep) | **84 ton** |
| Konsumsi harian | **9,2 ton/hari** |
| Cover | 84 ÷ 9,2 = **9,1 hari → habis 13 Sep** |
| Dipakai untuk | FG-1120 (brake caliper assembly) |

### 2.3 PO terdampak

| PO | Material | Qty | ETA awal | ETA revisi | Supplier |
|---|---|---|---|---|---|
| **4500018872** | M-4471 | 120 t | 14 Sep | **22 Sep** | SUP-2201 (Ningbo) |
| 4500018901 | M-4471 | 90 t | 24 Sep | 24 Sep | SUP-2201 → plant SBY1 |
| + 10 PO lain | 4 material | — | — | tergeser | 3 supplier |

Total 12 PO lewat Ningbo, nilai **Rp 8,4 miliar**. Hanya M-4471 yang kritis.

### 2.4 Komitmen hilir

3 sales order OEM untuk FG-1120, total **Rp 2,14 miliar**.
Penalti keterlambatan **0,5%/hari, cap 10%** → eksposur penalti maksimum **Rp 214 juta**.

### 2.5 Pemicu disrupsi

> Topan menutup Pelabuhan Ningbo–Zhoushan **8–13 September** (6 hari).

Gap produksi yang harus ditutup: **13 Sep → 22 Sep = 9 hari**.

### 2.6 Lima opsi dan hasilnya

| | Opsi | Tiba | Biaya tambahan | TKDN | Putusan |
|---|---|---|---|---|---|
| A | Air freight 40 t dari SUP-2201 | 11 Sep | +Rp 186 jt | 38,2% | Layak, termahal |
| B | Supplier lokal PT Logam Andalan (SUP-4417), Gresik, 60 t | 12 Sep | +Rp 94 jt | **41,6% ↑** | Layak, perlu requalifikasi metalurgi 3 hari |
| C | Realokasi 55 t dari SBY1 | 10 Sep | +Rp 22 jt | — | Layak, SBY1 jadi tipis |
| D | Supplier baru SUP-3390 (Vietnam) | 26 Sep | +Rp 61 jt | 36,1% ↓ | **DITOLAK** — LARTAS negara asal baru butuh 10 hari kerja; tiba 13 hari setelah lini berhenti |
| E | Supplier termurah SUP-5501 (Tiongkok), 100 t | 19 Sep | +Rp 48 jt | 34,8% ↓ | **DITOLAK** — TKDN jatuh ke 34,8%, melanggar ambang kontrak OEM 40% |

### 2.7 Rekomendasi agent: C + B

```
stok awal 4 Sep            84 t              habis 13 Sep
+ C: 55 t tiba 10 Sep      55 ÷ 9,2 = 6,0 hari   → cover s/d 19 Sep
+ B: 60 t tiba 12 Sep      60 ÷ 9,2 = 6,5 hari   → cover s/d 25 Sep
PO 4500018872 mendarat 22 Sep                    → tersambung, tidak ada stockout
```

- **Biaya: Rp 116 juta** vs Rp 186 juta air freight → **hemat Rp 70 juta (38%)**
- Melindungi **Rp 2,14 miliar** pendapatan terikat
- TKDN naik **38,2% → 41,6%**
- **Risiko sisa yang diakui agent:** SBY1 tinggal 4 hari cover sampai PO 4500018901 mendarat 24 Sep. Agent memberi tahu planner SBY1 dan memasukkannya ke daftar pantau — tidak menganggap kasus selesai.

Waktu tempuh agent: **18 menit**, tanpa pendampingan.

### 2.8 Sumber data — semuanya nyata, tidak ada mock

Ini perubahan penting: **tidak ada satu pun komponen yang di-mock.**

| Lapisan | Sumber nyata | Status | Cara akses |
|---|---|---|---|
| **ERP** | SAP S/4HANA Cloud **sandbox** di SAP Business Accelerator Hub | ✅ terkonfirmasi | `https://sandbox.api.sap.com/` · API key gratis dari akun SAP ID di `api.sap.com` |
| **Reasoning** | Claude di Amazon Bedrock | ✅ | Akun AWS, pay-as-you-go |
| **TKDN** | Register TKDN Kemenperin (P3DN) | ⚠️ verifikasi | Publik. Kemungkinan perlu ingest manual → rule pack berversi |
| **LARTAS** | Klasifikasi larangan/pembatasan INSW | ⚠️ verifikasi | Publik. Ingest ke rule pack |
| **Kalender libur** | SKB 3 Menteri libur nasional & cuti bersama | ✅ | Publik, terbit tahunan |
| **Kurs** | JISDOR Bank Indonesia | ✅ | Terbit harian |
| **Cuaca / siklon** | Buletin TCWC BMKG | ⚠️ verifikasi bentuk feed | Publik. Belum tentu JSON API bersih |
| **Posisi kapal** | AIS (mis. aisstream.io free tier) | ⚠️ verifikasi | Perlu daftar |

**Aturan penulisan:** yang ✅ boleh diklaim tegas di proposal. Yang ⚠️ ditulis sebagai
*"ingested into a versioned rule pack"* — jujur, dan tetap bukan mock, karena datanya nyata
walau cara masuknya bisa manual.

### 2.9 Satu-satunya yang dimodelkan: profil pelanggan

Daftar plant, laju konsumsi, dan klausul penalti kontrak. Alasannya sederhana: **kita belum punya
pelanggan.** Setiap deployment mengisi ini dari master data miliknya sendiri di hari pertama.

Tulis ini terang-terangan di proposal. Juri jauh lebih menghargai batas yang dinyatakan jelas
daripada klaim yang tidak bisa dipertanggungjawabkan — dan ini menghapus satu-satunya celah
"tapi datanya bohongan" yang bisa dipakai untuk menjatuhkan skor feasibility.

## 3. Multi-agent system — supervised swarm

### 3.1 Kenapa "supervised swarm", bukan "swarm" saja

Dua istilah ini sering dicampur. Pisahkan dengan tegas supaya siap kalau juri bertanya:

| | Orchestrator runtime | Supervisor agent |
|---|---|---|
| Apa | Yang menjalankan loop, berbagi konteks, membatasi handoff & timeout | Agent yang memutuskan siapa jalan berikutnya dan kapan berhenti |
| Swarm murni | **Ada** — Strands `Swarm`, OpenAI Swarm, semua punya ini | **Tidak ada** — agent saling oper sendiri |
| SIGAP | Ada | **Ada** |

Jadi benar bahwa swarm tetap punya orchestrator — tapi itu **plumbing**, bukan pengambil
keputusan. Yang tidak dimiliki swarm murni adalah supervisor yang menilai.

**SIGAP memakai keduanya** karena lingkungan terikat kontrak menuntut audit trail: harus ada
yang bertanggung jawab atas rekomendasi akhir dan bisa ditanya "kenapa". Swarm murni jalurnya
emergent — sulit diaudit dan sulit dibatasi. Itu sebabnya `max_handoffs` dan timeout ada di
setiap implementasi swarm.

**Kalimat siap pakai untuk juri:** *"Swarm primitives for context sharing and peer handoff,
under a supervisor for auditability — because a purchase order that breaches a contract needs
an accountable decision path, not an emergent one."*

### 3.2 Peta agent — 1 supervisor + 9 spesialis

```
                    ┌──────────────────────────────────────────┐
                    │  SUPERVISOR · SIGAP Core                  │
                    │  detect_disruption                        │
                    │  • memasukkan agent ke swarm              │
                    │  • menilai kapan bukti cukup              │
                    │  • menulis rekomendasi + risiko sisa      │
                    └───────────────────┬──────────────────────┘
                                        │ admits ↓   evidence ↑
   ┌──────────┬──────────┬──────────┬───┴──────┬──────────┐
   ▼          ▼          ▼          ▼          ▼
 Impact    Demand &   Inventory  Sourcing   Logistics
 Analyst   Consumpt.  Integrity             & ETA
   ▲          ▲          ▲          ▲          ▲
   └──────────┴──────────┴──────────┴──────────┘   ← handoff peer-to-peer
   ┌──────────┬──────────┬──────────┐                 (tanpa lewat supervisor)
   ▼          ▼          ▼          ▼
 Compliance  Simulation Precedent  Execution
  ◆ veto                            ⚠ gate
   └──────────┴──────────┴──────────┘
                    │
          SHARED BLACKBOARD
     (DynamoDB · AgentCore Memory)
      semua tulis & baca di sini
```

### 3.3 Peran & tools — 19 tools, 10 agent

| Agent | Peran | Tools | Interface |
|---|---|---|---|
| **Supervisor** | Memasukkan agent ke swarm, menilai kecukupan bukti, menulis rekomendasi & risiko sisa | `detect_disruption` | EventBridge |
| **Impact Analyst** | Menelusuri disrupsi ke komitmen yang benar-benar terancam | `get_open_purchase_orders` `get_material_stock` `get_bom_explosion` `get_sales_order_commitments` | `API_PURCHASEORDER_PROCESS_SRV` `API_MATERIAL_STOCK_SRV` `API_BILL_OF_MATERIAL_SRV` `API_SALES_ORDER_SRV` |
| **Demand & Consumption** | Memiliki sisi permintaan. Konsumsi adalah variabel, bukan konstanta | `get_demand_signal` `get_production_schedule` | SAP IBP demand plan · `API_PRODUCTION_ORDER_2_SRV` |
| **Inventory Integrity** | Stok tercatat mana yang benar-benar bisa dipakai — quality hold, batch ditolak, safety stock | `get_quality_holds` `get_safety_stock_policy` | `API_INSPECTIONLOT_SRV` · `API_PRODUCT_SRV` (MARC) |
| **Sourcing** | Mencari & mengkualifikasi pasokan alternatif | `find_alternate_sources` | EINA/EINE · SAP Ariba Sourcing |
| **Logistics & ETA** | Memodelkan tanggal tiba yang tahan uji: dwell Priok, transhipment, clearance, moda | `get_shipment_status` `estimate_eta` | SAP Business Network · model deterministik |
| **Compliance** ◆ veto | TKDN, LARTAS, klausul kontrak, kalender. **Penolakannya tidak bisa dikalahkan biaya** | `check_local_constraints` | Register TKDN · INSW · kalender |
| **Simulation** | Menghitung opsi yang lolos + kombinasinya, termasuk eksposur kurs. **Deterministik** | `simulate_scenario` | Mesin internal |
| **Precedent** | Memori institusional — apa yang pernah dilakukan pada kasus serupa, hasilnya bagaimana | `search_past_incidents` | Bedrock Knowledge Bases |
| **Execution** | Menulis balik ke SAP dalam batas wewenang, memberi tahu, memantau sampai diterima | `create_stock_transfer` `create_draft_po` `notify` `monitor_shipment` | `API_PURCHASEREQ_PROCESS_SRV` · SAP Ariba Buying |

### 3.4 Uji kelayakan agent

Sebuah agent layak berdiri sendiri **kalau ia bisa tidak setuju dengan agent lain.**
Kalau hanya menghitung dan tidak pernah punya pandangan yang bertabrakan, itu tool.

| Agent | Contoh pertentangan nyata |
|---|---|
| Demand vs Impact | Impact: habis 13 Sep. Demand: order OEM naik 40%, jadi habis 9 Sep |
| Inventory Integrity vs Impact | Impact: ada 84 t. Integrity: 23 t kena quality hold, safety stock menuntut 15 t → tersedia 46 t |
| Logistics vs Sourcing | Sourcing: supplier sanggup 12 Sep. Logistics: dwell Priok + clearance → 15 Sep, opsi gugur |
| Precedent vs Simulation | Simulation: opsi B termurah. Precedent: supplier itu gagal requalifikasi 14 bulan lalu |
| Compliance vs semua | Veto — opsi termurah melanggar ambang TKDN kontrak |

**Ditolak sebagai agent terpisah:** FX/Finance (aritmetika, tidak pernah bisa tidak setuju →
masuk Simulation) · Negotiation (butuh berhari-hari, window disrupsi hitungan jam).

### 3.5 Shared blackboard

Semua agent menulis dan membaca satu papan bersama. Tiap temuan membawa **provenance**:
`LIVE` · `CACHED` · `DERIVED` · `MODELLED` · `MISSING`.

Aturan: kalau input di jalur kritis bernilai `MISSING` atau `MODELLED`, Simulation tidak boleh
mengeluarkan angka penghematan — supervisor melaporkan apa yang kurang.

Ini yang memungkinkan handoff peer-to-peer: Inventory Integrity menulis quality hold ke papan,
Impact Analyst membacanya dan menghitung ulang tanggal stockout sendiri, tanpa supervisor.

### 3.6 Bukti routing runtime — aktivasi subset

| Skenario | Agent yang dipanggil |
|---|---|
| 1 · Ningbo tutup | Impact → Inventory Integrity → Sourcing → Logistics → Compliance → Simulation → **Compliance lagi** → Execution |
| 4 · Permintaan naik 40% | **Demand** → Impact → Inventory Integrity → Simulation → Execution *(Sourcing tidak dipanggil)* |
| 6 · Batch gagal inspeksi | **Inventory Integrity** → Impact → Sourcing → Compliance → Simulation → Execution |
| 3 · Tertahan bea cukai | **Logistics** → Impact → Precedent → Sourcing → Compliance → Execution |
| 10 · Supplier hilang TKDN | **Compliance** → Sourcing → Precedent → Simulation → Execution *(tidak ada disrupsi fisik)* |

Titik masuk beda, panjang beda, keanggotaan beda. **Pipeline tetap tidak bisa menghasilkan
lima baris ini.** Ini bukti terkuat untuk kriteria *autonomous multi-step reasoning*.

## 4. Constraint engine

Empat aturan yang dijalankan `check_local_constraints`. Ini isi `references/`.

| Aturan | Logika | Efek |
|---|---|---|
| **TKDN** | Hitung ulang rasio konten lokal portfolio kalau supplier ini dipakai | Blokir kalau hasilnya < ambang kontrak (40%) |
| **LARTAS** | Negara asal baru → tambah 10 hari kerja untuk izin impor | Geser ETA; sering membuat opsi jadi terlambat |
| **Kalender libur** | Cuti bersama & libur nasional membekukan bea cukai + logistik | Tambah hari kalender ke semua ETA yang melintasinya |
| **Dwell time Priok** | Variabel, bukan konstanta — pakai distribusi historis | ETA impor punya rentang, bukan satu tanggal |

---

## 5. Batas wewenang agent

| Aksi | Wewenang |
|---|---|
| Baca, analisis, simulasi, rekomendasi | Otonom penuh |
| Transfer stok antar-plant, dampak < Rp 50 jt | Otonom, lapor sesudahnya |
| Terbitkan purchase order | **Draft saja** — buyer yang approve |
| Supplier baru, atau nilai > Rp 500 jt | Eskalasi ke procurement lead |
| Apa pun yang melanggar TKDN / LARTAS | Diblokir secara desain |

Bounded autonomy bukan keterbatasan — ini yang membuat solusinya bisa dipakai di lingkungan
manufaktur yang terikat kontrak. Tulis ini di proposal.

---

## 6. Arsitektur & struktur repo

```
sigap/
├── SKILL.md                  ← definisi & metodologi agent (pola serenity-skill)
├── references/               ← pengetahuan domain, terpisah dari kode, bisa diaudit juri
│   ├── tkdn-rules.md
│   ├── lartas-procedure.md
│   ├── holiday-calendar.md
│   └── priok-dwell-time.md
├── agents/                   ← supervisor + 5 spesialis
│   ├── supervisor.py
│   ├── impact_analyst.py
│   ├── sourcing.py
│   ├── compliance.py
│   ├── simulation.py
│   └── execution.py
├── tools/                    ← 12 tools, satu file per tool
├── clients/
│   ├── sap_s4.py             ← satu OData client; base URL + key dari env
│   │                            sandbox hari ini, tenant pelanggan besok
│   ├── registers.py          ← TKDN · LARTAS · kalender · JISDOR → rule pack
│   └── signals.py            ← BMKG · notice pelabuhan · AIS
├── graph.py                  ← Strands supervisor pattern + Bedrock
├── evals/                    ← 10 skenario disrupsi ⭐ bukti otonomi
└── app.py                    ← Streamlit, tampilan agent trace
```

**Lapisan:**

| Lapisan | Teknologi |
|---|---|
| Reasoning | Claude di Amazon Bedrock |
| Orkestrasi | Strands Agents SDK (supervisor + 5 sub-agent) · Bedrock AgentCore (runtime, memory, observability) |
| Tools & data | AWS Lambda per tool · DynamoDB untuk memory · Bedrock Knowledge Bases untuk kontrak & histori insiden |
| Enterprise | SAP S/4HANA OData · SAP Ariba · SAP Business Network · SAP BAIP / Joule |
| Dibangun dengan | Kiro (spec-driven development) |

---

## 7. Eval suite — 10 skenario

Ini yang mengubah klaim "otonom" jadi sesuatu yang bisa dibuktikan.
Di Demo Day, juri memilih satu secara acak.

| # | Skenario | Menguji |
|---|---|---|
| 1 | Topan menutup Ningbo 6 hari | Baseline — jalur lengkap |
| 2 | Pabrik supplier kebakaran, kapasitas 0 selama 3 minggu | Gangguan tanpa batas waktu jelas |
| 3 | Dokumen COO bermasalah, tertahan bea cukai Priok 12 hari | Disrupsi di dalam negeri, bukan di laut |
| 4 | OEM menaikkan permintaan 40% mendadak | Disrupsi dari sisi permintaan, bukan pasokan |
| 5 | Tarif impor naik mendadak pada satu HS code | Perubahan ekonomi, bukan fisik |
| 6 | Batch masuk gagal inspeksi, 80 ton ditolak | Stok yang "ada" ternyata tidak terpakai |
| 7 | Transhipment Singapura tertunda | Keterlambatan bertingkat |
| 8 | Rupiah melemah 8% dalam sepekan | Ekonomi opsi impor berubah |
| 9 | Cuti bersama membekukan bea cukai 9 hari | Constraint kalender |
| 10 | Supplier lokal kehilangan sertifikasi TKDN | Constraint TKDN berubah di tengah jalan |

Skenario 8, 9, 10 khusus menguji constraint reasoning — bagian yang paling membedakan.

---

## 8. Prior art — dua repo referensi

### `YUHAO-corn/manufacturing-agents`
Replenishment manufaktur, 6 agent paralel via LangGraph, Streamlit + MongoDB + Redis,
model DashScope & Google AI. Klaim: biaya inventori −25%, stockout −62%.

**Diambil:** Streamlit untuk UI cepat · framing metrik before/after · prinsip "teknologi matang".
**Diambil sebagian:** pemecahan peran jadi agent spesialis — tapi dengan perbedaan penting,
SIGAP memakai **supervisor pattern dengan routing runtime**, bukan fan-out paralel dengan jalur
yang sudah ditentukan di awal. Peran spesialisnya mirip; cara supervisor memutuskan siapa yang
dipanggil dan kapan berhenti itu yang berbeda, dan itulah yang dinilai juri.
**Tidak diambil:** MongoDB/Redis · data source Tiongkok (TuShare, JuHe) · **lapisan model
non-AWS** — ini wajib pindah ke Bedrock.

### `muxuuu/serenity-skill`
Metodologi riset investasi yang dikemas sebagai Agent Skill: `SKILL.md` + `references/` +
`assets/` + `scripts/` + `evals/`.

**Diambil:** struktur `SKILL.md` + `references/` untuk memisahkan pengetahuan domain dari kode ·
`evals/` sebagai bukti otonomi · output terstruktur berbasis JSON · hierarki bukti — tiap klaim
agent harus menyebut sumbernya (nomor PO, pasal kontrak, sertifikat TKDN).

### ⚠️ Aturan orisinalitas
Hackathon mensyaratkan *"original work created during the hackathon period"*. Pakai keduanya
sebagai referensi arsitektur — aman. Fork lalu ganti nama — berisiko diskualifikasi dan mudah
ketahuan karena kedua repo publik. **Ambil polanya, tulis kodenya sendiri.**

---

## 9. Rencana 6 hari

| Hari | Target | PIC |
|---|---|---|
**Tahap 1 — submit proposal (keputusan tim: belum ada kode sampai 10 Sep).**

| Hari | Target | PIC |
|---|---|---|
| **Kam 4 – Jum 5 Sep** | Kunci skenario & angka · pastikan seluruh aritmetika §2 konsisten | Domain + Data |
| **Sab 6 – Min 7 Sep** | Rapikan spesifikasi: 12 tool contract, rule set, eval suite 10 skenario | Semua |
| **Sen 8 Sep** | Isi placeholder · review silang klaim vs kenyataan | Semua |
| **Sel 9 Sep** | Export PDF ketiga dokumen · cek proposal tetap 3 halaman | Frontend |
| **Rab 10 Sep** | Buffer + submit — **jangan di jam terakhir** | Semua |

**Tahap 2 — sesudah lolos kualifikasi:** ambil API key SAP Business Accelerator Hub, aktifkan
Bedrock, bangun `clients/sap_s4.py`, lalu skenario Ningbo end-to-end.

**Pembagian:**
- **Backend** → tools + agent loop (Strands + Bedrock)
- **Data/ML** → dataset sintetis + mesin `simulate_scenario` (matematika cost/OTIF/TKDN)
- **Frontend** → Streamlit agent trace + visual proposal
- **Domain** → skenario, angka, narasi bisnis (mengisi halaman 1 proposal)

---

## 9b. Deliverable

| File | Isi | Format cetak |
|---|---|---|
| `proposal/sigap-proposal.html` | Proposal 3 halaman | A4 potrait, Print → Save as PDF |
| `proposal/sigap-architecture.html` | Chart arsitektur sistem + runtime routing | A4 **landscape** |
| `proposal/sigap-business-model-canvas.html` | Business Model Canvas 9 blok | A4 **landscape** |
| `sigap/DESIGN.md` | Dokumen kerja tim (file ini) | — |

---

## 10. Checklist sebelum submit

- [ ] Placeholder terisi di **kedua** file: nama tim, universitas, 3 nama anggota
- [ ] **Tidak ada klaim present-tense soal kode yang berjalan.** Halaman 3 harus berbunyi "specification, not running software" selama belum ada implementasi
- [ ] Angka latensi ditulis sebagai *target*, bukan hasil pengukuran
- [ ] Maksimal 3 halaman — cek setelah export PDF
- [ ] Semua angka konsisten dengan §2 dokumen ini
- [ ] Klaim sumber data yang ⚠️ di §2.8 tetap ditulis sebagai "ingested into a versioned rule pack", jangan dinaikkan jadi klaim API sebelum diverifikasi
- [ ] Disebutkan terus terang bahwa hanya profil pelanggan yang dimodelkan, beserta alasannya
- [ ] Tidak ada kode hasil fork dari dua repo referensi

---

## 11. Jebakan yang harus dihindari

1. **Bikin dashboard dulu.** Dashboard tanpa agent = kalah. Agent tanpa dashboard = masih bisa menang.
2. **Menambah agent atau tools.** Enam agent, 12 tools — cukup. Yang dinilai kedalaman reasoning dan cara supervisor memilih rute, bukan jumlah kotak di diagram.
3. **Jangan pakai mock sama sekali.** Sandbox SAP gratis dan nyata — memakai mock padahal sandbox tersedia adalah kelemahan yang tidak perlu. Satu-satunya yang boleh dimodelkan adalah profil pelanggan, dan itu harus dinyatakan terbuka.
4. **Agent yang selalu benar.** Agent yang mengakui trade-off dan minta approval terlihat jauh lebih matang.
5. **Biaya dihitung LLM.** Harus deterministik, kalau tidak seluruh klaim penghematan bisa dipatahkan.
