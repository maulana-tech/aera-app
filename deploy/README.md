# Deploy AERA ke satu VPS (Docker Compose + HTTPS)

Satu server, tiga container: `agents` (Python, port 8787 hanya di jaringan internal), `aera` (Next.js) dan
`caddy` (HTTPS otomatis via Let's Encrypt). Database SQLite ada di volume `agent_data`.

> Jalur EC2 + systemd + GitHub Actions yang sudah ada tetap di `ops/CICD.md`. Panduan ini untuk VPS mana pun.

## 0. Yang dibutuhkan

- VPS Ubuntu 22.04/24.04, 2 vCPU / 2 GB RAM cukup (build Next butuh RAM; tambahkan swap 2 GB jika 1 GB).
- Domain atau subdomain, misalnya `aera.domainmu.com`, dengan **A record** ke IP VPS.
- Port 80 dan 443 terbuka; port 22 hanya untuk SSH.
- Docker + Compose: `curl -fsSL https://get.docker.com | sh`

**Jalankan instance tunggal.** Penjadwal job berjalan di dalam proses API dan datanya SQLite: jangan
menjalankan dua container `agents` untuk database yang sama.

## 1. Ambil kode

```bash
git clone https://github.com/maulana-tech/aera-app.git && cd aera-app
git checkout near-hackathon
```

## 2. Taruh rahasia di server (dari laptop, lewat scp; jangan lewat chat atau git)

```bash
# dari laptop, di folder repo
scp aera/agent/.env                       user@VPS:~/aera-app/aera/agent/.env
scp -r aera/agent/.secrets                user@VPS:~/aera-app/aera/agent/.secrets
ssh user@VPS 'chmod 700 ~/aera-app/aera/agent/.secrets && chmod 600 ~/aera-app/aera/agent/.secrets/*'
```

`.secrets/near.env` berisi **function-call key agen** (hanya bisa meminta pembayaran, tidak bisa melewati cap).
Key owner/approver vault **tidak pernah** ke server: tetap di wallet/keychain-mu.

Di `aera/agent/.env` server, pastikan:

| Variabel | Nilai |
|---|---|
| `AERA_WEB_URL` | `https://aera.domainmu.com` (dipakai di link checkout dan email) |
| `AERA_ENV` | biarkan `dev` untuk demo. `prod` = email benar-benar terkirim ke orang asli |
| `AERA_EXTERNAL_REDIRECT` | email-mu sendiri: semua email ke pelanggan/prospek dialihkan ke sini selama bukan prod |
| model (NEAR AI) | sama seperti di laptop |

## 3. Variabel compose (root `.env`)

```bash
cp deploy/compose.env.example .env
nano .env            # AERA_DOMAIN=aera.domainmu.com, akun demo opsional
chmod 600 .env
```

## 4. Database: bawa yang dari laptop (disarankan)

Server baru tanpa akun membuka halaman *Set up AERA*: **siapa pun yang membukanya pertama menjadi owner.**
Jadi sebelum domain dibuka, isi database dulu. Paling mudah membawa database lokal (akun, bisnis Lumen,
riwayat, bukti testnet ikut):

```bash
# di laptop: salinan yang konsisten (aman walau AERA sedang jalan)
sqlite3 aera/agent/data/aera.db ".backup aera/agent/data/aera-deploy.db"
scp aera/agent/data/aera-deploy.db user@VPS:~/aera-app/

# di server
docker compose up -d agents
docker compose cp aera-deploy.db agents:/app/data/aera.db
docker compose restart agents && rm aera-deploy.db
```

Mulai dari kosong? Buat owner lewat CLI **sebelum** langkah 5:

```bash
docker compose up -d agents
docker compose exec agents python manage.py user owner@domainmu.com "Nama" owner "<password-10+karakter>"
```

## 5. Nyalakan dengan HTTPS

```bash
docker compose --profile https up -d --build
docker compose ps
curl -fsS https://aera.domainmu.com/login -o /dev/null && echo web ok
docker compose exec agents python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8787/health').read()[:200])"
```

Sertifikat diambil Caddy otomatis saat permintaan pertama (DNS harus sudah mengarah ke VPS).

## 6. Sehari-hari

| Apa | Perintah |
|---|---|
| Update ke kode terbaru | `git pull && docker compose --profile https up -d --build` |
| Log agen / web | `docker compose logs -f agents` · `docker compose logs -f aera` |
| Cek kesiapan (model, TEE, vault) | `docker compose exec agents python manage.py ready` |
| Backup database | `sh deploy/backup.sh` (14 terakhir disimpan di `deploy/backups/`) |
| Backup harian otomatis | `crontab -e` → `30 2 * * * cd ~/aera-app && sh deploy/backup.sh >> deploy/backups/log 2>&1` |
| Ganti password | `docker compose exec agents python manage.py password <email> --generate` (lalu baca file di `.secrets`) |
| Hentikan semua kerja | Dashboard → kill switch (owner/approver) |

## 7. Webhook email masuk (opsional, untuk balasan prospek)

Set `AERA_INBOUND_SECRET` di `.secrets/notify.env`, lalu arahkan forwarder email (Cloudflare Email Workers,
Postmark, Mailgun) ke `POST https://aera.domainmu.com/api/aera/public/inbound/email` dengan header
`X-AERA-Inbound-Secret`. Atau isi `AERA_IMAP_*` dan AERA membaca inbox sendiri tiap 2 menit.

## Catatan keamanan

- Port 8787 tidak dibuka ke internet; hanya web lewat Caddy.
- `.env` root, `aera/agent/.env` dan `.secrets/` tidak pernah masuk image (`.dockerignore`) dan tidak di git.
- `AERA_ENV=prod` hanya bila kamu siap email benar-benar keluar; batasi dengan `AERA_EXTERNAL_DOMAINS`.
