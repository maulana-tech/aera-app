# SIGAP EC2 Setup and Operations Runbook

Concise operational guide for running SIGAP on an active AWS EC2 instance with the `sigap_agents` IAM Role attached.

---

## 1. Connecting via SSH

Ensure `sigap-admin-key.pem` is present on your local machine.

### 1.1 Linux / macOS (Terminal)
```bash
# 1. Restrict key file permissions (first time only)
chmod 400 ~/sigap-admin-key.pem

# 2. Connect to the EC2 server
ssh -i ~/sigap-admin-key.pem ubuntu@13.211.27.194
```
*(Replace `~/sigap-admin-key.pem` with your local file path, e.g., `~/Downloads/sigap-admin-key.pem`)*.

### 1.2 Windows (PowerShell)
```powershell
ssh -i "$HOME\Downloads\sigap-admin-key.pem" ubuntu@13.211.27.194
```

### 1.3 Disconnect
```bash
exit
```

---

## 2. Server Directory Layout

| Component | Path on Server | Port / Service |
|---|---|---|
| Repository Root | `/opt/sigap-project` | - |
| Python Agent Service | `/opt/sigap-project/sigap/agent` | `:8787` (`sigap-agent.service`) |
| Standalone Web App | `/opt/sigap-project/standalone` | `:3000` (`sigap-web.service`) |
| SQLite Database | `/var/lib/sigap/sigap.db` | - |
| Agent Configuration | `/opt/sigap-project/sigap/agent/.env` | - |
| Nginx Sites Configuration | `/etc/nginx/sites-available/` | `:80`, `:443` |

---

## 3. Initial Server Setup (One-time)

### 3.1 Swap & Base Packages
```bash
# Enable 2GB swap (required for memory stability on t3.micro)
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Install system dependencies
sudo apt update -y
sudo apt install -y python3-venv python3-pip git nginx certbot python3-certbot-nginx nodejs
```

### 3.2 Directory Permissions
```bash
sudo mkdir -p /var/lib/sigap /opt/sigap-project
sudo chown -R ubuntu:ubuntu /var/lib/sigap /opt/sigap-project
```

---

## 4. Python Agent Configuration

### 4.1 Virtual Environment & Dependencies
```bash
cd /opt/sigap-project/sigap/agent
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt boto3
```

### 4.2 Configuration File (`.env`)
File: `/opt/sigap-project/sigap/agent/.env`

```env
SIGAP_ENV=dev
SIGAP_SECRET=generate_using_manage_py
SIGAP_DB=/var/lib/sigap/sigap.db
AWS_REGION=ap-southeast-2
SIGAP_MODEL=global.anthropic.claude-haiku-4-5-20251001-v1:0
SAP_BASE_URL=https://sandbox.api.sap.com
SAP_API_KEY=
SIGAP_AUTONOMOUS_LIMIT_IDR=50000000
SIGAP_COST_CAP_IDR=500000
```
> *Generate secret key with: `PYTHONPATH=. .venv/bin/python manage.py secret`*

---

## 5. Systemd Service Management

### 5.1 Agent Service (`/etc/systemd/system/sigap-agent.service`)
```ini
[Unit]
Description=SIGAP Agent API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/sigap-project/sigap/agent
EnvironmentFile=/opt/sigap-project/sigap/agent/.env
ExecStart=/opt/sigap-project/sigap/agent/.venv/bin/python /opt/sigap-project/sigap/agent/api.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 5.2 Frontend Service (`/etc/systemd/system/sigap-web.service`)
```ini
[Unit]
Description=SIGAP Next.js Web App
After=network-online.target sigap-agent.service
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/sigap-project/standalone
Environment=NODE_ENV=production
Environment=PORT=3000
Environment=SIGAP_API=http://127.0.0.1:8787
ExecStart=/usr/bin/node server.js
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 5.3 Enable & Start Services
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sigap-agent sigap-web
```

---

## 6. Nginx & Domain Routing

### 6.1 Subdomain Mapping
- **`acy.lumbungstack.dev`** -> `http://127.0.0.1:8787` (Agent API)
- **`sigap.lumbungstack.dev`** -> `http://127.0.0.1:3000` (Web UI)

### 6.2 Nginx Configuration
`/etc/nginx/sites-available/acy.lumbungstack.dev`:
```nginx
server {
    listen 80;
    server_name acy.lumbungstack.dev;
    client_max_body_size 10m;
    location / {
        proxy_pass http://127.0.0.1:8787;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 660s;
    }
}
```

`/etc/nginx/sites-available/sigap.lumbungstack.dev`:
```nginx
server {
    listen 80;
    server_name sigap.lumbungstack.dev;
    client_max_body_size 10m;
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 660s;
    }
}
```

### 6.3 Enable Sites and Configure SSL
```bash
sudo ln -sf /etc/nginx/sites-available/acy.lumbungstack.dev /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/sigap.lumbungstack.dev /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# Generate SSL certificates
sudo certbot --nginx -d acy.lumbungstack.dev -d sigap.lumbungstack.dev --non-interactive --agree-tos --register-unsafely-without-email --redirect
```

---

## 7. Daily Operations

### Status Checks
```bash
sudo systemctl status sigap-agent
sudo systemctl status sigap-web
```

### Restart Services (After Code Updates)
```bash
sudo systemctl restart sigap-agent
sudo systemctl restart sigap-web
```

### Live Logs
```bash
sudo journalctl -u sigap-agent -f
sudo journalctl -u sigap-web -f
```

### Health Check
```bash
# From EC2 server
curl -s http://127.0.0.1:8787/health

# From remote client
curl -s https://acy.lumbungstack.dev/health
```

---

## 8. Local Team Development Workflow

For team members developing locally:

### 8.1 Local Configuration (`.env.local`)
Create `.env.local` in the project root of the local machine:
```env
SIGAP_API=https://acy.lumbungstack.dev
```

### 8.2 Run Local Frontend
```bash
npm run dev
```
Open in browser:
`http://localhost:3000/dashboard`

### 8.3 Architecture Benefits
- Next.js running locally proxies all API calls to the remote EC2 agent endpoint (`https://acy.lumbungstack.dev`).
- UI changes hot-reload instantly on local machines without touching the EC2 server.
- Team members do not need Python, AWS CLI, or Bedrock credentials configured locally.
