# Deploying ProfRating on AWS Lightsail

One small Linux server runs three Docker containers:

```
Internet ──443/80──▶ web  (Caddy: HTTPS certificates, the React app, /api → api)
                      api  (FastAPI; applies database migrations on start)
                      db   (PostgreSQL; only api can reach it)
```

Caddy serves the page and the API from one domain, so the login cookie works exactly as it
does with the Vite proxy in development.

## 0. Before you start

- **Region**: check it in AWS Settings → View all projects → Overview → Additional Info → Region.
  Create everything below in that Region.
- **Plan and spend limit**: check AWS Settings → Billing. If you're on the free plan, check that
  Lightsail is on the supported services list for your plan. Run `aws freetier get-account-plan-state`
  after `aws login` to see which plan you're on.
- **A domain (optional)**: Caddy needs a hostname for HTTPS. Without one, use the free
  `<static-ip-with-dashes>.sslip.io` (e.g. `13-250-1-2.sslip.io`), which always resolves to that IP.

## 1. Create the server (Lightsail console)

1. Create instance → the Region from step 0 → **Linux/Unix**, **OS Only**, **Ubuntu 24.04 LTS**.
2. Plan: **2 GB RAM** is comfortable (building the frontend and running Postgres). 1 GB works
   if you add swap (step 3).
3. Name it `profrating` and create it.
4. **Networking → Create static IP**, attach it to the instance. (Without one, the IP changes when
   the instance restarts. A static IP is free while attached, but billed if you leave it unattached.)
5. Instance → **Networking → IPv4 firewall**: keep SSH (22), add **HTTP (80)** and **HTTPS (443)**.
   For SSH you can restrict the source to your own IP.

## 2. Connect

Use the browser **Connect using SSH** button, or download the key from Account → SSH keys:

```bash
chmod 400 ~/Downloads/LightsailDefaultKey.pem
ssh -i ~/Downloads/LightsailDefaultKey.pem ubuntu@<static-ip>
```

## 3. Install Docker and git (on the server)

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker ubuntu      # run docker without sudo; log out and back in afterwards

# Only on a 1 GB instance: 2 GB of swap so the frontend build doesn't run out of memory
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 4. Get the code and configure

```bash
git clone https://github.com/ypuppy/Prof_Rating.git     # private repo: use a GitHub token or deploy key
cd Prof_Rating/deploy
cp .env.example .env
nano .env
```

In `.env`:
- `SITE_ADDRESS`: your domain, or `13-250-1-2.sslip.io` (your static IP with dashes)
- `POSTGRES_PASSWORD` and `SECRET_KEY`: new random values (the commands are in the file)
- `COOKIE_SECURE=true`
- `SMTP_*`: the Gmail App Password for login emails (port 587 is allowed from Lightsail)

## 5. Start

```bash
docker compose up -d --build        # first build takes a few minutes
docker compose ps                   # all three should be "Up"
docker compose logs -f api          # migrations, then "Application startup complete"; Ctrl+C to leave
```

Caddy gets the HTTPS certificate on the first visit; `docker compose logs web` shows it.

## 6. Load the data

```bash
docker compose exec api python scripts/sync_nus_data.py          # faculties, departments, modules
for f in fass biz soc cde; do
  docker compose exec api python scripts/import_staff_page.py --json data/${f}_staff.json --apply
done
```

Open `https://<SITE_ADDRESS>`, log in with your NUS email, and check the staff search.

## 7. Backups

```bash
./backup.sh                          # writes deploy/backups/profrating-<date>.sql.gz
crontab -e                           # daily at 03:00, keeps the last 14:
0 3 * * * /home/ubuntu/Prof_Rating/deploy/backup.sh >> /home/ubuntu/backup.log 2>&1
```

Backups on the same server don't survive losing the server: copy them off now and then
(`scp ubuntu@<ip>:Prof_Rating/deploy/backups/*.gz .`), or turn on Lightsail automatic snapshots.

Restore: `gunzip -c backups/<file>.sql.gz | docker compose exec -T db psql -U profrating profrating`

## Updating

```bash
cd ~/Prof_Rating && git pull
cd deploy && docker compose up -d --build     # migrations run automatically when api starts
```

New staff lists (each semester): crawl and reparse on your laptop, commit the `*_staff.json`,
then `git pull` on the server and run the import loop from step 6 again.

## Stopping and costs

`docker compose down` stops the site but keeps the data (volumes). To stop paying, delete the
instance **and** release the static IP in the Lightsail console. Take a backup first.
