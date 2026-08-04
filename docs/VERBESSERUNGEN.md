# Apex Capital — Verbesserungsvorschläge

Ergebnis eines vollständigen Durchgangs durch den Code (Stand August 2026).
Sortiert nach Wirkung, nicht nach Aufwand. Die Punkte 1–5 sind das, was ein
Investor in der Due Diligence zuerst findet.

---

## 1. Der Handelszwang macht die Performance-Historie unbrauchbar

**Wo:** `core/scheduler.py:288-299` (jeder Scan), `:373-384` (Deep Scan),
`:389-541` (`run_forced_trade`), `:147-180` (21:30-Enforcer)

Jeder Scan garantiert mindestens einen Kauf. Findet die Pipeline nichts, läuft
`run_forced_trade` — und dessen **Stufe 2 umgeht das Sprachmodell komplett**
(`scheduler.py:452-530`): sie baut ein `fake_result` mit `"verdict": "INVEST"`
zusammen und kauft den höchstbewerteten Titel nach reinem Indikator-Score.

Bei 6 Scans pro Tag plus dem 21:30-Enforcer plus dem Reinvest-Trigger nach jedem
Verkauf entsteht eine Historie, in der ein erheblicher Teil der Trades gar nicht
von den Agenten stammt. Damit misst die Wertentwicklung nicht die Qualität des
Konzepts — genau das, was sie beweisen soll.

**Vorschlag:** Handelszwang abschalten oder als separates Sleeve mit eigener
Buchführung führen (`trade.source = "llm" | "forced"`), damit beide Kurven
getrennt auswertbar sind.

---

## 2. Bei kaputtem LLM kauft das System trotzdem

**Wo:** `agents/committee.py:138-139`, `:161`

```python
if marcus.get("verdict") not in ("INVEST", "PASS", "WAIT"):
    marcus["verdict"] = "INVEST"
```

Liefert das Modell eine Fehlerantwort (`{"error": "all free models exhausted"}`),
parst das sauber als JSON, hat aber kein `verdict` — und der Fallback ist
`INVEST`. Ein Ausfall der LLM-Kette führt also zu Käufen, nicht zu Zurückhaltung.
Auch der `_parse_json`-Default (`committee.py:123-132`) ist `INVEST`.

**Vorschlag:** Fehlerfall → `WAIT`. Ein Verdikt, das kein Modell gefällt hat,
darf kein Kaufsignal sein.

---

## 3. Währung: Depot in EUR, Kurse in USD, keine Umrechnung

**Wo:** `core/portfolio.py` durchgehend, `data/market.py:99-104`

Das Depot rechnet in Euro (`cash_eur`, `price_eur`, `INITIAL_VALUE = 10_000.0`),
die Watchlist besteht fast vollständig aus US-Titeln, und `fetch_current_price`
liefert USD. Es findet nirgends eine FX-Umrechnung statt. Der EUR/USD-Kurs
schwankt zweistellig über ein Jahr — die ausgewiesene Rendite enthält also einen
systematischen, nicht ausgewiesenen Währungseffekt.

**Vorschlag:** Entweder Basiswährung auf USD umstellen (ehrlichste Variante) oder
EUR/USD beim Kauf und beim Verkauf mitziehen.

Ebenfalls nicht modelliert: Gebühren, Spreads, Slippage, Teilausführungen. Bei
der aktuellen Umschlagshäufigkeit (siehe Punkt 5) ist das kein Rundungsfehler.

---

## 4. Wettlauf beim Schreiben des Depots

**Wo:** `utils/db.py:225-253`, `core/portfolio.py:62-116`, `:271-346`

Das gesamte Depot liegt als **eine** Zeile mit einem JSON-Blob in `positions`.
Jede Änderung ist ein Read-Modify-Write ohne Sperre. Gleichzeitig laufen:

- der Monitor jede Minute (`scheduler.py:30-34`),
- Scans und manuelle Analysen als eigene Tasks,
- nach **jedem** Verkauf ein `asyncio.create_task(_trigger_reinvest())`
  (`portfolio.py:188`).

Zwei überlappende `execute_buy` lesen denselben Cash-Stand und schreiben
nacheinander — der zweite überschreibt die Position des ersten und gibt dasselbe
Geld zweimal aus. Kein theoretisches Problem: der Monitor kann mehrere Stops in
derselben Runde auslösen und damit mehrere Reinvest-Tasks parallel starten.

**Vorschlag:** Ein `asyncio.Lock` im `PortfolioManager` um jeden
Read-Modify-Write, oder `BEGIN IMMEDIATE` in `get_conn()` für schreibende Pfade.

---

## 5. Die Ausstiegsregeln erzeugen Umschlag ohne These

**Wo:** `core/portfolio.py:297-307` (48h-Regel), `:350-369` (Kapitalumschichtung)

- **48-Stunden-Regel:** Wer nach zwei Tagen unter +1,5 % liegt, fliegt raus. Das
  schneidet jede These ab, bevor sie sich entfalten kann — bei einem Stop von
  1,5 × ATR ist eine Bewegung von unter 1,5 % innerhalb von 48 Stunden schlicht
  Rauschen.
- **`_free_capital_for_new_position`** verkauft die **schwächste** Position, um
  Platz zu machen. Kombiniert mit dem Handelszwang aus Punkt 1 heißt das:
  Positionen im Drawdown werden systematisch zugunsten frischer
  Score-Spitzenreiter liquidiert.

**Vorschlag:** Haltefrist an ATR koppeln statt an eine feste Stundenzahl, und
Kapitalumschichtung nur zulassen, wenn die neue Idee eine deutlich höhere
Conviction hat als die verkaufte Position.

---

## 6. Dante ist Dekoration

**Wo:** `agents/cio.py:97-102`, `agents/devil.py:64-66`

Dante läuft **nach** dem INVEST-Verdikt, sein Report bekommt `advisory = True` —
und danach liest kein einziger Codepfad `severity` aus. Ein `HIGH`-Befund ändert
nichts an Positionsgröße, Stop oder Ausführung.

**Vorschlag:** `severity: HIGH` → Positionsgröße −30 % oder Verdikt auf `WAIT`.
Andernfalls den Agenten ehrlich als Kommentar labeln.

---

## 7. Kein Sektor- oder Korrelationslimit

**Wo:** `core/portfolio.py:19-20`, Watchlist in `main.py:39-57`

15 Positionen à 1 % Risiko klingt nach 15 % Gesamtrisiko — ist es aber nur bei
unkorrelierten Titeln. Auf der Watchlist stehen NVDA, AMD, AVGO, QCOM, TSM, ASML,
MU und INTC. Ein Halbleiter-Ausverkauf trifft acht Positionen gleichzeitig; die
1-%-Regel schützt dann gegen nichts.

**Vorschlag:** Maximal 3 Positionen je Sektor, plus Korrelationsprüfung gegen
bestehende Positionen vor dem Kauf.

---

## 8. Kein Not-Aus auf Fondsebene

**Wo:** `agents/risk.py:84-91`

Es gibt einen Größen-Multiplikator bei über 5 % Monatsverlust und nach drei
Verlusten in Folge — aber keine Schwelle, ab der das System aufhört zu kaufen.
Ein Regime, in dem die Strategie systematisch falsch liegt, wird nur langsamer
durchgehandelt, nicht gestoppt.

**Vorschlag:** Ab −15 % Gesamt-Drawdown alle Käufe aussetzen und nur noch
Positionen verwalten, bis ein Mensch freigibt.

---

## 9. Die Agenten-Scorecard misst nichts

**Wo:** `core/reporter.py:100-121`

```python
for name, key in keys.items():
    if key in signals:
        agents[name]["signals"] += 1
        if pnl > 0:
            agents[name]["wins"] += 1
```

Gezählt wird, ob ein Agent **einen Bericht abgegeben hat** — nicht, ob er zum
Kauf geraten hat. Da jeder Trade alle Berichte enthält, bekommen alle vier
Agenten zwangsläufig **exakt dieselbe Trefferquote**. Die Kennzahl ist damit
wertlos, obwohl die Rohdaten (`all_agent_signals`) alles enthalten, was man für
eine echte Attribution bräuchte.

**Vorschlag:** Nur zählen, wenn das Signal des Agenten mit der Richtung des Trades
übereinstimmt (`signal in ("BUY", "STRONG_BUY")`), und Trefferquote gegen die
Basisrate aller Trades ausweisen.

Nebenbei: `sell_trades` filtert auf `action == "SELL"`, `PARTIAL_SELL` fällt aus
der Statistik heraus — die realisierten Teilgewinne tauchen in der Trefferquote
nie auf.

---

## 10. Keine Authentifizierung auf schreibenden Endpunkten

**Wo:** `main.py:266-273` (`POST /api/sell/{ticker}`), `:301-305` (`POST /api/scan`),
`:287-296` (Watchlist), `:215-221` (`POST /api/analyze`)

Wer die URL kennt, kann jede Position liquidieren, die Watchlist ändern oder
beliebig viele Scans auslösen. Für eine öffentlich erreichbare Demo, die
Investoren gezeigt wird, ist das ein Problem — auch ohne echtes Geld, weil ein
Fremder die Historie zerstören kann, die den Beweis liefern soll.

**Vorschlag:** Ein API-Token für alle schreibenden Routen; lesende Routen und die
Dashboards können offen bleiben.

---

## 11. Kostenlose Modelle als Fundament — ohne Protokoll, welches gerade lief

**Wo:** `agents/base.py:23-42`, `:66-147`

Der Kommentar im Code sagt es selbst: der komplette OpenRouter-Free-Katalog war
schon einmal zu 100 % tot. Die Fallback-Kette fängt das gut ab — aber es wird
nirgends festgehalten, **welches Modell** eine Entscheidung getroffen hat. Damit
ist keine Entscheidung reproduzierbar, und ein stiller Modellwechsel kann das
Verhalten des ganzen Fonds verändern, ohne dass es jemand bemerkt.

**Vorschlag:** Modell-ID, Schlüssel-Index und Antwortzeit je Agentenaufruf in
`analysis_history` mitschreiben.

---

## 12. Zeitzonen und Handelskalender

**Wo:** `core/scheduler.py:27` (Europe/Berlin), `utils/db.py:295-302` (UTC-Tag),
`core/portfolio.py:109` (`datetime.utcnow()`)

Der Scheduler denkt in CET, `get_trades_today()` in UTC-Tagen. Der
21:30-CET-Enforcer prüft also gegen ein UTC-Fenster, das um 01:00 CET wechselt —
meistens passend, aber nicht sauber. Börsenfeiertage kennt das System gar nicht:
an Thanksgiving läuft der volle Scan-Zyklus gegen einen geschlossenen Markt.

**Vorschlag:** Durchgehend `datetime.now(timezone.utc)` (das
`utcnow()`-Muster ist zudem in neueren Python-Versionen deprecated) und einen
Handelskalender vor jeden Scan schalten.

---

## Reihenfolge der Umsetzung

| Stufe | Inhalt | Warum zuerst |
|---|---|---|
| **1 — Ehrlich messen** | Punkte 1, 9 + Benchmark gegen einen Index, Sharpe, Trefferquote | Ohne saubere Messung ist jede weitere Änderung ungeprüft |
| **2 — Härten** | Punkte 3, 4, 7, 8, 10 | Fehler, die Geld oder Daten kosten, sobald es ernst wird |
| **3 — Urteilsqualität** | Punkte 2, 5, 6, 11, 12 | Verbessert, was das Konzept eigentlich beweisen will |
