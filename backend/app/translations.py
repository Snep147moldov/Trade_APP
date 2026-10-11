"""Русский оригинал -> перевод по языкам.

Ключ — строка из кода (см. app/i18n.py). Отсутствующий ключ отдаёт
оригинал: промпты к модели намеренно остаются русскими, язык её ответа
задаётся отдельной строкой в конце промпта.
"""

TRANSLATIONS: dict[str, dict[str, str]] = {
    " (ещё не произошло).": {
        "en": " (has not happened yet).",
        "fr": " (ne s’est pas encore produit).",
        "de": " (noch nicht eingetreten).",
    },
    " (уже произошло — цели выше).": {
        "en": " (already happened — targets above).",
        "fr": " (déjà survenu — objectifs au-dessus).",
        "de": " (bereits eingetreten — Ziele darüber).",
    },
    " (уже произошло — цели ниже).": {
        "en": " (already happened — targets below).",
        "fr": " (déjà survenu — objectifs en dessous).",
        "de": " (bereits eingetreten — Ziele darunter).",
    },
    " · ордер {0} отклонён: {1}": {
        "en": " · order {0} rejected: {1}",
        "fr": " · ordre {0} rejeté : {1}",
        "de": " · Order {0} abgelehnt: {1}",
    },
    " Заметка: {0}": {
        "en": " Note: {0}",
        "fr": " Note : {0}",
        "de": " Notiz: {0}",
    },
    " Ордер {0} отклонён: {1}": {
        "en": " Order {0} rejected: {1}",
        "fr": " Ordre {0} rejeté : {1}",
        "de": " Order {0} abgelehnt: {1}",
    },
    " Советы: ": {
        "en": " Tips: ",
        "fr": " Conseils : ",
        "de": " Tipps: ",
    },
    " Стоп был переведён в безубыток.": {
        "en": " The stop had been moved to breakeven.",
        "fr": " Le stop avait été ramené au seuil de rentabilité.",
        "de": " Der Stop war auf Break-even gezogen worden.",
    },
    " Частичная фиксация сработала.": {
        "en": " The partial take-profit fired.",
        "fr": " La prise partielle s’est déclenchée.",
        "de": " Die Teilgewinnmitnahme hat ausgelöst.",
    },
    " до {0}": {
        "en": " until {0}",
        "fr": " jusqu’à {0}",
        "de": " bis {0}",
    },
    " — сделка не открыта.": {
        "en": " — no trade was opened.",
        "fr": " — aucun trade n’a été ouvert.",
        "de": " — es wurde kein Trade eröffnet.",
    },
    "(данные по {0} недоступны)": {
        "en": "(no data for {0})",
        "fr": "(aucune donnée pour {0})",
        "de": "(keine Daten zu {0})",
    },
    "(пусто)": {
        "en": "(empty)",
        "fr": "(vide)",
        "de": "(leer)",
    },
    ", заметка: {0}": {
        "en": ", note: {0}",
        "fr": ", note : {0}",
        "de": ", Notiz: {0}",
    },
    ", стратегия {0}": {
        "en": ", strategy {0}",
        "fr": ", stratégie {0}",
        "de": ", Strategie {0}",
    },
    "- {0} score {1}, {2}, {3}€, держали {4} баров": {
        "en": "- {0} score {1}, {2}, €{3}, held {4} bars",
        "fr": "- {0} score {1}, {2}, {3} €, tenu {4} barres",
        "de": "- {0} Score {1}, {2}, {3} €, {4} Bars gehalten",
    },
    ". Общий SL {0}.": {
        "en": ". Shared SL {0}.",
        "fr": ". SL commun {0}.",
        "de": ". Gemeinsamer SL {0}.",
    },
    ". Предупреждения: ": {
        "en": ". Warnings: ",
        "fr": ". Avertissements : ",
        "de": ". Warnungen: ",
    },
    "19–23 UTC: тонкая ликвидность и широкие спреды — размер позиции уменьшен вдвое": {
        "en": "19–23 UTC: thin liquidity and wide spreads — the position size is halved",
        "fr": "19–23 UTC : liquidité faible et spreads larges — la taille de position est divisée par deux",
        "de": "19–23 UTC: dünne Liquidität und weite Spreads — die Positionsgröße wird halbiert",
    },
    "2FA не включена": {
        "en": "2FA is not enabled",
        "fr": "La 2FA n’est pas activée",
        "de": "2FA ist nicht aktiviert",
    },
    "2FA уже включена": {
        "en": "2FA is already on",
        "fr": "La 2FA est déjà activée",
        "de": "2FA ist bereits aktiv",
    },
    "3 чистых убытка подряд по {0} — пауза 24ч (осталось {1}ч)": {
        "en": "3 clean losses in a row on {0} — a 24h pause ({1}h left)",
        "fr": "3 pertes nettes d’affilée sur {0} — pause de 24 h ({1} h restantes)",
        "de": "3 klare Verluste in Folge auf {0} — 24-Std.-Pause (noch {1} Std.)",
    },
    "<b>{0}</b>\\n{1} · {2} · {3}\\nРезультат: {4} п. · {5}€": {
        "en": "<b>{0}</b>\\n{1} · {2} · {3}\\nResult: {4} pts · €{5}",
        "fr": "<b>{0}</b>\\n{1} · {2} · {3}\\nRésultat : {4} pts · {5} €",
        "de": "<b>{0}</b>\\n{1} · {2} · {3}\\nErgebnis: {4} Pkt. · {5} €",
    },
    "ATR14 {0} в {1}× выше среднего — всплеск волатильности": {
        "en": "ATR14 {0} is {1}× above average — a volatility spike",
        "fr": "l’ATR14 {0} est {1}× au-dessus de la moyenne — pic de volatilité",
        "de": "ATR14 {0} liegt {1}× über dem Durchschnitt — Volatilitätsspitze",
    },
    "EMA{0} пересекла EMA{1} вверх (golden cross)": {
        "en": "EMA{0} crossed above EMA{1} (golden cross)",
        "fr": "l’EMA{0} a croisé au-dessus de l’EMA{1} (golden cross)",
        "de": "EMA{0} kreuzte über EMA{1} (Golden Cross)",
    },
    "EMA{0} пересекла EMA{1} вниз (death cross)": {
        "en": "EMA{0} crossed below EMA{1} (death cross)",
        "fr": "l’EMA{0} a croisé sous l’EMA{1} (death cross)",
        "de": "EMA{0} kreuzte unter EMA{1} (Death Cross)",
    },
    "FX Navigator — код восстановления": {
        "en": "FX Navigator — recovery code",
        "fr": "FX Navigator — code de récupération",
        "de": "FX Navigator — Wiederherstellungscode",
    },
    "Kelly: нет положительного ожидания по закрытым сделкам": {
        "en": "Kelly: no positive expectancy across the closed trades",
        "fr": "Kelly : aucune espérance positive sur les trades clôturés",
        "de": "Kelly: kein positiver Erwartungswert über die geschlossenen Trades",
    },
    "MACD пересёк сигнальную линию сверху вниз (медвежий кросс)": {
        "en": "MACD crossed its signal line downwards (bearish cross)",
        "fr": "le MACD a croisé sa ligne de signal vers le bas (croisement baissier)",
        "de": "MACD kreuzte seine Signallinie nach unten (bärische Kreuzung)",
    },
    "MACD пересёк сигнальную линию снизу вверх (бычий кросс)": {
        "en": "MACD crossed its signal line upwards (bullish cross)",
        "fr": "le MACD a croisé sa ligne de signal vers le haut (croisement haussier)",
        "de": "MACD kreuzte seine Signallinie nach oben (bullische Kreuzung)",
    },
    "MT5 не подключён": {
        "en": "MT5 is not connected",
        "fr": "MT5 n’est pas connecté",
        "de": "MT5 ist nicht verbunden",
    },
    "MT5 не подключён (нет токена или id счёта)": {
        "en": "MT5 is not connected (no token or account id)",
        "fr": "MT5 n’est pas connecté (pas de jeton ni d’id de compte)",
        "de": "MT5 ist nicht verbunden (kein Token oder keine Konto-ID)",
    },
    "MT5: открыто {0} позици(я/и) {1}": {
        "en": "MT5: {0} position(s) opened {1}",
        "fr": "MT5 : {0} position(s) ouverte(s) {1}",
        "de": "MT5: {0} Position(en) eröffnet {1}",
    },
    "MT5: позиция закрыта · {0} · сигнал #{1}\\nРеальный результат с комиссиями: {2}€": {
        "en": "MT5: position closed · {0} · signal #{1}\\nActual result including commissions: €{2}",
        "fr": "MT5 : position clôturée · {0} · signal #{1}\\nRésultat réel commissions comprises : {2} €",
        "de": "MT5: Position geschlossen · {0} · Signal #{1}\\nTatsächliches Ergebnis inklusive Kommissionen: {2} €",
    },
    "MT5: сигнал #{0} → {1}": {
        "en": "MT5: signal #{0} → {1}",
        "fr": "MT5 : signal #{0} → {1}",
        "de": "MT5: Signal #{0} → {1}",
    },
    "MetaApi вернул неожиданный ответ по счёту {0}": {
        "en": "MetaApi returned an unexpected response for account {0}",
        "fr": "MetaApi a renvoyé une réponse inattendue pour le compte {0}",
        "de": "MetaApi lieferte eine unerwartete Antwort für Konto {0}",
    },
    "MetaApi не вернул id счёта": {
        "en": "MetaApi returned no account id",
        "fr": "MetaApi n’a pas renvoyé d’id de compte",
        "de": "MetaApi lieferte keine Konto-ID",
    },
    "RSI14 = {0} ({1} {2})": {
        "en": "RSI14 = {0} ({1} {2})",
        "fr": "RSI14 = {0} ({1} {2})",
        "de": "RSI14 = {0} ({1} {2})",
    },
    "[недавняя сделка] {0}": {
        "en": "[recent trade] {0}",
        "fr": "[trade récent] {0}",
        "de": "[letzter Trade] {0}",
    },
    "[статистика] {0}": {
        "en": "[statistics] {0}",
        "fr": "[statistiques] {0}",
        "de": "[Statistik] {0}",
    },
    "[стиль] {0}": {
        "en": "[style] {0}",
        "fr": "[style] {0}",
        "de": "[Stil] {0}",
    },
    "[урок] {0}": {
        "en": "[lesson] {0}",
        "fr": "[leçon] {0}",
        "de": "[Lektion] {0}",
    },
    "\\n<i>Поддержка решений, не финансовый совет.</i>": {
        "en": "\\n<i>Decision support, not financial advice.</i>",
        "fr": "\\n<i>Aide à la décision, pas un conseil financier.</i>",
        "de": "\\n<i>Entscheidungshilfe, keine Finanzberatung.</i>",
    },
    "\\nПрогноз: {0} · Пред.: {1}": {
        "en": "\\nForecast: {0} · Prev.: {1}",
        "fr": "\\nPrévision : {0} · Préc. : {1}",
        "de": "\\nPrognose: {0} · Vorh.: {1}",
    },
    "\\nРеально в MT5: {0}€ ({1} орд., {2} лот)": {
        "en": "\\nActual in MT5: €{0} ({1} orders, {2} lots)",
        "fr": "\\nRéel dans MT5 : {0} € ({1} ordres, {2} lots)",
        "de": "\\nTatsächlich in MT5: {0} € ({1} Orders, {2} Lot)",
    },
    "\\nЧастичная фиксация была выполнена ранее.": {
        "en": "\\nA partial take-profit was taken earlier.",
        "fr": "\\nUne prise partielle a été effectuée plus tôt.",
        "de": "\\nEine Teilgewinnmitnahme erfolgte bereits.",
    },
    "\\n⏳ <b>Нужно подтверждение{0}</b> — без нажатия «Купить» сделка НЕ откроется.\\n": {
        "en": "\\n⏳ <b>Confirmation required{0}</b> — without pressing “Buy” NO trade opens.\\n",
        "fr": "\\n⏳ <b>Confirmation requise{0}</b> — sans appuyer sur « Acheter », AUCUN trade ne s’ouvre.\\n",
        "de": "\\n⏳ <b>Bestätigung erforderlich{0}</b> — ohne Druck auf „Kaufen“ öffnet KEIN Trade.\\n",
    },
    "\\n⚠️ <b>Брокер не торгует этот инструмент</b> — покупка из Telegram недоступна.": {
        "en": "\\n⚠️ <b>The broker does not trade this instrument</b> — buying from Telegram is unavailable.",
        "fr": "\\n⚠️ <b>Le courtier ne trade pas cet instrument</b> — l’achat depuis Telegram est indisponible.",
        "de": "\\n⚠️ <b>Der Broker handelt dieses Instrument nicht</b> — Kaufen aus Telegram ist nicht möglich.",
    },
    "\\n⚠️ <b>Только с превышением риска</b>: {0}.\\nРеальный риск составит ≈<b>{1}€</b> вместо {2}€. При нажатии «Купить» потребуется отдельное подтверждение.": {
        "en": "\\n⚠️ <b>Only by exceeding the risk</b>: {0}.\\nThe real risk would be about <b>€{1}</b> instead of €{2}. Pressing “Buy” will ask for a separate confirmation.",
        "fr": "\\n⚠️ <b>Uniquement en dépassant le risque</b> : {0}.\\nLe risque réel serait d’environ <b>{1} €</b> au lieu de {2} €. Appuyer sur « Acheter » demandera une confirmation distincte.",
        "de": "\\n⚠️ <b>Nur mit Überschreitung des Risikos</b>: {0}.\\nDas tatsächliche Risiko läge bei etwa <b>{1} €</b> statt {2} €. Ein Druck auf „Kaufen“ verlangt eine separate Bestätigung.",
    },
    "\\n⚠️ Запрошено {0} ордеров, брокер принял только {1}: {2}": {
        "en": "\\n⚠️ {0} orders requested, the broker accepted only {1}: {2}",
        "fr": "\\n⚠️ {0} ordres demandés, le courtier n’en a accepté que {1} : {2}",
        "de": "\\n⚠️ {0} Orders angefordert, der Broker nahm nur {1} an: {2}",
    },
    "\\n⚠️ С повышенным риском ≈{0}€ (×{1}) — по вашему подтверждению.": {
        "en": "\\n⚠️ At an elevated risk of about €{0} (×{1}) — on your confirmation.",
        "fr": "\\n⚠️ Avec un risque accru d’environ {0} € (×{1}) — sur votre confirmation.",
        "de": "\\n⚠️ Mit erhöhtem Risiko von etwa {0} € (×{1}) — auf Ihre Bestätigung.",
    },
    "\\n⚠️ не удалось закрыть: {0}": {
        "en": "\\n⚠️ could not close: {0}",
        "fr": "\\n⚠️ impossible de clôturer : {0}",
        "de": "\\n⚠️ konnte nicht geschlossen werden: {0}",
    },
    "\\n⛔️ <b>Сделка неисполнима</b>: {0}.\\nЧтобы её открыть, риск должен быть ×{1} (≈{2}€ вместо {3}€) — это выше потолка, кнопка не выдаётся.": {
        "en": "\\n⛔️ <b>The trade cannot be executed</b>: {0}.\\nOpening it would take ×{1} the risk (about €{2} instead of €{3}) — above the cap, so no button is offered.",
        "fr": "\\n⛔️ <b>Le trade n’est pas exécutable</b> : {0}.\\nL’ouvrir demanderait ×{1} le risque (environ {2} € au lieu de {3} €) — au-dessus du plafond, aucun bouton n’est proposé.",
        "de": "\\n⛔️ <b>Der Trade ist nicht ausführbar</b>: {0}.\\nIhn zu eröffnen erforderte das ×{1}-fache Risiko (etwa {2} € statt {3} €) — über der Obergrenze, daher wird keine Schaltfläche angeboten.",
    },
    "\\n🤖 <b>Избранное</b> — сделка открывается автоматически, подтверждение не требуется.": {
        "en": "\\n🤖 <b>Watchlist</b> — the trade opens automatically, no confirmation needed.",
        "fr": "\\n🤖 <b>Favoris</b> — le trade s’ouvre automatiquement, aucune confirmation requise.",
        "de": "\\n🤖 <b>Watchlist</b> — der Trade öffnet automatisch, keine Bestätigung nötig.",
    },
    "ai_weight должен быть от 0 до 0.5": {
        "en": "ai_weight must be between 0 and 0.5",
        "fr": "ai_weight doit être compris entre 0 et 0,5",
        "de": "ai_weight muss zwischen 0 und 0,5 liegen",
    },
    "invert_signal и factor_signs нельзя инвертировать одновременно": {
        "en": "invert_signal and factor_signs cannot both invert at once",
        "fr": "invert_signal et factor_signs ne peuvent pas inverser en même temps",
        "de": "invert_signal und factor_signs können nicht gleichzeitig invertieren",
    },
    "{0} ({1})": {
        "en": "{0} ({1})",
        "fr": "{0} ({1})",
        "de": "{0} ({1})",
    },
    "{0} {1} ({2} касаний)": {
        "en": "{0} {1} ({2} touches)",
        "fr": "{0} {1} ({2} touches)",
        "de": "{0} {1} ({2} Berührungen)",
    },
    "{0} {1} (важность {2})": {
        "en": "{0} {1} (importance {2})",
        "fr": "{0} {1} (importance {2})",
        "de": "{0} {1} (Wichtigkeit {2})",
    },
    "{0} {1} {2}: {3}, {4}€ ({5}R). Оценка {6}, уверенность {7}. Факторы ЗА: {8}. Факторы ПРОТИВ: {9}.": {
        "en": "{0} {1} {2}: {3}, €{4} ({5}R). Score {6}, confidence {7}. Factors FOR: {8}. Factors AGAINST: {9}.",
        "fr": "{0} {1} {2} : {3}, {4} € ({5}R). Score {6}, confiance {7}. Facteurs POUR : {8}. Facteurs CONTRE : {9}.",
        "de": "{0} {1} {2}: {3}, {4} € ({5}R). Score {6}, Konfidenz {7}. Faktoren DAFÜR: {8}. Faktoren DAGEGEN: {9}.",
    },
    "{0} {1}×{2} лот · SL {3} · TP {4}": {
        "en": "{0} {1}×{2} lots · SL {3} · TP {4}",
        "fr": "{0} {1}×{2} lots · SL {3} · TP {4}",
        "de": "{0} {1}×{2} Lot · SL {3} · TP {4}",
    },
    "{0} ×{1} по {2} лот · SL {3} · TP {4}": {
        "en": "{0} ×{1} at {2} lots · SL {3} · TP {4}",
        "fr": "{0} ×{1} à {2} lots · SL {3} · TP {4}",
        "de": "{0} ×{1} zu {2} Lot · SL {3} · TP {4}",
    },
    "{0} должен быть конечным и неотрицательным": {
        "en": "{0} must be finite and non-negative",
        "fr": "{0} doit être fini et non négatif",
        "de": "{0} muss endlich und nicht negativ sein",
    },
    "{0} должен быть конечным и положительным": {
        "en": "{0} must be finite and positive",
        "fr": "{0} doit être fini et positif",
        "de": "{0} muss endlich und positiv sein",
    },
    "{0} должен быть целым": {
        "en": "{0} must be an integer",
        "fr": "{0} doit être un entier",
        "de": "{0} muss eine ganze Zahl sein",
    },
    "{0} закрытых, win rate {1}%, profit factor {2}, матожидание {3}€": {
        "en": "{0} closed, win rate {1}%, profit factor {2}, expectancy €{3}",
        "fr": "{0} clôturés, taux de réussite {1} %, profit factor {2}, espérance {3} €",
        "de": "{0} geschlossen, Trefferquote {1} %, Profit-Faktor {2}, Erwartungswert {3} €",
    },
    "{0} лот, TP {1}": {
        "en": "{0} lots, TP {1}",
        "fr": "{0} lots, TP {1}",
        "de": "{0} Lot, TP {1}",
    },
    "{0} не может быть отрицательным/нечисловым": {
        "en": "{0} cannot be negative or non-numeric",
        "fr": "{0} ne peut pas être négatif ni non numérique",
        "de": "{0} darf nicht negativ oder nicht-numerisch sein",
    },
    "{0} отключён в настройках (накопленная статистика убыточна)": {
        "en": "{0} is disabled in the settings (its accumulated statistics are negative)",
        "fr": "{0} est désactivé dans les paramètres (ses statistiques accumulées sont négatives)",
        "de": "{0} ist in den Einstellungen deaktiviert (die gesammelte Statistik ist negativ)",
    },
    "{0} открыт(ых) сигнал(ов) по {1} (макс. {2})": {
        "en": "{0} open signal(s) on {1} (max {2})",
        "fr": "{0} signal(aux) ouvert(s) sur {1} (max {2})",
        "de": "{0} offene(s) Signal(e) auf {1} (max. {2})",
    },
    "{0} позиции в одну сторону ({1}) по {2}: {3}. Фактический риск складывается.": {
        "en": "{0} positions on the same side ({1}) on {2}: {3}. The actual risk adds up.",
        "fr": "{0} positions dans le même sens ({1}) sur {2} : {3}. Le risque réel s’additionne.",
        "de": "{0} Positionen in dieselbe Richtung ({1}) auf {2}: {3}. Das tatsächliche Risiko summiert sich.",
    },
    "{0} позиций ждут открытия рынка. Стопы не исполняются, пока рынок закрыт — воскресный гэп может открыться за стоп-лоссом.": {
        "en": "{0} positions are waiting for the market to open. Stops do not execute while the market is closed — a Sunday gap can open past the stop-loss.",
        "fr": "{0} positions attendent l’ouverture du marché. Les stops ne s’exécutent pas marché fermé — un gap du dimanche peut ouvrir au-delà du stop-loss.",
        "de": "{0} Positionen warten auf die Markteröffnung. Stops werden bei geschlossenem Markt nicht ausgeführt — ein Sonntags-Gap kann jenseits des Stop-Loss eröffnen.",
    },
    "{0} позиций останутся открытыми через выходные: {1}. Гэп в воскресенье может перескочить стоп-лосс (исполнение по худшей цене).": {
        "en": "{0} positions will stay open over the weekend: {1}. A Sunday gap can jump the stop-loss (filling at a worse price).",
        "fr": "{0} positions resteront ouvertes pendant le week-end : {1}. Un gap du dimanche peut sauter le stop-loss (exécution à un prix moins favorable).",
        "de": "{0} Positionen bleiben über das Wochenende offen: {1}. Ein Sonntags-Gap kann den Stop-Loss überspringen (Ausführung zu einem schlechteren Kurs).",
    },
    "{0} свечей с движением forex в закрытую субботнюю сессию UTC": {
        "en": "{0} candles show forex movement during the closed Saturday session in UTC",
        "fr": "{0} bougies montrent du mouvement forex pendant la session fermée du samedi en UTC",
        "de": "{0} Kerzen zeigen Forex-Bewegung während der geschlossenen Samstagssitzung in UTC",
    },
    "{0} убыточных сделок сегодня (лимит {1})": {
        "en": "{0} losing trades today (limit {1})",
        "fr": "{0} trades perdants aujourd’hui (limite {1})",
        "de": "{0} Verlusttrades heute (Limit {1})",
    },
    "{0} шт. (scope={1}, days={2}, ids={3})": {
        "en": "{0} items (scope={1}, days={2}, ids={3})",
        "fr": "{0} éléments (scope={1}, days={2}, ids={3})",
        "de": "{0} Einträge (scope={1}, days={2}, ids={3})",
    },
    "{0} — через ~30 минут. Возможен всплеск волатильности по инструментам с {1}.": {
        "en": "{0} — in about 30 minutes. Expect a possible volatility spike on instruments with {1}.",
        "fr": "{0} — dans environ 30 minutes. Un pic de volatilité est possible sur les instruments avec {1}.",
        "de": "{0} — in etwa 30 Minuten. Auf Instrumenten mit {1} ist eine Volatilitätsspitze möglich.",
    },
    "{0}: {1} сделок, win rate {2}%": {
        "en": "{0}: {1} trades, win rate {2}%",
        "fr": "{0} : {1} trades, taux de réussite {2} %",
        "de": "{0}: {1} Trades, Trefferquote {2} %",
    },
    "{0}: часы должны быть целыми от 0 до 23": {
        "en": "{0}: hours must be integers from 0 to 23",
        "fr": "{0} : les heures doivent être des entiers de 0 à 23",
        "de": "{0}: Stunden müssen ganze Zahlen von 0 bis 23 sein",
    },
    "{0}:00 UTC ({1}:00 Бухарест) — час отключён: на истории стратегия в нём убыточна": {
        "en": "{0}:00 UTC ({1}:00 Bucharest) — this hour is disabled: the strategy loses money in it historically",
        "fr": "{0}:00 UTC ({1}:00 Bucarest) — cette heure est désactivée : historiquement, la stratégie y perd de l’argent",
        "de": "{0}:00 UTC ({1}:00 Bukarest) — diese Stunde ist deaktiviert: Historisch verliert die Strategie darin Geld",
    },
    "{0}Купить ×{1}": {
        "en": "{0}Buy ×{1}",
        "fr": "{0}Acheter ×{1}",
        "de": "{0}Kaufen ×{1}",
    },
    "Азия": {
        "en": "Asia",
        "fr": "Asie",
        "de": "Asien",
    },
    "Акции": {
        "en": "Stocks",
        "fr": "Actions",
        "de": "Aktien",
    },
    "Алерт: {0} ({1})": {
        "en": "Alert: {0} ({1})",
        "fr": "Alerte : {0} ({1})",
        "de": "Alarm: {0} ({1})",
    },
    "Боковой канал": {
        "en": "Sideways range",
        "fr": "Range latéral",
        "de": "Seitwärtsrange",
    },
    "Бэктест {0} {1}": {
        "en": "Backtest {0} {1}",
        "fr": "Backtest {0} {1}",
        "de": "Backtest {0} {1}",
    },
    "Восходящий канал": {
        "en": "Rising channel",
        "fr": "Canal ascendant",
        "de": "Steigender Kanal",
    },
    "Восходящий клин": {
        "en": "Rising wedge",
        "fr": "Biseau ascendant",
        "de": "Steigender Keil",
    },
    "Восходящий клин: рост выдыхается (сходящиеся линии). Классически разрешается вниз.": {
        "en": "Rising wedge: the advance is running out of breath (converging lines). It classically resolves downwards.",
        "fr": "Biseau ascendant : la hausse s’essouffle (lignes convergentes). Il se résout classiquement vers le bas.",
        "de": "Steigender Keil: Der Anstieg geht die Luft aus (konvergierende Linien). Klassisch löst er sich nach unten auf.",
    },
    "Восходящий треугольник": {
        "en": "Ascending triangle",
        "fr": "Triangle ascendant",
        "de": "Aufsteigendes Dreieck",
    },
    "Время истекло": {
        "en": "Time ran out",
        "fr": "Délai écoulé",
        "de": "Zeit abgelaufen",
    },
    "Вс": {
        "en": "Sun",
        "fr": "dim.",
        "de": "So",
    },
    "Вт": {
        "en": "Tue",
        "fr": "mar.",
        "de": "Di",
    },
    "Вымпел": {
        "en": "Pennant",
        "fr": "Fanion",
        "de": "Wimpel",
    },
    "Высокая суммарная экспозиция": {
        "en": "High total exposure",
        "fr": "Exposition totale élevée",
        "de": "Hohe Gesamtexposure",
    },
    "Голова и плечи": {
        "en": "Head and shoulders",
        "fr": "Tête-épaules",
        "de": "Schulter-Kopf-Schulter",
    },
    "Два минимума на одном уровне: продавцы дважды не продавили ниже. Подтверждение — закрытие выше линии шеи {0}": {
        "en": "Two lows at the same level: the sellers failed twice to push lower. Confirmation is a close above the neckline {0}",
        "fr": "Deux creux au même niveau : les vendeurs ont échoué deux fois à descendre plus bas. La confirmation est une clôture au-dessus de l’encolure {0}",
        "de": "Zwei Tiefs auf demselben Niveau: Die Verkäufer scheiterten zweimal daran, tiefer zu drücken. Die Bestätigung ist ein Schluss über der Nackenlinie {0}",
    },
    "Две вершины на одном уровне: покупатели дважды не смогли пройти выше. Подтверждение — закрытие ниже линии шеи {0}": {
        "en": "Two highs at the same level: the buyers failed twice to get through. Confirmation is a close below the neckline {0}",
        "fr": "Deux sommets au même niveau : les acheteurs ont échoué deux fois à passer au-dessus. La confirmation est une clôture sous l’encolure {0}",
        "de": "Zwei Hochs auf demselben Niveau: Die Käufer scheiterten zweimal daran, darüber zu kommen. Die Bestätigung ist ein Schluss unter der Nackenlinie {0}",
    },
    "Двойная вершина": {
        "en": "Double top",
        "fr": "Double sommet",
        "de": "Doppeltop",
    },
    "Двойное дно": {
        "en": "Double bottom",
        "fr": "Double creux",
        "de": "Doppelboden",
    },
    "Если логин существует и к нему привязана почта, код отправлен. Он действует 15 минут.": {
        "en": "If the login exists and has an email attached, the code has been sent. It is valid for 15 minutes.",
        "fr": "Si l’identifiant existe et qu’une adresse e-mail y est rattachée, le code a été envoyé. Il est valable 15 minutes.",
        "de": "Wenn der Login existiert und eine E-Mail hinterlegt ist, wurde der Code gesendet. Er gilt 15 Minuten.",
    },
    "Закройте или сократите позиции до пятницы 21:00 UTC, либо примите риск гэпа осознанно.": {
        "en": "Close or trim the positions before Friday 21:00 UTC, or accept the gap risk deliberately.",
        "fr": "Clôturez ou réduisez les positions avant vendredi 21:00 UTC, ou acceptez sciemment le risque de gap.",
        "de": "Schließen oder verkleinern Sie die Positionen vor Freitag 21:00 UTC, oder nehmen Sie das Gap-Risiko bewusst in Kauf.",
    },
    "Закройте позицию немедленно — план риска уже нарушен.": {
        "en": "Close the position now — the risk plan is already broken.",
        "fr": "Clôturez la position maintenant — le plan de risque est déjà rompu.",
        "de": "Schließen Sie die Position jetzt — der Risikoplan ist bereits gebrochen.",
    },
    "Золото": {
        "en": "Gold",
        "fr": "Or",
        "de": "Gold",
    },
    "ИИ-анализ ещё не запускался — нейтральный фон.": {
        "en": "The AI analysis has not run yet — neutral backdrop.",
        "fr": "L’analyse IA n’a pas encore tourné — contexte neutre.",
        "de": "Die KI-Analyse lief noch nicht — neutrales Umfeld.",
    },
    "Импульс {0} за {1} баров, затем узкая консолидация — паттерн продолжения. Пробой в сторону импульса ({2}) наиболее вероятен.": {
        "en": "An impulse of {0} over {1} bars, then a tight consolidation — a continuation pattern. A break in the direction of the impulse ({2}) is most likely.",
        "fr": "Une impulsion de {0} sur {1} barres, puis une consolidation étroite — figure de continuation. Une cassure dans le sens de l’impulsion ({2}) est la plus probable.",
        "de": "Ein Impuls von {0} über {1} Bars, dann eine enge Konsolidierung — ein Fortsetzungsmuster. Ein Ausbruch in Richtung des Impulses ({2}) ist am wahrscheinlichsten.",
    },
    "Индексы": {
        "en": "Indices",
        "fr": "Indices",
        "de": "Indizes",
    },
    "Источник старого прогона не подтверждён; не используйте его для оценки стратегии": {
        "en": "The source of the old run is unconfirmed; do not use it to judge the strategy",
        "fr": "La source de l’ancienne exécution n’est pas confirmée ; ne l’utilisez pas pour juger la stratégie",
        "de": "Die Quelle des alten Laufs ist unbestätigt; nutzen Sie ihn nicht zur Bewertung der Strategie",
    },
    "Код для смены пароля: {0}\\n\\nДействует {1} минут. Если вы этого не запрашивали — просто не вводите его, пароль останется прежним.": {
        "en": "Your password reset code: {0}\\n\\nIt is valid for {1} minutes. If you did not ask for it, simply do not enter it and your password stays as it is.",
        "fr": "Votre code de réinitialisation : {0}\\n\\nIl est valable {1} minutes. Si vous ne l’avez pas demandé, ne le saisissez tout simplement pas et votre mot de passe restera inchangé.",
        "de": "Ihr Code zum Zurücksetzen des Passworts: {0}\\n\\nEr gilt {1} Minuten. Falls Sie ihn nicht angefordert haben, geben Sie ihn einfach nicht ein — Ihr Passwort bleibt unverändert.",
    },
    "Коррелированные позиции по {0}": {
        "en": "Correlated positions on {0}",
        "fr": "Positions corrélées sur {0}",
        "de": "Korrelierte Positionen auf {0}",
    },
    "Криптовалюты": {
        "en": "Crypto",
        "fr": "Cryptos",
        "de": "Krypto",
    },
    "Лимит достигнут — торговля остановлена": {
        "en": "A limit was hit — trading is halted",
        "fr": "Une limite est atteinte — le trading est arrêté",
        "de": "Ein Limit wurde erreicht — der Handel ist gestoppt",
    },
    "Ложный пробой": {
        "en": "False breakout",
        "fr": "Fausse cassure",
        "de": "Fehlausbruch",
    },
    "Ложный пробой поддержки {0}: цена вернулась выше — ловушка для продавцов, возможен ход вверх.": {
        "en": "A false break of support {0}: price came back above — a trap for sellers, an upward move is possible.",
        "fr": "Fausse cassure du support {0} : le prix est repassé au-dessus — un piège pour les vendeurs, un mouvement haussier est possible.",
        "de": "Fehlausbruch der Unterstützung {0}: Der Kurs kam darüber zurück — eine Falle für Verkäufer, eine Aufwärtsbewegung ist möglich.",
    },
    "Ложный пробой сопротивления {0}: цена вернулась под уровень — ловушка для покупателей, риск движения вниз.": {
        "en": "A false break of resistance {0}: price fell back under the level — a trap for buyers, with downside risk.",
        "fr": "Fausse cassure de la résistance {0} : le prix est repassé sous le niveau — un piège pour les acheteurs, avec un risque baissier.",
        "de": "Fehlausbruch des Widerstands {0}: Der Kurs fiel unter das Niveau zurück — eine Falle für Käufer, mit Abwärtsrisiko.",
    },
    "Лондон": {
        "en": "London",
        "fr": "Londres",
        "de": "London",
    },
    "Лондон+НЙ": {
        "en": "London+NY",
        "fr": "Londres+NY",
        "de": "London+NY",
    },
    "Медь": {
        "en": "Copper",
        "fr": "Cuivre",
        "de": "Kupfer",
    },
    "Металлы": {
        "en": "Metals",
        "fr": "Métaux",
        "de": "Metalle",
    },
    "Не открывайте новые позиции; закройте слабейшую, чтобы снизить экспозицию.": {
        "en": "Do not open new positions; close the weakest one to bring the exposure down.",
        "fr": "N’ouvrez pas de nouvelles positions ; clôturez la plus faible pour réduire l’exposition.",
        "de": "Eröffnen Sie keine neuen Positionen; schließen Sie die schwächste, um die Exposure zu senken.",
    },
    "Не удалось получить разбор.": {
        "en": "Could not get the review.",
        "fr": "Impossible d’obtenir l’analyse.",
        "de": "Auswertung konnte nicht abgerufen werden.",
    },
    "Не удалось разобрать новости.": {
        "en": "Could not analyse the news.",
        "fr": "Impossible d’analyser les actualités.",
        "de": "Nachrichten konnten nicht ausgewertet werden.",
    },
    "Нефть Brent": {
        "en": "Brent crude",
        "fr": "Pétrole Brent",
        "de": "Brent-Öl",
    },
    "Нефть WTI": {
        "en": "WTI crude",
        "fr": "Pétrole WTI",
        "de": "WTI-Öl",
    },
    "Нисходящий канал": {
        "en": "Falling channel",
        "fr": "Canal descendant",
        "de": "Fallender Kanal",
    },
    "Нисходящий канал: продажи от верхней границы. Пробой верхней границы вверх может означать разворот.": {
        "en": "Falling channel: sell at the upper edge. A break above the upper edge may mean a reversal.",
        "fr": "Canal descendant : vendez sur la borne supérieure. Une cassure au-dessus de la borne supérieure peut signaler un retournement.",
        "de": "Fallender Kanal: Verkaufen an der oberen Begrenzung. Ein Bruch über die obere Begrenzung kann eine Umkehr bedeuten.",
    },
    "Нисходящий клин": {
        "en": "Falling wedge",
        "fr": "Biseau descendant",
        "de": "Fallender Keil",
    },
    "Нисходящий клин: падение замедляется. Классически разрешается вверх.": {
        "en": "Falling wedge: the decline is slowing. It classically resolves upwards.",
        "fr": "Biseau descendant : la baisse ralentit. Il se résout classiquement vers le haut.",
        "de": "Fallender Keil: Der Rückgang verlangsamt sich. Klassisch löst er sich nach oben auf.",
    },
    "Нисходящий треугольник": {
        "en": "Descending triangle",
        "fr": "Triangle descendant",
        "de": "Absteigendes Dreieck",
    },
    "Новостей, способных сдвинуть рынок, не обнаружено.": {
        "en": "No market-moving news found.",
        "fr": "Aucune actualité susceptible de bouger le marché.",
        "de": "Keine marktbewegenden Nachrichten gefunden.",
    },
    "Новостной фон {0}": {
        "en": "News backdrop {0}",
        "fr": "Contexte des actualités {0}",
        "de": "Nachrichtenumfeld {0}",
    },
    "Новые входы будут заблокированы незадолго до закрытия.": {
        "en": "New entries will be blocked shortly before the close.",
        "fr": "Les nouvelles entrées seront bloquées peu avant la clôture.",
        "de": "Neue Einstiege werden kurz vor dem Schluss blockiert.",
    },
    "Новые сигналы блокируются до конца периода. Отдохните и разберите сегодняшние сделки в журнале.": {
        "en": "New signals are blocked until the period ends. Take a break and review today's trades in the journal.",
        "fr": "Les nouveaux signaux sont bloqués jusqu’à la fin de la période. Faites une pause et analysez les trades du jour dans le journal.",
        "de": "Neue Signale sind bis zum Periodenende gesperrt. Machen Sie eine Pause und werten Sie die heutigen Trades im Journal aus.",
    },
    "Нью-Йорк": {
        "en": "New York",
        "fr": "New York",
        "de": "New York",
    },
    "Открываю…": {
        "en": "Opening…",
        "fr": "Ouverture…",
        "de": "Wird eröffnet…",
    },
    "Открыто позиций: {0} · плавающий {1}€": {
        "en": "Open positions: {0} · floating €{1}",
        "fr": "Positions ouvertes : {0} · flottant {1} €",
        "de": "Offene Positionen: {0} · schwebend {1} €",
    },
    "Открыто позиций: {0} — воскресный гэп может перескочить стоп-лосс; рассмотрите закрытие до конца сессии.": {
        "en": "{0} positions are open — a Sunday gap can jump the stop-loss; consider closing before the session ends.",
        "fr": "{0} positions sont ouvertes — un gap du dimanche peut sauter le stop-loss ; envisagez de clôturer avant la fin de la session.",
        "de": "{0} Positionen sind offen — ein Sonntags-Gap kann den Stop-Loss überspringen; erwägen Sie, vor Sessionende zu schließen.",
    },
    "Открытый риск {0}% капитала (лимит {1}%).": {
        "en": "Open risk {0}% of capital (limit {1}%).",
        "fr": "Risque ouvert {0} % du capital (limite {1} %).",
        "de": "Offenes Risiko {0} % des Kapitals (Limit {1} %).",
    },
    "Оценка {0}, уверенность {1}%, режим {2}. Цена {3}, SL {4}, TP {5}. {6}.\\n⚠️ Сигнал НЕ создан и позиция НЕ открывается: {7} не входит в автоскан ({8}). Это только наблюдение.": {
        "en": "Score {0}, confidence {1}%, regime {2}. Price {3}, SL {4}, TP {5}. {6}.\\n⚠️ NO signal was created and NO position is opened: {7} is not in the autoscan ({8}). This is an observation only.",
        "fr": "Score {0}, confiance {1} %, régime {2}. Prix {3}, SL {4}, TP {5}. {6}.\\n⚠️ AUCUN signal créé et AUCUNE position ouverte : {7} ne fait pas partie de l’autoscan ({8}). Ceci n’est qu’une observation.",
        "de": "Score {0}, Konfidenz {1} %, Regime {2}. Kurs {3}, SL {4}, TP {5}. {6}.\\n⚠️ Es wurde KEIN Signal erstellt und KEINE Position eröffnet: {7} gehört nicht zum Autoscan ({8}). Dies ist nur eine Beobachtung.",
    },
    "ПОКУПКА": {
        "en": "BUY",
        "fr": "ACHAT",
        "de": "KAUF",
    },
    "ПОКУПКА 📈": {
        "en": "BUY 📈",
        "fr": "ACHAT 📈",
        "de": "KAUF 📈",
    },
    "ПРОДАЖА": {
        "en": "SELL",
        "fr": "VENTE",
        "de": "VERKAUF",
    },
    "ПРОДАЖА 📉": {
        "en": "SELL 📉",
        "fr": "VENTE 📉",
        "de": "VERKAUF 📉",
    },
    "Палладий": {
        "en": "Palladium",
        "fr": "Palladium",
        "de": "Palladium",
    },
    "Память пока пуста — накопленных уроков нет.": {
        "en": "Memory is still empty — no lessons collected yet.",
        "fr": "La mémoire est encore vide — aucune leçon accumulée.",
        "de": "Das Gedächtnis ist noch leer — keine gesammelten Lektionen.",
    },
    "Пароль изменён. Войдите с новым паролем.": {
        "en": "Password changed. Sign in with the new one.",
        "fr": "Mot de passe modifié. Connectez-vous avec le nouveau.",
        "de": "Passwort geändert. Melden Sie sich mit dem neuen an.",
    },
    "Перевёрнутые голова и плечи": {
        "en": "Inverse head and shoulders",
        "fr": "Tête-épaules inversée",
        "de": "Umgekehrte Schulter-Kopf-Schulter",
    },
    "Пересмотрите тейк-профит или откажитесь от таких сделок: матожидание отрицательно даже при винрейте 50%.": {
        "en": "Rework the take-profit or skip trades like this: the expectancy is negative even at a 50% win rate.",
        "fr": "Revoyez le take-profit ou renoncez à ce type de trade : l’espérance est négative même avec un taux de réussite de 50 %.",
        "de": "Überarbeiten Sie den Take-Profit oder lassen Sie solche Trades aus: Der Erwartungswert ist selbst bei 50 % Trefferquote negativ.",
    },
    "Платина": {
        "en": "Platinum",
        "fr": "Platine",
        "de": "Platin",
    },
    "Плоская поддержка и снижающиеся максимумы — продавцы давят. Чаще пробивается вниз.": {
        "en": "Flat support with falling highs — the sellers are pressing. It breaks downwards more often.",
        "fr": "Support plat et sommets décroissants — les vendeurs pressent. La cassure se fait plus souvent vers le bas.",
        "de": "Flache Unterstützung bei fallenden Hochs — die Verkäufer drücken. Der Ausbruch erfolgt öfter nach unten.",
    },
    "Плоское сопротивление и растущие минимумы — покупатели давят. Статистически чаще пробивается вверх.": {
        "en": "Flat resistance with rising lows — the buyers are pressing. Statistically it breaks upwards more often.",
        "fr": "Résistance plate et creux croissants — les acheteurs pressent. Statistiquement, la cassure se fait plus souvent vers le haut.",
        "de": "Flacher Widerstand bei steigenden Tiefs — die Käufer drücken. Statistisch erfolgt der Ausbruch öfter nach oben.",
    },
    "Пн": {
        "en": "Mon",
        "fr": "lun.",
        "de": "Mo",
    },
    "Позиция за стопом — {0}": {
        "en": "The position is past its stop — {0}",
        "fr": "La position a dépassé son stop — {0}",
        "de": "Die Position liegt hinter ihrem Stop — {0}",
    },
    "Приближение к лимиту": {
        "en": "Approaching a limit",
        "fr": "Limite proche",
        "de": "Limit rückt näher",
    },
    "Природный газ": {
        "en": "Natural gas",
        "fr": "Gaz naturel",
        "de": "Erdgas",
    },
    "Пробой поддержки {0} с закрытием ниже. Уровень теперь может работать сопротивлением.": {
        "en": "A break of support {0} with a close below. The level may now act as resistance.",
        "fr": "Cassure du support {0} avec clôture en dessous. Le niveau peut désormais agir en résistance.",
        "de": "Bruch der Unterstützung {0} mit Schluss darunter. Das Niveau kann nun als Widerstand wirken.",
    },
    "Пробой сопротивления {0} с закрытием выше. Уровень теперь может работать поддержкой.": {
        "en": "A break of resistance {0} with a close above. The level may now act as support.",
        "fr": "Cassure de la résistance {0} avec clôture au-dessus. Le niveau peut désormais agir en support.",
        "de": "Bruch des Widerstands {0} mit Schluss darüber. Das Niveau kann nun als Unterstützung wirken.",
    },
    "Пробой уровня": {
        "en": "Level breakout",
        "fr": "Cassure de niveau",
        "de": "Niveau-Ausbruch",
    },
    "Проверьте позиции сразу после открытия (воскресенье ~21:00 UTC).": {
        "en": "Check the positions right after the open (Sunday, about 21:00 UTC).",
        "fr": "Vérifiez les positions juste après l’ouverture (dimanche, vers 21:00 UTC).",
        "de": "Prüfen Sie die Positionen direkt nach der Eröffnung (Sonntag, etwa 21:00 UTC).",
    },
    "Проверяю…": {
        "en": "Checking…",
        "fr": "Vérification…",
        "de": "Wird geprüft…",
    },
    "Пропущен": {
        "en": "Skipped",
        "fr": "Ignoré",
        "de": "Übersprungen",
    },
    "Пт": {
        "en": "Fri",
        "fr": "ven.",
        "de": "Fr",
    },
    "Разбор журнала": {
        "en": "Journal review",
        "fr": "Analyse du journal",
        "de": "Journal-Auswertung",
    },
    "Разворотная формация вверх: правое плечо выше головы. Пробой шеи {0} ": {
        "en": "An upward reversal: the right shoulder sits above the head. A break of the neckline {0} ",
        "fr": "Un retournement haussier : l’épaule droite est au-dessus de la tête. Une cassure de l’encolure {0} ",
        "de": "Eine Aufwärtsumkehr: Die rechte Schulter liegt über dem Kopf. Ein Bruch der Nackenlinie {0} ",
    },
    "Разворотная формация: правое плечо ниже головы — импульс роста угасает. Пробой шеи {0} ": {
        "en": "A reversal shape: the right shoulder sits below the head — the upward impulse is fading. A break of the neckline {0} ",
        "fr": "Une figure de retournement : l’épaule droite est sous la tête — l’impulsion haussière s’éteint. Une cassure de l’encolure {0} ",
        "de": "Eine Umkehrformation: Die rechte Schulter liegt unter dem Kopf — der Aufwärtsimpuls erlischt. Ein Bruch der Nackenlinie {0} ",
    },
    "Реально в MT5: <b>{0}€</b> · баланс {1}€ · эквити {2}€": {
        "en": "Actual in MT5: <b>€{0}</b> · balance €{1} · equity €{2}",
        "fr": "Réel dans MT5 : <b>{0} €</b> · solde {1} € · équité {2} €",
        "de": "Tatsächlich in MT5: <b>{0} €</b> · Saldo {1} € · Equity {2} €",
    },
    "Рекомендуемое число ордеров: <b>{0}</b> (тейки ступенями: +1R, цель, цель×1.5)\\n": {
        "en": "Recommended number of orders: <b>{0}</b> (laddered take-profits: +1R, target, target ×1.5)\\n",
        "fr": "Nombre d’ordres recommandé : <b>{0}</b> (take-profits échelonnés : +1R, objectif, objectif ×1,5)\\n",
        "de": "Empfohlene Anzahl Orders: <b>{0}</b> (gestaffelte Take-Profits: +1R, Ziel, Ziel ×1,5)\\n",
    },
    "Риск позиции выше плана — {0}": {
        "en": "Position risk above plan — {0}",
        "fr": "Risque de position supérieur au plan — {0}",
        "de": "Positionsrisiko über Plan — {0}",
    },
    "Рынок закрывается в 21:00 UTC (через ~{0} ч). ": {
        "en": "The market closes at 21:00 UTC (in about {0} h). ",
        "fr": "Le marché ferme à 21:00 UTC (dans environ {0} h). ",
        "de": "Der Markt schließt um 21:00 UTC (in etwa {0} Std.). ",
    },
    "Рынок закрывается через {0} ч": {
        "en": "The market closes in {0} h",
        "fr": "Le marché ferme dans {0} h",
        "de": "Der Markt schließt in {0} Std.",
    },
    "Рынок закрыт (выходные)": {
        "en": "The market is closed (weekend)",
        "fr": "Le marché est fermé (week-end)",
        "de": "Der Markt ist geschlossen (Wochenende)",
    },
    "СИНТЕТИЧЕСКИЕ ДАННЫЕ: провайдер не отдал реальные свечи, использован встроенный симулятор. Эти метрики НЕ отражают рынок и не годятся для оценки стратегии — проверьте ключи API.": {
        "en": "SYNTHETIC DATA: the provider returned no real candles, so the built-in simulator was used. These figures do NOT reflect the market and cannot be used to judge the strategy — check your API keys.",
        "fr": "DONNÉES SYNTHÉTIQUES : le fournisseur n’a pas renvoyé de vraies bougies, le simulateur intégré a été utilisé. Ces chiffres ne reflètent PAS le marché et ne permettent pas de juger la stratégie — vérifiez vos clés API.",
        "de": "SYNTHETISCHE DATEN: Der Anbieter lieferte keine echten Kerzen, daher wurde der eingebaute Simulator verwendet. Diese Zahlen spiegeln den Markt NICHT wider und taugen nicht zur Bewertung der Strategie — prüfen Sie Ihre API-Schlüssel.",
    },
    "Сб": {
        "en": "Sat",
        "fr": "sam.",
        "de": "Sa",
    },
    "Свежих заголовков не найдено.": {
        "en": "No fresh headlines found.",
        "fr": "Aucun titre récent trouvé.",
        "de": "Keine aktuellen Schlagzeilen gefunden.",
    },
    "Сделка #{0} {1} {2} → {3}": {
        "en": "Trade #{0} {1} {2} → {3}",
        "fr": "Trade #{0} {1} {2} → {3}",
        "de": "Trade #{0} {1} {2} → {3}",
    },
    "Серебро": {
        "en": "Silver",
        "fr": "Argent",
        "de": "Silber",
    },
    "Сжатие волатильности: рынок копит энергию, направление задаст пробой одной из сторон.": {
        "en": "Volatility squeeze: the market is storing energy; a break of one side will set the direction.",
        "fr": "Compression de volatilité : le marché accumule de l’énergie ; la cassure d’un côté donnera la direction.",
        "de": "Volatilitätskompression: Der Markt sammelt Energie; der Bruch einer Seite gibt die Richtung vor.",
    },
    "Сигнал #{0} ({1}, уверенность {2}%): открыто {3} ордер(а) — ": {
        "en": "Signal #{0} ({1}, confidence {2}%): {3} order(s) opened — ",
        "fr": "Signal #{0} ({1}, confiance {2} %) : {3} ordre(s) ouvert(s) — ",
        "de": "Signal #{0} ({1}, Konfidenz {2} %): {3} Order(s) eröffnet — ",
    },
    "Сигнал #{0}: оценка {1}, уверенность {2}%. Цена {3}, SL {4}, TP {5}. Купить можно из Telegram; добавьте в «Избранное» для автоскана/автотрейда.": {
        "en": "Signal #{0}: score {1}, confidence {2}%. Price {3}, SL {4}, TP {5}. You can buy from Telegram; add it to the watchlist for autoscan and auto-trading.",
        "fr": "Signal #{0} : score {1}, confiance {2} %. Prix {3}, SL {4}, TP {5}. Vous pouvez acheter depuis Telegram ; ajoutez-le aux favoris pour l’autoscan et le trading auto.",
        "de": "Signal #{0}: Score {1}, Konfidenz {2} %. Kurs {3}, SL {4}, TP {5}. Sie können aus Telegram kaufen; fügen Sie es der Watchlist für Autoscan und Auto-Trading hinzu.",
    },
    "Сигнал #{0}: под риском {1}% капитала при плане {2}%.": {
        "en": "Signal #{0}: {1}% of capital at risk against a plan of {2}%.",
        "fr": "Signal #{0} : {1} % du capital à risque pour un plan de {2} %.",
        "de": "Signal #{0}: {1} % des Kapitals im Risiko gegenüber einem Plan von {2} %.",
    },
    "Сигнал #{0}: риск/прибыль {1} < 1.0.": {
        "en": "Signal #{0}: risk/reward {1} < 1.0.",
        "fr": "Signal #{0} : risque/gain {1} < 1,0.",
        "de": "Signal #{0}: Chance-Risiko {1} < 1,0.",
    },
    "Сигнал #{0}: текущий убыток {1}R превышает план (−1R). Возможен гэп или пропуск стопа.": {
        "en": "Signal #{0}: the current loss of {1}R is beyond plan (−1R). A gap or a skipped stop is possible.",
        "fr": "Signal #{0} : la perte actuelle de {1}R dépasse le plan (−1R). Un gap ou un stop manqué est possible.",
        "de": "Signal #{0}: Der aktuelle Verlust von {1}R liegt über Plan (−1R). Ein Gap oder ein übersprungener Stop ist möglich.",
    },
    "Сигнал не подтверждён": {
        "en": "The signal was not confirmed",
        "fr": "Le signal n’a pas été confirmé",
        "de": "Das Signal wurde nicht bestätigt",
    },
    "Сигнал устарел": {
        "en": "The signal is stale",
        "fr": "Le signal est périmé",
        "de": "Das Signal ist veraltet",
    },
    "Сигналы: закрыто {0} ({1}П/{2}У) · {3}€ (расчёт сайта)": {
        "en": "Signals: {0} closed ({1}W/{2}L) · €{3} (the app's own figure)",
        "fr": "Signaux : {0} clôturés ({1}G/{2}P) · {3} € (chiffre de l’application)",
        "de": "Signale: {0} geschlossen ({1}G/{2}V) · {3} € (Zahl der App)",
    },
    "Сидней": {
        "en": "Sydney",
        "fr": "Sydney",
        "de": "Sydney",
    },
    "Симметричный треугольник": {
        "en": "Symmetrical triangle",
        "fr": "Triangle symétrique",
        "de": "Symmetrisches Dreieck",
    },
    "Скоро важная новость: {0}": {
        "en": "Important news soon: {0}",
        "fr": "Actualité importante bientôt : {0}",
        "de": "Wichtige Nachricht in Kürze: {0}",
    },
    "Слабое соотношение R:R — {0}": {
        "en": "Weak risk/reward — {0}",
        "fr": "Rapport risque/gain faible — {0}",
        "de": "Schwaches Chance-Risiko-Verhältnis — {0}",
    },
    "Снизьте темп: следующая сделка только по идеальному сетапу.": {
        "en": "Slow down: take the next trade only on a perfect setup.",
        "fr": "Ralentissez : ne prenez le prochain trade que sur une configuration parfaite.",
        "de": "Treten Sie kürzer: Nehmen Sie den nächsten Trade nur bei einem perfekten Setup.",
    },
    "Сократите размер позиции или закройте часть, чтобы вернуться к плану.": {
        "en": "Cut the position size or close part of it to get back to plan.",
        "fr": "Réduisez la taille de la position ou clôturez-en une partie pour revenir au plan.",
        "de": "Verringern Sie die Positionsgröße oder schließen Sie einen Teil, um zum Plan zurückzukehren.",
    },
    "Ср": {
        "en": "Wed",
        "fr": "mer.",
        "de": "Mi",
    },
    "Стиль пользователя: риск {0}% на сделку, R:R {1}, сайзинг {2}, вес ИИ {3}": {
        "en": "User style: risk {0}% per trade, R:R {1}, sizing {2}, AI weight {3}",
        "fr": "Style de l’utilisateur : risque {0} % par trade, R:R {1}, dimensionnement {2}, poids IA {3}",
        "de": "Nutzerstil: Risiko {0} % pro Trade, R:R {1}, Sizing {2}, KI-Gewicht {3}",
    },
    "Стоп {0}": {
        "en": "Stop {0}",
        "fr": "Stop {0}",
        "de": "Stop {0}",
    },
    "Считайте эти позиции одной сделкой: суммарный риск не должен превышать разовый лимит на сделку.": {
        "en": "Treat these positions as one trade: their combined risk should not exceed the single-trade limit.",
        "fr": "Considérez ces positions comme un seul trade : leur risque cumulé ne doit pas dépasser la limite par trade.",
        "de": "Behandeln Sie diese Positionen als einen Trade: Ihr Gesamtrisiko darf das Limit je Trade nicht überschreiten.",
    },
    "Токио": {
        "en": "Tokyo",
        "fr": "Tokyo",
        "de": "Tokio",
    },
    "Флаг": {
        "en": "Flag",
        "fr": "Drapeau",
        "de": "Flagge",
    },
    "Флэтовый диапазон: торговля от границ, пробой задаёт направление.": {
        "en": "A range: trade the edges; a breakout sets the direction.",
        "fr": "Un range : tradez les bornes ; une cassure donne la direction.",
        "de": "Eine Range: Handeln Sie die Ränder; ein Ausbruch gibt die Richtung vor.",
    },
    "Форекс": {
        "en": "Forex",
        "fr": "Forex",
        "de": "Forex",
    },
    "Фьючерс 10Y T-Note (ZN)": {
        "en": "10Y T-Note future (ZN)",
        "fr": "Future T-Note 10 ans (ZN)",
        "de": "10Y-T-Note-Future (ZN)",
    },
    "Фьючерс Dow (YM)": {
        "en": "Dow future (YM)",
        "fr": "Future Dow (YM)",
        "de": "Dow-Future (YM)",
    },
    "Фьючерс NASDAQ (NQ)": {
        "en": "NASDAQ future (NQ)",
        "fr": "Future NASDAQ (NQ)",
        "de": "NASDAQ-Future (NQ)",
    },
    "Фьючерс S&P 500 (ES)": {
        "en": "S&P 500 future (ES)",
        "fr": "Future S&P 500 (ES)",
        "de": "S&P-500-Future (ES)",
    },
    "Фьючерс золото (GC)": {
        "en": "Gold future (GC)",
        "fr": "Future or (GC)",
        "de": "Gold-Future (GC)",
    },
    "Фьючерс нефть WTI (CL)": {
        "en": "WTI crude future (CL)",
        "fr": "Future pétrole WTI (CL)",
        "de": "WTI-Öl-Future (CL)",
    },
    "Фьючерсы": {
        "en": "Futures",
        "fr": "Futures",
        "de": "Futures",
    },
    "Цена движется в восходящем канале: покупки от нижней границы, цели у верхней. Пробой нижней границы — сигнал слабости.": {
        "en": "Price runs in a rising channel: buy at the lower edge, target the upper one. A break of the lower edge signals weakness.",
        "fr": "Le prix évolue dans un canal ascendant : achetez sur la borne inférieure, visez la supérieure. Une cassure de la borne inférieure signale une faiblesse.",
        "de": "Der Kurs läuft in einem steigenden Kanal: Kaufen an der unteren Begrenzung, Ziel an der oberen. Ein Bruch der unteren Begrenzung signalisiert Schwäche.",
    },
    "Чт": {
        "en": "Thu",
        "fr": "jeu.",
        "de": "Do",
    },
    "Энергоносители": {
        "en": "Energy",
        "fr": "Énergie",
        "de": "Energie",
    },
    "автоторговля выключена": {
        "en": "auto-trading is off",
        "fr": "le trading automatique est désactivé",
        "de": "Auto-Trading ist aus",
    },
    "адрес выглядит некорректно": {
        "en": "the address looks wrong",
        "fr": "l’adresse semble incorrecte",
        "de": "die Adresse sieht falsch aus",
    },
    "адрес удалён": {
        "en": "address removed",
        "fr": "adresse supprimée",
        "de": "Adresse entfernt",
    },
    "алерт не найден": {
        "en": "alert not found",
        "fr": "alerte introuvable",
        "de": "Alarm nicht gefunden",
    },
    "без стратегии": {
        "en": "no strategy",
        "fr": "sans stratégie",
        "de": "ohne Strategie",
    },
    "близко к дневному лимиту убытка ({0}€ из {1}€)": {
        "en": "close to the daily loss limit (€{0} of €{1})",
        "fr": "proche de la limite de perte journalière ({0} € sur {1} €)",
        "de": "nahe am Tagesverlustlimit ({0} € von {1} €)",
    },
    "близко к месячному лимиту убытка ({0}€)": {
        "en": "close to the monthly loss limit (€{0})",
        "fr": "proche de la limite de perte mensuelle ({0} €)",
        "de": "nahe am monatlichen Verlustlimit ({0} €)",
    },
    "близко к недельному лимиту убытка ({0}€)": {
        "en": "close to the weekly loss limit (€{0})",
        "fr": "proche de la limite de perte hebdomadaire ({0} €)",
        "de": "nahe am wöchentlichen Verlustlimit ({0} €)",
    },
    "брокер не вернул bid/ask": {
        "en": "the broker returned no bid/ask",
        "fr": "le courtier n’a pas renvoyé de bid/ask",
        "de": "der Broker lieferte kein Bid/Ask",
    },
    "брокер не отвечает: {0}": {
        "en": "the broker is not responding: {0}",
        "fr": "le courtier ne répond pas : {0}",
        "de": "der Broker antwortet nicht: {0}",
    },
    "брокер повторил страницу истории": {
        "en": "the broker repeated a history page",
        "fr": "le courtier a répété une page d’historique",
        "de": "der Broker wiederholte eine Verlaufsseite",
    },
    "бэктест не найден": {
        "en": "backtest not found",
        "fr": "backtest introuvable",
        "de": "Backtest nicht gefunden",
    },
    "высокое": {
        "en": "high",
        "fr": "élevé",
        "de": "hoch",
    },
    "движение {0}% за {1} баров (порог {2}%)": {
        "en": "a move of {0}% over {1} bars (threshold {2}%)",
        "fr": "un mouvement de {0} % sur {1} barres (seuil {2} %)",
        "de": "eine Bewegung von {0} % über {1} Bars (Schwelle {2} %)",
    },
    "для AI-бэктеста нужны сохранённые исторические векторы": {
        "en": "an AI backtest needs stored historical vectors",
        "fr": "un backtest IA nécessite des vecteurs historiques enregistrés",
        "de": "ein KI-Backtest benötigt gespeicherte historische Vektoren",
    },
    "дневная цель прибыли достигнута (+{0}€) — торговля остановлена": {
        "en": "the daily profit target is reached (+€{0}) — trading is halted",
        "fr": "l’objectif de profit journalier est atteint (+{0} €) — le trading est arrêté",
        "de": "das Tagesgewinnziel ist erreicht (+{0} €) — der Handel ist gestoppt",
    },
    "дневной лимит убытка достигнут ({0}€ из {1}€)": {
        "en": "the daily loss limit is reached (€{0} of €{1})",
        "fr": "la limite de perte journalière est atteinte ({0} € sur {1} €)",
        "de": "das Tagesverlustlimit ist erreicht ({0} € von {1} €)",
    },
    "до закрытия рынка {0} мин — новые входы скоро будут заблокированы; открытые позиции рассмотрите закрыть до пятницы 21:00 UTC": {
        "en": "{0} min to the market close — new entries will be blocked shortly; consider closing open positions before Friday 21:00 UTC",
        "fr": "{0} min avant la fermeture du marché — les nouvelles entrées seront bientôt bloquées ; envisagez de clôturer les positions ouvertes avant vendredi 21:00 UTC",
        "de": "{0} Min. bis Marktschluss — neue Einstiege werden bald blockiert; erwägen Sie, offene Positionen vor Freitag 21:00 UTC zu schließen",
    },
    "ещё не подтверждён.": {
        "en": "not confirmed yet.",
        "fr": "pas encore confirmé.",
        "de": "noch nicht bestätigt.",
    },
    "закрыт": {
        "en": "closed",
        "fr": "fermé",
        "de": "geschlossen",
    },
    "закрытие {0} выше верхней полосы Боллинджера {1}": {
        "en": "the close {0} is above the upper Bollinger band {1}",
        "fr": "la clôture {0} est au-dessus de la bande de Bollinger supérieure {1}",
        "de": "der Schlusskurs {0} liegt über dem oberen Bollinger-Band {1}",
    },
    "закрытие {0} ниже нижней полосы Боллинджера {1}": {
        "en": "the close {0} is below the lower Bollinger band {1}",
        "fr": "la clôture {0} est sous la bande de Bollinger inférieure {1}",
        "de": "der Schlusskurs {0} liegt unter dem unteren Bollinger-Band {1}",
    },
    "занято {0} позиций из {1} — свободных слотов нет": {
        "en": "{0} of {1} position slots are taken — none free",
        "fr": "{0} emplacements de position sur {1} sont pris — aucun libre",
        "de": "{0} von {1} Positionsplätzen belegt — keiner frei",
    },
    "запись не найдена": {
        "en": "record not found",
        "fr": "enregistrement introuvable",
        "de": "Eintrag nicht gefunden",
    },
    "заполните логин, пароль и сервер MT5": {
        "en": "fill in the MT5 login, password and server",
        "fr": "renseignez l’identifiant, le mot de passe et le serveur MT5",
        "de": "füllen Sie MT5-Login, Passwort und Server aus",
    },
    "запрос сброса: {0} (без адреса или нет пользователя)": {
        "en": "reset request: {0} (no address or no such user)",
        "fr": "demande de réinitialisation : {0} (pas d’adresse ou utilisateur inexistant)",
        "de": "Zurücksetzungsanfrage: {0} (keine Adresse oder kein solcher Benutzer)",
    },
    "категория: {0}": {
        "en": "category: {0}",
        "fr": "catégorie : {0}",
        "de": "Kategorie: {0}",
    },
    "код выслан на {0}": {
        "en": "code sent to {0}",
        "fr": "code envoyé à {0}",
        "de": "Code an {0} gesendet",
    },
    "код не подошёл — проверьте приложение-аутентификатор": {
        "en": "the code did not match — check your authenticator app",
        "fr": "le code ne correspond pas — vérifiez votre application d’authentification",
        "de": "der Code passt nicht — prüfen Sie Ihre Authenticator-App",
    },
    "код неверный или истёк": {
        "en": "the code is wrong or has expired",
        "fr": "le code est incorrect ou expiré",
        "de": "der Code ist falsch oder abgelaufen",
    },
    "комиссия съедает весь допустимый риск": {
        "en": "the commission eats the whole allowed risk",
        "fr": "la commission absorbe tout le risque autorisé",
        "de": "die Kommission frisst das gesamte erlaubte Risiko",
    },
    "логин не короче 3 символов": {
        "en": "the login must be at least 3 characters",
        "fr": "l’identifiant doit faire au moins 3 caractères",
        "de": "der Login muss mindestens 3 Zeichen haben",
    },
    "максимальная просадка достигнута ({0}%)": {
        "en": "the maximum drawdown is reached ({0}%)",
        "fr": "le drawdown maximal est atteint ({0} %)",
        "de": "der maximale Drawdown ist erreicht ({0} %)",
    },
    "месячный лимит убытка достигнут ({0}€)": {
        "en": "the monthly loss limit is reached (€{0})",
        "fr": "la limite de perte mensuelle est atteinte ({0} €)",
        "de": "das monatliche Verlustlimit ist erreicht ({0} €)",
    },
    "минимальный лот ×{0} рискует ×{1} (потолок ×{2}) — нужен депозит крупнее, меньше ордеров или более узкий стоп": {
        "en": "the minimum lot ×{0} risks ×{1} (cap ×{2}) — you need a bigger deposit, fewer orders or a tighter stop",
        "fr": "le lot minimum ×{0} risque ×{1} (plafond ×{2}) — il faut un dépôt plus important, moins d’ordres ou un stop plus serré",
        "de": "das Mindestlot ×{0} riskiert ×{1} (Obergrenze ×{2}) — Sie brauchen eine größere Einlage, weniger Orders oder einen engeren Stop",
    },
    "минимальный лот брокера ({0}) ×{1} рискует ×{2} от заданного": {
        "en": "the broker's minimum lot ({0}) ×{1} risks ×{2} of what was set",
        "fr": "le lot minimum du courtier ({0}) ×{1} risque ×{2} de ce qui est défini",
        "de": "das Mindestlot des Brokers ({0}) ×{1} riskiert ×{2} des Vorgegebenen",
    },
    "направление {0} не торгуется": {
        "en": "direction {0} is not traded",
        "fr": "la direction {0} n’est pas tradée",
        "de": "Richtung {0} wird nicht gehandelt",
    },
    "не задан Anthropic API ключ": {
        "en": "no Anthropic API key is set",
        "fr": "aucune clé API Anthropic définie",
        "de": "kein Anthropic-API-Schlüssel gesetzt",
    },
    "не задан Anthropic API ключ — введите его в «Подключениях»": {
        "en": "no Anthropic API key — enter one under Connections",
        "fr": "aucune clé API Anthropic — saisissez-en une dans Connexions",
        "de": "kein Anthropic-API-Schlüssel — tragen Sie einen unter Verbindungen ein",
    },
    "не задан токен бота": {
        "en": "no bot token set",
        "fr": "aucun jeton de bot défini",
        "de": "kein Bot-Token gesetzt",
    },
    "не заданы токен бота или chat_id": {
        "en": "the bot token or chat_id is missing",
        "fr": "le jeton du bot ou le chat_id est manquant",
        "de": "Bot-Token oder chat_id fehlt",
    },
    "не проводился": {
        "en": "never ran",
        "fr": "jamais exécuté",
        "de": "nie ausgeführt",
    },
    "не удалось закрыть позицию": {
        "en": "could not close the position",
        "fr": "impossible de clôturer la position",
        "de": "Position konnte nicht geschlossen werden",
    },
    "не удалось определить chat_id": {
        "en": "could not determine the chat_id",
        "fr": "impossible de déterminer le chat_id",
        "de": "chat_id konnte nicht ermittelt werden",
    },
    "не удалось подключить MT5": {
        "en": "could not connect MT5",
        "fr": "impossible de connecter MT5",
        "de": "MT5 konnte nicht verbunden werden",
    },
    "неверные OHLC": {
        "en": "invalid OHLC",
        "fr": "OHLC invalides",
        "de": "ungültige OHLC",
    },
    "неверные исторические bid/ask OHLC": {
        "en": "invalid historical bid/ask OHLC",
        "fr": "OHLC bid/ask historiques invalides",
        "de": "ungültige historische Bid/Ask-OHLC",
    },
    "неверные параметры частичной фиксации": {
        "en": "invalid partial take-profit parameters",
        "fr": "paramètres de prise partielle invalides",
        "de": "ungültige Parameter für die Teilgewinnmitnahme",
    },
    "неверный код": {
        "en": "wrong code",
        "fr": "code incorrect",
        "de": "falscher Code",
    },
    "неверный код 2FA": {
        "en": "wrong 2FA code",
        "fr": "code 2FA incorrect",
        "de": "falscher 2FA-Code",
    },
    "неверный код двухфакторной аутентификации": {
        "en": "wrong two-factor authentication code",
        "fr": "code d’authentification à deux facteurs incorrect",
        "de": "falscher Zwei-Faktor-Authentifizierungscode",
    },
    "неверный код: {0}": {
        "en": "wrong code: {0}",
        "fr": "code incorrect : {0}",
        "de": "falscher Code: {0}",
    },
    "неверный логин или пароль": {
        "en": "wrong login or password",
        "fr": "identifiant ou mot de passe incorrect",
        "de": "falscher Login oder falsches Passwort",
    },
    "недельный лимит убытка достигнут ({0}€)": {
        "en": "the weekly loss limit is reached (€{0})",
        "fr": "la limite de perte hebdomadaire est atteinte ({0} €)",
        "de": "das wöchentliche Verlustlimit ist erreicht ({0} €)",
    },
    "недостаточно данных для walk-forward (нужно больше баров)": {
        "en": "not enough data for walk-forward (more bars are needed)",
        "fr": "pas assez de données pour le walk-forward (il faut plus de barres)",
        "de": "nicht genügend Daten für Walk-Forward (mehr Bars nötig)",
    },
    "недостаточно завершённых свечей для подтверждённого сигнала": {
        "en": "not enough completed candles for a confirmed signal",
        "fr": "pas assez de bougies terminées pour un signal confirmé",
        "de": "nicht genügend abgeschlossene Kerzen für ein bestätigtes Signal",
    },
    "недостаточно свечей для профиля объёма": {
        "en": "not enough candles for a volume profile",
        "fr": "pas assez de bougies pour un profil de volume",
        "de": "nicht genügend Kerzen für ein Volumenprofil",
    },
    "недоступен": {
        "en": "unavailable",
        "fr": "indisponible",
        "de": "nicht verfügbar",
    },
    "незавершённые свечи запрещены в бэктесте": {
        "en": "unfinished candles are not allowed in a backtest",
        "fr": "les bougies non terminées sont interdites dans un backtest",
        "de": "unfertige Kerzen sind im Backtest nicht erlaubt",
    },
    "неизвестная категория: {0}": {
        "en": "unknown category: {0}",
        "fr": "catégorie inconnue : {0}",
        "de": "unbekannte Kategorie: {0}",
    },
    "неизвестный инструмент {0}": {
        "en": "unknown instrument {0}",
        "fr": "instrument inconnu {0}",
        "de": "unbekanntes Instrument {0}",
    },
    "неизвестный таймфрейм": {
        "en": "unknown timeframe",
        "fr": "unité de temps inconnue",
        "de": "unbekannter Zeitrahmen",
    },
    "неизвестный таймфрейм {0} ({1})": {
        "en": "unknown timeframe {0} ({1})",
        "fr": "unité de temps inconnue {0} ({1})",
        "de": "unbekannter Zeitrahmen {0} ({1})",
    },
    "неизвестный тип алерта {0}": {
        "en": "unknown alert type {0}",
        "fr": "type d’alerte inconnu {0}",
        "de": "unbekannter Alarmtyp {0}",
    },
    "некорректная котировка bid/ask": {
        "en": "malformed bid/ask quote",
        "fr": "cotation bid/ask incorrecte",
        "de": "fehlerhafte Bid/Ask-Notierung",
    },
    "некорректный ответ истории сделок": {
        "en": "malformed trade history response",
        "fr": "réponse d’historique des trades incorrecte",
        "de": "fehlerhafte Antwort der Trade-Historie",
    },
    "нельзя удалить собственный аккаунт": {
        "en": "you cannot delete your own account",
        "fr": "vous ne pouvez pas supprimer votre propre compte",
        "de": "Sie können Ihr eigenes Konto nicht löschen",
    },
    "неподтверждённые данные: ": {
        "en": "unconfirmed data: ",
        "fr": "données non confirmées : ",
        "de": "unbestätigte Daten: ",
    },
    "неполные/неверные исторические bid/ask": {
        "en": "incomplete or invalid historical bid/ask",
        "fr": "bid/ask historiques incomplets ou invalides",
        "de": "unvollständige oder ungültige historische Bid/Ask",
    },
    "нет": {
        "en": "none",
        "fr": "aucun",
        "de": "keine",
    },
    "нет свежей котировки брокера для проверки входа": {
        "en": "no fresh broker quote to validate the entry",
        "fr": "aucune cotation récente du courtier pour valider l’entrée",
        "de": "keine aktuelle Broker-Notierung zur Prüfung des Einstiegs",
    },
    "нет свечей в периоде оценки": {
        "en": "no candles in the evaluation window",
        "fr": "aucune bougie dans la fenêtre d’évaluation",
        "de": "keine Kerzen im Bewertungsfenster",
    },
    "нет сообщений — напишите боту что-нибудь и повторите": {
        "en": "no messages — send your bot something and try again",
        "fr": "aucun message — écrivez quelque chose au bot et réessayez",
        "de": "keine Nachrichten — schreiben Sie dem Bot etwas und versuchen Sie es erneut",
    },
    "нет сохранённых исторических AI-векторов": {
        "en": "no stored historical AI vectors",
        "fr": "aucun vecteur IA historique enregistré",
        "de": "keine gespeicherten historischen KI-Vektoren",
    },
    "нет токена MetaApi (metaapi.cloud)": {
        "en": "no MetaApi token (metaapi.cloud)",
        "fr": "aucun jeton MetaApi (metaapi.cloud)",
        "de": "kein MetaApi-Token (metaapi.cloud)",
    },
    "нечисловые или бесконечные OHLC": {
        "en": "non-numeric or infinite OHLC",
        "fr": "OHLC non numériques ou infinis",
        "de": "nicht-numerische oder unendliche OHLC",
    },
    "нечисловые/отсутствующие OHLC или временные метки": {
        "en": "non-numeric or missing OHLC or timestamps",
        "fr": "OHLC ou horodatages non numériques ou manquants",
        "de": "nicht-numerische oder fehlende OHLC oder Zeitstempel",
    },
    "низкое": {
        "en": "low",
        "fr": "faible",
        "de": "niedrig",
    },
    "новый пароль должен быть не короче 8 символов": {
        "en": "the new password must be at least 8 characters",
        "fr": "le nouveau mot de passe doit faire au moins 8 caractères",
        "de": "das neue Passwort muss mindestens 8 Zeichen haben",
    },
    "нужно больше {0} завершённых свечей": {
        "en": "more than {0} completed candles are needed",
        "fr": "il faut plus de {0} bougies terminées",
        "de": "es werden mehr als {0} abgeschlossene Kerzen benötigt",
    },
    "нужны права администратора": {
        "en": "administrator rights are required",
        "fr": "des droits d’administrateur sont requis",
        "de": "Administratorrechte sind erforderlich",
    },
    "объём 0: минимальный лот брокера по {0} рискует больше заданного риска — сделка пропущена": {
        "en": "size 0: the broker's minimum lot on {0} risks more than the risk you set — the trade was skipped",
        "fr": "taille 0 : le lot minimum du courtier sur {0} risque plus que le risque défini — le trade a été ignoré",
        "de": "Größe 0: Das Mindestlot des Brokers auf {0} riskiert mehr als das gesetzte Risiko — der Trade wurde übersprungen",
    },
    "объём 0: риск не укладывается в минимальный лот": {
        "en": "size 0: the risk does not fit into the minimum lot",
        "fr": "taille 0 : le risque ne tient pas dans le lot minimum",
        "de": "Größe 0: Das Risiko passt nicht in das Mindestlot",
    },
    "объём {0} ниже минимального лота брокера (0.01)": {
        "en": "size {0} is below the broker's minimum lot (0.01)",
        "fr": "la taille {0} est inférieure au lot minimum du courtier (0,01)",
        "de": "Größe {0} liegt unter dem Mindestlot des Brokers (0,01)",
    },
    "объём в {0}× выше среднего за 20 баров": {
        "en": "volume is {0}× above the 20-bar average",
        "fr": "le volume est {0}× au-dessus de la moyenne sur 20 barres",
        "de": "das Volumen liegt {0}× über dem 20-Bar-Durchschnitt",
    },
    "объём и цены должны быть конечными положительными числами": {
        "en": "size and prices must be finite positive numbers",
        "fr": "la taille et les prix doivent être des nombres finis positifs",
        "de": "Größe und Kurse müssen endliche positive Zahlen sein",
    },
    "ордер отклонён": {
        "en": "order rejected",
        "fr": "ordre rejeté",
        "de": "Order abgelehnt",
    },
    "открытых позиций {0}, плавающий P&L {1}€, дневной P&L {2}€, открытый риск {3}%": {
        "en": "{0} open positions, floating P&L €{1}, daily P&L €{2}, open risk {3}%",
        "fr": "{0} positions ouvertes, P&L flottant {1} €, P&L du jour {2} €, risque ouvert {3} %",
        "de": "{0} offene Positionen, schwebendes P&L {1} €, Tages-P&L {2} €, offenes Risiko {3} %",
    },
    "отправка не удалась": {
        "en": "sending failed",
        "fr": "l’envoi a échoué",
        "de": "Senden fehlgeschlagen",
    },
    "отрицательный исторический спред": {
        "en": "negative historical spread",
        "fr": "spread historique négatif",
        "de": "negativer historischer Spread",
    },
    "ошибка MT5": {
        "en": "MT5 error",
        "fr": "erreur MT5",
        "de": "MT5-Fehler",
    },
    "ошибка Telegram API": {
        "en": "Telegram API error",
        "fr": "erreur de l’API Telegram",
        "de": "Telegram-API-Fehler",
    },
    "ошибка ИИ-конвейера: {0}": {
        "en": "AI pipeline error: {0}",
        "fr": "erreur du pipeline IA : {0}",
        "de": "Fehler der KI-Pipeline: {0}",
    },
    "ошибка ИИ-разбора: {0}": {
        "en": "AI review error: {0}",
        "fr": "erreur d’analyse IA : {0}",
        "de": "Fehler der KI-Auswertung: {0}",
    },
    "ошибка анализа: {0}": {
        "en": "analysis error: {0}",
        "fr": "erreur d’analyse : {0}",
        "de": "Analysefehler: {0}",
    },
    "ошибка ассистента: {0}": {
        "en": "assistant error: {0}",
        "fr": "erreur de l’assistant : {0}",
        "de": "Assistentenfehler: {0}",
    },
    "ошибка новостного анализа: {0}": {
        "en": "news analysis error: {0}",
        "fr": "erreur d’analyse des actualités : {0}",
        "de": "Fehler der Nachrichtenanalyse: {0}",
    },
    "ошибка отправки": {
        "en": "send failed",
        "fr": "échec de l’envoi",
        "de": "Senden fehlgeschlagen",
    },
    "пароль изменён по коду": {
        "en": "password changed with a code",
        "fr": "mot de passe modifié par code",
        "de": "Passwort per Code geändert",
    },
    "пароль короче 8 символов": {
        "en": "the password is shorter than 8 characters",
        "fr": "le mot de passe fait moins de 8 caractères",
        "de": "das Passwort ist kürzer als 8 Zeichen",
    },
    "пароль не короче 8 символов": {
        "en": "the password must be at least 8 characters",
        "fr": "le mot de passe doit faire au moins 8 caractères",
        "de": "das Passwort muss mindestens 8 Zeichen haben",
    },
    "пауза: сигнал по {0} {1} уже был за последние {2} мин": {
        "en": "cooldown: there was already a signal on {0} {1} in the last {2} min",
        "fr": "pause : il y a déjà eu un signal sur {0} {1} dans les {2} dernières minutes",
        "de": "Pause: Es gab bereits ein Signal auf {0} {1} in den letzten {2} Min.",
    },
    "по {0} уже есть открытая позиция": {
        "en": "there is already an open position on {0}",
        "fr": "il y a déjà une position ouverte sur {0}",
        "de": "auf {0} ist bereits eine Position offen",
    },
    "по каталогу": {
        "en": "from the catalogue",
        "fr": "du catalogue",
        "de": "aus dem Katalog",
    },
    "повторные временные метки": {
        "en": "duplicate timestamps",
        "fr": "horodatages en double",
        "de": "doppelte Zeitstempel",
    },
    "повторные/неупорядоченные свечи или неверные OHLC": {
        "en": "duplicate or unordered candles, or invalid OHLC",
        "fr": "bougies en double ou désordonnées, ou OHLC invalides",
        "de": "doppelte oder ungeordnete Kerzen oder ungültige OHLC",
    },
    "подтверждён — цель ≈ высота головы вверх.": {
        "en": "confirmed — the target is roughly the head's height upwards.",
        "fr": "confirmé — l’objectif correspond à la hauteur de la tête vers le haut.",
        "de": "bestätigt — das Ziel entspricht etwa der Kopfhöhe nach oben.",
    },
    "подтверждён — цель ≈ высота головы вниз.": {
        "en": "confirmed — the target is roughly the head's height downwards.",
        "fr": "confirmé — l’objectif correspond à la hauteur de la tête vers le bas.",
        "de": "bestätigt — das Ziel entspricht etwa der Kopfhöhe nach unten.",
    },
    "получено только {0} свечей — мало для бэктеста": {
        "en": "only {0} candles came back — too few for a backtest",
        "fr": "seulement {0} bougies reçues — trop peu pour un backtest",
        "de": "nur {0} Kerzen erhalten — zu wenige für einen Backtest",
    },
    "пользователь не найден": {
        "en": "user not found",
        "fr": "utilisateur introuvable",
        "de": "Benutzer nicht gefunden",
    },
    "попытка входа: {0}": {
        "en": "sign-in attempt: {0}",
        "fr": "tentative de connexion : {0}",
        "de": "Anmeldeversuch: {0}",
    },
    "провайдер вернул синтетические свечи — оценка стратегии запрещена": {
        "en": "the provider returned synthetic candles — evaluating the strategy is refused",
        "fr": "le fournisseur a renvoyé des bougies synthétiques — l’évaluation de la stratégie est refusée",
        "de": "der Anbieter lieferte synthetische Kerzen — eine Strategiebewertung wird verweigert",
    },
    "проверьте вход: баланс, риск %, цены входа и стопа": {
        "en": "check the inputs: balance, risk %, entry and stop prices",
        "fr": "vérifiez les entrées : solde, risque %, prix d’entrée et de stop",
        "de": "prüfen Sie die Eingaben: Saldo, Risiko %, Einstiegs- und Stopkurs",
    },
    "проверьте порог оценки и процент риска": {
        "en": "check the score threshold and the risk percentage",
        "fr": "vérifiez le seuil de score et le pourcentage de risque",
        "de": "prüfen Sie die Score-Schwelle und den Risikoprozentsatz",
    },
    "пропущен": {
        "en": "skipped",
        "fr": "ignoré",
        "de": "übersprungen",
    },
    "просадка {0}% приближается к лимиту {1}%": {
        "en": "the drawdown of {0}% is approaching the {1}% limit",
        "fr": "le drawdown de {0} % approche la limite de {1} %",
        "de": "der Drawdown von {0} % nähert sich dem Limit von {1} %",
    },
    "просрочен": {
        "en": "expired",
        "fr": "expiré",
        "de": "abgelaufen",
    },
    "против тренда старшего ТФ ({0}) — нужна оценка не ниже ±{1}": {
        "en": "against the higher timeframe trend ({0}) — a score of at least ±{1} is required",
        "fr": "à contre-tendance de l’unité de temps supérieure ({0}) — un score d’au moins ±{1} est requis",
        "de": "gegen den Trend des höheren Zeitrahmens ({0}) — ein Score von mindestens ±{1} ist nötig",
    },
    "риск {0}% на сделку выше рекомендуемых 1–2%": {
        "en": "risk of {0}% per trade is above the recommended 1–2%",
        "fr": "un risque de {0} % par trade dépasse les 1–2 % recommandés",
        "de": "ein Risiko von {0} % pro Trade liegt über den empfohlenen 1–2 %",
    },
    "риск по {0} уже {1}% (лимит {2}%) — открытые позиции ставят на то же движение": {
        "en": "the risk on {0} is already {1}% (limit {2}%) — the open positions bet on the same move",
        "fr": "le risque sur {0} est déjà de {1} % (limite {2} %) — les positions ouvertes parient sur le même mouvement",
        "de": "das Risiko auf {0} liegt bereits bei {1} % (Limit {2} %) — die offenen Positionen setzen auf dieselbe Bewegung",
    },
    "риск-менеджер не рассчитал размер позиции": {
        "en": "the risk manager did not size the position",
        "fr": "le gestionnaire de risque n’a pas calculé la taille de position",
        "de": "der Risikomanager hat keine Positionsgröße berechnet",
    },
    "роль: admin или user": {
        "en": "role: admin or user",
        "fr": "rôle : admin ou user",
        "de": "Rolle: admin oder user",
    },
    "рынок закрывается через {0} мин — вход перед выходными опасен: гэп в воскресенье может перескочить стоп-лосс": {
        "en": "the market closes in {0} min — entering before the weekend is risky: a Sunday gap can jump the stop-loss",
        "fr": "le marché ferme dans {0} min — entrer avant le week-end est risqué : un gap du dimanche peut sauter le stop-loss",
        "de": "der Markt schließt in {0} Min. — ein Einstieg vor dem Wochenende ist riskant: Ein Sonntags-Gap kann den Stop-Loss überspringen",
    },
    "рынок закрыт (выходные) — исполнение невозможно до открытия": {
        "en": "the market is closed (weekend) — nothing can execute until it opens",
        "fr": "le marché est fermé (week-end) — aucune exécution avant l’ouverture",
        "de": "der Markt ist geschlossen (Wochenende) — vor der Eröffnung ist keine Ausführung möglich",
    },
    "с {0}:00 до {1}:00 (Бухарест) новые сделки не открываются — тонкая ликвидность вне сессий": {
        "en": "between {0}:00 and {1}:00 (Bucharest) no new trades open — liquidity is thin outside the sessions",
        "fr": "entre {0}:00 et {1}:00 (Bucarest) aucun nouveau trade n’est ouvert — la liquidité est faible hors sessions",
        "de": "zwischen {0}:00 und {1}:00 (Bukarest) werden keine neuen Trades eröffnet — außerhalb der Sessions ist die Liquidität dünn",
    },
    "с новой сделкой открытый риск {0}% превышает {1}%": {
        "en": "with the new trade the open risk {0}% exceeds {1}%",
        "fr": "avec le nouveau trade, le risque ouvert de {0} % dépasse {1} %",
        "de": "mit dem neuen Trade übersteigt das offene Risiko von {0} % {1} %",
    },
    "с новой сделкой риск по {0} превышает {1}%": {
        "en": "with the new trade the risk on {0} exceeds {1}%",
        "fr": "avec le nouveau trade, le risque sur {0} dépasse {1} %",
        "de": "mit dem neuen Trade übersteigt das Risiko auf {0} {1} %",
    },
    "свечи должны идти строго по времени": {
        "en": "candles must be strictly in time order",
        "fr": "les bougies doivent être strictement ordonnées dans le temps",
        "de": "Kerzen müssen streng zeitlich geordnet sein",
    },
    "сделок ещё нет": {
        "en": "no trades yet",
        "fr": "aucun trade pour l’instant",
        "de": "noch keine Trades",
    },
    "сессия истекла — войдите заново": {
        "en": "your session expired — sign in again",
        "fr": "votre session a expiré — reconnectez-vous",
        "de": "Ihre Sitzung ist abgelaufen — melden Sie sich erneut an",
    },
    "сигнал {0} c оценкой {1} (порог {2})": {
        "en": "signal {0} with score {1} (threshold {2})",
        "fr": "signal {0} avec un score de {1} (seuil {2})",
        "de": "Signal {0} mit Score {1} (Schwelle {2})",
    },
    "сигнал не найден": {
        "en": "signal not found",
        "fr": "signal introuvable",
        "de": "Signal nicht gefunden",
    },
    "сигнал не подтверждён ({0})": {
        "en": "the signal was not confirmed ({0})",
        "fr": "le signal n’a pas été confirmé ({0})",
        "de": "das Signal wurde nicht bestätigt ({0})",
    },
    "символ {0} недоступен у брокера": {
        "en": "symbol {0} is unavailable at the broker",
        "fr": "le symbole {0} est indisponible chez le courtier",
        "de": "Symbol {0} ist beim Broker nicht verfügbar",
    },
    "символ {0} недоступен у брокера {1} — торговля этим инструментом невозможна": {
        "en": "symbol {0} is unavailable at broker {1} — this instrument cannot be traded",
        "fr": "le symbole {0} est indisponible chez le courtier {1} — cet instrument ne peut pas être tradé",
        "de": "Symbol {0} ist beim Broker {1} nicht verfügbar — dieses Instrument kann nicht gehandelt werden",
    },
    "синтетические свечи не являются рыночной историей": {
        "en": "synthetic candles are not market history",
        "fr": "les bougies synthétiques ne sont pas de l’historique de marché",
        "de": "synthetische Kerzen sind keine Markthistorie",
    },
    "слабые места и повторяющиеся ошибки": {
        "en": "weak spots and recurring mistakes",
        "fr": "points faibles et erreurs récurrentes",
        "de": "Schwachstellen und wiederkehrende Fehler",
    },
    "сначала вызовите /2fa/setup": {
        "en": "call /2fa/setup first",
        "fr": "appelez d’abord /2fa/setup",
        "de": "rufen Sie zuerst /2fa/setup auf",
    },
    "совокупная оценка {0} ниже порога ±{1}": {
        "en": "the combined score {0} is below the ±{1} threshold",
        "fr": "le score global {0} est sous le seuil de ±{1}",
        "de": "der Gesamtscore {0} liegt unter der Schwelle ±{1}",
    },
    "создание счёта: {0}": {
        "en": "account creation: {0}",
        "fr": "création du compte : {0}",
        "de": "Kontoerstellung: {0}",
    },
    "соотношение риск/прибыль ниже 1.0": {
        "en": "the risk/reward ratio is below 1.0",
        "fr": "le rapport risque/gain est inférieur à 1,0",
        "de": "das Chance-Risiko-Verhältnis liegt unter 1,0",
    },
    "спред {0} п. ({1}) съедает {2}% риска (допустимо {3}%)": {
        "en": "the spread of {0} pts ({1}) eats {2}% of the risk (allowed {3}%)",
        "fr": "le spread de {0} pts ({1}) absorbe {2} % du risque (autorisé {3} %)",
        "de": "der Spread von {0} Pkt. ({1}) frisst {2} % des Risikos (erlaubt {3} %)",
    },
    "среднее": {
        "en": "medium",
        "fr": "moyen",
        "de": "mittel",
    },
    "стоп ({0}) уже 0.8×ATR14 ({1}) — рыночный шум может выбить позицию; рассмотрите SL ≥ 1.5×ATR": {
        "en": "the stop ({0}) is tighter than 0.8×ATR14 ({1}) — market noise can knock the position out; consider an SL of at least 1.5×ATR",
        "fr": "le stop ({0}) est plus serré que 0,8×ATR14 ({1}) — le bruit du marché peut sortir la position ; envisagez un SL d’au moins 1,5×ATR",
        "de": "der Stop ({0}) ist enger als 0,8×ATR14 ({1}) — Marktrauschen kann die Position ausstoppen; erwägen Sie einen SL von mindestens 1,5×ATR",
    },
    "стоп-лосс {0} п. — слишком близко (< 5 п.)": {
        "en": "stop-loss {0} pts — too close (< 5 pts)",
        "fr": "stop-loss {0} pts — trop proche (< 5 pts)",
        "de": "Stop-Loss {0} Pkt. — zu nah (< 5 Pkt.)",
    },
    "суммарный открытый риск {0}% ≥ лимита {1}%": {
        "en": "total open risk {0}% ≥ the {1}% limit",
        "fr": "risque ouvert total {0} % ≥ la limite de {1} %",
        "de": "gesamtes offenes Risiko {0} % ≥ Limit {1} %",
    },
    "счёт разворачивается — статус обновится через минуту": {
        "en": "the account is being provisioned — the status updates in a minute",
        "fr": "le compte est en cours de déploiement — le statut se met à jour dans une minute",
        "de": "das Konto wird bereitgestellt — der Status aktualisiert sich in einer Minute",
    },
    "тайм-аут MetaApi; позиция у брокера НЕ найдена — ордер, вероятно, не прошёл": {
        "en": "MetaApi timed out; NO position was found at the broker — the order probably did not go through",
        "fr": "délai dépassé sur MetaApi ; AUCUNE position trouvée chez le courtier — l’ordre n’est probablement pas passé",
        "de": "MetaApi-Zeitüberschreitung; beim Broker wurde KEINE Position gefunden — die Order ging vermutlich nicht durch",
    },
    "таймфрейм 1m заблокирован: статистически убыточен (спред/шум); используйте 15m и выше": {
        "en": "the 1m timeframe is blocked: statistically it loses money (spread and noise); use 15m and above",
        "fr": "l’unité de temps 1m est bloquée : statistiquement elle perd de l’argent (spread et bruit) ; utilisez 15m et plus",
        "de": "der 1m-Zeitrahmen ist gesperrt: statistisch verliert er Geld (Spread und Rauschen); nutzen Sie 15m und höher",
    },
    "такой логин уже существует": {
        "en": "that login already exists",
        "fr": "cet identifiant existe déjà",
        "de": "dieser Login existiert bereits",
    },
    "текущий пароль неверен": {
        "en": "the current password is wrong",
        "fr": "le mot de passe actuel est incorrect",
        "de": "das aktuelle Passwort ist falsch",
    },
    "тикер: 1–10 символов A-Z, 0-9 или точка": {
        "en": "ticker: 1–10 characters, A-Z, 0-9 or a dot",
        "fr": "ticker : 1 à 10 caractères, A-Z, 0-9 ou un point",
        "de": "Ticker: 1–10 Zeichen, A-Z, 0-9 oder ein Punkt",
    },
    "требуемая маржа {0}€ превышает баланс — уменьшите размер или плечо": {
        "en": "the required margin of €{0} exceeds the balance — reduce the size or the leverage",
        "fr": "la marge requise de {0} € dépasse le solde — réduisez la taille ou le levier",
        "de": "die erforderliche Margin von {0} € übersteigt den Saldo — verringern Sie Größe oder Hebel",
    },
    "требуется вход": {
        "en": "sign-in required",
        "fr": "connexion requise",
        "de": "Anmeldung erforderlich",
    },
    "у брокера": {
        "en": "from the broker",
        "fr": "du courtier",
        "de": "vom Broker",
    },
    "уверенность {0}% ниже порога автотрейда {1}%": {
        "en": "confidence {0}% is below the {1}% auto-trade threshold",
        "fr": "la confiance de {0} % est sous le seuil de trading auto de {1} %",
        "de": "Konfidenz {0} % liegt unter der Auto-Trade-Schwelle von {1} %",
    },
    "уровни сигнала уже не соответствуют цене брокера": {
        "en": "the signal's levels no longer match the broker's price",
        "fr": "les niveaux du signal ne correspondent plus au prix du courtier",
        "de": "die Niveaus des Signals passen nicht mehr zum Kurs des Brokers",
    },
    "флэт (ADX {0} < {1}, Hurst {2}) — оценка недостаточно сильная": {
        "en": "range (ADX {0} < {1}, Hurst {2}) — the score is not strong enough",
        "fr": "range (ADX {0} < {1}, Hurst {2}) — le score n’est pas assez fort",
        "de": "Seitwärts (ADX {0} < {1}, Hurst {2}) — der Score ist nicht stark genug",
    },
    "цена {0} выше уровня {1}": {
        "en": "price {0} is above level {1}",
        "fr": "le prix {0} est au-dessus du niveau {1}",
        "de": "Kurs {0} liegt über Niveau {1}",
    },
    "цена {0} ниже уровня {1}": {
        "en": "price {0} is below level {1}",
        "fr": "le prix {0} est en dessous du niveau {1}",
        "de": "Kurs {0} liegt unter Niveau {1}",
    },
    "цена брокера ушла от входа на {0}R (предел {1}R)": {
        "en": "the broker's price has drifted {0}R from the entry (limit {1}R)",
        "fr": "le prix du courtier s’est écarté de {0}R de l’entrée (limite {1}R)",
        "de": "der Broker-Kurs hat sich {0}R vom Einstieg entfernt (Limit {1}R)",
    },
    "язык не поддерживается": {
        "en": "language not supported",
        "fr": "langue non prise en charge",
        "de": "Sprache nicht unterstützt",
    },
    "ℹ️ По сигналу #{0} позиция уже открыта.": {
        "en": "ℹ️ A position is already open on signal #{0}.",
        "fr": "ℹ️ Une position est déjà ouverte sur le signal #{0}.",
        "de": "ℹ️ Auf Signal #{0} ist bereits eine Position offen.",
    },
    "⏰ Сигнал #{0} ({1} {2}) — подтверждение не получено, сделка НЕ открыта.": {
        "en": "⏰ Signal #{0} ({1} {2}) — no confirmation came, NO trade was opened.",
        "fr": "⏰ Signal #{0} ({1} {2}) — aucune confirmation reçue, AUCUN trade ouvert.",
        "de": "⏰ Signal #{0} ({1} {2}) — keine Bestätigung erhalten, KEIN Trade eröffnet.",
    },
    "⏰ Сигнал #{0}: время на подтверждение истекло — сделка не открыта.": {
        "en": "⏰ Signal #{0}: the confirmation window closed — no trade was opened.",
        "fr": "⏰ Signal #{0} : la fenêtre de confirmation est écoulée — aucun trade ouvert.",
        "de": "⏰ Signal #{0}: Das Bestätigungsfenster ist abgelaufen — kein Trade eröffnet.",
    },
    "⏳ Пятница: рынок скоро закрывается": {
        "en": "⏳ Friday: the market closes soon",
        "fr": "⏳ Vendredi : le marché ferme bientôt",
        "de": "⏳ Freitag: der Markt schließt bald",
    },
    "⏳ Сигнал #{0} истёк": {
        "en": "⏳ Signal #{0} expired",
        "fr": "⏳ Signal #{0} expiré",
        "de": "⏳ Signal #{0} abgelaufen",
    },
    "⏸ Сигнал #{0} уже закрыт ({1}) — вход неактуален.": {
        "en": "⏸ Signal #{0} is already closed ({1}) — the entry is stale.",
        "fr": "⏸ Le signal #{0} est déjà clôturé ({1}) — l’entrée est périmée.",
        "de": "⏸ Signal #{0} ist bereits geschlossen ({1}) — der Einstieg ist hinfällig.",
    },
    "⚠️ <b>Сигнал #{0}: превышение риска</b>\\n{1} · {2}.\\n\\nЗаданный риск: {3}€\\nРеальный риск: <b>{4}€</b> (×{5}) при {6} лот ×{7}\\n\\nОткрыть ТОЛЬКО эту сделку с повышенным риском?": {
        "en": "⚠️ <b>Signal #{0}: risk overshoot</b>\\n{1} · {2}.\\n\\nRisk set: €{3}\\nReal risk: <b>€{4}</b> (×{5}) at {6} lots ×{7}\\n\\nOpen ONLY this trade at the higher risk?",
        "fr": "⚠️ <b>Signal #{0} : dépassement de risque</b>\\n{1} · {2}.\\n\\nRisque défini : {3} €\\nRisque réel : <b>{4} €</b> (×{5}) à {6} lots ×{7}\\n\\nOuvrir UNIQUEMENT ce trade au risque majoré ?",
        "de": "⚠️ <b>Signal #{0}: Risikoüberschreitung</b>\\n{1} · {2}.\\n\\nGesetztes Risiko: {3} €\\nTatsächliches Risiko: <b>{4} €</b> (×{5}) bei {6} Lot ×{7}\\n\\nNUR diesen Trade mit erhöhtem Risiko eröffnen?",
    },
    "⚠️ <b>Через {0} мин</b> — новость с высоким влиянием по <b>{1}</b>:\\n{2}": {
        "en": "⚠️ <b>In {0} min</b> — high-impact news on <b>{1}</b>:\\n{2}",
        "fr": "⚠️ <b>Dans {0} min</b> — actualité à fort impact sur <b>{1}</b> :\\n{2}",
        "de": "⚠️ <b>In {0} Min.</b> — Nachricht mit hohem Einfluss zu <b>{1}</b>:\\n{2}",
    },
    "⚠️ Сигнал #{0} {1} {2}: автоматически НЕ открыт — {3}": {
        "en": "⚠️ Signal #{0} {1} {2}: NOT opened automatically — {3}",
        "fr": "⚠️ Signal #{0} {1} {2} : PAS ouvert automatiquement — {3}",
        "de": "⚠️ Signal #{0} {1} {2}: NICHT automatisch eröffnet — {3}",
    },
    "⛔️ Сигнал #{0} не подтверждён ({1}) — сделка не открыта.": {
        "en": "⛔️ Signal #{0} was not confirmed ({1}) — no trade was opened.",
        "fr": "⛔️ Le signal #{0} n’a pas été confirmé ({1}) — aucun trade ouvert.",
        "de": "⛔️ Signal #{0} wurde nicht bestätigt ({1}) — kein Trade eröffnet.",
    },
    "⛔️ Сигнал #{0} неисполним: {1}. Сделка не открыта.": {
        "en": "⛔️ Signal #{0} cannot be executed: {1}. No trade was opened.",
        "fr": "⛔️ Le signal #{0} n’est pas exécutable : {1}. Aucun trade ouvert.",
        "de": "⛔️ Signal #{0} ist nicht ausführbar: {1}. Kein Trade eröffnet.",
    },
    "⛔️ Сигнал #{0} уже ": {
        "en": "⛔️ Signal #{0} is already ",
        "fr": "⛔️ Le signal #{0} est déjà ",
        "de": "⛔️ Signal #{0} ist bereits ",
    },
    "✅ <b>{0}</b> — тестовое сообщение. Подключение работает.": {
        "en": "✅ <b>{0}</b> — test message. The connection works.",
        "fr": "✅ <b>{0}</b> — message de test. La connexion fonctionne.",
        "de": "✅ <b>{0}</b> — Testnachricht. Die Verbindung funktioniert.",
    },
    "✅ Да, рискнуть {0}€": {
        "en": "✅ Yes, risk €{0}",
        "fr": "✅ Oui, risquer {0} €",
        "de": "✅ Ja, {0} € riskieren",
    },
    "✅ Открыто по сигналу #{0}: {1} ×{2} по {3} лот {4}\\nSL {5} · TP {6}": {
        "en": "✅ Opened on signal #{0}: {1} ×{2} at {3} lots {4}\\nSL {5} · TP {6}",
        "fr": "✅ Ouvert sur le signal #{0} : {1} ×{2} à {3} lots {4}\\nSL {5} · TP {6}",
        "de": "✅ Auf Signal #{0} eröffnet: {1} ×{2} zu {3} Lot {4}\\nSL {5} · TP {6}",
    },
    "✅ Сигнал #{0} достиг цели": {
        "en": "✅ Signal #{0} reached its target",
        "fr": "✅ Le signal #{0} a atteint son objectif",
        "de": "✅ Signal #{0} hat sein Ziel erreicht",
    },
    "✖️ Отмена": {
        "en": "✖️ Cancel",
        "fr": "✖️ Annuler",
        "de": "✖️ Abbrechen",
    },
    "✖️ Пропустить": {
        "en": "✖️ Skip",
        "fr": "✖️ Passer",
        "de": "✖️ Überspringen",
    },
    "✖️ Сигнал #{0} пропущен — сделка НЕ открыта.": {
        "en": "✖️ Signal #{0} skipped — NO trade was opened.",
        "fr": "✖️ Signal #{0} ignoré — AUCUN trade ouvert.",
        "de": "✖️ Signal #{0} übersprungen — KEIN Trade eröffnet.",
    },
    "❌ MT5 не подключён — откройте «Подключения» в приложении.": {
        "en": "❌ MT5 is not connected — open Connections in the app.",
        "fr": "❌ MT5 n’est pas connecté — ouvrez Connexions dans l’application.",
        "de": "❌ MT5 ist nicht verbunden — öffnen Sie Verbindungen in der App.",
    },
    "❌ Ордер отклонён: {0}": {
        "en": "❌ Order rejected: {0}",
        "fr": "❌ Ordre rejeté : {0}",
        "de": "❌ Order abgelehnt: {0}",
    },
    "❌ Сигнал #{0} не найден.": {
        "en": "❌ Signal #{0} not found.",
        "fr": "❌ Signal #{0} introuvable.",
        "de": "❌ Signal #{0} nicht gefunden.",
    },
    "👁 Наблюдение: {0} · {1} — {2}": {
        "en": "👁 Watching: {0} · {1} — {2}",
        "fr": "👁 Observation : {0} · {1} — {2}",
        "de": "👁 Beobachtung: {0} · {1} — {2}",
    },
    "📊 <b>Итог дня · {0}</b>": {
        "en": "📊 <b>Day summary · {0}</b>",
        "fr": "📊 <b>Bilan du jour · {0}</b>",
        "de": "📊 <b>Tagesbilanz · {0}</b>",
    },
    "🔒 <b>Закрытие перед выходными</b> (до закрытия рынка {0} мин)\\nЗакрыто позиций: {1}\\n": {
        "en": "🔒 <b>Closing before the weekend</b> ({0} min to the market close)\\nPositions closed: {1}\\n",
        "fr": "🔒 <b>Clôture avant le week-end</b> ({0} min avant la fermeture du marché)\\nPositions clôturées : {1}\\n",
        "de": "🔒 <b>Schließen vor dem Wochenende</b> ({0} Min. bis Marktschluss)\\nGeschlossene Positionen: {1}\\n",
    },
    "🔭 <b>Вне избранного</b>\\n": {
        "en": "🔭 <b>Outside the watchlist</b>\\n",
        "fr": "🔭 <b>Hors favoris</b>\\n",
        "de": "🔭 <b>Außerhalb der Watchlist</b>\\n",
    },
    "🔭 Вне избранного: {0} · {1} — {2}": {
        "en": "🔭 Outside the watchlist: {0} · {1} — {2}",
        "fr": "🔭 Hors favoris : {0} · {1} — {2}",
        "de": "🔭 Außerhalb der Watchlist: {0} · {1} — {2}",
    },
    "🛑 Сигнал #{0} закрыт по стопу": {
        "en": "🛑 Signal #{0} closed on its stop",
        "fr": "🛑 Le signal #{0} a été clôturé sur son stop",
        "de": "🛑 Signal #{0} wurde am Stop geschlossen",
    },
    "🤖 Автотрейд: {0} {1} ×{2}": {
        "en": "🤖 Auto-trade: {0} {1} ×{2}",
        "fr": "🤖 Trade auto : {0} {1} ×{2}",
        "de": "🤖 Auto-Trade: {0} {1} ×{2}",
    },
}
