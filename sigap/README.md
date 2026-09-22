# SIGAP

**Sistem Intelijen Gangguan & Antisipasi Pasokan**

Asisten otomatis untuk pabrik yang bahan bakunya banyak diimpor. Kalau ada gangguan
pasokan, sistem menyelidiki dampaknya sendiri, menyusun pilihan jalan keluar, mencoret
yang melanggar aturan, menghitung mana yang paling murah, lalu mengeksekusinya ke SAP
setelah disetujui orang yang berwenang.

---

## Jalankan

```bash
cd sigap/agent
python3 kelola.py rahasia                 # export keluarannya sebagai SIGAP_SECRET
python3 kelola.py pengguna budi@kpn.co.id "Budi" buyer sandi123
python3 api.py                            # :8787

cd ../..
SIGAP_API=http://127.0.0.1:8787 npm run dev
open http://localhost:3000/sigap
```

## Mulai dari mana

| Mau apa | Buka |
|---|---|
| Paham produknya | `PLAN.md` §1 dan §3 |
| Lihat sudah sampai mana | `PLAN.md` §2 |
| Mulai ngoding | `agent/README.md`, lalu `TEKNIS.md` |
| Kenal agent-nya satu per satu | `AGENT.md` |
| Butuh angka atau skenario | `DESIGN.md` §2 |
| Bingung ambil data dari mana | `SUMBER-DATA.md` |

## Isi

| Berkas | Isinya |
|---|---|
| **`PLAN.md`** ⭐ | Rencana, status tiap bagian, urutan kerja. Bahasa sehari-hari |
| **`AGENT.md`** | Rujukan lengkap 11 agent: fungsi, alat, parameter, batas wewenang |
| `DESIGN.md` | Angka skenario, aturan lokal, eval suite |
| `TEKNIS.md` | Nama fungsi dan parameter persis |
| `SUMBER-DATA.md` | Hasil pengecekan tiap sumber data |
| `agent/` | Kode — lihat `agent/README.md` |

## Yang perlu diingat

**PLAN.md rujukan utama.** Kalau ada yang berbeda antar dokumen, PLAN.md yang benar.

**Angka selalu dari DESIGN.md §2**, dan diverifikasi mesin:

```bash
cd agent && python3 -m engine.simulate
```

Kalau ada angka di dokumen yang tidak bisa direproduksi perintah itu, **dokumennya yang salah.**

**Tiga hal yang menghambat sekarang:** `SAP_API_KEY`, `AWS_REGION`, dan `references/`
(aturan TKDN & LARTAS). Yang ketiga bisa dikerjakan sekarang juga dan tidak menunggu apa pun.
