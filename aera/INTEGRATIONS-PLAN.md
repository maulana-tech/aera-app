# Rencana: agen yang terhubung ke tool sungguhan (MCP, skills, integrasi)

Tujuan: setiap agen bisa memakai tool yang dipakai bisnis sehari-hari. Contohnya Marketing posting ke
media sosial, Sales mengelola Meta Ads dan lead, dan semua agen bisa membaca dan menulis Docs/Sheets.
Pengguna cukup menghubungkan akun sekali, lalu tim yang mengerjakan.

Syaratnya tidak berubah dari prinsip AERA: **agen boleh bertindak, tapi setiap tindakan keluar
dijaga Guardian, punya batas, dan bisa dihentikan.** Fitur baru tidak boleh membuka celah yang
selama ini ditutup.

---

## 0. Titik awal (sudah ada di kode)

| Bagian | Keadaan sekarang | File |
|---|---|---|
| MCP keluar | Tool dari server lain di-namespace `mcp__server__tool` dan diberikan per agen. **Hanya tool baca**; tool yang menulis tidak pernah diberikan | `clients/mcp_client.py`, `core/registry.py` |
| Composio | Mengirim Gmail; OAuth disimpan Composio, AERA hanya memegang project key | `clients/composio.py` |
| Capability | 7 capability terbuka + 3 yang dikunci (guardian, treasury, supervisor) | `agents/roles.py` |
| Skill | 4 prosedur: fulfil_order, pay_for_something, screen_for_manipulation, answer_a_customer | `core/skills.py` |
| Aksi keluar | `raise_action(kind, …)` → Guardian (allow/warn/block) → eksekusi di `settle.py` | `core/actions.py`, `settle.py` |
| Persetujuan | `approval_required` di profil bisnis | `core/business.py` |

Yang belum ada: **jalur tulis ke platform luar yang dijaga.** Itu inti rencana ini.

---

## 1. Fase 0 — Model murah dulu (1 hari)

Integrasi menambah panggilan model, jadi biaya per panggilan harus turun dulu.

1. Uji **DeepSeek V4.1 Flash** (TEE, $0.30/$1.20 per juta token): tool calling sebagai Supervisor dan
   format attestation-nya.
2. Kalau lolos: Supervisor dan Guardian pindah dari Kimi K3 ($3.30/$16.50), dan fallback dari
   GLM 5.3 ke DeepSeek V4.1 Flash. Spesialis tetap GLM 5.3 Flash.
3. Harga sudah diambil live dari daftar model NEAR AI (commit `92940b3`).

**Selesai bila:** satu order penuh berjalan di model baru, semua bukti attested, dan biayanya di
bawah $0.15.

---

## 2. Desain: dari akun terhubung sampai tindakan yang dijaga

```
 Akun terhubung        Capability          Tool                      Penjaga
 (Connector)           (izin per agen)     (baca / tulis)
 ───────────────       ────────────        ───────────────────       ─────────────────────────
 Composio OAuth   ──►  social         ──►  social.read_*  ─────────► langsung (data = tidak dipercaya)
 (Meta, LinkedIn,      ads                 social.publish_post ────► raise_action("publish_post")
  Google, HubSpot)     workspace           ads.create_draft ───────► raise_action("ad_change")
 MCP server lain       crm                 sheets.append_row ──────► raise_action("doc_write")
                                                                      │
                                                                      ▼
                                              Guardian (aturan di kode) ─► allow / warn / block
                                              Batas di profil (anggaran iklan, jumlah post/hari)
                                              Persetujuan orang bila perlu ─► settle.py mengeksekusi
```

### 2.1 Connector: satu lapisan untuk semua akun
- **Composio sebagai jalur utama** untuk SaaS ber-OAuth: Meta Ads, Facebook Pages, LinkedIn,
  LinkedIn Ads, Google Sheets/Docs/Drive, Gmail, HubSpot, Notion, Slack. Token OAuth disimpan
  Composio, **AERA tidak pernah memegangnya**, sama seperti Gmail sekarang.
- **MCP server pihak lain** untuk yang tidak ada di Composio. Ini sudah didukung untuk tool baca.
- File baru `clients/connectors.py`: daftar akun terhubung, toolkit, versi yang dipin, dan scope.
  Satu antarmuka `call(connector, tool, args)` untuk Composio maupun MCP.
- **Versi toolkit dipin** (seperti `GMAIL_VERSION` sekarang), supaya perubahan di sisi Composio tidak
  diam-diam mengubah arti sebuah aksi.

### 2.2 Capability baru (`agents/roles.py`)

| Capability | Baca | Tulis (selalu lewat `raise_action`) |
|---|---|---|
| `social` | post, komentar, insight halaman | `publish_post`, `schedule_post`, `reply_comment` |
| `ads` | kampanye, ad set, insight, pengeluaran | `ad_change`: buat draf, ubah anggaran, pause/resume |
| `workspace` | Docs, Sheets, Drive | `doc_write`: buat/ubah dokumen, tambah baris sheet |
| `crm` | lead, kontak, deal | `crm_update`: buat atau ubah lead dan deal |
| `inbox` | email masuk (Gmail) | — (membalas tetap lewat `messaging`) |

`ads` **tidak** dikunci ke Treasurer, karena mengelola iklan memang pekerjaan Sales/Marketing. Tapi
setiap perubahan anggaran tunduk pada batas uang (bagian 2.4).

### 2.3 Jalur tulis yang dijaga — perubahan inti
Hari ini `core/registry.py` membuang semua tool remote yang menulis. Itu diganti dengan:

1. Tool tulis dari connector **tidak dieksekusi langsung oleh agen.** Agen memanggil tool AERA
   (misalnya `publish_post`), yang memanggil `raise_action(kind, payload)`.
2. Guardian memeriksa payload dengan aturan per jenis aksi (bagian 2.5).
3. `allow` → `settle.py` mengeksekusi lewat connector; `warn` → menunggu orang; `block` → final.
4. **Tool tulis MCP yang tidak dikenal** tetap tidak diberikan secara default. Owner bisa
   mengizinkannya per tool, dan tool itu selalu berjalan sebagai aksi
   `external_write` yang **wajib disetujui orang**.
5. Setiap aksi idempoten (`idempotency_key` sudah ada), jadi retry tidak menghasilkan dua post atau
   dua iklan.

### 2.4 Batas baru di profil bisnis (`core/business.py`)

| Batas | Default | Arti |
|---|---|---|
| `ads.max_daily_budget_usd` | $10 | Total anggaran harian semua kampanye yang boleh diatur agen sendiri |
| `ads.max_change_pct` | 20% | Kenaikan anggaran lebih dari ini perlu orang |
| `social.max_posts_per_day` | 3 | Batas posting otomatis |
| `approval_required` (tambahan) | `publish_post`, `ad_launch`, `ad_budget_increase` | Selalu perlu orang, sampai owner melonggarkannya |

Pengeluaran iklan **tidak lewat vault** (dibayar ke Meta dengan kartu atau saldo akun iklan), jadi
batasnya ditegakkan dua kali: di Guardian, dan dengan **spending limit di akun iklan Meta itu
sendiri**. Ini dipasang owner saat onboarding dan dicek `manage.py ready`.

### 2.5 Aturan Guardian baru (`core/guardian.py`)
- **Isi publik:** injection, klaim terlarang dari profil ("promise investment returns"), data sensitif
  (input pelanggan, kontak, brief yang belum terbit), dan data pelanggan lain. Semua dicek sebelum post
  atau iklan terbit.
- **Data dari luar tidak dipercaya:** komentar, DM, dan isi email masuk diperlakukan sebagai *data*,
  bukan perintah. Prompt injection lewat komentar media sosial adalah risiko nyata.
- **Uang iklan:** batas di 2.4, ditambah penolakan target atau negara yang dilarang profil.
- **Kill switch:** menghentikan semua connector sekaligus, termasuk pause semua kampanye aktif lewat
  `ads.pause_all` (aksi darurat yang boleh dijalankan Guardian sendiri).

---

## 3. Peran agen setelah integrasi

| Agen | Tool baru | Contoh pekerjaan otomatis | Perlu orang |
|---|---|---|---|
| **Marketing** | `social`, `workspace` | menyusun kalender konten di Sheets, menulis post, menjadwalkan, membaca insight mingguan | post pertama ke platform baru, post di luar kalender |
| **Sales** | `ads`, `crm`, `workspace` | laporan performa Meta Ads, draf kampanye baru, kualifikasi lead dari form iklan ke CRM/Sheets | meluncurkan kampanye, menaikkan anggaran > 20% |
| **Customer Support** | `inbox`, `crm` | membaca email masuk, menyiapkan balasan, mencatat tiket | pesan pertama ke kontak baru, refund |
| **Writer** | `workspace` | mengekspor deliverable ke Google Docs selain PDF | — |
| **Analyst** | `workspace`, `ads` (baca) | laporan mingguan di Sheets: pendapatan, biaya, ROAS | — |
| **Fulfilment** | `workspace` | mengirim deliverable lewat link Drive, mencatat order ke Sheets | — |
| **Procurement** | `research`, `workspace` | membandingkan vendor di sheet | vendor baru |
| **Treasurer** | (tetap) | — | sesuai batas vault |

---

## 4. Skill baru (`core/skills.py`)

| Skill | Siapa | Langkah singkat |
|---|---|---|
| `weekly_content_calendar` | Marketing | baca insight → usulkan 5 post → tulis ke Sheets → minta persetujuan sekali untuk satu minggu |
| `publish_social_post` | Marketing | ambil dari kalender → cek Guardian → terbitkan → catat link dan waktu |
| `launch_ad_campaign` | Sales | tujuan dan anggaran → draf kampanye (status *paused*) → persetujuan orang → aktifkan |
| `weekly_ads_report` | Sales, Analyst | insight 7 hari → hitung CPA/ROAS → tulis ke Sheets → ringkasan di Chat |
| `qualify_lead` | Sales | lead masuk → cocokkan offering → skor → simpan ke CRM → draf balasan |
| `sync_orders_to_sheet` | Fulfilment | setiap order paid/delivered → tambah baris di Sheets bisnis |
| `answer_inbox` | Support | email masuk → klasifikasi → draf balasan → Guardian |

Setiap skill tetap dicek terhadap registry (tool yang tidak ada akan ketahuan saat start) dan dimeter
pemakaiannya, seperti sekarang.

---

## 5. Antarmuka

1. **Halaman Integrations** (gabungan halaman MCP sekarang + akun Composio):
   - tombol *Connect* per platform (alur OAuth Composio), status, scope yang diminta;
   - akses per agen: centang agen mana yang boleh memakai akun itu, dan apakah baca saja atau
     baca dan tulis;
   - tombol *Disconnect*.
2. **Kartu persetujuan yang bisa dibaca:** pratinjau post (teks, gambar, platform), dan perubahan
   iklan sebagai diff ("anggaran $5 → $8/hari, +60%: di atas batas 20%").
3. **Onboarding langkah baru (opsional):** "Hubungkan tool yang kamu pakai", yang otomatis
   mengusulkan capability ke agen yang relevan.
4. **Log:** setiap aksi ke platform luar tercatat dengan link hasilnya (URL post, id kampanye).

---

## 6. Privasi dan keamanan

| Risiko | Penanganan |
|---|---|
| Token akun bocor | Disimpan Composio, tidak di AERA; scope seminimal mungkin per toolkit |
| Data pelanggan keluar ke platform | Guardian memeriksa setiap payload tulis; data sensitif diblok, PII disensor bila perlu |
| Prompt injection dari komentar/DM/email | Semua data dari connector berlabel *untrusted* dan tidak boleh menjadi dasar sebuah aksi. **Aturan ini harus dibangun ulang di Fase 1:** komentar di `core/registry.py` merujuk ke `tools/execution.py`, file yang sudah terhapus |
| Agen menghabiskan anggaran iklan | Batas di profil + Guardian + spending limit di akun Meta; kill switch mem-pause semua kampanye |
| Post salah terbit | Default perlu persetujuan; kalender mingguan disetujui sekali; ada aksi `delete_post` |
| Model melihat data platform | Tetap di model TEE NEAR AI. Platform pihak ketiga (Meta, Google) tentu melihat apa yang dikirim ke sana, dan itu disebut jelas di UI |

---

## 7. Urutan kerja

| Fase | Isi | Perkiraan | Selesai bila |
|---|---|---|---|
| **0** | Model murah (bagian 1) | 1 hari | order penuh < $0.15, attested |
| **1** ✅ | Jalur tulis yang dijaga (`core/external.py`), aturan "data luar bukan dasar aksi" (`untrusted_input`), izin tulis per tool di halaman MCP | selesai 2026-11-12 | teruji end-to-end dengan server MCP tiruan, lewat UI: diizinkan → diajukan agen → disetujui → dieksekusi |
| **2** | **Google Sheets/Docs** (`workspace`) + skill `sync_orders_to_sheet`, `weekly_ads_report` (versi tanpa iklan) | 2–3 hari | order masuk otomatis tercatat di Sheets bisnis |
| **3** | **Facebook Pages + LinkedIn** (`social`) + `weekly_content_calendar`, `publish_social_post` | 3–4 hari | satu minggu konten disetujui sekali lalu terbit sendiri |
| **4** | **Meta Ads** (`ads`) + `launch_ad_campaign`, laporan iklan | 4–5 hari, ditambah waktu review app Meta | kampanye dibuat sebagai draf, diaktifkan setelah persetujuan, anggaran tidak bisa melewati batas |
| **5** | CRM (HubSpot atau Sheets) + `qualify_lead`, inbox Support | 3 hari | lead dari iklan masuk CRM dan dibalas |

Urutan ini sengaja dimulai dari Google Sheets: aksesnya paling mudah, risikonya paling rendah, dan
langsung berguna. Meta Ads paling akhir karena paling berisiko (uang) dan butuh review.

---

## 8. Risiko dan hal yang perlu dicek

- **Meta Ads:** Composio tidak menyediakan app terkelola, jadi kita perlu **app Meta sendiri**
  (Meta for Developers), verifikasi bisnis, dan izin `ads_management` lewat App Review. Ini bisa
  makan waktu berhari-hari sampai berminggu-minggu. Selama menunggu, mode pengembangan app Meta
  bisa dipakai dengan akun iklan milik sendiri.
- **Instagram:** di Composio tidak ada toolkit Instagram terpisah; aset Instagram diakses lewat
  Meta Ads. Posting organik ke Instagram perlu dicek kemampuannya.
- **Facebook:** hanya Facebook Pages, bukan akun pribadi.
- **X (Twitter):** API berbayar; tidak dimasukkan sampai ada kebutuhan.
- **Kuota dan rate limit** tiap platform: aksi yang kena limit harus *held*, bukan diulang terus.
- **Biaya model** naik karena agen membaca insight dan komentar. Batas biaya per run dan per hari
  tetap berlaku.

---

## 9. Yang perlu diputuskan owner

1. **Platform pertama** setelah Google Sheets: Facebook Pages/LinkedIn (organik) atau Meta Ads
   (berbayar)?
2. **Composio** sebagai lapisan akun (disarankan, karena token tidak disimpan AERA), atau OAuth
   sendiri per platform?
3. **Seberapa otomatis** post dan iklan di awal: semuanya perlu persetujuan (disarankan untuk
   demo), atau kalender mingguan disetujui sekali?

---

Sumber yang dicek (2026-11-11):
- Composio toolkits: https://docs.composio.dev/toolkits
- Composio Meta Ads (tanpa app terkelola, OAuth2/API key): https://docs.composio.dev/toolkits/metaads.md
- Composio Facebook (Pages saja): https://docs.composio.dev/kb/toolkit/facebook.md
