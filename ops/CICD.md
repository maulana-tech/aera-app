# CI/CD SIGAP lewat SSH: GitHub → EC2

Push ke **semua branch** menjalankan CI. PR menuju `main` juga menjalankan CI.
Deployment hanya berjalan setelah CI lulus untuk push ke `main` atau manual run
pada `main`. Build memakai GitHub runner Ubuntu x86_64, Node 22, dan Webpack.
CI memeriksa lint, output agent, self-check Python, serta transport SSH/rollback.

Deployment ini tidak memerlukan CloudFormation, Terraform, S3, OIDC, atau
AWS access key GitHub. `ops/aws-cicd.yaml` adalah alternatif SSM lama dan tidak
dipakai workflow SSH. Role EC2 yang sudah memberikan akses Bedrock tetap dipakai.
Tidak perlu upgrade account hanya untuk menjalankan script deployment SSH.

## 1. Siapkan server

Target mengikuti runbook `sigap/AGENT-ONLY-EXTERNAL-DEPLOYMENT.md`:

- EC2 Ubuntu **x86_64**, user SSH `ubuntu`, port **22**.
- Node.js **22** tersedia di `/usr/bin/node`; Python **3.10+**, `python3-venv`,
  `curl`, `flock`, dan `tar` tersedia. AWS CLI tidak diperlukan untuk deploy SSH.
- Unit `sigap-agent.service` dan `sigap-web.service` sudah berjalan sebagai `ubuntu`.
- User `ubuntu` bisa menjalankan `sudo -n true` tanpa password dan tanpa TTY.
- `.env` tetap di `/opt/sigap-project/sigap/agent/.env`.
- `.env` harus berisi `SIGAP_DB=/var/lib/sigap/sigap.db`, secret session, region,
  model, dan konfigurasi SAP yang diperlukan. Database tetap di lokasi tersebut
  dan direktorinya harus dapat ditulis `ubuntu`.
- Jika systemd menggunakan `EnvironmentFile`, gunakan `KEY=value` dengan komentar
  di baris tersendiri. Jangan memasukkan AWS access key ke `.env`.
- EC2 bisa mengakses repository dependency Python melalui internet.
- Izin dan akses model Bedrock tetap diperlukan untuk menjalankan agent; deploy
  SSH tidak mengubah kebijakan atau mengaktifkan model.

Verifikasi lewat koneksi SSH admin yang sudah dipercaya:

```bash
/usr/bin/node --version
python3 --version
sudo -n true
sudo systemctl is-active sigap-agent sigap-web
curl --fail http://127.0.0.1:8787/health
curl --fail http://127.0.0.1:3000/login
```

Pastikan Nginx tetap mengarah ke frontend 3000 dan backend 8787.

## 2. Buat key deployment khusus

Jalankan di laptop, bukan di GitHub atau lewat chat:

```bash
mkdir -p ~/.ssh
ssh-keygen -t ed25519 -N '' -C 'github-sigap-deploy' -f ~/.ssh/sigap-github-deploy
```

Melalui sesi SSH admin, tambahkan isi file **`sigap-github-deploy.pub`** ke
`/home/ubuntu/.ssh/authorized_keys` di EC2. Jangan menimpa key admin yang sudah ada.
Tambahkan prefix `restrict` pada baris key tersebut untuk menonaktifkan forwarding
serta PTY; SSH noninteraktif dan transfer SFTP/SCP tetap tersedia:

```text
restrict ssh-ed25519 AAAA... github-sigap-deploy
```

File `.ssh/authorized_keys` harus dimiliki `ubuntu`, permission direktori `.ssh`
700, permission file `authorized_keys` 600. Key ini menjalankan deploy sebagai
`ubuntu` dan memakai sudo; perlakukan private key sebagai kredensial server.

Coba koneksi dengan key baru dan host key server yang sudah diverifikasi:

```bash
ssh -i ~/.ssh/sigap-github-deploy -o BatchMode=yes ubuntu@<IP-ATAU-DNS-EC2> 'sudo -n true'
```

## 3. Ambil host key EC2 yang dipercaya

Di sesi SSH admin yang sudah dipercaya (atau EC2 console yang terautentikasi),
jalankan pada **server EC2**:

```bash
printf 'sigap-ec2 '
sudo cat /etc/ssh/ssh_host_ed25519_key.pub
```

Salin satu baris hasilnya. Bentuknya:

```text
sigap-ec2 ssh-ed25519 AAAAC3... root@server
```

Prefix `sigap-ec2` wajib: workflow memakai `HostKeyAlias=sigap-ec2`. Ini adalah
**public host key server**, bukan public key deployment yang dibuat di laptop.
Jangan mengambil key dari koneksi yang belum diverifikasi, dan jangan mematikan
host key checking ketika mendapat error. Jika server diganti atau host key
berubah, verifikasi ulang melalui akses admin sebelum mengganti secret.

## 4. Isi konfigurasi GitHub

Repo → **Settings → Secrets and variables → Actions**. Gunakan konfigurasi
**repository**, sehingga tidak memerlukan pengelolaan environment `production`.

Pada tab **Variables**, klik **New repository variable**:

| Nama | Isi |
|---|---|
| `EC2_HOST` | IP publik atau hostname DNS EC2; tanpa `https://`, username, port, atau path |

Pada tab **Secrets**, klik **New repository secret**:

| Nama | Isi |
|---|---|
| `EC2_SSH_KEY` | Seluruh isi private key `~/.ssh/sigap-github-deploy`, termasuk BEGIN/END dan newline |
| `EC2_KNOWN_HOSTS` | Satu baris public host key server dengan prefix `sigap-ec2` dari langkah 3 |

Private key harus tanpa passphrase karena workflow noninteraktif. Private key
hanya dimasukkan melalui GitHub Secrets; jangan commit atau kirim melalui chat.
`AWS_REGION`, `AWS_ROLE_ARN`, `DEPLOY_BUCKET`, dan `EC2_INSTANCE_ID` tidak dibaca
oleh workflow SSH. Environment `production` juga tidak dipakai workflow ini.

## 5. Pastikan jaringan SSH dapat dijangkau

Koneksi SSH dari laptop belum membuktikan runner GitHub dapat masuk. Security
group, network ACL, firewall OS, dan route EC2 harus mengizinkan port 22 dari
jalur jaringan runner yang disetujui pengelola. Aturan SSH dengan source **My IP**
hanya mengizinkan laptop tersebut, bukan runner GitHub.

Runner GitHub Ubuntu biasa mempunyai IP keluar yang berubah-ubah. Jangan
mengandalkan IP satu run untuk deploy berikutnya, atau membuka port 22 ke semua
IP sebagai solusi otomatis. Jika tidak tersedia jalur jaringan yang diizinkan,
pengaturan runner dengan egress tetap/VPN atau self-hosted runner perlu dilakukan
sebelum SSH dari GitHub bisa bekerja. Script tidak mengubah security group AWS.

## 6. Aktifkan workflow

Setelah konfigurasi server, GitHub, dan jaringan siap, commit dan push perubahan
workflow ke `main`. Buka **Actions → CI and deploy EC2** untuk melihat CI/deploy.
Jika sudah dipush, **Run workflow** dari `main` memulai deployment baru.

Mintalah admin repo membatasi perubahan `main` melalui PR, review, dan required
status check job `ci`. Job deploy memiliki guard `main`; secret tidak digunakan
pada job PR atau push ke branch lain. Workflow SSH tidak memiliki approval gate
environment, sehingga izin push/perubahan workflow ke `main` perlu dikendalikan.

## Cara deploy dan rollback

CI memaketkan Next.js standalone, static/public assets, serta file backend,
prompt, fixture, dan references yang sudah tracked Git. `.env`, virtualenv,
dan database lokal tidak dimasukkan ke paket.

`ops/deploy-ssh.sh` memverifikasi private key/host key, memeriksa sudo, mengirim
paket lewat SCP, memverifikasi SHA-256 di EC2, lalu menjalankan `ops/deploy.sh`
melalui `sudo -n`. Kredensial sementara pada runner dan paket upload dibersihkan.

Release berada di `/opt/sigap-project/releases/<commit>-<run>-<attempt>`.
Dependency Python diinstall di virtualenv release sebagai `ubuntu`. Versi Python
dependency belum dikunci, mengikuti requirements repo, ditambah boto3 untuk SDK
Bedrock. Build frontend dilakukan di GitHub, bukan pada EC2 kecil.

Script mengubah symlink `/opt/sigap-project/current`, memasang systemd drop-in
`10-release.conf`, dan restart dua service. Health check memeriksa service aktif,
backend `/health`, dan frontend `/login`. Jika gagal, symlink serta drop-in lama
dipulihkan lalu service direstart; job GitHub tetap gagal. Pada deploy pertama,
konfigurasi service awal dipulihkan. ENV dan database disimpan di luar release.

Restart menyebabkan jeda singkat. Rollback kode tidak membatalkan perubahan
schema/data. Endpoint `/health` hanya membuktikan backend hidup; tidak menguji
panggilan Bedrock atau SAP asli. Release lokal lama tetap disimpan untuk rollback;
hapus release yang tidak aktif secara berkala agar disk tidak penuh.

## Validasi offline

```bash
bash -n ops/deploy.sh
bash -n ops/deploy-ssh.sh
python3 ops/test_deploy.py
python3 ops/test_deploy_ssh.py
```

Test memakai stub dan direktori sementara, tanpa mengakses EC2/AWS. Test memeriksa
aktivasi, pemulihan konfigurasi, kegagalan SSH/deploy, host checking, input host,
secret yang belum diisi, dan pembersihan kredensial sementara.

Referensi:
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://man.openbsd.org/ssh_config
