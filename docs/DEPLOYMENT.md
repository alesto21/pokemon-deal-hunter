# Deploying on Proxmox (Ubuntu 24.04 LTS VM)

## VM sizing

| Resource | Recommendation | Why |
|---|---|---|
| vCPU | 2 | Scans are I/O-bound (a few HTTP requests every 30 min). The only CPU spike is `next build` during image builds. |
| RAM | 4 GB | Runtime is ~1 GB (Postgres ~200 MB, API ~120 MB, worker ~120 MB, web ~150 MB). With 2 GB, `docker compose build` of the Next.js app can hit the OOM killer. |
| Disk | 32 GB | Ubuntu ~5 GB + images ~2.5 GB. Postgres grows by a few hundred MB per year at the default retention (raw snapshots pruned after 30 days). 11 backups of a small DB. |

An LXC container also works, but Docker inside unprivileged LXC needs `nesting=1,keyctl=1` and is
more fiddly. A VM is the boring choice.

## 1. Create the VM

Proxmox UI → **Create VM**:
- OS: upload `ubuntu-24.04-live-server-amd64.iso` to local storage, then select it
- System: q35, UEFI (OVMF) + EFI disk, **QEMU guest agent: on**
- Disk: 32 GB, VirtIO SCSI single, discard on (SSD)
- CPU: 2 cores, type `host`
- Memory: 4096 MB (ballooning off or min 4096)
- Network: VirtIO, bridge `vmbr0`
- Options → **Start at boot: yes** (the system should survive host reboots)

Install Ubuntu with the OpenSSH server enabled, then:
```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y qemu-guest-agent unattended-upgrades git
sudo systemctl enable --now qemu-guest-agent
sudo dpkg-reconfigure -plow unattended-upgrades
```

## 2. Install Docker (official repository)

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt update && sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER && newgrp docker
docker compose version   # needs ≥ 2.24 (for `!reset` in docker-compose.prod.yml)
```

## 3. Clone the repo

```bash
git clone <your-repo-url> ~/pokemon-deal-hunter   # or: rsync -a --exclude node_modules --exclude .venv ./ vm:~/pokemon-deal-hunter
cd ~/pokemon-deal-hunter
```

## 4. Configure `.env`

```bash
cp .env.example .env && chmod 600 .env
# generate strong values:
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=')|" .env
sed -i "s|^API_KEY=.*|API_KEY=$(openssl rand -base64 32 | tr -d '/+=')|" .env
nano .env   # CARDTRADER_API_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DASHBOARD_PASSWORD
```
(Or run `python -m app.cli setup` on your Mac and copy the resulting `.env` over with `scp`.)

Edit preferences in `config/*.yaml` whenever you like. They hot-reload and are mounted read-only
into the containers.

## 5. Start

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## 6. Migrations

The `migrate` service runs `alembic upgrade head` automatically before the API and worker start.
To run it by hand (e.g. after `git pull`):
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate
```

## 7. Verify

```bash
docker compose ps                                   # all healthy, migrate "exited (0)"
docker compose exec api python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000/ready').read().decode())"
docker compose exec api python -m app.cli cardtrader-check --set-code TEF   # LIVE mode if token set
docker compose exec api python -m app.cli source-health
docker compose logs -f worker                       # "scheduler_started", then "collector_run_ok"
curl -s http://127.0.0.1:3000/api/health
```

## 8. Telegram

1. In Telegram, talk to **@BotFather** → `/newbot` → copy the token into `TELEGRAM_BOT_TOKEN`.
2. Send any message to your new bot, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `result[0].message.chat.id` into
   `TELEGRAM_CHAT_ID`.
3. `docker compose up -d` (recreates containers with the new env), then
   `docker compose exec api python -m app.cli test-telegram`.

## 9. Remote access with Tailscale (recommended)

Do **not** port-forward the dashboard to the internet.

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```
Then pick one:
- **Simplest:** keep `BIND_ADDRESS=127.0.0.1` and run `sudo tailscale serve --bg 3000`. The
  dashboard is then available at `https://<vm-name>.<tailnet>.ts.net` for your tailnet only, with HTTPS.
- **Or:** set `BIND_ADDRESS=<the VM's 100.x.y.z Tailscale IP>` in `.env` and
  `docker compose up -d`. Reachable only over Tailscale.

Set `DASHBOARD_PASSWORD` either way, for defence in depth.

## Backups

The prod compose file adds a `backup` container that runs `pg_dump` daily at 02:00 into
`./backups/daily`, copies Sunday dumps to `./backups/weekly`, and keeps **7 daily + 4 weekly**.

- Manual backup now: `scripts/backup-now.sh`
- Off-VM copies: also enable Proxmox's own VM backup (Datacenter → Backup, e.g. weekly to another
  disk/PBS), and/or `rsync ./backups` to your Mac or NAS.

### Restore

```bash
scripts/restore.sh backups/daily/dealhunter_2026-09-30_0200.dump
```
This stops api/worker/web, runs `pg_restore --clean --if-exists` into the running Postgres,
re-runs migrations and starts the services again. To restore onto a fresh VM: steps 1–4, then
`docker compose up -d postgres`, then the restore script, then step 5.

## Restarts, updates and scan locks

`docker compose restart worker`, `up -d --build`, host reboots and `docker compose down` are all
safe during a scan. The worker gets SIGTERM, stops scheduling new jobs, lets the running scan
finish (normally 15–20 s) and releases its lock. Compose waits up to 60 s (`stop_grace_period`)
before killing it. If it is ever killed anyway (SIGKILL, power loss), the restarted worker frees
its predecessor's lock on start-up (`stale_lock_recovered` in `docker compose logs worker`).
Any other abandoned lock expires after `scan_lock_stale_minutes` (10) in `config/sources.yaml`.
Check the status with `docker compose exec api python -m app.cli source-health`. If it shows
`worker: OVERDUE` (or the dashboard shows WORKER OVERDUE), the worker is not running:
`docker compose ps worker`, `docker compose logs --tail 50 worker`, then `docker compose up -d worker`.
Keep exactly one worker per deployment (the compose file already does; don't scale it).

Known limitation: a scan started ad hoc (dashboard "Run now" or `scan-now`) that is hard-killed
keeps its lock until the 10-minute stale timeout. Scheduled scans are recovered immediately
when the worker restarts.

Proxmox: shut the VM down with **Shutdown**, not **Stop**. That gives Docker time to stop the
containers gracefully (set the VM's shutdown timeout ≥ 90 s under Options → Start/Shutdown order).

## Updating

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker image prune -f
```
