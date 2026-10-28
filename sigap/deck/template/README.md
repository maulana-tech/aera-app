# Plotting di atas template panitia

Template panitia (`template-1920x1080.png`) adalah **1920 × 1080**, sama persis
dengan kanvas deck. Yang dikirim panitia ada dua file, `7.png` dan `8.png` —
keduanya **identik piksel per piksel**, jadi hanya ada satu template.

Masalahnya bukan ruang kosong, tapi bentuknya: gradien ungu naik dari kanan
bawah, jadi **area putih itu berbentuk baji, bukan kotak**. Melebar di atas,
menyempit di bawah. Semua angka di bawah ini diukur dari file-nya
(`measure.py`), bukan dikira-kira.

## Lembar plotting

`sheets/` berisi tujuh PNG, dibuat oleh `plot.mjs`:

| | isi |
|---|---|
| `00-grid.png` | lembar ukur: zona terlarang, zona putih, 12 kolom, garis bantu |
| `01-cover.png` | sampul |
| `02-divider.png` | pembatas bagian |
| `03-content.png` | judul + isi — layout yang paling sering dipakai |
| `04-two-column.png` | dua kolom |
| `05-metrics.png` | angka besar |
| `06-wide-visual.png` | kartu putih untuk diagram, tabel, screenshot |

```bash
node plot.mjs            # semua
node plot.mjs 03         # satu saja
```

Butuh playwright. Kalau belum ada di folder ini:
`PLAYWRIGHT_DIR=/path/ke/node_modules node plot.mjs`.

## Angka yang mengikat

**Jangan ditimpa — milik panitia:**

| | x | y | lebar | tinggi |
|---|---|---|---|---|
| logo Sokrates | 82 | 58 | 282 | 82 |
| lockup Hackathon | 1452 | 52 | 392 | 130 |
| logo partner | 66 | 912 | 510 | 112 |
| foto robot | 1460 | 834 | 458 | 244 |

**Pita konten** di antara logo-logo itu: `x 80 → 1840`, `y 240 → 856`.

**Zona putih** — satu-satunya tempat teks gelap terbaca:

- **Zona A**, putih lebar: `x 80 → 1032`, `y 240 → 500` (952 × 260)
- **Zona B**, kolom putih: `x 80 → 768`, `y 500 → 856` (688 × 356)

Di luar itu gradiennya terlalu pekat. Pilihannya dua: **teks putih**, atau
**kartu putih** seperti di `06-wide-visual.png` — kartu `x 80 → 1840`,
`y 240 → 856` merebut kembali seluruh pita, dan keempat logo panitia tetap
terlihat di sekelilingnya.

**Grid**: 12 kolom × 110 px, gutter 40 px, total tepat 1760 px.
Kolom ke-*i* mulai di `80 + (i−1) × 150`.

Tapi grid itu untuk perataan, bukan batas. **Batas yang sebenarnya adalah
x = 768 begitu melewati y = 500.** Dua kolom di grid (kolom 1–3 dan 4–6)
berakhir di x = 910 dan sudah masuk ungu; makanya `04-two-column.png` memotong
dua kolom dari lebar putihnya sendiri: 688 = 324 + 40 + 324.

## Kenapa angkanya bisa dipercaya

`plot.mjs` mengukur setiap elemen teks di tiap lembar terhadap zona di atas,
bukan hanya menggambarnya. Hasilnya `7 sheets · 0 problem(s)`.

Angka itu baru berarti setelah pemeriksanya sendiri diuji: dua kesalahan
ditanam — kolom isi dilebarkan 120 px melewati batas putih, dan teks sampul
digeser naik ke bawah logo panitia. Keduanya tertangkap, dengan menyebut
elemen dan koordinatnya (`right=888 (max 768)`, `over sokrates: "SIGAP"`).

Versi pertama lembar metrik lolos dari mata tapi tidak dari pengukur: tiga
angka besar berdampingan butuh lebih dari 260 px per kolom, dan "Rp 116 jt"
sendirian sudah lebih lebar dari itu. Sekarang angkanya berderet ke bawah.

## Catatan

Deck 27 halaman di `../slides/sigap-hackathon/` memakai palet gelap
(`#0B0D10`). Template ini putih. Keduanya tidak bisa dipakai bersamaan apa
adanya — ini lembar plotting untuk PPT di atas template panitia, dan deck yang
sudah ada tidak diubah.
