# SIGAP

**Sistem Intelijen Gangguan & Antisipasi Pasokan**
AI Agentic Hackathon 2026 · Track 01 — Intelligent Supply Chain

Asisten otomatis untuk pabrik yang bahan bakunya banyak diimpor. Kalau ada gangguan pasokan,
sistem menyelidiki sendiri dampaknya, menyusun pilihan jalan keluar, mencoret yang melanggar
aturan, menghitung mana yang paling murah, lalu mengeksekusinya ke SAP setelah disetujui orang.

Yang hari ini butuh 2–3 hari kerja manusia, dikerjakan dalam belasan menit.

---

## Mulai dari mana

**Baru pertama baca?** → `PLAN.md` bagian 1 dan 2.
**Mau mulai ngoding?** → `PLAN.md` bagian 15, lalu `TEKNIS.md`.
**Butuh angka atau skenario?** → `DESIGN.md` bagian 2.
**Bingung ambil data dari mana?** → `SUMBER-DATA.md`.

---

## Isi folder ini

| File | Isinya | Untuk siapa |
|---|---|---|
| **`PLAN.md`** ⭐ | Rencana lengkap: apa yang dibangun, cara kerjanya, 11 agent, 10 tahap, pembagian kerja, biaya, risiko, daftar istilah | **Semua orang.** Bahasa sehari-hari |
| `DESIGN.md` | Rincian teknis: angka skenario, 23 alat lengkap dengan nama, aturan lokal, batas wewenang, 14 skenario uji | Yang menulis kode |
| `TEKNIS.md` | Nama fungsi dan parameter persis: cara panggil Claude di Bedrock, hemat biaya, penanda asal data | Programmer |
| `SUMBER-DATA.md` | Hasil pengecekan tiap sumber data — mana yang siap, mana yang perlu diambil manual | Orang domain + backend |
| `REFERENSI-manufacturing-agents.md` | Pembacaan repo pembanding: apa yang layak ditiru, apa yang tidak | Referensi |
| `isi-repo-manufacturing-agents.txt` | Daftar 415 file repo itu | Referensi |

Dokumen proposal ada di `../proposal/`.

---

## Yang perlu diingat

**PLAN.md adalah rujukan utama.** Kalau ada yang berbeda antar dokumen, PLAN.md yang benar.

**Angka selalu dari DESIGN.md bagian 2.** Jangan ubah satu angka tanpa mengecek turunannya —
semuanya saling terkait.

**Tiga hal yang paling sering salah urut:**

1. **Penanda asal data dibuat di Tahap 1**, bukan belakangan. Satu pembungkus sekarang, versus
   menambal 23 alat nanti.
2. **Ahli Aturan dibangun di Tahap 3**, bukan menjelang akhir. Itu satu-satunya bagian yang tidak
   bisa ditiru tim lain — kalau ditunda, biasanya tidak pernah selesai.
3. **Orang domain paling sibuk di Tahap 3**, bukan di awal. Dokumen aturan TKDN dan LARTAS itu
   isinya pengetahuan, bukan kode.

---

## Yang dikerjakan sekarang

1. Ambil kunci API SAP di `api.sap.com` — **ini menghambat semuanya**
2. Minta izin model Claude di AWS Bedrock, pastikan wilayahnya mana
3. Tahap 1: penghubung SAP + satu alat + penanda asal data + satu agent
4. Simpan tangkapan layar hasil panggilan SAP pertama yang berhasil
