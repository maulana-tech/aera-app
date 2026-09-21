# SIGAP — scaffold agent

## Jalankan

```bash
cd sigap/agent
python3 main.py --anggap-langsung     # jalur penuh sampai rekomendasi
python3 main.py                       # tanpa flag → kalkulator menahan angka
```

Jejaknya ditulis ke `app/sigap/jejak.json`, dibaca dashboard di `/sigap`.

## Pengecekan mandiri

```bash
python3 -m core.provenance     # label asal data
python3 -m engine.simulate     # kalkulator — mereproduksi angka DESIGN.md §2
python3 -m agents.definisi     # 11 agent, 23 alat, satu veto
```

## Isi

```
core/provenance.py   label asal data — dipakai SEMUA alat
core/jejak.py        perekam jejak → JSON untuk dashboard
clients/sap_s4.py    klien OData; sandbox hari ini, tenant pelanggan besok
tools/_sumber.py     coba SAP dulu, jatuh ke fixture kalau kunci belum ada
tools/impact.py      4 alat Ahli Dampak          ✅ jadi
tools/sourcing.py    1 alat Ahli Pencari Sumber  ✅ jadi
engine/simulate.py   kalkulator — Python murni, tanpa AI
agents/definisi.py   11 agent, instruksi di prompts/
prompts/             supervisor.txt · compliance.txt  (9 lagi menyusul)
fixtures/            data contoh, selalu berlabel CONTOH
main.py              penjalan skenario
```

## Yang sudah jalan

- Label asal data melekat di tiap alat, dan **kegagalan tidak mengarang nilai**
- Kalkulator **menolak** mengeluarkan angka kalau masukannya belum tepercaya
- Lima alat baca sungguhan, otomatis pakai SAP begitu `SAP_API_KEY` diisi
- Jalur penuh Ningbo mereproduksi angka dokumen: B+C Rp 116 juta, hemat Rp 70 juta (38%)
- Ahli Aturan mencoret D dan E dengan alasan aturan, bukan harga
- Dashboard `/sigap` menampilkan jejak + badge asal data

## Yang belum

- **Belum ada pemanggilan Bedrock.** Mode saat ini `runut`: urutan langkah mengikuti
  rancangan, angkanya dihitung kalkulator sungguhan. Ditandai jelas di jejak dan di UI.
- 18 alat lagi masih berupa nama di `agents/definisi.py`
- `references/` (aturan TKDN & LARTAS) belum ditulis — tugas orang domain, Tahap 3
- 9 prompt lagi

## Langkah berikutnya

1. Isi `SAP_API_KEY` → lima alat langsung pakai data sungguhan, badge berubah jadi `langsung`
2. Aktifkan Bedrock → ganti mode runut dengan supervisor sungguhan di `graph.py`
3. Tulis `references/tkdn-rules.md` dan `lartas-procedure.md`

```bash
export SAP_API_KEY="..."          # dari https://api.sap.com
export SAP_BASE_URL="https://sandbox.api.sap.com"
```

⚠️ Strands Agents SDK butuh Python 3.10+. Mesin ini 3.9 — pasang versi baru sebelum Tahap 4.
