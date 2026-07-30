# Codnixy AI Trade — context de lucru

Bot de asistare a deciziilor de trading. Semnale deterministe (formule + indicatori),
notificate în Telegram, executate opțional în MT5 prin MetaApi. Broker curent:
**FusionMarkets-Demo**. Toată contabilitatea în EUR.

`README.md` descrie arhitectura și providerii. Fișierul ăsta ține contextul
operațional și concluziile investigațiilor — ce nu se vede din cod.

## Unde e ce

```
backend/app/
  signals/engine.py      formula de confluență (ponderi, regim trend/flat)
  services/analysis.py   orchestrare: candles -> indicatori -> scor -> niveluri
  risk/manager.py        porțile de risc (toate refuzurile de semnal trec pe aici)
  services/tracking.py   ciclul de viață al semnalului + poarta de confirmare
  services/telegram_bot.py  long-poll callback-uri, butoanele Купить/Пропустить
  services/scheduler.py  buclele de fundal (autoscan, market scan, ticks)
  services/mt5.py        MetaApi: ordine, simboluri, dimensionare lot
  services/candles.py    provideri + simulator intern (atenție, vezi mai jos)
  backtest/engine.py     backtest pe aceeași formulă
  tools/export_trades.py export read-only al istoricului, cu credențiale redactate
frontend/                Next.js 16 — vezi frontend/AGENTS.md ÎNAINTE de a scrie cod
```

## Rulare locală (Mac) — capcane

**`.venv` e stricat.** A fost creat la calea veche `~/Desktop/forex_app/backend/.venv`;
proiectul s-a mutat în `~/Desktop/projects/my/forex_app`. Lipsește symlink-ul
`python`, dar `site-packages` e intact. Rulează așa:

```bash
cd backend
PY=/opt/homebrew/opt/python@3.14/bin/python3.14
PYTHONPATH=.venv/lib/python3.14/site-packages $PY -c "import app.main"
```

**`frontend/node_modules/.bin` e gol**, deși pachetele există. Pentru typecheck:

```bash
cd frontend && node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json
```

DB local: `backend/forex.db` — **gol (0 semnale)**. Datele reale sunt pe VPS.
Nu rula `sqlite3`/`python` din altă cwd: creezi un `forex.db` gol aiurea.

## Producție (VPS)

```
host   root@srv1830103 : ~/forex_app          (docker compose: backend, frontend, caddy)
DB     host ./data/forex.db  ->  container /data/forex.db     NU /app/forex.db
env    DATABASE_URL=sqlite:////data/forex.db
porturi backend e `expose`, nu `ports` — NU răspunde pe localhost:8000 din host.
        Doar Caddy publică 80/443.
```

Comenzi utile:

```bash
docker compose exec -T backend python3 -c "import sqlite3; print(sqlite3.connect('/data/forex.db')...)"
docker compose logs --tail=40 backend
docker compose up -d --build
```

**Obligatoriu 1 singur worker uvicorn** — scheduler-ul, cache-urile și stream-ul WS
trăiesc în proces; mai mulți workeri dublează semnalele.

Migrații: `_COLUMN_ADDS` în `backend/app/database.py`, aplicate la pornire.
Setările persistate în tabela `settings` **au prioritate față de defaults din
`config.py`** — schimbarea unui default NU afectează instalările existente.

## Concluzii demonstrate (nu le re-deriva)

Investigație iulie 2026, pe 199 semnale închise reale + backtest pe date de piață.

1. **Formula NU e stricată.** WR 32.5% (fără zero-uri) vs prag de rentabilitate
   35.7% la R:R 1.8. `z = -0.85, p = 0.20` — nedistinct statistic de breakeven.
   E[R] = −0.053, în zgomot față de zero.
2. **Nu există regresie de formulă.** Engine-ul vechi (`4fe5702`) vs HEAD pe date
   identice dă seturi de tranzacții **identice bit-cu-bit** (331 trade-uri).
   Ramura „ranging" din `4ec648d` atinge 15.8% din bare, dar scorul nu ajunge
   la prag acolo → zero tranzacții diferite.
3. **Baseline-ul „WR 84%" era fals.** `backtest_runs` 1 și 2 (06-07 / 12-07) au
   rulat pe **simulatorul intern** — sumă de sinusoide, `EUR = 1.0850`. EUR/USD
   real în acea fereastră: 1.1330–1.1651; tranzacțiile stocate erau la 1.078–1.087.
   `get_candles` cade tăcut pe simulator când providerul nu are instrumentul.
   Acum lumânările simulate sunt marcate `simulated: True` și backtestul
   raportează `data_source`.
4. **Nu e eroare de semn.** Inversarea direcției pe 1890 tranzacții:
   WR 28.8% → 37.0%, dar E[R] rămâne negativ (−0.058). Un semn inversat ar fi
   făcut varianta inversată clar profitabilă.
5. **Banii se pierdeau în execuție, nu în semnale.** Măsurat pe tranzacțiile
   legate la broker: câștigurile realizau **4.7%** din cât promitea aplicația,
   pierderile **193%**. App raporta +10.40 EUR, brokerul plătise −219.91 EUR.
6. **Încrederea motorului e anti-predictivă.** `corr(confidence, win) = −0.093`.
   Sub 60% încredere → WR 31.2%; peste 75% (poarta autotrade) → WR 25.0%.
   `autotrade_min_confidence` selectează tranzacțiile mai proaste.
7. **`pnl_pips` nu e comparabil între instrumente.** `auto_pip()` scalează după
   `base_price` din catalog, iar catalogul e rămas mult în urmă (ZEC listat 30,
   real 476.89). „ZEC −10055 pips" și „ATOM −176.3 pips" sunt amândouă ≈ −1R.
8. Categorii, pe date reale: crypto major E[R] −0.004 · crypto exotic −0.223 ·
   metale −0.379 · forex −0.504. Dintre metale doar **XAU** e la breakeven
   (PF ~1.01); XAG și XPT sunt clar negative.

## Ce s-a reparat (branch `fix/execution-layer`, commit `074a311`)

| Zonă | Înainte | Acum |
|---|---|---|
| Confirmare Telegram | butoane decorative; autotrade/mirror trimiteau ordinul independent | `confirm_state` autoritar: Accept deschide, Decline/tăcere nu |
| Dimensionare lot | `units_to_lots` umfla tăcut la lotul minim 0.01 → risc ×2.4–5.6 | refuză (0 loturi) dacă riscul nu încape; `max_risk_overshoot` |
| Simboluri broker | DYDX & co. ajungeau la user, respinse la execuție | scanul filtrează după lista brokerului (cache 1h) |
| Spread | necontabilizat | `max_cost_ratio` = 0.25 respinge altcoin ilichid |
| Scale-out | n=2 dădea 1.4R mediu contra −1R pierdere | scară centrată pe țintă, 1.8R la orice n |
| Breakeven | 1.0R → 36/199 (18%) închise la exact 0.00 EUR | 1.3R |

Test: `19/19` verificări pe poarta de confirmare (Accept / Decline / timeout /
accept târziu / chat străin / gate off). Rulat cu un broker fals care înregistrează
fiecare ordin — verifică execuția reală, nu doar starea.

## Convenții

- Text către utilizator (Telegram, UI, mesaje de eroare): **rusă**.
- Docs de deploy: română. Comentarii în cod: engleză sau rusă, ca în fișierul vecin.
- Comentariile explică **de ce**, cu cifre când există (vezi `mt5.py:units_to_lots`).
- Funcțiile MT5 returnează `{"ok": bool, ...}` și **nu ridică excepții** —
  trading-ul nu are voie să omoare bucla scheduler-ului.
- Porțile de risc adaugă un motiv în `reasons[]`; UI le afișează ca atare.

## Rămas deschis

- **Doar 19 din 199 semnale aveau P&L de broker.** Nediagnosticat: `mt5_sync` nu
  leagă, sau semnalele n-au fost executate. Cu poarta de confirmare activă se
  poate distinge acum.
- Feed divergent app↔broker: 1 caz din 6 (`hit_tp` în app, pierdere la broker).
  Marginal față de dimensionare, dar real — aplicația evaluează pe lumânări mid
  Twelve Data, brokerul umple pe bid/ask.
- Spread/swap nu intră deloc în P&L-ul urmărit de aplicație.
- Prag Hurst 0.55 vs mediană măsurată 0.546 → comutatorul de regim e practic
  zgomot. Estimator R/S pe 100 randamente, 4 puncte de regresie.
- `_kelly_fraction` numără câștigurile pe `pnl_pips`, `signal_stats` pe
  `pnl_money` — surse divergente.
- Docstring-ul din `engine.py` citează Moskowitz/Ooi/Pedersen 2012 pentru
  `tsmom`, dar studiul e pe lookback 12 luni / deținere 1 lună, pe futures
  lichide. Codul aplică 20 de bare pe 15m/1h. Citarea nu susține utilizarea.

## Securitate

Credențialele (parolă MT5, chei API) stau **în clar** în tabela `settings`.
Orice copie a `forex.db` le conține. `tools/export_trades.py` le redactează —
folosește-l când partajezi istoricul, nu fișierul `.db` brut.
