# Hetzner Deployment Runbook (US-0.10)

> **Status:** Phase 0 deferred — operator runs this manually with the VM and DNS in hand.

## 0. Prerequisites

- Hetzner account
- A domain (e.g. `yourdomain.dev`) with DNS managed somewhere editable (Cloudflare, Namecheap, …)
- An SSH keypair (`~/.ssh/jarvis_ed25519`)
- The decrypted `.env.production` file (or sops + age in place — see [secrets.md](../secrets.md))

## 1. Provision

- Hetzner Cloud → New Server → CAX11 (ARM, 2 vCPU, 4 GB)
- Image: Ubuntu 24.04
- SSH key: paste your public key
- Firewall: 22 / 80 / 443 only

Note the IPv4 address.

## 2. DNS

Add an `A` record:

```
jarvis.yourdomain.dev → <hetzner-ipv4>     TTL 300
```

Wait for propagation: `dig +short jarvis.yourdomain.dev`.

## 3. Harden the host

```bash
ssh root@<ip>

# disable root password / password auth entirely
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd

# firewall
apt-get update && apt-get install -y ufw fail2ban unattended-upgrades
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# unattended security upgrades
dpkg-reconfigure -plow unattended-upgrades
```

## 4. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
```

## 5. Deploy

```bash
mkdir -p /srv/jarvis && cd /srv/jarvis
git clone <your-repo> .

# decrypt or copy production env
sops --decrypt .env.production.enc > .env
chmod 600 .env

# bring up prod stack
make prod-up
```

## 6. Register webhook

Set `TELEGRAM_WEBHOOK_URL=https://jarvis.yourdomain.dev/webhooks/telegram` in `.env`, then:

```bash
make register-webhook
```

## 7. Verify

```bash
# from the server:
curl -s http://localhost:8000/health | jq

# from the outside:
curl -s https://jarvis.yourdomain.dev/health | jq

# send a message via Telegram and watch:
make logs
```

## 8. Rollback

```bash
git log --oneline -5
git checkout <previous-sha>
make prod-up
```

State (Postgres, Redis) survives — Compose restarts containers, not volumes.
