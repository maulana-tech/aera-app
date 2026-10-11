#!/usr/bin/env bash
# Executed as root by SSM on Ubuntu EC2. Dependencies run as ubuntu.
set -Eeuo pipefail
[[ $EUID == 0 ]] || { echo 'Run via SSM or sudo'; exit 1; }
archive=${1:?release archive required}
release_id=${2:?release ID required}
[[ $release_id =~ ^[a-f0-9]{40}-[0-9]+-[0-9]+$ ]] || { echo 'Invalid release ID'; exit 1; }
root=/opt/sigap-project
release="$root/releases/$release_id"
current="$root/current"
env_file="$root/sigap/agent/.env"
[[ -f $env_file ]] || { echo "Missing server configuration: $env_file"; exit 1; }
for tool in node python3 curl flock runuser; do command -v "$tool" >/dev/null; done
[[ $(node -p 'process.versions.node.split(".")[0]') == 22 ]] || { echo 'Install Node.js 22 on EC2'; exit 1; }
# ponytail: one EC2 deployment lock; use an orchestrator for multiple instances.
exec 9>/var/lock/sigap-deploy.lock
flock -w 120 9
mkdir -p "$root/releases"
[[ ! -e $release ]] || { echo 'Release already exists; rerun the GitHub workflow'; exit 1; }
mkdir "$release"
tar -xzf "$archive" -C "$release" --no-same-owner
[[ -f $release/standalone/server.js && -f $release/sigap/agent/api.py ]]
ln -s "$env_file" "$release/sigap/agent/.env"
chown -R ubuntu:ubuntu "$release"
runuser -u ubuntu -- python3 -m venv "$release/sigap/agent/.venv"
runuser -u ubuntu -- "$release/sigap/agent/.venv/bin/pip" install \
  -r "$release/sigap/agent/requirements.txt" boto3
runuser -u ubuntu -- "$release/sigap/agent/.venv/bin/python" -c \
  'import sys; sys.path.insert(0, sys.argv[1]); from core.config import CFG; assert CFG.database == "/var/lib/sigap/sigap.db", "Set absolute SIGAP_DB in the server .env"' \
  "$release/sigap/agent"

# Overrides preserve the existing unit's user, environment, and restart settings.
agent_override=/etc/systemd/system/sigap-agent.service.d/10-release.conf
web_override=/etc/systemd/system/sigap-web.service.d/10-release.conf
mkdir -p "$(dirname "$agent_override")" "$(dirname "$web_override")"
backup=$(mktemp -d)
previous=$(readlink "$current" || true)
for name in agent web; do
  path_var="${name}_override"
  path=${!path_var}
  if [[ -f $path ]]; then cp "$path" "$backup/$name"; fi
done
switched=0
rollback() {
  code=$?
  trap - ERR
  if [[ $switched == 1 ]]; then
    echo 'Deployment failed; restoring previous service configuration'
    if [[ -n $previous ]]; then
      ln -s "$previous" "$current.rollback"
      mv -Tf "$current.rollback" "$current"
    else
      rm -f "$current"
    fi
    for name in agent web; do
      path_var="${name}_override"
      path=${!path_var}
      if [[ -f $backup/$name ]]; then cp "$backup/$name" "$path"; else rm -f "$path"; fi
    done
    systemctl daemon-reload || true
    systemctl restart sigap-agent sigap-web || true
  fi
  rm -rf "$backup"
  exit "$code"
}
trap rollback ERR
[[ ! -e $current || -L $current ]] || { echo "$current must be a symlink"; false; }
ln -s "$release" "$current.new"
switched=1
mv -Tf "$current.new" "$current"
cat > "$agent_override" <<UNIT
[Service]
WorkingDirectory=$current/sigap/agent
ExecStart=
ExecStart=$current/sigap/agent/.venv/bin/python $current/sigap/agent/api.py
Environment=SIGAP_DB=/var/lib/sigap/sigap.db
UNIT
cat > "$web_override" <<UNIT
[Service]
WorkingDirectory=$current/standalone
ExecStart=
ExecStart=/usr/bin/node $current/standalone/server.js
Environment=NODE_ENV=production
Environment=HOSTNAME=127.0.0.1
Environment=PORT=3000
Environment=SIGAP_API=http://127.0.0.1:8787
UNIT
systemctl daemon-reload
systemctl restart sigap-agent sigap-web
healthy=0
for attempt in $(seq 1 30); do
  if systemctl is-active --quiet sigap-agent sigap-web && \
      curl --fail --silent --max-time 5 http://127.0.0.1:8787/health >/dev/null && \
      curl --fail --silent --max-time 5 http://127.0.0.1:3000/login >/dev/null; then
    healthy=1
    break
  fi
  sleep 2
done
[[ $healthy == 1 ]] || { echo 'Service health check failed'; false; }
trap - ERR
rm -rf "$backup"
echo "Deployed $release_id"
