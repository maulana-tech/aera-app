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
open http://localhost:3000/sigap
```

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

`SIGAP_ENV=prod` tanpa `SAP_API_KEY` atau `AWS_REGION` akan **menolak start**.
Produksi tidak boleh menebak apa pun.

## API

| | |
|---|---|
| `GET /sehat` | status sambungan |
| `POST /peristiwa` | terima gangguan, mulai penanganan |
| `GET /jalan` | daftar penanganan |
| `GET /jalan/{id}` | langkah, aksi, persetujuan |
| `POST /aksi/{id}/putusan` | setujui · tolak · naikkan |

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

## Pengecekan

```bash
python3 -m core.provenance     # label asal data
python3 -m engine.simulate     # kalkulator — mereproduksi angka DESIGN.md §2
python3 -m agents.definisi     # 11 agent, 23 alat, satu veto
```

## Yang belum

- **`references/`** — aturan TKDN & LARTAS. Ahli Aturan sudah membacanya kalau ada;
  tanpa itu ia menilai dari parameter dan menandai hasilnya `CONTOH`. Tugas orang domain.
- **Auth.** `Putusan.tsx` masih mengirim `oleh: "planner"` yang dipatok. Ganti dengan
  identitas sesi sebelum dipakai sungguhan — tanpa itu jejak audit tidak bernilai.
- **9 prompt** ahli lainnya.
- **Menulis balik ke SAP.** Aksi sudah tercatat dan idempoten, tapi belum benar-benar
  memanggil `API_PURCHASEREQ_PROCESS_SRV`.
- **Python 3.10+** untuk Strands. Mesin ini 3.9.
