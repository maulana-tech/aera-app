#!/usr/bin/env bash
# GitHub runner → Ubuntu EC2; credentials come from Actions secrets.
set -Eeuo pipefail
archive=${1:?release archive required}
for key in EC2_HOST EC2_SSH_KEY EC2_KNOWN_HOSTS RELEASE_ID; do
  [[ -n ${!key:-} ]] || { echo "Missing GitHub configuration: $key"; exit 1; }
done
[[ $EC2_HOST =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*$ ]] || { echo 'Invalid EC2_HOST (use IPv4 or DNS only)'; exit 1; }
[[ $RELEASE_ID =~ ^[a-f0-9]{40}-[0-9]+-[0-9]+$ ]] || { echo 'Invalid RELEASE_ID'; exit 1; }
[[ -f $archive ]] || { echo 'Release archive missing'; exit 1; }
umask 077
ssh_dir=$(mktemp -d)
remote_dir=''
target="ubuntu@$EC2_HOST"
ssh_options=(-i "$ssh_dir/key" -o BatchMode=yes -o IdentitiesOnly=yes
  -o StrictHostKeyChecking=yes -o HostKeyAlias=sigap-ec2
  -o "UserKnownHostsFile=$ssh_dir/known_hosts" -o ConnectTimeout=15
  -o ServerAliveInterval=30 -o ServerAliveCountMax=4)
cleanup() {
  code=$?
  trap - EXIT
  if [[ -n $remote_dir ]]; then
    ssh "${ssh_options[@]}" -T "$target" "rm -rf -- '$remote_dir'" >/dev/null 2>&1 || true
  fi
  rm -rf "$ssh_dir"
  exit "$code"
}
trap cleanup EXIT
printf '%s\n' "$EC2_SSH_KEY" | tr -d '\r' > "$ssh_dir/key"
printf '%s\n' "$EC2_KNOWN_HOSTS" | tr -d '\r' > "$ssh_dir/known_hosts"
unset EC2_SSH_KEY EC2_KNOWN_HOSTS
ssh-keygen -y -P '' -f "$ssh_dir/key" >/dev/null 2>&1 || { echo 'EC2_SSH_KEY must be a valid private key without a passphrase'; exit 1; }
ssh-keygen -F sigap-ec2 -f "$ssh_dir/known_hosts" >/dev/null || { echo 'EC2_KNOWN_HOSTS must contain the verified sigap-ec2 host key'; exit 1; }
# Check sudo before sending a large archive; GitHub cannot enter a password.
remote_dir=$(ssh "${ssh_options[@]}" -T "$target" 'sudo -n true && mktemp -d /tmp/sigap-upload.XXXXXXXXXX')
[[ $remote_dir =~ ^/tmp/sigap-upload\.[a-zA-Z0-9]+$ ]] || { remote_dir=''; echo 'Unexpected remote upload directory'; exit 1; }
scp "${ssh_options[@]}" "$archive" "$target:$remote_dir/release.tar.gz"
digest=$(sha256sum "$archive" | cut -d ' ' -f1)
ssh "${ssh_options[@]}" -T "$target" "bash -s -- '$remote_dir' '$RELEASE_ID' '$digest'" <<'REMOTE'
set -Eeuo pipefail
work=$1
release_id=$2
digest=$3
trap 'rm -rf -- "$work"' EXIT
printf '%s  %s\n' "$digest" "$work/release.tar.gz" | sha256sum -c -
tar -xzf "$work/release.tar.gz" -C "$work" ./deploy.sh
sudo -n bash "$work/deploy.sh" "$work/release.tar.gz" "$release_id"
REMOTE
remote_dir=''
