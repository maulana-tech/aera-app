#!/usr/bin/env bash
# Deploy Docker containers to EC2 using GHCR images over SSH.
set -Eeuo pipefail

for key in EC2_HOST EC2_SSH_KEY EC2_KNOWN_HOSTS IMAGE_WEB IMAGE_AGENTS; do
  [[ -n ${!key:-} ]] || { echo "Missing configuration: $key"; exit 1; }
done

[[ $EC2_HOST =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*$ ]] || { echo 'Invalid EC2_HOST'; exit 1; }

umask 077
ssh_dir=$(mktemp -d)
target="ubuntu@$EC2_HOST"

cleanup() {
  rm -rf "$ssh_dir"
}
trap cleanup EXIT

printf '%s\n' "$EC2_SSH_KEY" | tr -d '\r' > "$ssh_dir/key"
printf '%s\n' "$EC2_KNOWN_HOSTS" | tr -d '\r' > "$ssh_dir/known_hosts"

ssh_options=(
  -i "$ssh_dir/key"
  -o BatchMode=yes
  -o IdentitiesOnly=yes
  -o StrictHostKeyChecking=yes
  -o HostKeyAlias=sigap-ec2
  -o "UserKnownHostsFile=$ssh_dir/known_hosts"
  -o ConnectTimeout=15
  -o ServerAliveInterval=30
  -o ServerAliveCountMax=4
)

echo "==> Verifying SSH connection to $EC2_HOST..."
ssh "${ssh_options[@]}" -T "$target" "echo 'SSH connection verified'"

echo "==> Uploading docker-compose.yml..."
ssh "${ssh_options[@]}" -T "$target" "mkdir -p /opt/sigap-project"
scp "${ssh_options[@]}" docker-compose.yml "$target:/opt/sigap-project/docker-compose.yml"

echo "==> Deploying containers on EC2..."
ssh "${ssh_options[@]}" -T "$target" "bash -s" <<REMOTE
set -Eeuo pipefail
cd /opt/sigap-project

export IMAGE_WEB="$IMAGE_WEB"
export IMAGE_AGENTS="$IMAGE_AGENTS"

# If GHCR credentials are provided in env, login to registry
if [[ -n "${GHCR_TOKEN:-}" && -n "${GHCR_USER:-}" ]]; then
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
fi

echo "--> Pulling latest images..."
docker compose pull

echo "--> Recreating and starting containers..."
docker compose up -d --remove-orphans

echo "--> Cleaning up unused dangling images..."
docker image prune -f

echo "--> Checking container status..."
docker compose ps
REMOTE

echo "==> Deployment completed successfully!"

