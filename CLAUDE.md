# Aurex — context de lucru

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

Ordinele aplicației au comentariu `Aurex #id` (până la redenumirea din
11 septembrie — `Codnixy #id`; ambele sunt recunoscute, vezi `config.is_our_order`).
În istoricul brokerului există
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

## Descoperirea centrală (august 2026): formula tranzacționa invers

Măsurat cu `tools/factors` pe 22.928 observații orare, 16 perechi, orizont 6 bare.
**Information coefficient e NEGATIV la șapte factori din opt:**

```
rsi -0.072 · kama_er -0.065 · roc -0.058 · tsmom -0.047
stoch -0.047 · trend -0.044 · macd -0.024
bollinger +0.070   ← singurul pozitiv, singurul de revenire la medie
```

Mărimile sunt în intervalul publicat pentru premii reale (0.04–0.10) — deci
factorii **conțin informație**, dar motorul le citea semnul invers. Perechile
revin la medie pe orizont de ore; formula era construită pentru trend.

Confirmat independent pe bani: măturarea a 720 de combinații dă **0 pozitive**
în direcția normală și **58 pozitive** inversat.

### Validare pe date nevăzute (`tools/validate`)

```
inversare totală, prag 0.25 / R:R 1.8 / SL 2.0 / fără ieșire pe timp
  prima jumătate   359 tranz.  WR 39.3%  E[R] +0.075  PF 1.13
  a doua jumătate  419 tranz.  WR 39.6%  E[R] +0.075  PF 1.13
```

Două perioade independente, aceeași cifră — nu e potrivire pe istoric.

**Filtrul pe ore trece testul cinstit** (ore alese DOAR din prima jumătate,
aplicate pe a doua): `E[R] +0.075 → +0.146`, `PF 1.13 → 1.26`, cu 30% mai
puține tranzacții. Ore blocate (UTC): **2, 6, 7, 9, 10, 11, 20**.
UTC 7–11 = dimineața Londrei, unde piața chiar face trend — exact acolo unde o
strategie de revenire la medie trebuie să piardă.

### Ipoteză respinsă: corecția pe factori

Ideea „inversăm doar factorii de momentum, `bollinger` are deja semnul corect"
sună logic și e **mai proastă**: `E[R] +0.024`, `PF 1.04`, instabil între
jumătăți (+0.032 / +0.017) față de +0.075 / 1.13 la inversarea totală.
De ce — neelucidat. Posibil IC-ul pozitiv al lui `bollinger` e parțial zgomot,
sau se comportă altfel în combinație decât singur. Cod: `INVERTED_SIGNS` vs
`MEASURED_SIGNS` în `signals/engine.py`.

### Ipoteză respinsă: mai puțini factori

Matricea de corelații arată redundanță masivă (`kama_er ~ roc` = 0.95,
`bollinger ~ rsi` = −0.80, 85% din pondere în perechi corelate), iar IC-ul
scorului combinat (0.067) e **sub** cel mai bun factor singur (0.087). Concluzia
firească — „folosim un factor, nu opt" — e **greșită**:

```
formula completă (16 perechi)      +0.132 / +0.165   total +0.149  PF 1.26
doar bollinger (11 perechi)        +0.215 / +0.053   total +0.131  PF 1.23
bollinger+rsi, semne măsurate      +0.088 / −0.007   total +0.040  PF 1.07
```

Varianta simplă e nu doar mai slabă, ci **instabilă**: cade de patru ori între
jumătăți, unde formula completă se îmbunătățește. Explicație probabilă: IC
măsoară corelație de rang monotonă, dar tranzacționarea folosește un **prag**.
Media mai multor semnale corelate e mai stabilă la extreme, iar acolo se
deschid tranzacțiile. Cod: `factor_subset` în `score_components`.

**Atenție la testare:** `--invert` inversează TOȚI factorii. Pentru un subset
care conține `bollinger` (singurul cu semn corect) asta garantează pierdere —
`bollinger` singur cu `--invert` dă −0.208, cu semnul lui natural +0.131.
Pentru subseturi mixte se folosește `--measured`.

### Ce NU a fost validat

- **`ai_weight`** — backtestul rulează cu 0. Cele 15% de AI din producție nu au
  fost testate în varianta inversată. De aceea `ai_weight = 0` la pornire.
- **`htf_trend`** (12% pondere) — backtestul e pe un singur timeframe.
- **Spread** — backtestul presupune 1.0 punct uniform; pe crossuri e mai mare.
- **4h și 1d** — validat doar 1h, deși ambele rulează în autoscan.
- **Factorii exogeni** (`signals/exogenous.py`): `session` IC +0.013 și
  `dollar_align` +0.002 sunt zgomot. `vol_regime` dă +0.047 și e necorelat cu
  tot restul (|r| ≤ 0.09) — dar e un factor FĂRĂ direcție, deci rezultatul e
  suspect: XAU are și volatilitate mare, și trend puternic în eșantion. De
  verificat fără aur înainte de a-l lua în serios.

## Investigație septembrie 2026 — 37 tranzacții pe cont real (100 EUR)

Cont FusionMarkets-Live 429070, 98.19 -> 59.99 EUR. Ale noastre: 29 tranzacții,
−38.20 EUR. Măsurat cu `tools/report.py`.

```
37 tranz. · WR 24.3% · E[R] −0.181 · PF 0.69   (ținta din backtest: +0.146)
majori (cu USD)   16 tranz. · WR 50.0% · E[R] +0.187 · PF 1.44
crossuri          21 tranz. · WR  4.8% · E[R] −0.461 · PF 0.32
```

**Pe majori formula se poartă exact ca în backtest.** Crossurile: un singur
câștig din 21. La un winrate real de 40% asta are probabilitatea 0.03% — nu e
noroc prost. **Rămâne neexplicat.** Două ipoteze verificate și respinse mai jos.

### Ipoteză respinsă: semnalele erau construite pe simulator

Simulatorul nu iese din banda de 0.85% în jurul lui `base_price` (măsurat
0.79% pe 3000 de bare). Din 37 de tranzacții ajunse la broker, **una singură**
are intrarea în bandă. Restul au fost pe prețuri reale.

Garda rămâne necesară: până la `92946b5` nimic nu împiedica deschiderea unui
semnal pe lumânări sintetice, iar #531 NZD/USD a primit
`TRADE_RETCODE_INVALID_STOPS` fiindcă nivelurile veneau de lângă `base_price`
0.61 în timp ce piața era la 0.588.

### Ipoteză respinsă: crossurile-s prea scumpe la spread

Părea decisivă — cu piața **închisă**, spreadul dus-întors era 236% din R pe
AUD/CHF, 204% pe CAD/CHF. Peste 100% înseamnă că tranzacția nu poate ieși pe
plus, aritmetic. **Artefact de piață închisă.** Aceleași perechi, cu piața
deschisă:

```
AUD_CHF 17.10 п -> 0.10 п (1.4% din R)    GBP_CHF 7.70 -> 0.00 (0.0%)
CAD_CHF 11.90 п -> 0.90 п (15.4%)         AUD_NZD 19.60 -> 0.30 (2.1%)
NZD_CAD 15.20 п -> 1.10 п (12.0%)
```

Tot ce nu-i paladiu stă sub 16% din R. **Măsurați spreadul doar cu piața
deschisă.** `tools/report.py` afișează și decalajul provider-broker, adăugat
ca următoarea ipoteză de verificat (nivelurile se calculează pe închiderea
lumânării providerului, ordinul se execută la prețul brokerului).

Reparație colaterală, reală: `catalog_spread` întoarce **0.02% pentru orice
pereche forex**, deci poarta `max_cost_ratio` scoria EUR/USD drept mai scump
decât NZD/CAD și nu s-a declanșat niciodată. Acum citește bid/ask de la broker
(`mt5.symbol_price`, cache 60s).

### Validare 7 septembrie: ținta lungă e singura care ține

1499 bare 1h, 16 perechi, `--invert --min-score 0.25 --sl 2.0 --trend-hours 9,10,11`.

```
            prima jum.        a doua jum.
R:R 0.5     +0.033            -0.086
R:R 0.8     +0.067            -0.075
R:R 1.0     +0.114            -0.053
R:R 1.2     +0.190            -0.058
R:R 1.3     +0.183            -0.058
R:R 1.8     +0.233            +0.013   <- singura cu ambele jumătăți pozitive
```

Monoton: **cu cât ținta e mai lungă, cu atât mai bine.** Ideea „luăm profit la
+30-40 de puncte în loc să așteptăm ținta" e testată și e mai proastă la orice
prag. La 1.8: total +0.123, PF 1.21 — coerent cu august (+0.149, PF 1.26).

A doua jumătate (≈7 aug – 7 sep) e la **zero**, nu pe plus: E[R] +0.013,
PF 1.02, WR 37.1%. Exact perioada în care contul real a pierdut 38 EUR.

### Ipoteze respinse la aceeași rulare

**Breakeven — orice formă răstoarnă a doua jumătate în minus:**

```
fără transfer            +0.233 / +0.013
+1.3R -> stop în 0       +0.232 / -0.015
+1.3R -> blochează 0.5R  +0.226 / -0.034
+1.0R -> blochează 0.5R  +0.206 / -0.051
```

Winrate crește (45% -> 53%), așteptarea scade. Închiderile la `+0.00 EUR` care
enervau utilizatorul sunt prețul corect: alternativa măsoară mai prost.
`breakeven_at_r = 0`.

**Ieșirea pe timp cât tranzacția e în plus** (`profit_exit_bars`): 6 bare la
+0.3R dă +0.123 / −0.008, 8 bare la +0.5R dă +0.146 / −0.019, față de
+0.233 / +0.013 fără ea. Taie din câștiguri mai mult decât salvează din
pierderi. `profit_exit_bars = 0`.

**Filtrul pe ore nu mai ajută la R:R 1.8.** Testul cinstit (ore alese din
prima jumătate, aplicate pe a doua): +0.013 -> −0.041. În august ajuta
(+0.075 -> +0.146) la aceeași metodă. Nu-l reintroduceți fără o nouă măsurare.

### Bugetul providerului și abonamentul

Cache 1h = 5 min, 16 perechi × (1h + confirmare TF superior) = 32 combinații
× 12 cereri/oră = **9216/zi**. `TWELVEDATA_RPM` (implicit 7) trebuie ridicat
odată cu tariful, altfel plata nu schimbă nimic — pe VPS e în `.env`, nu în
`docker-compose.yml`.

Abonamentul Twelve Data căzuse pe 15 august (factură refuzată). Dashboard-ul
arăta „Grow 55 activ" în timp ce API-ul întorcea 401 „subscription expired" —
**nu vă luați după dashboard, întrebați `/api_usage`**. `tools/feed.py` face
exact asta și afișează corpul brut al răspunsului.

### Mesaj fantomă în Telegram

`CONFIDENCE_TFS` trimitea „Движок уверен" cu preț, SL și TP, fără să creeze
semnal și fără să deschidă poziție — și rula pe 1h (dublând autoscanul) și pe
4h (care nu se tranzacționează deloc). Acum se derivă din `AUTOSCAN_TFS` și
scrie explicit că nu se deschide nimic.

## Instrumente de analiză

`backend/app/tools/sweep.py` — măturare de parametri pe lumânări reale, prin
același motor care tranzacționează (`backtest.engine.simulate`). Grilă:
prag de scor × R:R × lățime stop, pe mai multe timeframe-uri, cu tranzacțiile
tuturor perechilor puse într-un pool comun (per pereche sunt 3–4 tranzacții = zgomot).

```bash
docker compose exec -T backend python3 -m app.tools.sweep --tf 1h --both
docker compose exec -T backend python3 -m app.tools.factors --tf 1h --horizon 6
docker compose exec -T backend python3 -m app.tools.excursion --tf 1h
docker compose exec -T backend python3 -m app.tools.validate --invert \
    --min-score 0.25 --rr 1.8 --sl 2.0
```

- `sweep` — grilă prag × R:R × stop × ieșire pe timp, cu `--invert` / `--both`
- `factors` — information coefficient per factor + corelația dintre ei
- `excursion` — cât merge prețul în favoare înainte să se închidă tranzacția
- `validate` — verificare pe jumătatea nevăzută + defalcare pe oră de intrare

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
