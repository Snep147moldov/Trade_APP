# Audit strategie Aurex — 12–13 septembrie 2026

**Am corectat erori de calcul, execuție simulată, selecție a datelor și evidență MT5. Nu am demonstrat o creștere considerabilă și stabilă a win rate-ului. Variantele testate, inclusiv AI, nu justifică activarea unei strategii noi pe bani reali.** Rezultatul auditului este cod corectat, evaluări reproductibile și respingerea explicită a variantelor fără avantaj demonstrat.

Modificările sunt în proiectul local. VPS-ul `109.176.198.229` a fost consultat pentru un export al datelor; nu am făcut deploy, nu am schimbat setările lui și nu am trimis ordine sau mesaje Telegram. Baza locală și baza VPS nu au fost modificate în timpul testelor. Testele brokerului folosesc simulări în memorie.

## 1. Ce arată tranzacțiile existente

Sursa este exportul VPS: **667 semnale, dintre care 656 închise; 160 tranzacții executate cu rezultat MT5 salvat**. Baza locală conținea doar 52 de semnale și nu putea reprezenta activitatea din producție.

| Populație și metodă | Închise | Câștigătoare | Win rate | P&L EUR |
|---|---:|---:|---:|---:|
| Calculul vechi al dashboardului: toate semnalele, `pnl_money` | 656 | 188 | 28,66% | −9,49 |
| Calcul corectat: numai execuții cu `mt5_pnl` disponibil | 160 | 54 | **33,75%** | **−385,15** |
| Execuții cu intrare începând din 28 august | 43 | 8 | **18,60%** | **−47,41** |

Diferența dintre primele două rânduri este o **corectare a populației și a sursei P&L**, nu o îmbunătățire a tranzacțiilor. Semnalele simulate ascundeau amploarea pierderii brokerului. În cele 160 de execuții există 102 pierderi și 4 rezultate zero; zero rămâne în numitor, dar nu este pierdere.

Pentru cele 160 de execuții: profit factor în EUR **0,5501**, rezultat mediu **−0,4180R**, câștig mediu **+1,0515R**, pierdere medie **−1,2124R**. Intervalul Wilson 95% pentru win rate este **26,88–41,38%**. În perioada recentă este **9,74–32,62%**. Aceste intervale sunt aproximări binomiale; tranzacțiile valutare corelate reduc informația efectivă.

**Limită a reconcilierii:** aceste cifre recalculează câmpurile MT5 deja salvate. Cererea separată pentru istoricul complet al deal-urilor brokerului nu a returnat un export utilizabil. Prin urmare, nu afirm că am reverificat fiecare comision sau fiecare închidere parțială istorică. Erorile de sincronizare descrise mai jos sunt confirmate în cod și reproduse prin teste; efectul lor exact asupra trecutului necesită backfill reușit din broker.

### Concentrarea pierderilor

| Grup | Tranzacții | Win rate | P&L EUR | E[R] |
|---|---:|---:|---:|---:|
| Perechi cu USD, fără metale | 70 | 48,57% | +12,19 | −0,0807 |
| Cross-uri valutare | 67 | 25,37% | −117,43 | −0,2314 |
| Metale | 23 | 13,04% | −279,91 | −1,9884 |
| 15 minute | 34 | 29,41% | −188,30 | −1,2673 |
| 1 oră | 113 | 33,63% | −211,94 | −0,2014 |
| 4 ore | 7 | 42,86% | +2,76 | −0,1835 |
| 1 zi | 3 | 100% | +18,51 | +0,7846 |

Grupele de instrumente și cele de timeframe sunt două descompuneri ale aceleiași populații; nu se adună între ele. Mai există 3 tranzacții pe 5m, cu −6,18 EUR și win rate 0%.

Metalele explică aproximativ 73% din pierderea netă agregată. Pe 15m, pierderea medie este **2,11R**, mult peste stopul teoretic de 1R. Acest fapt indică o problemă de risc realizat, dimensionare, execuție sau evidență; exportul disponibil nu permite atribuirea exactă între aceste cauze. Pe majors, profitul monetar ușor pozitiv coexistă cu E[R] negativ deoarece mărimile pozițiilor diferă. Cele 3 tranzacții zilnice nu demonstrează un win rate viitor de 100%.

## 2. Formula și indicatorii

Formula este `score = Σ(weight_i × signed_component_i)`, limitată la [−1, +1]. Ea reprezintă o combinație de indicatori, **nu o probabilitate calibrată de câștig**.

| Componentă | Calcul | Observație |
|---|---|---|
| Trend | `tanh((EMA20 − EMA50) / ATR14)` | Direcție normalizată la volatilitate |
| TSMOM | `tanh((close_t − close_t−20) / (ATR14 × √20))` | Proxy de momentum; nu reproducerea exactă a unei strategii academice |
| KAMA ER | `abs(close_t − close_t−10) / Σabs(Δclose)` × semnul mișcării | Eficiența traseului; nu este media adaptivă KAMA |
| MACD | `tanh(2 × histogram_MACD / ATR14)` | Accelerație; EMA 12/26 și semnal 9 |
| RSI | `(RSI14 − 50)/50` în trend; contrarian peste 70/sub 30 în range | Semantica se schimbă cu regimul |
| Stochastic | Combinație 60% diferență K−D, 40% poziție K | K 14, neteziri 3 și 3; contrarian în range |
| Bollinger | `clip(2 × (0,5 − %B))` | Revenire spre medie; fereastră 20, benzi 2σ |
| ROC | `tanh(ROC10 / (2 × ATR%))` | Altă măsură a mișcării prețului |
| HTF | Trend calculat pe timeframe superior închis | Eliminat și ponderile renormalizate dacă lipsește |
| AI știri | `clip(sentiment_base − sentiment_quote)` | Vector arhivat, cu depreciere temporală |
| AI predicție | Bias direcțional pentru pereche | Contribuție separată, plafon comun cu știrile |

ATR și ADX folosesc netezirea Wilder. RSI are acum valoare neutră 50 când atât câștigul, cât și pierderea medie sunt zero. Stochastic nu mai este contaminat de `NaN` sau de valori artificiale în perioada de inițializare. EMA, SMA, ATR, RSI, ADX și seriile de scoring sunt verificate prin teste, inclusiv invarianta la adăugarea de date viitoare.

Regimul vechi este range numai dacă `ADX14 < 18` **și** Hurst < 0,55. Hurst este estimat R/S clasic pe 100 de randamente logaritmice, cu patru scări. Nu este testul R/S modificat al lui Lo și nu dovedește statistic existența unui trend. Pragul binar poate schimba brusc sensul oscilatoarelor.

Ponderile tehnice inițiale sunt 0,16/0,14/0,13/0,12/0,09/0,06/0,10/0,05, plus HTF 0,12. Sunt ponderi relative, apoi sunt normalizate. Trend, TSMOM, ER, MACD și ROC reprezintă **aproximativ 70,6% din bugetul tehnic fără HTF**, în regimul de trend. Cinci transformări ale aceleiași serii nu echivalează cu cinci surse independente de informație.

În producție, `factor_signs=inverted` inversează inclusiv componente deja contrariene; orele UTC 9, 10, 11 folosesc semnele originale. Am testat eliminarea acestei alternanțe, dar rezultatul nu a trecut evaluarea rezervată. Nu am dedus o regulă nouă de ore sau instrumente din pierderile deja observate.

VWAP și Ichimoku sunt calculate pentru afișare, dar nu intră în această sumă. Ichimoku deplasează înainte valori calculate în trecut; această deplasare grafică nu oferă acces la prețuri viitoare. VWAP este pe volum furnizat de sursă, nu pe volumul consolidat al întregii piețe forex.

## 3. Definițiile financiare corecte

- `win_rate = 100 × count(P&L_net > 0) / count(tranzacții închise cu rezultat cunoscut)`.
- `R_i = P&L_net_i / riscul_EUR_inițial_i`; `E[R] = media(R_i)`.
- `PF_EUR = suma profiturilor nete / abs(suma pierderilor nete)`; PF în R se raportează separat.
- Sharpe per tranzacție = `media(R) / deviația_standard_eșantion(R)`. Nu este Sharpe anualizat.
- Drawdown-ul backtestului include capitalul marcat la piață la închiderea fiecărei bare; drawdown-ul numai pe rezultate realizate este separat. Nu este un maxim intrabar calculat din tick-uri.

La un câștig fix de 1,8R și o pierdere fixă de 1R, pragul ideal fără costuri este `1 / 2,8 = 35,71%`. El nu este automat pragul strategiei reale cu parțiale, gap-uri și pierderi variabile. Cu mediile observate +1,0515R/−1,2124R, echilibrul ar cere aproximativ **53,55% câștiguri dintre rezultatele nenule**, dacă aceste medii ar rămâne stabile. Cu aceeași proporție de zero, aproximativ 52,22% din toate închiderile. Este o identitate descriptivă, nu o estimare garantată pentru viitor.

Un spread complet este `ask − bid`; o intrare și o ieșire la mijlocul neschimbat al pieței pierd un spread complet. Nu se dublează încă o dată. Slippage-ul se aplică separat la fiecare execuție. Calculatorul pe preț de referință folosește:

```
units = (risk_EUR − commission) / ((dist_SL + spread) × EUR_per_quote)
TP_net = units × (dist_SL × RR − spread) × EUR_per_quote − commission
```

În backtest, intrarea este deja pe ask/bid executabil, stopul se construiește față de acea intrare, iar bugetul pentru stop include comisionul și slippage-ul de ieșire. Aceste convenții diferite sunt explicite; spread-ul nu se adaugă din nou aceleiași execuții.

## 4. Probleme corectate direct

| Problemă | Corecție și efect |
|---|---|
| Date simulate sau forex cu mișcare sâmbăta puteau alimenta analiza | Verificări de proveniență, OHLC, ordine temporală și sesiune; blocare în analiză, tracking și backtest |
| Resampling 40m pierdea marca de simulare și accepta grupuri incomplete | Propagarea provenienței și verificarea exactă a sub-barelor necesare |
| Fallback la lumânări în formare și confirmare HTF prea nouă | Semnal confirmat numai din bare închise; HTF închis cel târziu la momentul deciziei |
| Stochastic/SMA contaminate de NaN; RSI și ADX pe serie plată | Inițializare și propagare corecte; RSI 50, ADX 0 pe piață plată |
| Hurst/ER diferite între live și backtest | Aceleași ferestre și indexare, fără rotunjire înaintea scoringului; warmup de backtest 200 bare |
| Renormalizarea regimului putea crește implicit ponderea AI | Bugete tehnic și AI normalizate separat; plafonul comun AI rămâne respectat |
| Componente afișate fără semnul inversării | Componentele returnate reconstruiesc scorul efectiv |
| Adaptare a ponderilor din „memorie” fără replay istoric validat | Separată de memoria asistentului; adaptarea de trading este implicit oprită, multiplicatorii limitați la ±15% |
| Intrare simulată și evaluare a barei de intrare incorecte | Decizie pe bara precedentă, intrare la open-ul următor, evaluarea riscului inclusiv în bara intrării |
| Gap TP confundat cu SL atins ulterior în aceeași bară | Open-ul este procesat primul; intrabar ambiguu rămâne conservator SL-first |
| Costuri, fracții, R rotunjit și poziții terminale omise | Bid/ask istoric, slippage bilateral, R net precis, ponderare parțiale, lichidare explicită la capătul datelor |
| Trailing/breakeven folosind îmbunătățirea aceleiași bare | Noul stop se aplică barei următoare și este limitat de prețul curent |
| Walk-forward cu granițe neclare și selecție pe eșantioane prea mici | Segmente cronologice disjuncte, închidere la graniță, capital compus, selecție penalizată pentru incertitudine |
| WR/P&L amestecau paper și broker; zero devenea pierdere | Populație explicită, rezultat net MT5 prioritar, lipsa de rezultat exclusă, zero separat și interval WR |
| Kelly folosea RR configurat și putea reveni la risc fix cu avantaj negativ | Maximizare empirică `mean(log(1+fR))`; jumătate Kelly, zero risc la medie nepozitivă, plafon la riscul fix și 5% |
| Limitele de expunere verificau numai pozițiile deja deschise | Includ și tranzacția propusă; soldul real zero sau indisponibil nu este înlocuit cu capitalul fictiv pentru ordine live |
| Calculatorul trunchia unități și trata toate contractele ca 100.000 unități | Unități fracționare, contract orientativ specific instrumentului, profit TP net după costuri |
| Intrări broker mult deplasate față de semnal | Cotare proaspătă și respingere peste 0,25R abatere; verificare direcție SL/TP și valori finite |
| Comentarii `#id` ale altor sisteme puteau fi atribuite semnalelor Aurex | Identificare cu marca Aurex/Codnixy; intrările cu proprietate ambiguă nu se atribuie |
| Eroare API poziții interpretată ca absență a pozițiilor | Nu se închide un semnal real pe baza unui snapshot eșuat sau a rezultatului paper |
| Comision IN omis; fereastra de 7 zile înlocuia P&L cumulat | Registru `broker_deals` persistent, deduplicat pe cont/ticket; backfill inițial, toate paginile API, comisioane IN și OUT, dată de închidere din broker |
| Corelații Spearman false la egalități și coș valutar aliniat după index | Ranguri medii și aliniere după timestamp; eliminarea concluziilor automate „IC bun”/„independență” |
| Sweep recalcula indicatorii pentru fiecare combinație | Refolosirea seriilor precalculate; analiza orelor reexecută strategia, nu șterge retrospectiv pierderi |

Tabelul `broker_deals` este nou și se creează prin mecanismul existent `init_db` la pornirea versiunii actualizate. Nu l-am creat pe VPS. Prima sincronizare reușită va putea revizui P&L și data unor închideri istorice; acest efect necesită verificare după backfill. Pozițiile netting cu proprietate mixtă/reversări nu pot fi atribuite sigur unui singur semnal și sunt excluse din atribuirea automată.

## 5. Date și protocol de evaluare

Primul export H1 primit prin Twelve Data conținea 5.000 de bare pe instrument, inclusiv **1.412 bare de weekend**, fără întrerupere a secvenței orare și cu mișcare sâmbăta. Acest lot a fost exclus. Constatarea privește lotul primit, nu toate datele furnizorului.

Am descărcat arhivele **bid și ask Dukascopy**, păstrând manifestul cu URL-uri și SHA256. Cele 15 instrumente sunt EUR/USD, GBP/USD, USD/JPY, USD/CHF, AUD/USD, USD/CAD, NZD/USD, EUR/GBP, EUR/JPY, GBP/JPY, EUR/CAD, AUD/NZD, CAD/CHF, GBP/CHF, NZD/CAD.

- Februarie–august: **3.627 bare H1 active/instrument**, 54.405 în total; eliminate placeholder-ele fără volum din piața închisă.
- Extensie până la 11 septembrie, ora 20:00 UTC: **3.837 bare/instrument**, 57.555 în total. Pentru septembrie au fost agregate numai ore cu toate cele 60 de minute disponibile.
- Training până la **11 iunie 21:00 UTC**, exclusiv; validare până la **22 iulie 10:00 UTC**, exclusiv; evaluare rezervată până la **31 august 23:00 UTC**.
- Datele anterioare graniței servesc numai la indicatori. Pozițiile sunt închise la granițe. Orice rezultat ulterior graniței nu intră în antrenarea segmentului precedent.
- Aceleași conturi de cercetare independente, 10.000 EUR/pereche și 1% risc/tranzacție, pentru toate variantele. Acestea nu reproduc capitalul de 900 EUR, riscul de 5% și expunerile simultane ale VPS-ului.
- Spread bid/ask istoric, slippage 0,2 pip pe fiecare execuție. Nu există istoric complet al swap-ului/comisioanelor specifice brokerului; acestea sunt zero în aceste experimente, nu presupuse inexistente în realitate.

Intervalele E[R] folosesc grupare pe săptămână pentru dependența dintre perechi. Aproximația normală este fragilă cu puține săptămâni, în special în septembrie. Nu o folosesc ca dovadă că o variantă slab pozitivă trebuie activată.

## 6. Înainte și după corectarea motorului

Aceeași familie de semnale și aceleași date calendaristice februarie–august; codul inițial este păstrat din revizia `d7d5902`.

| Motor | Tranzacții | Win rate | PF EUR | E[R] |
|---|---:|---:|---:|---:|
| Inițial: spread estimat, R rotunjit, warmup 60 | 2.094 | 34,77% | 0,9493 | −0,0383 |
| Corectat: bid/ask, execuție și R net, warmup 200 | 2.073 | **32,47%** | **0,8572** | **−0,1258** |

Aceasta măsoară **impactul cumulat al corecțiilor și al modelului de cost**, nu efectul izolat al unui singur indicator. Motorul vechi primește aceeași serie midpoint, dar ignoră arhiva bid/ask. Diferența de număr de tranzacții este explicată inclusiv de warmup și de momentul/condițiile execuției. Corectarea a făcut evaluarea mai severă; nu a creat profit.

## 7. Variante de formulă și AI

### Combinații tehnice

Am fixat 14 variante: semne originale/inversate, praguri 0,25/0,35/0,45, stop 1,5/2 ATR, plus două variante `regime_balanced`. Ultima combină continuu trend/MACD cu Bollinger/RSI contrarian, folosind ADX și ER pentru proporție, reducând numărul de componente care repetă aceeași mișcare. Niciuna nu a obținut E[R] pozitiv în training.

Varianta selectată numai pentru cercetare a fost inversată, prag 0,25, stop 2 ATR, fără orele cu semne originale. Validarea a respins promovarea.

| Evaluare rezervată 22 iulie–31 august | Tranzacții | Win rate | PF EUR | E[R] |
|---|---:|---:|---:|---:|
| Formula de referință, motor corectat | 437 | **34,78%** | 0,8955 | −0,0718 |
| Candidatul selectat | 432 | **34,03%** | 0,8586 | −0,0948 |

Win rate-ul candidatului scade cu 0,75 puncte procentuale. Nu a fost activat. Analiza costurilor cu slippage 0/0,5/1 pip nu a schimbat concluzia de lipsă a profitabilității stabile. Am evitat micșorarea artificială a TP-ului pentru a produce mai multe câștiguri mici și pierderi mari.

### Model statistic de probabilitate

Am implementat o regresie logistică regularizată cu opt variabile disponibile înaintea intrării: scor, RSI/Bollinger/trend/MACD orientate după direcție, ADX, ER și cost/stop. Standardizarea este antrenată numai pe trecut. Modelul se antrenează înainte de 1 iulie, se calibrează separat între 1–16 iulie, iar pragul se selectează între 16 iulie–1 septembrie. Modelul și pragul sunt salvate înaintea testului final.

În 1–11 septembrie, baza produce **161 tranzacții, WR 29,19%, PF 0,6910, E[R] −0,2108**. Filtrul selectat la probabilitate ≥0,38714 produce **zero tranzacții**. Win rate-ul său este **nedefinit**, nu 100%. Scorul Brier este **0,20967**, mai slab decât predicția constantă bazată pe frecvența din training (**0,20770**, mai mic este mai bun). Modelul a fost respins și nu este integrat în execuția live.

### AI pe analizele existente

VPS-ul avea **123 de analize AI arhivate**. Am reexecutat numai vectorii salvați efectiv, disponibili cel târziu la decizie, cu înjumătățirea contribuției la 12 ore. Nu am cerut unui LLM actual să „prezică” trecutul pe care îl poate cunoaște.

Ponderile 0/5/10/15% au fost comparate pe 16 iulie–31 august. La 10%, validarea arăta WR 38,03%, PF 1,0347, E[R] +0,0176. Limita inferioară E[R] era însă −0,1452, deci condiția de promovare nu era îndeplinită.

| Test rezervat 1–11 septembrie | Tranzacții | Win rate | PF EUR | E[R] |
|---|---:|---:|---:|---:|
| Fără AI | 161 | **29,19%** | 0,6910 | −0,2108 |
| AI arhivat, pondere 10% | 147 | **29,93%** | 0,7027 | −0,2037 |

Diferența este **+0,74 puncte procentuale**, cu rezultat încă negativ și intervale WR larg suprapuse. Nu demonstrează o creștere considerabilă. Ponderea AI de pe VPS a rămas 0. Niciun prag nu a fost reajustat după examinarea rezultatelor din septembrie.

## 8. Ce afectează performanța și ce rămâne de validat

1. **Avantajul direcțional este insuficient.** Formula rămâne negativă pe date curate chiar înainte de toate costurile specifice brokerului. Un LLM sau încă un indicator nu adaugă automat informație independentă.
2. **Riscul realizat diferă de cel declarat.** Pierderile mari în R, în special pe 15m și metale, cer reconstrucție din prețuri/volume/contracte și deal-uri. Garda de abatere a intrării și corecțiile de dimensionare reduc căi concrete de eroare; creșterea lor efectivă de win rate nu este încă măsurată în producție.
3. **Cost/ATR, instrumentul și regimul contează.** Cross-urile și metalele au rezultate slabe; simpla excludere aleasă din aceeași istorie ar introduce selecție retrospectivă. Nu prezint filtrarea pierderilor cunoscute drept optimizare validată.
4. **„Confidence” inducea în eroare.** Semnalele cu scor afișat ≥80% au câștigat numai 6/18, adică 33,33%; grupa 70–80% a câștigat 25/66, adică 37,88%. UI precizează acum că este puterea euristică a semnalului. Nu există o calibrare care să susțină acele procente ca probabilități.
5. **Riscul de 5% amplifică pierderea, nu calitatea predicției.** Cinci stopuri consecutive de 1R ar reduce capitalul cu 22,62%, zece cu 40,13%, în modelul cu risc procentual constant și fără gap-uri. Setările VPS au limite zilnice/drawdown dezactivate. Nu le-am modificat automat.
6. **Backtestul nu reproduce întregul portofoliu live.** Nu include HTF istoric sincronizat, limite de expunere simultană, cooldown/confirmări manuale exacte, latență, spread-ul specific contului, pașii de lot și toate swap-urile. Suma P&L a celor 15 conturi independente nu este randamentul unui portofoliu comun.
7. **Auditul nu poate șterge istoricul selecției manuale.** Perioadele anterioare pot fi deja folosite de experimentele documentate în proiect. Septembrie a fost separat în această rundă, dar este scurt. Rezultatele nu constituie dovada absenței absolute a overfitting-ului.
8. **Limite operaționale rămase:** P&L paper rămâne un model pe bare și nu înlocuiește brokerul; curbele reconstruite din capital inițial plus rezultate nu reprezintă extrasul contului cu depuneri/retrageri; contractele calculatorului sunt orientative. Registrul nou tratează conturile separat, dar schema istorică a semnalelor nu oferă o atribuire completă pentru schimbări vechi de cont sau poziții netting comune mai multor sisteme.

Următorul experiment justificat este colectarea prospectivă a deciziilor, cotațiilor brokerului, costurilor și rezultatului net, cu un protocol fixat înaintea colectării. Un predictor nou trebuie comparat cu o bază simplă și validat pe o perioadă ulterioară. Criteriul trebuie să includă E[R]/PF/drawdown și volumul de tranzacții, alături de win rate. Variantele încercate în acest audit rămân de cercetare.

## 9. Verificare și reproducere

**46 teste de regresie trecute**, inclusiv disponibilitatea temporală AI, egalități Spearman, consistența indicatorilor live/backtest, execuție pe bara următoare, costuri, SL/TP ambiguu, gap-uri, parțiale, capital marcat la piață, walk-forward, Kelly, populații broker/paper, sincronizare eșuată, comisioane și paginare MT5. TypeScript `tsc --noEmit` trece. Reexecutarea cu parametrii fixați a reprodus toate cele **42 de verificări de metrici**, iar toate cele **15 checksum-uri** ale datelor inițiale coincid. Nu am pornit schedulerul sau aplicația conectată la broker pentru aceste teste.

Fișierele rezultate sunt alături de acest raport: `broker_snapshot_results.json`, `protocol.json`, `selection.json`, `results.json`, `legacy_before.json`, `holdout_trades.json`, `probability_model.json`, `probability_results.json`, `ai_selection.json`, `ai_results.json`, `data_manifest.json`, `verification.json`.

Datele complete și copia codului inițial sunt păstrate local în `data/strategy-audit-2026-09-12/`, director ignorat de Git. Exportul VPS conține informații despre tranzacții și nu este inclus în fișierele urmărite de Git. Am verificat că setul februarie–august păstrează exact cele 15 checksum-uri din protocolul inițial. Arhivele binare originale descărcate în această sesiune se află și în `/private/tmp/forex-audit-dukascopy/raw/`.

Din rădăcina proiectului, cu dependențele backend instalate:

```sh
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
node frontend/node_modules/typescript/bin/tsc --noEmit -p frontend/tsconfig.json
PYTHONPATH=backend python -m app.tools.verify_audit --data-dir data/strategy-audit-2026-09-12 --report-dir reports/strategy-audit-2026-09-12
PYTHONPATH=backend python -m app.tools.audit_snapshot --snapshot data/strategy-audit-2026-09-12/vps_snapshot.json --output data/strategy-audit-2026-09-12/recalculated_snapshot.json
```

Pentru repetarea completă, folosiți un director nou de rezultate, fără a suprascrie protocolul acestei runde:

```sh
PYTHONPATH=backend python -m app.tools.audit_strategy --data-dir data/strategy-audit-2026-09-12/feb_aug --snapshot data/strategy-audit-2026-09-12/vps_snapshot.json --output data/strategy-audit-2026-09-12/replay
PYTHONPATH=backend python -m app.tools.audit_probability --data-dir data/strategy-audit-2026-09-12/feb_sep --snapshot data/strategy-audit-2026-09-12/vps_snapshot.json --output data/strategy-audit-2026-09-12/replay
PYTHONPATH=backend python -m app.tools.audit_ai --data-dir data/strategy-audit-2026-09-12/feb_sep --snapshot data/strategy-audit-2026-09-12/vps_snapshot.json --output data/strategy-audit-2026-09-12/replay
```

În acest workspace, `.venv/bin/python` are legături nefuncționale. Verificările au folosit `/opt/homebrew/opt/python@3.14/bin/python3.14`, cu `PYTHONPATH=backend:backend/.venv/lib/python3.14/site-packages`. Nu am modificat mediul utilizatorului.

## Surse metodologice

- Execuție pe bara următoare, costuri, limite ale simulării și evaluare: [TradingView — Strategies](https://www.tradingview.com/pine-script-docs/concepts/strategies/).
- Ambiguitatea traseului intrabar: [TradingView — Bar Magnifier](https://www.tradingview.com/support/solutions/43000669285-what-is-bar-magnifier-backtesting-mode/).
- Riscul selecției repetate a strategiilor: [Bailey et al. — The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).
- Arhive și export de piață: [Dukascopy — Data export](https://www.dukascopy.com/wiki/es/development/data-export/).
- Sesiuni valutare și închiderea pieței: [OANDA — Hours of operation](https://www.oanda.com/us-en/trading/hours-of-operation/).
- Paginarea istoricului brokerului, limită 1.000 deal-uri/pagină: [MetaApi — Read deals by time range](https://metaapi.cloud/docs/client/restApi/api/retrieveHistoricalData/readDealsByTimeRange/).

Cifrele de performanță din raport provin din execuțiile acestui proiect și din exportul salvat, nu din sursele metodologice de mai sus.
