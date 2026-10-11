# CI/CD SIGAP: GitHub main → EC2

Pipeline menjalankan lint, build Next.js, self-check Python, dan test rollback.
CI juga memeriksa rendering output agent dari `scripts/check-agent-output.mjs`.
PR ke `main` hanya menjalankan CI. Push/merge ke `main` menjalankan CI lalu deploy.
`workflow_dispatch` juga tersedia, tetapi deployment hanya diizinkan dari `main`.
Build berjalan di GitHub (Ubuntu x86_64, Node 22), bukan di EC2.
CI memakai `next build --webpack`, yang sudah diverifikasi untuk project ini.

## 1. Buat resource AWS sekali

Siapkan **instance ID** EC2 yang sudah menjalankan SIGAP, misalnya `i-0123456789abcdef0`.
Gunakan region EC2 tersebut; runbook lama menggunakan `ap-southeast-2`, tetapi
pastikan instance yang dipilih benar. Instance harus Ubuntu **x86_64**.

Di AWS Console, buka **CloudFormation → Create stack → With new resources →
Upload a template file**. Upload `ops/aws-cicd.yaml` dari repo ini.

- Stack name: `sigap-cicd`.
- `GitHubRepository`: `maulana-tech/socrates` (ubah jika repo berbeda).
- `InstanceId`: ID EC2 target.
- `ExistingGitHubOidcProviderArn`: kosong jika belum ada provider GitHub.
  Jika sudah ada, buka IAM → Identity providers → `token.actions.githubusercontent.com`
  dan salin ARN-nya. Gunakan provider yang memiliki audience `sts.amazonaws.com`.
- Konfirmasi capability pembuatan IAM resources, lalu Create stack.
- Tunggu status `CREATE_COMPLETE`; buka tab **Outputs**.

Stack membuat bucket privat terenkripsi, role GitHub khusus deployment,
role/profile EC2 dengan SSM + baca release + inference Claude, dan OIDC provider
jika diperlukan. Stack tidak membuat EC2 baru atau mengubah instance yang ada.

Identitas pembuat stack memerlukan izin CloudFormation, IAM, dan S3 yang sesuai.
Policy IAM/EC2/SSM/S3/Bedrock yang dibahas sebelumnya **belum memberikan izin
CloudFormation**. Minta admin menjalankan stack, atau tambahkan izin CloudFormation
untuk stack ini. Template tidak otomatis mengaktifkan akses model Bedrock.

## 2. Siapkan EC2 sekali

EC2 → Instances → pilih instance → Actions → Security → Modify IAM role.
Pilih instance profile dari Output `Ec2InstanceProfileName`. Jika role lama punya
izin tambahan yang masih diperlukan, sertakan izin itu pada role baru sebelum
mengganti profile; sebuah EC2 hanya menggunakan satu instance profile.

Alternatif mempertahankan role lama `sigap_agents`: attach
`AmazonSSMManagedInstanceCore` dan salin inline policy `ReadReleases` serta
`ClaudeInference` dari role keluaran stack ke role lama. Profile baru tidak wajib
dipasang apabila izin itu sudah terpasang pada role lama.

Pastikan:

- SSM Agent aktif dan instance muncul **Online** di Systems Manager → Fleet Manager.
- AWS CLI v2, Node.js **22** di `/usr/bin/node`, Python **3.10+**, `python3-venv`,
  `curl`, dan `flock` tersedia. EC2 memerlukan internet untuk SSM/S3 dan pip,
  atau endpoint/rute jaringan yang sesuai.
- User Linux `ubuntu` dan unit `sigap-agent.service` / `sigap-web.service` sudah ada,
  sesuai `sigap/AGENT-ONLY-EXTERNAL-DEPLOYMENT.md`. User service harus `ubuntu`.
- `.env` tetap di `/opt/sigap-project/sigap/agent/.env` dan berisi
  `SIGAP_DB=/var/lib/sigap/sigap.db` (path absolut), `SIGAP_SECRET`, region/model,
  dan SAP key sesuai lingkungan. Jangan simpan AWS access key di `.env`.
- `/var/lib/sigap` dimiliki `ubuntu` dan menyimpan database yang sudah digunakan.
  Jangan mengganti path database sebelum menyalin data lama dengan benar.
- Jika unit lama memakai `EnvironmentFile`, gunakan format systemd: `KEY=value`,
  komentar di baris tersendiri; hindari komentar di akhir nilai.
- Akses model Claude sudah diaktifkan di account; First Time Use Anthropic sudah
  dipenuhi. Izin template mencakup model Claude dan inference profile Claude
  lintas region. Pembatasan SCP/region organisasi masih dapat memblokir inference.

Contoh pengecekan melalui SSH atau SSM Session Manager:

```bash
/usr/bin/node --version
python3 --version
aws --version
sudo systemctl is-active sigap-agent sigap-web
sudo test -f /opt/sigap-project/sigap/agent/.env
sudo install -d -o ubuntu -g ubuntu /var/lib/sigap
curl --fail http://127.0.0.1:8787/health
curl --fail http://127.0.0.1:3000/login
```

Nginx dan domain tetap memakai port 3000/8787 seperti runbook. Deployment tidak
memerlukan GitHub mengakses port SSH EC2.

## 3. Isi GitHub environment

Repo GitHub → **Settings → Environments → New environment → `production`**.
Pada deployment branches/tags, pilih **Selected branches and tags**, tambahkan
branch `main`. Untuk deploy otomatis, jangan aktifkan required reviewers.
Trust OIDC template menggunakan subject environment `production`; pembatasan
branch environment ini wajib, selain guard `main` pada workflow.

Pada environment `production`, tambahkan **Variables**, bukan secrets:

| Variable | Sumber |
|---|---|
| `AWS_REGION` | Output `AWSRegion` |
| `AWS_ROLE_ARN` | Output `GitHubRoleArn` |
| `DEPLOY_BUCKET` | Output `DeployBucket` |
| `EC2_INSTANCE_ID` | ID EC2 target, sama dengan parameter stack |

Tidak diperlukan AWS access key, secret access key, atau private SSH key.
Tidak perlu menyalin SAP key atau SIGAP_SECRET ke GitHub.

## 4. Aktifkan pipeline

Commit file workflow dan folder `ops`, lalu push/merge ke `main`:

```bash
git add .github/workflows/deploy.yml ops app components hooks README.md
git commit -m "ci: deploy SIGAP main to EC2 through SSM"
git push origin main
```

Buka tab **Actions → CI and deploy EC2** untuk hasil CI dan deployment.
SSM command ID juga tercetak di log deploy. Untuk melindungi `main`, jadikan
job `ci` sebagai required status check melalui branch protection/ruleset.

## Cara deployment bekerja

Artifact frontend mencakup standalone server, public, dan static assets.
Backend termasuk prompt, fixture, dan references yang **sudah tracked Git**.
`.env`, database lokal, dan virtualenv tidak dimasukkan ke artifact.

Paket diupload ke `releases/<commit>-<run>-<attempt>.tar.gz` di S3. EC2 memverifikasi
SHA-256 lalu menyiapkan virtualenv di `/opt/sigap-project/releases/<release-id>`.
Dependensi backend diinstall sebagai `ubuntu`, bukan root. Pipeline tidak
mengubah requirements aplikasi; boto3 ditambahkan pada virtualenv untuk Bedrock.
Versi dependency Python belum dikunci, mengikuti requirements repo saat ini.

Symlink `/opt/sigap-project/current` menunjuk release aktif. Script membuat
systemd drop-in `10-release.conf` untuk memakai symlink tersebut dan restart dua
service. ENV dan database tetap berada di lokasi lama, di luar release.
Health check memeriksa service aktif, API `/health`, dan frontend `/login`.
Jika gagal, symlink dan drop-in sebelumnya dikembalikan lalu service direstart;
GitHub tetap melaporkan deployment gagal. Pada deployment pertama, konfigurasi
service awal dipulihkan. Rollback kode **tidak membatalkan perubahan database**.
`/health` hanya membuktikan API hidup; tidak melakukan panggilan Bedrock/SAP asli.

Ada jeda singkat ketika service direstart. Release lokal lama dipertahankan agar
rollback tersedia; hapus release yang tidak aktif secara berkala untuk menjaga
ruang disk. Paket S3 kedaluwarsa setelah 30 hari. Workflow concurrency dan lock
EC2 mencegah dua deployment mengubah service secara bersamaan.

## Validasi lokal

```bash
bash -n ops/deploy.sh
python3 ops/test_deploy.py
npm run lint
node scripts/check-agent-output.mjs
npm run build -- --webpack
cd sigap/agent && SIGAP_ENV=dev python3 manage.py check
```

Test deployment memakai command stub dan direktori sementara. Test memeriksa
aktivasi release, rollback setelah kegagalan health check, dan pemulihan unit
awal pada deployment pertama; tidak mengakses AWS atau mengubah systemd host.

Referensi:
- https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws
- https://docs.aws.amazon.com/systems-manager/latest/userguide/setup-instance-permissions.html
- https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html
