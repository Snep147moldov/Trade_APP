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

## Investigație august 2026 — 75 tranzacții cu P&L real de broker

Prima măsurătoare pe bani reali, nu pe modelul aplicației. Metrica e multiplul R
(`mt5_pnl / risk_amount`), nu euro bruți: riscul per tranzacție a variat 2.4 → 20 EUR
în perioadă, iar mediile în euro amestecă poziții de mărimi diferite.

```
75 tranzacții, total −57.19R
câștiguri  22 · media +1.07R   (ținta 1.8R)
zerouri     8 · media  0.00R
pierderi   45 · media −1.79R   (stopul ar trebui să plafoneze la −1.0R)
winrate 29.3% istoric · 25.7% după reparațiile de execuție
prag de rentabilitate la R:R 1.8 = 35.7%
```

**Chiar cu execuție perfectă (pierderi exact −1.0R), E[R] = −0.40R.** Deficitul e
în selecția semnalelor, nu în execuție — nicio reparație de dimensionare nu acoperă
10 puncte de winrate.

Efectul reparațiilor, măsurat: pierderea medie −2.27R → −1.34R, câștigul +0.89R →
+1.34R.

Pe timeframe (bani de broker): 4h −7.97 EUR (3 tranz., WR 33%) · 1h −147.01
(41, 39%) · 15m −181.14 (30, 30%).

### Ipoteze infirmate de date (nu le relua)

1. **Breakeven-ul NU strică nimic.** Cu breakeven: 15 tranz., +0.58R medie, +8.7R
   total. Fără: 60 tranz., −1.10R medie, −65.89R. Suspiciunea era că mută stopul
   la intrare și transformă câștigătoarele în zerouri — datele arată invers.
2. **Bug-ul cu ordinele multiple NU explică pierderile mari.** Cu un singur ordin
   pierderea medie era tot −1.74R (2 ordine: −2.15R, 3 ordine: −1.66R).
3. **„Încrederea mare selectează tranzacții proaste" era artefact.** Segmentul
   >80% pierduse −106.82 EUR pe 7 tranzacții, dar −102.68 din ele veneau din
   patru tranzacții USD/JPY din 23 iulie cu 2–3 ordine, unde riscul se înmulțea
   cu numărul de ordine. Concluzia 6 din secțiunea iulie e contaminată la fel.
4. **„Câștigurile realizau 5% din promis" NU era spread.** Volumul trimis
   brokerului era de 7–15× mai mic decât cel calculat (dimensionarea pe risc
   încă inactivă, se folosea lot fix). Concluzia 5 din iulie descrie același
   artefact.
5. **„Formula veche era mai bună" — nu există.** Vezi concluzia 2 din iulie:
   engine-ul s-a schimbat o singură dată și acea schimbare nu produce tranzacții
   diferite. Ce s-a schimbat între timp a fost dimensionarea.

### Sursă de tranzacționare străină pe cont

Ordinele aplicației au comentariu `Codnixy #id`. În istoricul brokerului există
tranzacții XAUUSD cu **comentariu gol**, lot 0.05, deschise/închise la 1–10 minute,
direcție inversată des (EA sau altcineva — utilizatorul le-a confirmat ca fiind
sub controlul lui). **Orice analiză trebuie să filtreze după comentariu**, altfel
amestecă două strategii.

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

## Ce s-a reparat în august (același branch)

| Commit | Problemă | Simptom măsurat |
|---|---|---|
| `4236f3a` | `mt5_region` cache-uit diverge de regiunea reală MetaApi | `NotFoundError` la fiecare ordin; `status()` se auto-repara, restul nu |
| `5bd228b` | Semnale rezolvate pe lumânări **simulate** în weekend | site −146.95 EUR/zi vs broker +37.85, balanță neschimbată |
| `92136cb` | `units_to_lots` verifica toleranța doar când rotunjirea dădea zero | 700 units USD/JPY → 0.01 lot (risc ×1.43) trecea nechestionat |
| `92136cb` | `signal_lots` citea `max_risk_overshoot` din app-config, unde cheia nu există | setarea din UI ignorată tăcut |
| `8c62e67` | Riscul se **înmulțea** cu numărul de ordine în loc să se împartă | semnal de 12 EUR risca 37; grupul #83–#88 = −102 EUR |
| `577b8e8` | `round(units)` → 0 pe metale, `signal_lots` cădea pe lot fix | #172 XAU: risc declarat 9.91, pierdere reală 54.35 |
| `d1a7010` | Aplicația rula o simulare paralelă pe lumânări peste poziții vii | #216 GBP/JPY `hit_sl` în app la +8.08 EUR la broker; prețul nu atinsese stopul |
| `a69253a` | Închiderea semnalului era declanșată pe eveniment, nu pe stare | un tick ratat (restart) lăsa semnalul `open` pe veci (#336 cu +50.97 încasat) |
| `5a34990` | Dimensionarea pornea de la P&L de hârtie | 275 semnale neexecutate trăgeau −231.59 EUR din baza de calcul |
| `5a34990` | `open_risk` număra semnale `unconfirmed` | putea epuiza `max_open_risk_pct` și bloca tranzacționarea reală |
| `f873dbd` | Butoanele ×2/×3 multiplicau riscul pe metale (lot minim indivizibil) | #321 XPT declarat −20.50, decontat −41.02 |

**Verificare că dimensionarea e corectă acum:** la 1 ordin, `pnl_money` și `mt5_pnl`
coincid la cent (#338 +18.18/+18.18, #331 −12.70/−12.70, #340 −9.60/−9.60).

## Instrumente de analiză

`backend/app/tools/sweep.py` — măturare de parametri pe lumânări reale, prin
același motor care tranzacționează (`backtest.engine.simulate`). Grilă:
prag de scor × R:R × lățime stop, pe mai multe timeframe-uri, cu tranzacțiile
tuturor perechilor puse într-un pool comun (per pereche sunt 3–4 tranzacții = zgomot).

```bash
docker compose exec -T backend python3 -m app.tools.sweep            # 15m,1h,4h
docker compose exec -T backend python3 -m app.tools.sweep --tf 1h --bars 2000
```

Refuză lumânările sintetice și exclude instrumentele din `blocked_instruments`.
**Atenție:** la rulări lungi providerul începe să întoarcă sintetic (limită de
rată) — pe 4h, după 15m și 1h, jumătate din perechi cad. Rulează timeframe-urile
separat când contează eșantionul.

## Convenții

- Text către utilizator (Telegram, UI, mesaje de eroare): **rusă**.
- Docs de deploy: română. Comentarii în cod: engleză sau rusă, ca în fișierul vecin.
- Comentariile explică **de ce**, cu cifre când există (vezi `mt5.py:units_to_lots`).
- Funcțiile MT5 returnează `{"ok": bool, ...}` și **nu ridică excepții** —
  trading-ul nu are voie să omoare bucla scheduler-ului.
- Porțile de risc adaugă un motiv în `reasons[]`; UI le afișează ca atare.

## Setări cu justificare din date (august 2026)

Toate schimbate pe baza celor 75 de tranzacții reale. **Setările persistate în DB
au prioritate — schimbarea default-ului din `config.py` NU afectează producția**,
trebuie actualizat și rândul `strategy` din tabela `settings`.

| Setare | Valoare | De ce |
|---|---|---|
| `min_score` | 0.45 | winrate sub pragul de rentabilitate; iulie a măsurat 31%→39% la prag 0.3→0.4, 0.45 e pariu pe continuarea relației |
| `max_risk_overshoot` | 1.05 | la 1.25 pierderea medie rămânea −1.34R; toleranța se consuma integral |
| `max_manual_overshoot` | 3.0 | plafon pentru confirmarea manuală de depășire (buton separat în Telegram) |
| `blocked_instruments` | XPT_USD, XAG_USD | 14 tranz. / −161.47 EUR în 8 zile; XPT 0 câștiguri din 5, XAG 0 din 2. Fără ele perioada e +10.88 |
| `daily_cutoff_hour` | 22 (București) | ordine noi blocate seara |
| `quiet_resume_hour` | 9 | 16 semnale consecutive 22:37–01:37, toate stop-loss |
| `market_scan_min_confidence` | 70 | doar control de zgomot pentru instrumentele din afara watchlist-ului; încrederea nu are legătură demonstrată cu rezultatul |
| `AUTOSCAN_TFS` | 1h, 4h, 1d | 15m scos: 30 tranz., WR 30%, −181 EUR |

XAU rămâne activ: singurul metal la breakeven (+50.97 EUR în perioadă).

## Rămas deschis

- **Winrate 25.7% la prag de rentabilitate 35.7%.** Problema centrală. Reparațiile
  de execuție au adus pierderea medie de la −2.27R la −1.34R, dar nu pot închide
  un deficit de 10 puncte de winrate. Următorul pas e măturarea de parametri
  (`tools/sweep.py`) — dacă nicio combinație nu iese pe plus, discuția se mută
  la ce factori intră în formulă, nu la cum se ponderează.
- **Cuantizarea lotului subdimensionează câștigurile.** Lot minim 0.01: o poziție
  calculată la 0.015 se rotunjește în jos la 0.01 (−33%). Rotunjirea în sus e
  plafonată de `max_risk_overshoot`, cea în jos trece tăcut — deci sistemul
  subdimensionează sistematic. Contribuie la câștiguri de +1.07R din 1.8R ținta.
  Fix candidat: prag și pe partea de jos (respinge sub ~0.8× din calculat).
- Spread/swap nu intră în P&L-ul urmărit de aplicație (la broker sunt 0 pe contul
  curent — verificat pe 147 înregistrări).
- 7 semnale închise fals pe lumânări simulate în weekend (+28.69 EUR inventat)
  poluează statisticile istorice. Comandă de marcare `invalid` pregătită, nerulată.
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
