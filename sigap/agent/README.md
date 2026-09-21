# SIGAP — sistem agent

Aplikasi respons gangguan pasokan. Bukan proyek demo: produksi menolak jalan
tanpa SAP dan model sungguhan.

## Jalankan

```bash
# 1. layanan agent
cd sigap/agent
python3 api.py                      # :8787

# 2. antarmuka
cd ../..
SIGAP_API=http://127.0.0.1:8787 npm run dev

# 3. kirim aksi yang sudah disetujui ke SAP (jalankan berkala)
cd sigap/agent && python3 pengirim.py
open http://localhost:3000/sigap
```

## Siapkan akun

```bash
python3 kelola.py rahasia                 # keluarannya diexport sebagai SIGAP_SECRET
python3 kelola.py pengguna budi@kpn.co.id "Budi Santoso" buyer sandi123
```

Peran dan batas nilai yang boleh disetujui:

| Peran | Batas |
|---|---|
| `planner` | hanya membaca, tidak boleh menyetujui |
| `buyer` | sampai Rp 500 juta |
| `procurement_lead` | sampai Rp 10 miliar |
| `admin` | sampai Rp 10 miliar |

## Konfigurasi

| Variabel | Arti | Wajib di produksi |
|---|---|---|
| `SIGAP_ENV` | `dev` · `staging` · `prod` | — |
| `SAP_API_KEY` | kunci dari api.sap.com | ✅ |
| `SAP_BASE_URL` | default sandbox SAP | — |
| `AWS_REGION` | wilayah yang menyediakan Claude | ✅ |
| `SIGAP_MODEL` | default `anthropic.claude-opus-5` | — |
| `SIGAP_BATAS_OTONOM_IDR` | batas aksi tanpa persetujuan, default 50 juta | — |
| `SIGAP_BATAS_BIAYA_IDR` | pagu biaya model per peristiwa, default 500 ribu | — |
| `SIGAP_DB` | berkas SQLite, default `data/sigap.db` | — |
| `SIGAP_SECRET` | kunci tanda tangan token sesi | ✅ |

`SIGAP_ENV=prod` tanpa `SAP_API_KEY` atau `AWS_REGION` akan **menolak start**.
Produksi tidak boleh menebak apa pun.

## API

| | |
|---|---|
| `GET /sehat` | status sambungan |
| `POST /peristiwa` | terima gangguan, mulai penanganan |
| `GET /jalan` | daftar penanganan |
| `GET /jalan/{id}` | langkah, aksi, persetujuan |
| `POST /masuk` | tukar email+sandi jadi token sesi |
| `GET /saya` | identitas dan batas wewenang |
| `POST /aksi/{id}/putusan` | setujui · tolak · naikkan — **butuh token** |

```bash
curl -X POST localhost:8787/peristiwa -H 'content-type: application/json' \
  -d '{"jenis":"port_closure","judul":"Ningbo tutup 6 hari",
       "pemicu":"advisory maritim","muatan":{"pelabuhan":"CNNGB"}}'
```

## Bentuk sistem

```
api.py                 layanan HTTP
graph.py               tim agent — ketua + ahli, putaran tool-use ke Bedrock
core/konfigurasi.py    produksi menolak data contoh
core/simpan.py         SQLite: peristiwa, jalan, langkah, aksi, persetujuan
core/provenance.py     label asal data — melekat di SEMUA alat
core/registry.py       daftar alat: skema yang dilihat model = fungsi yang jalan
clients/sap_s4.py      OData; sandbox hari ini, tenant pelanggan besok
tools/                 12 alat terdaftar
engine/simulate.py     kalkulator — Python murni, tanpa AI
agents/definisi.py     11 agent, instruksi di prompts/
```

## Jaminan yang ditegakkan kode, bukan instruksi

1. **Kegagalan tidak mengarang nilai.** Alat gagal → `Asal.TIDAK_ADA`, bukan tebakan.
2. **Kalkulator menolak** mengeluarkan angka rupiah kalau masukannya belum tepercaya.
3. **Aksi idempoten.** Kunci yang sama tidak pernah membuat pesanan kedua.
4. **Persetujuan sekali pakai.** Aksi yang sudah diputus tidak bisa diputus ulang.
5. **Batas putaran dan pagu biaya** per peristiwa — tim agent tidak bisa berputar tanpa henti.
6. **Produksi menolak start** tanpa SAP dan model.
7. **Identitas hanya dari token sesi.** Mengaku sebagai peran lain lewat badan
   permintaan diabaikan — ini yang membuat kolom "disetujui oleh" bernilai.
8. **Wewenang dicek di server**, bukan di tombol. Tombol yang mati di UI cuma
   kenyamanan; penolakan sebenarnya terjadi di API.
9. **Gagal kirim ke SAP tidak mengubah status.** Aksi tetap `disetujui` dan dicoba
   lagi; kunci idempoten mencegah pesanan ganda.

## Pengecekan

```bash
python3 -m core.provenance     # label asal data
python3 -m engine.simulate     # kalkulator — mereproduksi angka DESIGN.md §2
python3 -m agents.definisi     # 11 agent, 23 alat, satu veto
```

## Yang belum

- **`references/`** — aturan TKDN & LARTAS. Ahli Aturan sudah membacanya kalau ada;
  tanpa itu ia menilai dari parameter dan menandai hasilnya `CONTOH`. Tugas orang domain.
- **SSO.** Auth sekarang lokal (pbkdf2 + token HMAC). Di perusahaan sungguhan ini
  diganti SSO perusahaan — `identitas.dari_token()` satu-satunya titik yang berubah.
- **9 prompt** ahli lainnya.
- **Nama layanan tulis SAP belum diverifikasi.** `pengirim.py` memetakan aksi ke
  `API_PURCHASEREQ_PROCESS_SRV` dan sejenisnya; jalurnya sudah lengkap termasuk token
  CSRF, tapi nama entitasnya perlu dicocokkan dengan sandbox sebelum dipakai.
- **Python 3.10+** untuk Strands. Mesin ini 3.9.
