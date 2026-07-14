# Hostare pe Hostinger — ghid complet

Aplicația are un backend Python care rulează permanent (scheduler, alerte,
tracking, WebSocket) — **nu funcționează pe hostingul shared Hostinger**
(acela e pentru PHP/site-uri statice). Varianta corectă și ieftină:
**Hostinger VPS** cu Docker. Totul de mai jos este deja pregătit în repo:
`docker-compose.yml`, `Caddyfile`, Dockerfile-uri, backup.

---

## 0. Ce cumperi

1. **VPS Hostinger** — hostinger.ro → VPS → planul **KVM 1** (1 vCPU / 4 GB
   RAM / 50 GB) e suficient; **KVM 2** dacă vrei rezervă. Perioada lungă =
   preț mic (~4–6 €/lună).
2. La crearea VPS-ului alege template-ul **„Ubuntu 24.04 with Docker”**
   (categoria *OS with Panel/Apps*). Dacă ai ales Ubuntu simplu, nu-i
   problemă — pasul 2 instalează Docker manual.
3. Setează parola root / cheia SSH când ți se cere. Notează IP-ul VPS-ului
   (îl vezi în hPanel → VPS → Overview).
4. *(Opțional, recomandat)* un **domeniu** (poate fi tot de la Hostinger).

## 1. Domeniul (opțional, dar aduce HTTPS automat)

În hPanel → **Domains → DNS Zone** la domeniul tău:

| Tip | Nume | Valoare | TTL |
|-----|------|---------|-----|
| A   | `trade` (sau `@`) | IP-ul VPS-ului | 300 |

Aștepți 5–30 min propagarea. Fără domeniu aplicația merge pe
`http://IP_VPS` (fără certificat — acceptabil doar pentru teste).

## 2. Pregătirea VPS-ului (o singură dată)

Conectare (din terminalul Mac-ului):

```bash
ssh root@IP_VPS
```

Apoi pe VPS:

```bash
# dacă template-ul NU avea Docker preinstalat:
curl -fsSL https://get.docker.com | sh

# firewall: doar SSH + web
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# utilizator de aplicație (să nu rulezi totul ca root) — opțional dar corect
adduser --disabled-password --gecos "" trade
usermod -aG docker trade
```

## 3. Urcarea proiectului

Varianta A — **git** (recomandat; pune repo-ul pe GitHub privat):

```bash
su - trade
git clone https://github.com/UTILIZATOR/forex_app.git
cd forex_app
```

Varianta B — **direct de pe Mac**, fără git:

```bash
# rulat PE MAC, din ~/Desktop:
rsync -av --exclude 'backend/.venv' --exclude 'frontend/node_modules' \
      --exclude 'frontend/.next' --exclude 'backend/forex.db' \
      forex_app/ trade@IP_VPS:~/forex_app/
```

## 4. Configurare

```bash
cd ~/forex_app
cp .env.example .env
nano .env        # DOMAIN=trade.exemplu.ro  (sau lasă gol pentru IP)
```

Dacă vrei să păstrezi datele existente de pe Mac (semnale, setări, memorie
AI), copiază baza local → VPS **înainte de prima pornire**:

```bash
# pe Mac:
mkdir -p data && cp backend/forex.db data/forex.db   # o dată, local
rsync -av data/ trade@IP_VPS:~/forex_app/data/
```

## 5. Pornire

```bash
docker compose up -d --build      # prima dată durează ~3-5 min
docker compose ps                 # toate 3: backend, frontend, caddy = running
docker compose logs -f backend    # Ctrl+C ca să ieși
```

Deschide `https://trade.exemplu.ro` (sau `http://IP_VPS`). Login implicit
`admin / admin12345` → **schimbă imediat parola** în «Аккаунт», apoi
introdu cheile Twelve Data / Anthropic / Telegram în «Подключения».

## 6. Backup automat (zilnic, 03:20)

```bash
chmod +x deploy/backup.sh
(crontab -l 2>/dev/null; echo "20 3 * * * $HOME/forex_app/deploy/backup.sh $HOME/forex_app") | crontab -
./deploy/backup.sh    # test — apare backups/forex_*.db.gz
```

Restaurare: `docker compose down`, dezarhivezi peste `data/forex.db`,
`docker compose up -d`.

## 7. Update la o versiune nouă

```bash
cd ~/forex_app
git pull                       # sau rsync din nou de pe Mac
docker compose up -d --build   # reconstruiește doar ce s-a schimbat
```

Datele nu se pierd: baza stă în `./data`, certificatele în volumul Caddy.

## 8. Operare curentă

```bash
docker compose logs -f backend     # loguri live
docker compose restart backend     # restart doar API
docker compose down && docker compose up -d   # restart tot
docker system prune -f             # curățare imagini vechi (ocazional)
```

---

## Cum e legat totul (arhitectura pe VPS)

```
Internet ──443/80──> Caddy ──/api/*──> backend :8000 (FastAPI, 1 worker,
                       │                scheduler + alerte + tracking)
                       └──restul──────> frontend :3000 (Next.js standalone)
                                        backend ↔ ./data/forex.db (volum)
```

- **Un singur domeniu** pentru tot: frontend-ul cheamă `/api/...` relativ →
  zero probleme CORS, iar Caddy ia și reînnoiește singur certificatul
  Let's Encrypt (când `DOMAIN` e setat).
- **Un singur worker uvicorn** — obligatoriu: scheduler-ul, cache-urile de
  cotații și stream-ul Twelve Data trăiesc în proces; mai mulți workeri ar
  dubla semnalele/alertele.
- Cheile API introduse în UI stau în baza SQLite de pe volum, nu în imagine.

## Probleme frecvente

| Simptom | Cauză / soluție |
|---|---|
| `https://` nu se deschide, `http://` merge | DNS-ul încă nu arată spre VPS sau `DOMAIN` greșit în `.env`; `docker compose logs caddy` |
| 502 pe `/api` | backend-ul încă pornește sau a picat: `docker compose logs backend` |
| Build frontend pică pe RAM (KVM 1) | `docker compose build frontend` separat; dacă tot pică: pornește temporar swap: `fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile` |
| Ai uitat parola admin | `docker compose exec backend python -c "from app.database import SessionLocal; from app.models import User; from app.auth.security import hash_password; db=SessionLocal(); u=db.query(User).filter_by(username='admin').one(); u.password_hash=hash_password('admin12345'); db.commit(); print('reset')"` |
| Vrei alt port în loc de 80/443 | schimbă maparea la serviciul `caddy` în `docker-compose.yml` |
